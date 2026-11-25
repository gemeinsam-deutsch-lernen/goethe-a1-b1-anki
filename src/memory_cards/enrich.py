"""Grammar enrichment from the Wiktextract (kaikki.org) German dump (CC BY-SA).

https://kaikki.org/dictionary/German/  — one JSON object per (word, part of speech).
We keep a compact index with only the fields we need for the words in our lists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

KAIKKI_FILE = "kaikki.org-dictionary-German.jsonl"
INDEX_FILE = "index.json"
POS_KEEP = {"noun", "verb", "adj", "adv", "prep", "conj", "pron", "det", "intj", "num",
            "particle", "phrase", "article", "postp", "contraction", "name"}

_WORD_RE = re.compile(r'"word": "((?:[^"\\]|\\.)*)"')
_GENDER = {"m": "der", "f": "die", "n": "das", "p": "die"}


def _has(tags, *need):
    return tags is not None and all(t in tags for t in need)


def _compact(d: dict) -> dict:
    pos = d.get("pos")
    out: dict = {"pos": pos}
    forms = d.get("forms", [])
    ht = (d.get("head_templates") or [{}])[0]
    expansion = ht.get("expansion", "")
    m = re.search(r"\(([^,()]+)", expansion)
    out["class"] = m.group(1).strip() if m else ""
    if pos == "noun":
        g = str((ht.get("args") or {}).get("1", "")).split(",")[0]
        out["gender"] = [_GENDER[x] for x in re.findall(r"[mfnp]", g.split("/")[0])][:2]
        if "p" in g.split("/")[0][:1]:
            out["plural_only"] = True
        out["genitive"] = [f["form"] for f in forms if f.get("tags") == ["genitive"]]
        out["plural"] = [f["form"] for f in forms if f.get("tags") == ["plural"]]
        if not out["genitive"]:
            out["genitive"] = [f["form"] for f in forms if _has(f.get("tags"), "genitive", "singular")]
        if not out["plural"]:
            out["plural"] = [f["form"] for f in forms
                             if _has(f.get("tags"), "nominative", "plural")]
        out["plural"] = list(dict.fromkeys(out["plural"]))
        out["genitive"] = list(dict.fromkeys(out["genitive"]))
    elif pos == "verb":
        def first(*tags):
            for f in forms:
                if _has(f.get("tags"), *tags) and "subjunctive" not in f.get("tags", []):
                    return f["form"]
            return ""
        out["er"] = first("present", "singular", "third-person")
        out["praeteritum"] = first("past") or first("preterite", "singular", "third-person")
        out["partizip2"] = first("participle", "past")
        out["aux"] = list(dict.fromkeys(f["form"] for f in forms if f.get("tags") == ["auxiliary"]))
    return out


def build_index(kaikki_dir: Path, words: set[str]) -> dict[str, list[dict]]:
    """Scan the dump once and keep entries for `words` (exact match, case-sensitive)."""
    index: dict[str, list[dict]] = {}
    with open(kaikki_dir / KAIKKI_FILE, encoding="utf-8") as f:
        for line in f:
            # Cheap pre-filter before JSON parsing.
            # Nested objects (derived terms etc.) also have "word" keys, so check all.
            if not any(w in words for w in _WORD_RE.findall(line)):
                continue
            d = json.loads(line)
            if d.get("word") not in words:
                continue
            if d.get("lang_code") != "de" or d.get("pos") not in POS_KEEP:
                continue
            # Skip pure form-of entries (e.g. "fuhr" as past of "fahren").
            senses = d.get("senses", [])
            if senses and all("form_of" in s or "alt_of" in s for s in senses):
                if d.get("pos") != "noun":
                    continue
            index.setdefault(d["word"], []).append(_compact(d))
    return index


def load_or_build_index(kaikki_dir: Path, words: set[str]) -> dict[str, list[dict]]:
    path = kaikki_dir / INDEX_FILE
    if path.exists():
        idx = json.loads(path.read_text(encoding="utf-8"))
        if words <= set(idx.get("__words__", [])):
            return idx
    idx = build_index(kaikki_dir, words)
    idx["__words__"] = sorted(words)
    path.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    return idx


def lookup(index: dict, word: str, pos: str | None = None, article: str = "",
           plural: list[str] | None = None) -> dict | None:
    """First entry with the given POS; for nouns prefer matching gender, then plural."""
    cands = [e for e in index.get(word, []) if pos is None or e["pos"] == pos]
    if not cands:
        return None

    def score(e):
        s = 0
        if article and article in e.get("gender", []):
            s += 2
        if plural and set(plural) & set(e.get("plural", [])):
            s += 1
        return -s

    return sorted(cands, key=score)[0]


def is_strong(verb_class: str) -> bool:
    """Strong and irregular (mixed, modal, suppletive) verbs get the '*' marker."""
    c = verb_class.lower()
    return "strong" in c or "irregular" in c or "mixed" in c or "preterite-present" in c
