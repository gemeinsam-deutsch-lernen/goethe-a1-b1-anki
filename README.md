# Memory Cards — Goethe A1–B1 (DE ↔ RU / UK)

Builds an Anki package (`.apkg`) from the official Goethe-Institut word lists
(Start Deutsch 1 / A1, Goethe-Zertifikat A2, Goethe-Zertifikat B1).

## Decks

Two independent packages with the same German content:

| Package | Deck | Translation |
|---|---|---|
| `dist/Deutsch_Goethe_A1-B1_RU.apkg` | `Deutsch Goethe A1–B1 (RU)` | Russian |
| `dist/Deutsch_Goethe_A1-B1_UK.apkg` | `Deutsch Goethe A1–B1 (UK)` | Ukrainian |

They use different deck/model IDs and note GUIDs, so both can be imported side by side.
Each deck has three sub-decks:

| Sub-deck | Front/back content |
|---|---|
| `1 Nomen` | article + noun coloured by gender (**der** blue, **die** red, **das** green), full plural, genitive singular, feminine form, regional variants |
| `2 Verben` | infinitive (`*` = strong/irregular), 3rd person singular, Präteritum, `hat`/`ist` + Partizip II |
| `3 Andere` | adjectives, adverbs, prepositions, phrases, word-formation prefixes |

Every note has two cards:

* **RU/UK → DE** — front: translated word + translations of all examples; back: German word, forms and the examples (DE + translation) with audio.
* **DE → RU/UK** — front: German word + German examples with audio; back: forms, translated word, examples with translations.

All official example sentences are included (merged across levels, duplicates removed).
German audio (word and every example) is synthesised locally with [Piper](https://github.com/OHF-Voice/piper1-gpl)
(`de_DE-thorsten-low`), encoded as mono MP3 so it plays on Anki Desktop, AnkiDroid and AnkiMobile.
Tags: `goethe`, `A1`/`A2`/`B1` (every level the word appears in), `pos::noun|verb|other`.
New cards are ordered A1 → A2 → B1. Note GUIDs are stable, so re-importing an updated package updates notes in place.

## Build

Requires [uv](https://docs.astral.sh/uv/) (Python 3.12 is pinned in `.python-version`).

```sh
uv sync
uv run mc download   # Goethe PDFs + kaikki.org German dump (~1.1 GB) into cache/
uv run mc parse      # PDFs + Wiktionary forms -> data/entries.json, data/parse_report.json
uv run mc batches --lang uk   # (only if translations are missing) -> data/translations/uk/todo/*.input.json
uv run mc validate --lang ru  # every entry has a word translation + one sentence per DE example
uv run mc validate --lang uk
uv run mc tts                 # Piper -> cache/audio/*.mp3 (idempotent, content-hashed file names)
uv run mc build --lang ru     # -> dist/Deutsch_Goethe_A1-B1_RU.apkg
uv run mc build --lang uk     # -> dist/Deutsch_Goethe_A1-B1_UK.apkg
uv run pytest
```

## Pipeline

1. `parse_goethe.py` — reads the PDFs character by character with pdfplumber and splits each
   page into headword/example columns by x position (two columns per page for A2/B1).
   Wrapped headwords, wrapped verb forms, feminine forms sharing an example, numbered B1
   examples and sentences broken across columns are reassembled heuristically.
2. `data/fixes.json` — manual corrections for the few layout/typo cases heuristics cannot resolve.
3. `entries.py` — classifies noun/verb/other, merges the three levels (lowest level wins,
   examples are unioned) and enriches grammar from Wiktionary via the
   [kaikki.org](https://kaikki.org/dictionary/German/) extract: genitive, missing plurals,
   missing verb forms, auxiliary, and verb class (strong/irregular → `*`). Goethe data takes
   priority; disagreements are listed in `data/parse_report.json`.
4. `data/translations/<lang>/` — Russian (`ru`) and Ukrainian (`uk`) translations
   (see `GUIDELINES.md`), one JSON file per batch, keyed by entry id. Later batch files override
   earlier ones. They are machine-assisted and should be spot-checked. Adding a language:
   register it in `translations.LANGS` and `build_deck.LANG_CONFIG`, then `mc batches --lang <code>`.
5. `tts.py`, `build_deck.py` — audio and package assembly with genanki.

Not included: the thematic "Wortgruppen" lists (numbers, countries, …) at the start of each PDF,
which have no example sentences.

## Sources and licences

* Word lists © Goethe-Institut — downloaded at build time, not stored in the repository; for personal study.
* Wiktionary data via kaikki.org — CC BY-SA.
* Piper TTS (GPL-3.0); voice `thorsten` by Thorsten Müller — CC0.
