"""Checks on the committed data (no PDFs or network needed)."""

import json
import re
from collections import defaultdict
from pathlib import Path

import pytest

from memory_cards.build_deck import note_fields
from memory_cards.translations import LANGS, load, validate

DATA = Path(__file__).resolve().parents[1] / "data"
ENTRIES = json.loads((DATA / "entries.json").read_text(encoding="utf-8"))


def _lemma(e: dict) -> str:
    w = e.get("word") or e.get("infinitive") or ""
    return re.sub(r"^\(sich\)\s*|^sich\s+", "", w).lower()


def test_ids_unique():
    ids = [e["id"] for e in ENTRIES]
    assert len(ids) == len(set(ids))


def test_no_duplicate_lemmas_within_pos():
    groups = defaultdict(list)
    for e in ENTRIES:
        key = (e["pos"], _lemma(e), e.get("article", ""))
        groups[key].append(e)
    dups = {k: [e["id"] for e in v] for k, v in groups.items() if len(v) > 1}
    # Real homographs differ in plural ("der Ausdruck": Ausdrücke vs. Ausdrucke).
    dups = {k: v for k, v in dups.items()
            if len({e.get("plural") for e in groups[k]}) < len(groups[k])}
    assert not dups


def test_no_verb_listed_as_other():
    verbs = {_lemma(e) for e in ENTRIES if e["pos"] == "verb"}
    clash = [e["id"] for e in ENTRIES if e["pos"] == "other" and _lemma(e) in verbs]
    assert not clash


@pytest.mark.parametrize("lang", sorted(LANGS))
def test_translations_valid(lang):
    assert validate(DATA / "entries.json", DATA / "translations", lang) == []


def test_validate_reports_stale(tmp_path):
    entries = tmp_path / "entries.json"
    entries.write_text(json.dumps([{"id": "a", "examples": []}]), encoding="utf-8")
    (tmp_path / "tr" / "ru").mkdir(parents=True)
    (tmp_path / "tr" / "ru" / "batch_001.json").write_text(json.dumps([
        {"id": "a", "ru": "а", "ru_examples": []},
        {"id": "gone", "ru": "б", "ru_examples": []},
    ]), encoding="utf-8")
    assert validate(entries, tmp_path / "tr", "ru") == ["stale     gone: not in entries.json"]


@pytest.mark.parametrize("lang", sorted(LANGS))
def test_front_side_has_no_german(lang):
    tr = load(DATA / "translations", lang)
    label = LANGS[lang]["label"]
    for e in ENTRIES:
        fields = note_fields(e, tr[e["id"]], lang, lambda text: "")
        word = fields[6]  # translated word, shown on the front of the translation -> DE card
        assert not re.search(r"[A-Za-zÄÖÜäöüß]{2,}", word), (label, e["id"], word)


def test_hint_goes_to_back():
    e = next(e for e in ENTRIES if e["id"] == "other:mal")
    fields = note_fields(e, {"id": e["id"], "ru": "раз", "hint": "mal = einmal",
                             "ru_examples": ["x"] * len(e["examples"])}, "ru", lambda text: "")
    assert "mal = einmal" in fields[5] and "mal" not in fields[6]
