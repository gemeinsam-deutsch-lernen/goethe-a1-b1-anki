"""Assemble the .apkg with genanki (https://github.com/kerrickstaley/genanki).

Model/deck IDs and note GUIDs are stable, so re-importing an updated package
updates existing notes instead of duplicating them (Anki matches notes by GUID).
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import genanki

from .translations import load as load_translations
from .tts import audio_name, speakable, word_text

REPO_URL = "https://github.com/lernen-deutsch/goethe-a1-b1-anki"
DECK_DESCRIPTION = f"""Vocabulary of the official Goethe-Institut word lists:
<a href="https://www.goethe.de/pro/relaunch/prf/de/A1_SD1_Wortliste_02.pdf">Start Deutsch 1 (A1)</a>,
<a href="https://www.goethe.de/pro/relaunch/prf/de/Goethe-Zertifikat_A2_Wortliste.pdf">Goethe-Zertifikat A2</a>,
<a href="https://www.goethe.de/pro/relaunch/prf/de/Goethe-Zertifikat_B1_Wortliste.pdf">Goethe-Zertifikat B1</a>
— © Goethe-Institut e.V. Unofficial, non-commercial study material, not affiliated with the Goethe-Institut.<br>
Grammar: Wiktionary via kaikki.org (CC BY-SA). Audio: Piper TTS. Source and updates: <a href="{REPO_URL}">{REPO_URL}</a>"""
SUBDECKS = {"noun": "1 Nomen", "verb": "2 Verben", "other": "3 Andere"}
POS_INDEX = {"noun": 1, "verb": 2, "other": 3}
# Per target language: deck name, ID base and GUID namespace. Never change existing values:
# Anki matches decks/models by ID and notes by GUID when re-importing.
LANG_CONFIG = {
    "ru": {"deck": "Deutsch Goethe A1–B1 (RU)", "deck_base": 1_732_560_000,
           "model_base": 1_732_561_000, "guid_ns": "goethe-a1-b1"},
    "uk": {"deck": "Deutsch Goethe A1–B1 (UK)", "deck_base": 1_732_570_000,
           "model_base": 1_732_571_000, "guid_ns": "goethe-a1-b1-uk"},
}
LEVEL_ORDER = {"A1": 0, "A2": 1, "B1": 2}

CSS = """
.card { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; font-size: 20px;
  text-align: center; color: #1f2328; background: #fff; line-height: 1.4; }
.nightMode.card, .night_mode .card { color: #e6edf3; background: #1e1e1e; }
.word { font-size: 34px; font-weight: 600; margin: 8px 0 4px; }
.ru-word { font-size: 30px; font-weight: 600; margin: 8px 0 4px; }
.forms { font-size: 19px; color: #57606a; margin-bottom: 4px; }
.nightMode .forms { color: #9ea7b3; }
.extra { font-size: 15px; color: #6e7781; margin: 2px 0; }
.nightMode .extra { color: #8b949e; }
.der { color: #1f6feb; } .die { color: #d1242f; } .das { color: #1a7f37; }
.nightMode .der { color: #58a6ff; } .nightMode .die { color: #ff7b72; } .nightMode .das { color: #3fb950; }
.strong { color: #bf8700; font-weight: 700; }
.examples { text-align: left; max-width: 640px; margin: 14px auto 0; padding-left: 1.2em; }
.examples li { margin: 6px 0; }
.ex-ru { color: #57606a; font-size: 17px; }
.nightMode .ex-ru { color: #9ea7b3; }
.level { position: absolute; top: 6px; right: 10px; font-size: 12px; color: #8c959f; }
hr#answer { margin: 14px 0; }
"""

def _fields(L: str) -> list[str]:
    return ["ID", "Level", "Gender", "WordDE", "Forms", "Extra", L,
            "ExDE", f"Ex{L}", "ExPairs", "ExPairsSilent", "WordAudio"]


RU_DE_FRONT = """<div class="level">{{Level}}</div>
<div class="ru-word">{{RU}}</div>
{{#ExRU}}<ol class="examples">{{ExRU}}</ol>{{/ExRU}}"""

RU_DE_BACK = """<div class="level">{{Level}}</div>
<div class="ru-word">{{RU}}</div>
<hr id="answer">
<div class="word {{Gender}}">{{WordDE}}</div> {{WordAudio}}
{{#Forms}}<div class="forms">{{Forms}}</div>{{/Forms}}
{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}
{{#ExPairs}}<ol class="examples">{{ExPairs}}</ol>{{/ExPairs}}"""

DE_RU_FRONT = """<div class="level">{{Level}}</div>
<div class="word {{Gender}}">{{WordDE}}</div> {{WordAudio}}
{{#ExDE}}<ol class="examples">{{ExDE}}</ol>{{/ExDE}}"""

DE_RU_BACK = """<div class="level">{{Level}}</div>
<div class="word {{Gender}}">{{WordDE}}</div>
{{#Forms}}<div class="forms">{{Forms}}</div>{{/Forms}}
{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}
<hr id="answer">
<div class="ru-word">{{RU}}</div>
{{#ExPairsSilent}}<ol class="examples">{{ExPairsSilent}}</ol>{{/ExPairsSilent}}"""


def _localize(template: str, L: str) -> str:
    """Templates are written for RU; rename the translation fields for other languages."""
    return template.replace("{{RU}}", "{{%s}}" % L).replace("ExRU}}", f"Ex{L}}}}}")


def _model(pos: str, lang: str) -> genanki.Model:
    from .translations import LANGS

    L = LANGS[lang]["label"]
    title = {"noun": "Nomen", "verb": "Verben", "other": "Andere"}[pos]
    return genanki.Model(
        LANG_CONFIG[lang]["model_base"] + POS_INDEX[pos],
        f"Goethe A1–B1 {title} ({L}↔DE)",
        fields=[{"name": f} for f in _fields(L)],
        templates=[
            {"name": f"{L} → DE", "qfmt": _localize(RU_DE_FRONT, L), "afmt": _localize(RU_DE_BACK, L)},
            {"name": f"DE → {L}", "qfmt": _localize(DE_RU_FRONT, L), "afmt": _localize(DE_RU_BACK, L)},
        ],
        css=CSS,
        sort_field_index=3,
    )


def _e(s: str) -> str:
    return html.escape(s, quote=False)


def _word_and_forms(e: dict) -> tuple[str, str, str, str]:
    """-> (gender class, DE headword html, forms html, extra html)"""
    extra = []
    if e.get("regional"):
        extra.append(_e(e["regional"]))
    if e["pos"] == "noun":
        art = e["article"] + (f'/{e["article2"]}' if e.get("article2") else "")
        word = f'{_e(art)} {_e(e["word"])}'
        forms = []
        if e["pl_only"]:
            forms.append("nur Plural")
        elif e["plural"]:
            forms.append(_e(e["plural"]))
        else:
            forms.append("nur Singular")
        if e.get("genitive"):
            forms.append(_e(e["genitive"]))
        fem = [v for v in e.get("variants", []) if v.startswith("die ")]
        if fem:
            extra.insert(0, _e(fem[0]))
        elif e.get("feminine"):
            extra.insert(0, _e(e["feminine"]))
        return e["article"], word, " · ".join(forms), "<br>".join(extra)
    if e["pos"] == "verb":
        star = '<span class="strong">*</span>' if e["strong"] else ""
        word = _e(e["infinitive"]) + star
        if e.get("prep"):
            word += f' <span class="extra">({_e(e["prep"])})</span>'
        parts = []
        if e["er"]:
            parts.append("er " + _e(e["er"]))
        if e["praeteritum"]:
            parts.append(_e(e["praeteritum"]))
        if e["partizip2"]:
            parts.append(_e(f'{e["aux"]} {e["partizip2"]}'.strip()))
        if e.get("verb_note"):
            extra.append(_e(e["verb_note"]))
        return "", word, " · ".join(parts), "<br>".join(extra)
    word = _e(e["word"])
    if e.get("pos_label"):
        extra.insert(0, _e(e["pos_label"]))
    for n in e.get("notes", []):
        extra.append(_e(n))
    return "", word, "", "<br>".join(extra)


def _sound(name: str) -> str:
    return f"[sound:{name}]"


def note_fields(e: dict, t: dict, lang: str, clip) -> list[str]:
    """Field values in model order; `clip(text)` returns a [sound:] tag (or "")."""
    gender, word, forms, extra = _word_and_forms(e)
    de = e["examples"]
    tr = t[f"{lang}_examples"]
    ex_de = "".join(f"<li>{_e(d)} {clip(d)}</li>" for d in de)
    ex_tr = "".join(f"<li>{_e(r)}</li>" for r in tr)
    pairs = "".join(
        f'<li>{_e(d)} {clip(d)}<br><span class="ex-ru">{_e(r)}</span></li>' for d, r in zip(de, tr)
    )
    pairs_silent = "".join(
        f'<li>{_e(d)}<br><span class="ex-ru">{_e(r)}</span></li>' for d, r in zip(de, tr)
    )
    return [e["id"], e["level"], gender, word, forms, extra, _e(t[lang]),
            ex_de, ex_tr, pairs, pairs_silent, clip(word_text(e))]


def build_package(data: Path, cache: Path, dist: Path, voice: str, lang: str = "ru") -> Path:
    cfg = LANG_CONFIG[lang]
    entries = json.loads((data / "entries.json").read_text(encoding="utf-8"))
    tr = load_translations(data / "translations", lang)
    audio_dir = cache / "audio"

    models = {p: _model(p, lang) for p in SUBDECKS}
    decks = {
        p: genanki.Deck(
            cfg["deck_base"] + POS_INDEX[p], f'{cfg["deck"]}::{SUBDECKS[p]}', description=DECK_DESCRIPTION
        )
        for p in SUBDECKS
    }
    media: set[Path] = set()
    missing_audio = 0
    entries = sorted(entries, key=lambda e: LEVEL_ORDER[e["level"]])  # stable: keeps file order

    def clip(text: str) -> str:
        nonlocal missing_audio
        name = audio_name(speakable(text), voice)
        p = audio_dir / name
        if not p.exists():
            missing_audio += 1
            return ""
        media.add(p)
        return _sound(name)

    for i, e in enumerate(entries):
        note = genanki.Note(
            model=models[e["pos"]],
            fields=note_fields(e, tr[e["id"]], lang, clip),
            tags=["goethe", *e["levels"], f'pos::{e["pos"]}'],
            guid=genanki.guid_for(cfg["guid_ns"], e["id"]),
            due=i,
        )
        decks[e["pos"]].add_note(note)

    if missing_audio:
        print(f"warning: {missing_audio} audio clips missing (run `mc tts`)")
    pkg = genanki.Package(list(decks.values()))
    pkg.media_files = sorted(str(p) for p in media)
    dist.mkdir(parents=True, exist_ok=True)
    out = dist / f"Deutsch_Goethe_A1-B1_{lang.upper()}.apkg"
    pkg.write_to_file(out)
    return out
