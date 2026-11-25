"""Build data/entries.json: parse all levels, classify, merge across levels, enrich."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .enrich import is_strong, load_or_build_index, lookup
from .normalize import clean, lemma_key, parse_noun, parse_verb, split_regional
from .parse_goethe import examples_of, notes_of, parse_level

LEVELS = ("A1", "A2", "B1")
LEVEL_RANK = {lv: i for i, lv in enumerate(LEVELS)}

POS_LABELS = {
    "adj": "Adj.", "adv": "Adv.", "prep": "Präp.", "conj": "Konj.", "pron": "Pron.",
    "det": "Art./Det.", "intj": "Interj.", "num": "Num.", "particle": "Partikel",
    "phrase": "Wendung", "article": "Art.",
}


def _classify(head: str) -> str:
    h = clean(head)
    if re.match(r"(der|die|das)(/(der|die|das))?\s", h) or re.search(r"\((Pl|pl)\.\)", h) and h[:1].isupper():
        return "noun"
    if re.search(r",\s*(es\s+)?(hat|ist)(/(hat|ist))?\s", h):
        return "verb"
    return "candidate"


def _candidate_verb_inf(head: str) -> str | None:
    """A1 lists verbs without forms: 'abfahren', '(sich) anmelden', 'Rad fahren'."""
    h = clean(head)
    h = re.sub(r"\(sich\)|^sich\s+", "", h).strip()
    parts = [p.strip() for p in h.split(",")]
    if len(parts) >= 3:  # "müssen, muss, musste" / "gießen, gießt, goss, gegossen"
        h = parts[0]
    if re.fullmatch(r"[a-zäöüß]+(e[lr]?n|n)", h):
        return h
    return None


def _record(raw, level: str) -> dict:
    head = clean(raw.head)
    rec = {
        "level": level,
        "head": head,
        "variants": [clean(v) for v in raw.variant_heads],
        "examples": examples_of(raw),
        "notes": notes_of(raw),
        "page": raw.page,
    }
    kind = _classify(head)
    if kind == "noun":
        n = parse_noun(head)
        if n:
            rec["pos"], rec["noun"] = "noun", n
            return rec
        kind = "candidate"
    if kind == "verb":
        v = parse_verb(head)
        if v:
            rec["pos"], rec["verb"] = "verb", v
            return rec
    rec["pos"] = "candidate"
    return rec


def _key(rec: dict) -> str:
    if rec["pos"] == "noun":
        return "noun:" + lemma_key(rec["noun"]["word"])
    if rec["pos"] == "verb":
        return "verb:" + lemma_key(rec["verb"]["infinitive"])
    main, _ = split_regional(rec["head"])
    prefix = "-" if re.search(r"\w-$", main.split(",")[0].split("/")[0].strip()) else ""
    return "other:" + lemma_key(main) + (" prefix" if prefix else "")


def _slug(key: str) -> str:
    s = key.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9:]+", "-", s).strip("-")


def _lookup_words(rec: dict) -> set[str]:
    out = set()
    if rec["pos"] == "noun":
        out.add(rec["noun"]["word"])
    elif rec["pos"] == "verb":
        out.add(rec["verb"]["infinitive"])
    else:
        main, _ = split_regional(rec["head"])
        main = re.sub(r"\s*\(.*?\)", "", main).strip()
        out.add(main)
        out.add(main.split(",")[0].strip())
        out.add(re.sub(r"-$", "", main.split(",")[0].strip()))
    return {w for w in out if w}


def _merge(a: dict, b: dict) -> dict:
    """Merge record b (higher level) into a (lower level)."""
    a["levels"] = sorted(set(a["levels"]) | {b["level"]}, key=LEVEL_RANK.get)
    seen = {re.sub(r"\W+", "", x.lower()) for x in a["examples"]}
    for ex in b["examples"]:
        k = re.sub(r"\W+", "", ex.lower())
        if k not in seen:
            a["examples"].append(ex)
            seen.add(k)
    for field in ("notes", "variants"):
        for x in b[field]:
            if x not in a[field]:
                a[field].append(x)
    # Grammar: later levels give more forms (B1 lists Präteritum) -> prefer non-empty newer.
    for sub in ("noun", "verb"):
        if sub in a and sub in b:
            for k, v in b[sub].items():
                if v not in ("", None, False, []):
                    a[sub][k] = v
    a["heads"].append(b["head"])
    return a


def build(
    pdf_dir: Path,
    kaikki_dir: Path,
    fixes_path: Path | None = None,
    overrides_path: Path | None = None,
) -> tuple[list[dict], dict]:
    fixes = {}
    if fixes_path and fixes_path.exists():
        fixes = json.loads(fixes_path.read_text(encoding="utf-8"))
    recs = []
    for lv in LEVELS:
        raws = parse_level(lv, pdf_dir)
        i = 0
        while i < len(raws):
            raw = raws[i]
            fix = fixes.get(f"{lv}|{clean(raw.head)}")
            if fix:
                if fix.get("skip"):
                    i += 1
                    continue
                if fix.get("merge_next") and i + 1 < len(raws):
                    raw.ex_lines += [(t, False) for t, _ in raws[i + 1].ex_lines]
                    i += 1
                if fix.get("head"):
                    raw.head_lines = [fix["head"]]
            recs.append(_record(raw, lv))
            i += 1

    overrides = {}
    if overrides_path and overrides_path.exists():
        overrides = json.loads(overrides_path.read_text(encoding="utf-8"))

    words = set()
    for r in recs:
        words |= _lookup_words(r)
        inf = _candidate_verb_inf(r["head"]) if r["pos"] == "candidate" else None
        if inf:
            words.add(inf)
    index = load_or_build_index(kaikki_dir, words)

    # Resolve candidates: verb without forms, or "other".
    for r in recs:
        if r["pos"] != "candidate":
            continue
        inf = _candidate_verb_inf(r["head"])
        other_pos = {"adj", "conj", "prep"}
        if inf and lookup(index, inf, "verb") and not any(lookup(index, inf, p) for p in other_pos):
            r["pos"] = "verb"
            v = parse_verb(r["head"])
            r["verb"] = v or {"infinitive": inf, "reflexive": "", "prep": "", "er": "",
                              "praeteritum": "", "aux": "", "partizip2": "", "note": "",
                              "regional": "", "has_forms": False}
        else:
            r["pos"] = "other"

    merged: dict[str, dict] = {}
    for r in recs:
        k = _key(r)
        # Homographs with different plurals are separate words
        # ("der Ausdruck, ¨-e" expression vs. "der Ausdruck, -e" printout).
        if r["pos"] == "noun":
            k += ":" + r["noun"]["article"]
            n = 2
            while k in merged and merged[k]["level"] == r["level"] and (
                merged[k]["noun"]["plural"] != r["noun"]["plural"]
            ):
                k = re.sub(r"#\d+$", "", k) + f"#{n}"
                n += 1
        r.setdefault("levels", [r["level"]])
        r.setdefault("heads", [r["head"]])
        if k in merged:
            _merge(merged[k], r)
        else:
            merged[k] = r

    report = {"kaikki_missing": [], "plural_mismatch": [], "no_examples": []}
    out = []
    for k, r in merged.items():
        e = {
            "id": _slug(k),
            "pos": r["pos"],
            "level": r["level"],
            "levels": r["levels"],
            "heads": r["heads"],
            "variants": r["variants"],
            "examples": r["examples"],
            "notes": r["notes"],
        }
        if r["pos"] == "noun":
            e.update(_enrich_noun(r["noun"], index, report))
        elif r["pos"] == "verb":
            e.update(_enrich_verb(r["verb"], index, report))
        else:
            e.update(_enrich_other(r, index))
        ov = overrides.get(e["id"])
        if ov:
            e.update(ov)
        if not e["examples"]:
            report["no_examples"].append(e["id"])
        out.append(e)
    out = [e for e in out if not e.get("skip")]
    out.sort(key=lambda e: (LEVEL_RANK[e["level"]], e["pos"], _sort_word(e)))
    return out, report


def _sort_word(e: dict) -> str:
    return (e.get("word") or e.get("infinitive") or "").lower()


def _enrich_noun(n: dict, index: dict, report: dict) -> dict:
    k = lookup(index, n["word"], "noun", n["article"], n["plural"])
    plural = n["plural"]
    if k is None:
        report["kaikki_missing"].append("noun:" + n["word"])
    if k and plural and k.get("plural") and not set(plural) & set(k["plural"]):
        report["plural_mismatch"].append(f'{n["word"]}: goethe={plural} wiki={k["plural"]}')
    if not plural and not n["sg_only"] and k and k.get("plural"):
        plural = k["plural"][:2]
    genitive = ""
    if not n["pl_only"] and k and k.get("genitive"):
        gens = [g for g in k["genitive"] if g != n["word"] or n["article"] == "die"]
        gens = gens or k["genitive"]
        art = "der" if n["article"] == "die" else "des"
        genitive = f"{art} " + "/".join(gens[:2])
    elif not n["pl_only"] and n["article"] == "die":
        genitive = "der " + n["word"]
    return {
        "article": n["article"],
        "article2": n["article2"],
        "word": n["word"],
        "plural": "die " + "/".join(plural) if plural and not n["pl_only"] else "",
        "sg_only": n["sg_only"] or (not plural and not n["pl_only"]),
        "pl_only": n["pl_only"],
        "genitive": genitive,
        "feminine": n["feminine"],
        "regional": n["regional"],
    }


def _enrich_verb(v: dict, index: dict, report: dict) -> dict:
    inf = v["infinitive"]
    k = lookup(index, inf, "verb")
    if k is None and " " in inf:  # "spazieren gehen" -> look up "gehen" for the class
        k = lookup(index, inf.split()[-1], "verb")
    if k is None:
        report["kaikki_missing"].append("verb:" + inf)
    er, praet, aux, part2 = v["er"], v["praeteritum"], v["aux"], v["partizip2"]
    if k and " " not in inf:
        er = er or k.get("er", "")
        praet = praet or k.get("praeteritum", "")
        part2 = part2 or k.get("partizip2", "")
        if not aux and k.get("aux"):
            aux = "/".join("hat" if a == "haben" else "ist" for a in k["aux"])
    strong = is_strong(k.get("class", "")) if k else False
    refl = v["reflexive"]
    return {
        "infinitive": (refl + " " if refl else "") + inf,
        "er": er,
        "praeteritum": praet,
        "aux": aux,
        "partizip2": part2,
        "strong": strong,
        "verb_class": k.get("class", "") if k else "",
        "prep": v["prep"],
        "verb_note": v["note"],
        "regional": v["regional"],
    }


def _enrich_other(r: dict, index: dict) -> dict:
    main, regional = split_regional(r["head"])
    label = ""
    for w in sorted(_lookup_words(r), key=len, reverse=True):
        for e in index.get(w, []):
            if e["pos"] in POS_LABELS:
                label = POS_LABELS[e["pos"]]
                break
        if label:
            break
    return {"word": main, "pos_label": label, "regional": regional}
