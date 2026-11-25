"""Integration checks against the official PDFs (skipped if not downloaded: `uv run mc download`)."""

from pathlib import Path

import pytest

from memory_cards.parse_goethe import examples_of, parse_level

PDF = Path(__file__).resolve().parents[1] / "cache" / "pdf"
pytestmark = pytest.mark.skipif(not (PDF / "Goethe-Zertifikat_B1_Wortliste.pdf").exists(), reason="PDFs missing")


@pytest.fixture(scope="module")
def levels():
    return {lv: {e.head: e for e in parse_level(lv, PDF)} for lv in ("A1", "A2", "B1")}


def test_counts(levels):
    assert 650 <= len(levels["A1"]) <= 720
    assert 1100 <= len(levels["A2"]) <= 1200
    assert 2800 <= len(levels["B1"]) <= 3000


def test_verb_forms_wrapped(levels):
    e = levels["B1"]["abhängen, hängt ab, hing ab, hat abgehangen (von)"]
    assert examples_of(e) == ["Vielleicht bleiben wir ein paar Tage länger, das hängt vom Wetter ab."]


def test_numbered_examples(levels):
    assert len(examples_of(levels["B1"]["aber"])) == 7


def test_stem_headword_not_joined(levels):
    assert "all-" in levels["A1"] and "allein" in levels["A1"]


def test_feminine_variant(levels):
    e = levels["B1"]["der Bekannte, -n"]
    assert e.variant_heads == ["die Bekannte, -n"]
    assert examples_of(e) == ["In Hannover wohnen Bekannte von mir."]


def test_sentence_tail_goes_to_previous_entry(levels):
    assert examples_of(levels["B1"]["der Coiffeur, -e"]) == ["Du siehst toll aus! Wer ist dein Coiffeur?"]
