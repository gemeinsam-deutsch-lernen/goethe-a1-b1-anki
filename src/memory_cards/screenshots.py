"""Render README screenshots from the real card templates with headless Chrome.

The Anki template syntax used by the deck ({{Field}}, {{#Field}}...{{/Field}}) is
rendered here directly; [sound:...] tags become Anki-like play buttons.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .build_deck import CSS, DE_RU_BACK, DE_RU_FRONT, RU_DE_BACK, RU_DE_FRONT, _fields, _localize, note_fields
from .translations import LANGS
from .translations import load as load_translations

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
]

PLAY = (
    '<span style="display:inline-block;width:22px;height:22px;border-radius:50%;'
    'background:#8c959f;color:#fff;font-size:11px;line-height:22px;text-align:center;'
    'vertical-align:middle">▶</span>'
)

# (file name, entry id, lang, template side, dark mode)
SHOTS = [
    ("noun-de-ru-back.png", "noun:tisch:der", "ru", "de_back", False),
    ("verb-de-ru-back.png", "verb:fahren", "ru", "de_back", True),
    ("ru-de-front.png", "noun:bahnhof:der", "ru", "tr_front", False),
    ("uk-de-back.png", "noun:frage:die", "uk", "tr_back", False),
]


def _render(template: str, fields: dict[str, str]) -> str:
    def section(m):
        return m.group(2) if fields.get(m.group(1), "").strip() else ""

    out = re.sub(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", section, template, flags=re.S)
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: fields.get(m.group(1), ""), out)
    return re.sub(r"\[sound:[^\]]+\]", PLAY, out)


def _chrome() -> str:
    for c in CHROME_CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    raise SystemExit("Chrome/Chromium not found")


def _trim(path: Path, bg: str, pad: int = 48) -> None:
    """Cut the empty background below the card content."""
    from PIL import Image, ImageChops

    img = Image.open(path).convert("RGB")
    color = tuple(int(bg[i : i + 2], 16) for i in (1, 3, 5))
    diff = ImageChops.difference(img, Image.new("RGB", img.size, color))
    bbox = diff.getbbox()
    if bbox:
        img.crop((0, 0, img.width, min(img.height, bbox[3] + pad))).save(path, optimize=True)


def render_all(data: Path, out_dir: Path, width: int = 560) -> list[Path]:
    entries = {e["id"]: e for e in json.loads((data / "entries.json").read_text(encoding="utf-8"))}
    out_dir.mkdir(parents=True, exist_ok=True)
    chrome = _chrome()
    written = []
    for name, eid, lang, side, dark in SHOTS:
        e = entries[eid]
        t = load_translations(data / "translations", lang)[eid]
        L = LANGS[lang]["label"]
        values = dict(zip(_fields(L), note_fields(e, t, lang, lambda text: "[sound:x.mp3]")))
        template = {
            "de_front": DE_RU_FRONT, "de_back": DE_RU_BACK,
            "tr_front": RU_DE_FRONT, "tr_back": RU_DE_BACK,
        }[side]
        body = _render(_localize(template, L), values)
        bg = "#1e1e1e" if dark else "#ffffff"
        page = (
            f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}'
            f"body{{margin:0;padding:28px 20px;background:{bg};position:relative}}</style></head>"
            f'<body class="card{" nightMode" if dark else ""}">{body}</body></html>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "card.html"
            html_path.write_text(page, encoding="utf-8")
            height = 2000  # tall viewport, trimmed to the content below
            target = out_dir / name
            subprocess.run(
                [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                 "--force-device-scale-factor=2", f"--window-size={width},{height}",
                 f"--screenshot={target}", html_path.as_uri()],
                check=True, capture_output=True,
            )
        _trim(target, bg)
        written.append(target)
    return written
