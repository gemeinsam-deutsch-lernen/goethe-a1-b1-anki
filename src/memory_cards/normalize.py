"""Turn raw Goethe headword strings into structured noun / verb / other records."""

from __future__ import annotations

import re
import unicodedata

ARTICLES = ("der", "die", "das")
_REGION = r"(?:D|A|CH)"
_REGION_PAREN = re.compile(rf"\(\s*{_REGION}(?:\s*,\s*{_REGION})*\s*\)")
_FLAGS = re.compile(r"\((Sg|Pl|pl|sg)\.\)")


def clean(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = s.replace("­", "").replace("–", "-").replace("“", "¨").replace("̈", "¨")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def split_regional(head: str) -> tuple[str, str]:
    """'das Abitur (D)→A, CH: Matura' -> ('das Abitur', '(D) → A, CH: Matura')."""
    m = re.search(rf"\s*({_REGION_PAREN.pattern}|→)", head)
    if not m:
        return head, ""
    note = head[m.start():].strip()
    note = re.sub(r"\s*→\s*", " → ", note).strip()
    return head[: m.start()].strip().rstrip(","), note


_UMLAUT = {"a": "ä", "o": "ö", "u": "ü", "A": "Ä", "O": "Ö", "U": "Ü"}


def umlaut(word: str) -> str:
    """Umlaut the stressed stem vowel (last a/o/u that is not in a suffix like -el/-en)."""
    i = len(word) - 1
    while i >= 0:
        ch = word[i]
        if ch in "aouAOU":
            if ch in "uU" and i > 0 and word[i - 1] in "aA":  # au -> äu
                return word[: i - 1] + _UMLAUT[word[i - 1]] + word[i:]
            return word[:i] + _UMLAUT[ch] + word[i + 1 :]
        i -= 1
    return word


def apply_plural(word: str, notation: str) -> list[str] | None:
    """Expand Goethe plural notation for `word`. Returns None if not understood."""
    n = notation.strip().rstrip(";,.").strip()
    if not n:
        return None
    if "/" in n and not n.startswith("/"):
        out: list[str] = []
        for part in n.split("/"):
            r = apply_plural(word, part)
            if r is None:
                return None
            out += r
        return out
    if re.fullmatch(r"[A-ZÄÖÜ][\wäöüß]+", n):  # full form, e.g. "Risiken"
        return [n]
    um = False
    # Umlaut markers: "¨-e", "-¨e", "¨e", "-ä, e", "ä, er", "-Ä", "-ü"
    m = re.fullmatch(r"-?\s*(?:¨|[äöüÄÖÜ])\s*-?\s*,?\s*([a-z]*)", n)
    if m:
        um = True
        suffix = m.group(1)
    else:
        m = re.fullmatch(r"-\s*([a-z]*)", n)
        if not m:
            return None
        suffix = m.group(1)
    base = umlaut(word) if um else word
    # Latin/Greek stems: Datum -> Daten, Thema -> Themen, Konto -> Konten, Museum -> Museen
    if suffix in ("en", "n") and not um:
        m2 = re.fullmatch(r"(.+?)(um|us|a|o|on)", word)
        if m2 and word.endswith(("um", "us", "a", "o")) and not word.endswith(("ua",)):
            return [m2.group(1) + "en"]
    return [base + suffix]


_NOUN = re.compile(
    r"^(?P<art>der|die|das)(?:/(?P<art2>der|die|das))?\s+"
    r"(?P<word>[A-ZÄÖÜa-z(][^,;/]*?)\s*(?:,\s*(?P<pl>[^/;]*?))?\s*(?=$|/|;|,\s*(?:der|die|das)\b)"
)


def parse_noun(head: str) -> dict | None:
    h = clean(head)
    h, regional = split_regional(h)
    sg_only = bool(re.search(r"\((Sg|sg)\.\)", h))
    pl_only = bool(re.search(r"\((Pl|pl)\.\)", h))
    h = _FLAGS.sub("", h).strip()
    h = re.sub(r"\s+,", ",", h)
    m = _NOUN.match(h)
    if not m:
        # "Abgase (Pl.)" without article
        if pl_only and re.fullmatch(r"[A-ZÄÖÜ][\wäöüß-]+", h):
            return {"article": "die", "word": h, "plural": [h], "pl_only": True,
                    "sg_only": False, "plural_notation": "", "regional": regional,
                    "feminine": "", "article2": ""}
        return None
    word = m.group("word").strip()
    word = re.sub(r"\s*\(.*?\)\s*$", "", word).strip() or word
    if word.count("(") > word.count(")"):  # "Bescheid (bekommen/geben/sagen)" cut at "/"
        word = word[: word.rindex("(")].strip()
    notation = (m.group("pl") or "").strip()
    rest = h[m.end():].strip(" ,/;")
    plural = None
    if pl_only:
        plural = [word]
    elif notation and not sg_only:
        plural = apply_plural(word, notation)
    return {
        "article": m.group("art"),
        "article2": m.group("art2") or "",
        "word": word,
        "plural_notation": notation,
        "plural": plural,
        "sg_only": sg_only,
        "pl_only": pl_only,
        "feminine": rest,
        "regional": regional,
    }


def parse_verb(head: str) -> dict | None:
    h = clean(head)
    h, regional = split_regional(h)
    note = ""
    mnote = re.search(r"\((hat \w+ als Modalverb)\)", h)
    if mnote:
        note = mnote.group(1)
        h = (h[: mnote.start()] + h[mnote.end():]).strip()
    prep = ""
    mprep = re.search(r"\s*\((von|mit|an|auf|für|über|um|zu|nach|vor|in|aus)\)\s*$", h)
    if mprep:
        prep = mprep.group(1)
        h = h[: mprep.start()].strip()
    parts = [p.strip() for p in h.split(",") if p.strip()]
    if not parts:
        return None
    inf = parts[0]
    reflexive = ""
    if re.search(r"\(sich\)", inf):
        reflexive = "(sich)"
    elif re.match(r"sich\s", inf):
        reflexive = "sich"
    inf_clean = re.sub(r"\(sich\)|^sich\s+", "", inf).strip()
    if not re.fullmatch(r"[a-zäöüß()\-/ ]+", inf_clean):
        return None
    forms = parts[1:]
    forms = [re.sub(r"^es\s+", "", p) for p in forms]  # "es regnet", "es hat geregnet"
    # Perfekt is the last form; search from the end so "zu sein, ist zu, war zu,
    # ist zu gewesen" does not take the er-form "ist zu" for the Perfekt.
    perfekt = next((p for p in reversed(forms) if re.match(r"(hat|ist)(/(hat|ist))?\s", p)), "")
    if not perfekt and forms and re.match(r"ge\w+$", forms[-1]):
        perfekt = forms[-1]  # PDF typo: "gießen, gießt, goss, gegossen"
    others = [p for p in forms if p != perfekt]
    er = others[0] if others else ""
    praet = others[1] if len(others) > 1 else ""
    aux, part2 = "", ""
    if perfekt:
        mp = re.match(r"(?:(hat|ist)(?:/(hat|ist))?\s+)?(.*)", perfekt)
        aux = "/".join(x for x in (mp.group(1), mp.group(2)) if x)
        part2 = mp.group(3).strip()
    return {
        "infinitive": inf_clean,
        "reflexive": reflexive,
        "prep": prep,
        "er": er,
        "praeteritum": praet,
        "aux": aux,
        "partizip2": part2,
        "note": note,
        "regional": regional,
        "has_forms": bool(forms),
    }


def lemma_key(s: str) -> str:
    s = clean(s).lower()
    s = re.sub(r"\(sich\)|^sich\s+|\(.*?\)", "", s)
    return re.sub(r"[^\wäöüß]+", " ", s).strip()
