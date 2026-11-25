"""Command line entry point: `uv run mc <command>`."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache"
DATA = ROOT / "data"
DIST = ROOT / "dist"

PDF_URLS = {
    "A1_SD1_Wortliste_02.pdf": "https://www.goethe.de/pro/relaunch/prf/de/A1_SD1_Wortliste_02.pdf",
    "Goethe-Zertifikat_A2_Wortliste.pdf": "https://www.goethe.de/pro/relaunch/prf/de/Goethe-Zertifikat_A2_Wortliste.pdf",
    "Goethe-Zertifikat_B1_Wortliste.pdf": "https://www.goethe.de/pro/relaunch/prf/de/Goethe-Zertifikat_B1_Wortliste.pdf",
}
LANG_CHOICES = ("ru", "uk")
KAIKKI_URL = "https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl"


def _download(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"exists  {dest.relative_to(ROOT)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"fetch   {url}")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(dest)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest() if dest.stat().st_size < 50 << 20 else "-"
    print(f"saved   {dest.relative_to(ROOT)} sha256={sha}")


def cmd_download(args) -> None:
    for name, url in PDF_URLS.items():
        _download(url, CACHE / "pdf" / name)
    _download(KAIKKI_URL, CACHE / "kaikki" / "kaikki.org-dictionary-German.jsonl")


def cmd_parse(args) -> None:
    from .entries import build

    entries, report = build(
        CACHE / "pdf", CACHE / "kaikki", DATA / "fixes.json", DATA / "overrides.json"
    )
    (DATA / "entries.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (DATA / "parse_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    c = collections.Counter((e["level"], e["pos"]) for e in entries)
    print(f"{len(entries)} entries, {sum(len(e['examples']) for e in entries)} examples")
    for k in sorted(c):
        print(f"  {k[0]} {k[1]:6} {c[k]}")
    for k, v in report.items():
        print(f"  report.{k}: {len(v)}")


def cmd_batches(args) -> None:
    from .translations import make_batches

    hint = "ru" if args.lang != "ru" else None
    n = make_batches(DATA / "entries.json", DATA / "translations", args.lang, args.size, hint)
    print(f"{n} batch input files in {DATA / 'translations' / args.lang / 'todo'}")


def cmd_validate(args) -> None:
    from .translations import validate

    problems = validate(DATA / "entries.json", DATA / "translations", args.lang)
    for p in problems[:200]:
        print(p)
    print(f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


def cmd_tts(args) -> None:
    from .tts import synthesize_all

    synthesize_all(DATA / "entries.json", CACHE, args.voice, args.jobs)


def cmd_build(args) -> None:
    from .build_deck import build_package

    out = build_package(DATA, CACHE, DIST, args.voice, args.lang)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


def cmd_screenshots(args) -> None:
    from .screenshots import render_all

    for p in render_all(DATA, ROOT / "docs" / "screenshots"):
        print(f"wrote {p.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="mc", description="Goethe A1-B1 Anki deck builder")
    sub = ap.add_subparsers(required=True)
    sub.add_parser("download", help="fetch Goethe PDFs and the kaikki dump").set_defaults(f=cmd_download)
    sub.add_parser("parse", help="PDFs + kaikki -> data/entries.json").set_defaults(f=cmd_parse)
    b = sub.add_parser("batches", help="split entries into translation batches")
    b.add_argument("--size", type=int, default=100)
    b.add_argument("--lang", choices=LANG_CHOICES, default="ru")
    b.set_defaults(f=cmd_batches)
    v = sub.add_parser("validate", help="check translations are complete")
    v.add_argument("--lang", choices=LANG_CHOICES, default="ru")
    v.set_defaults(f=cmd_validate)
    t = sub.add_parser("tts", help="synthesize German audio with Piper")
    t.add_argument("--voice", default="de_DE-thorsten-low")
    t.add_argument("--jobs", type=int, default=4)
    t.set_defaults(f=cmd_tts)
    d = sub.add_parser("build", help="assemble the .apkg")
    d.add_argument("--voice", default="de_DE-thorsten-low")
    d.add_argument("--lang", choices=LANG_CHOICES, default="ru")
    d.set_defaults(f=cmd_build)
    sub.add_parser("screenshots", help="render README card screenshots (needs Chrome)").set_defaults(f=cmd_screenshots)
    args = ap.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
