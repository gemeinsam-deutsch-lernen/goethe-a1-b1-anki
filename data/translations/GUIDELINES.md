# Translation guidelines (DE → RU / UK)

Translations live in one directory per language: `ru/`, `uk/`.
Translators receive `<lang>/todo/batch_NNN.input.json` and write `<lang>/batch_NNN.json`.

## Input item
```json
{"id": "noun:abfahrt:die", "pos": "noun", "de": "die Abfahrt (Pl. die Abfahrten)",
 "notes": [], "examples": ["Vor der Abfahrt rufe ich an.", "..."],
 "hint_ru": "отъезд, отправление"}
```
`hint_ru` (only in non-Russian batches) shows which senses were chosen for the Russian deck.
Use it to disambiguate, but **translate from the German**, never from the Russian.

## Output item (same order, one per input item, nothing else)
Keys are the language code and `<code>_examples`:
```json
{"id": "noun:abfahrt:die", "ru": "отъезд, отправление", "ru_examples": ["Перед отъездом я позвоню.", "..."]}
{"id": "noun:abfahrt:die", "uk": "від'їзд, відправлення", "uk_examples": ["Перед від'їздом я подзвоню.", "..."]}
```

## Rules (all languages)
- `<code>_examples` must contain **exactly** one sentence per German example, in the same order.
- The word translation gives the equivalent(s) of the headword **in the senses used by the examples**.
  - Several distinct senses: separate with `; `. Synonyms of one sense: separate with `, `.
  - Keep it short: at most ~4 equivalents in total.
  - Nouns: nominative singular without any article (plural-only nouns: plural form).
    If the entry also lists a feminine form, give both (`"учитель, учительница"`).
  - Verbs: infinitive; give the aspect pair where natural (`"звонить / позвонить"`).
    Reflexive `sich`/`(sich)` → reflexive verb where natural.
    If a preposition is shown, add the government in brackets (`"интересоваться (чем-л.)"`).
  - Prefixes/stems (`Haupt-`, `irgend-`, `all-`) — describe the meaning briefly
    (`"главный, основной (в сложных словах)"`).
  - Regional words (marked `(A)`, `(CH)`, `(D)` in `de`): translate normally and append the
    country note: RU `(австр.)`, `(швейц.)`, `(герм.)`; UK `(австр.)`, `(швейц.)`, `(нім.)`.
- Example translations: natural, idiomatic, faithful to the meaning; keep dialogue dashes (`–`),
  names and numbers; keep the register (du → ты/ти, Sie → вы/ви).
- Output valid JSON (UTF-8, no comments, no trailing commas). Use «» for quotes inside the
  translation so no escaping is needed.

## Ukrainian specifics
- Modern standard Ukrainian (current orthography): no Russianisms or surzhyk
  (`зараз`, not `сейчас`; `потрібно/треба`, not `нужно`; `вибачте`, not `извините`).
- Apostrophe is the typewriter `'` (`від'їзд`, `м'ясо`); never use letters ы, э, ё, ъ.
- Use the vocative where natural in address (`пане Мюллер`), `Ви` for polite Sie only when
  addressing one person in letters; otherwise `ви`.
- Grammar abbreviations in word translations: `(чого-н.)`, `(кого-н.)`, `(чим-н.)`.
