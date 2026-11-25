"""Translations (one directory per target language): batch files and validation.

Input batches:  data/translations/<lang>/todo/batch_NNN.input.json  (generated, not edited)
Output batches: data/translations/<lang>/batch_NNN.json              (committed)

Output format: a JSON list of objects
    {"id": "...", "<lang>": "word translation", "<lang>_examples": ["...", ...]}
with exactly one sentence per German example, in the same order.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

LANGS = {
    "ru": {"name": "Russian", "label": "RU", "script": re.compile(r"[А-Яа-яЁё]")},
    "uk": {"name": "Ukrainian", "label": "UK", "script": re.compile(r"[А-Яа-яЄєІіЇїҐґ']")},
}


def display_de(e: dict) -> str:
    if e["pos"] == "noun":
        s = f'{e["article"]} {e["word"]}'
        if e["plural"]:
            s += f' (Pl. {e["plural"]})'
        elif e["pl_only"]:
            s += " (nur Pl.)"
        if e.get("feminine"):
            s += f' / {e["feminine"]}'
    elif e["pos"] == "verb":
        s = e["infinitive"]
        if e.get("prep"):
            s += f' ({e["prep"]})'
    else:
        s = e["word"]
    if e.get("regional"):
        s += f'  [{e["regional"]}]'
    return s


def make_batches(entries_path: Path, trans_root: Path, lang: str, size: int,
                 hint_lang: str | None = None) -> int:
    """Write input batches for entries that are missing or incomplete in `lang`.

    `hint_lang` adds an existing translation (e.g. Russian) as a disambiguation hint.
    """
    entries = json.loads(entries_path.read_text(encoding="utf-8"))
    out_dir = trans_root / lang
    done = load(trans_root, lang)
    hints = load(trans_root, hint_lang) if hint_lang else {}
    todo = [e for e in entries if e["id"] not in done or not _complete(e, done[e["id"]], lang)]
    tdir = out_dir / "todo"
    tdir.mkdir(parents=True, exist_ok=True)
    for old in tdir.glob("batch_*.input.json"):
        old.unlink()
    existing = sorted(out_dir.glob("batch_*.json"))
    start = int(existing[-1].stem.split("_")[1]) + 1 if existing else 1
    n = 0
    for i in range(0, len(todo), size):
        payload = []
        for e in todo[i : i + size]:
            item = {"id": e["id"], "pos": e["pos"], "de": display_de(e),
                    "notes": e.get("notes", []), "examples": e["examples"]}
            h = hints.get(e["id"])
            if h:
                item[f"hint_{hint_lang}"] = h[hint_lang]
            payload.append(item)
        name = f"batch_{start + n:03d}.input.json"
        (tdir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        n += 1
    return n


def load(trans_root: Path, lang: str) -> dict[str, dict]:
    """id -> item; later batch files override earlier ones."""
    out: dict[str, dict] = {}
    for p in sorted((trans_root / lang).glob("batch_*.json")):
        for item in json.loads(p.read_text(encoding="utf-8")):
            out[item["id"]] = item
    return out


def _complete(e: dict, t: dict, lang: str) -> bool:
    return bool(t.get(lang)) and len(t.get(f"{lang}_examples", [])) == len(e["examples"])


def validate(entries_path: Path, trans_root: Path, lang: str) -> list[str]:
    entries = json.loads(entries_path.read_text(encoding="utf-8"))
    tr = load(trans_root, lang)
    script = LANGS[lang]["script"]
    problems = []
    for e in entries:
        t = tr.get(e["id"])
        if not t:
            problems.append(f'missing   {e["id"]}')
            continue
        if not t.get(lang) or not script.search(t[lang]):
            problems.append(f'no-word   {e["id"]}: {t.get(lang)!r}')
        rx = t.get(f"{lang}_examples", [])
        if len(rx) != len(e["examples"]):
            problems.append(f'count     {e["id"]}: de={len(e["examples"])} {lang}={len(rx)}')
        for s in rx:
            if not s or not script.search(s):
                problems.append(f'bad-ex    {e["id"]}: {s!r}')
        if lang == "uk" and re.search(r"[ЫыЭэЁёЪъ]", t.get(lang, "") + " ".join(rx)):
            problems.append(f'russian?  {e["id"]}: contains Ы/Э/Ё/Ъ')
    return problems
