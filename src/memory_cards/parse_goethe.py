"""Parse the official Goethe-Institut word lists (A1, A2, B1) into raw entries.

Layout notes (measured on the official PDFs):
* A1 has one column per page: headword at x~140, example sentences at x~235.
* A2/B1 have two columns per page, each split into a headword sub-column and an
  example sub-column.
* Body text is a regular (non-bold) face at 8-9 pt; page headers, footers,
  section titles and the big alphabet letters are bold or differently sized,
  so filtering by font is enough to drop them.

Characters are assigned to regions by their x position (not by word), because
headword and example sometimes touch without whitespace ("alltäglich1. Das").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

# (pdf file name, alphabetical page range, list of (head_x0, ex_x0, ex_x1) columns)
LAYOUTS = {
    "A1": {
        "file": "A1_SD1_Wortliste_02.pdf",
        "pages": range(8, 27),
        "columns": [(100, 230, 600)],
        "sizes": (8.9, 9.1),
        "numbered": False,
    },
    "A2": {
        "file": "Goethe-Zertifikat_A2_Wortliste.pdf",
        "pages": range(7, 31),
        "columns": [(25, 100, 295), (295, 365, 600)],
        "sizes": (7.9, 8.1),
        "numbered": False,
    },
    "B1": {
        "file": "Goethe-Zertifikat_B1_Wortliste.pdf",
        "pages": range(15, 102),
        "columns": [(25, 125, 305), (305, 405, 600)],
        "sizes": (7.9, 8.1),
        "numbered": True,
    },
}

TOP_MIN, TOP_MAX = 40, 790
LINE_TOL = 2.5


@dataclass
class RawEntry:
    level: str
    head_lines: list[str] = field(default_factory=list)
    ex_lines: list[tuple[str, bool]] = field(default_factory=list)  # (text, starts_new)
    page: int = 0
    variants: list[list[str]] = field(default_factory=list)  # extra headwords, e.g. feminine

    @property
    def current_head(self) -> list[str]:
        return self.variants[-1] if self.variants else self.head_lines

    @property
    def variant_heads(self) -> list[str]:
        return [join_lines(v) for v in self.variants]

    @property
    def head(self) -> str:
        return join_lines(self.head_lines)


def join_lines(lines: list[str]) -> str:
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if not out:
            out = ln
        elif re.search(r"[a-zäöüß]-$", out) and ln[:1].islower() or (
            re.search(r"[-–¨]$", out) and ln in ("e", "n", "en", "er", "s", "se", "nen")
        ):
            out = out[:-1] + ln  # soft hyphenation: "Aben-" + "teuer"
        elif out.endswith("/") or out.endswith("(") or ln.startswith(")"):
            out += ln
        else:
            out += " " + ln
    return re.sub(r"\s+", " ", out).strip()


def _chars_to_text(chars: list[dict]) -> str:
    chars = sorted(chars, key=lambda c: c["x0"])
    out = []
    prev = None
    for c in chars:
        if prev is not None and c["x0"] - prev["x1"] > c["size"] * 0.18:
            out.append(" ")
        out.append(c["text"])
        prev = c
    return "".join(out).strip()


def page_lines(page, layout) -> list[list[tuple[str, str]]]:
    """Return, per column, a list of (head_text, example_text) lines in y order."""
    lo, hi = layout["sizes"]
    chars = [
        c
        for c in page.chars
        if lo <= c["size"] <= hi
        and "Bold" not in c["fontname"]
        and TOP_MIN < c["top"] < TOP_MAX
        and c["text"].strip()
    ]
    result = []
    for head_x, ex_x, end_x in layout["columns"]:
        col = [c for c in chars if head_x <= c["x0"] < end_x]
        rows: list[list[dict]] = []
        for c in sorted(col, key=lambda c: c["top"]):
            if rows and abs(rows[-1][0]["top"] - c["top"]) <= LINE_TOL:
                rows[-1].append(c)
            else:
                rows.append([c])
        lines = []
        for row in rows:
            row.sort(key=lambda c: c["x0"])
            split = next((i for i, c in enumerate(row) if c["x0"] >= ex_x), len(row))
            # A headword that overflows into the example column ("heruntergelad|en")
            # is glued to it without a gap; keep such characters with the head.
            j = split
            while 0 < j < len(row) and row[j]["x0"] - row[j - 1]["x1"] < 0.8:
                j += 1
            glued = "".join(c["text"] for c in row[split:j])
            if j > split and not re.match(r"\d", glued):
                split = j
            head = _chars_to_text(row[:split])
            ex = _chars_to_text(row[split:])
            # Plural marker printed in the example column: "die Sehenswürdigkeit," "-en Welche"
            m = re.match(r"^([-–¨“]+[a-zäöü]*)(?=\s|$)", ex)
            if m and head.endswith(","):
                head += " " + m.group(1)
                ex = ex[m.end():].strip()
            # Plural suffix split off by the column edge: "der Klick, -" | "s Um das ..."
            m = re.match(r"^([a-zäöü]{1,3})\s+(?=[A-ZÄÖÜ„0-9])", ex)
            if m and re.search(r",\s*[-–¨]$", head):
                head += m.group(1)
                ex = ex[m.end():].strip()
            lines.append((head, ex))
        result.append(lines)
    return result


_VERB_FORM_START = re.compile(r"^(hat|ist|hat/ist|ist/hat|war|wurde)\b")
_NUMBERED = re.compile(r"^\d{1,2}\.\s")
_SENT_END = re.compile(r"[.!?…:“\"»)]$|\.\.\.$")


_VERB_HEAD = re.compile(
    r"^(\(?sich\)? )?[a-zäöü(][\w()\- ]*n( \(sich\))?, (sich )?[a-zäöü]\S*[td]\b"
)


def _head_continues(head_so_far: str, prev_line: str, line: str) -> bool:
    prev = prev_line.rstrip()
    if not prev:
        return False
    if prev.endswith((",", ";", "→", "/", "(", ":")):
        return True
    if re.search(r",\s*[-–¨]$", prev) and line in ("e", "n", "en", "er", "s", "se", "nen"):
        return True  # "der Zeitpunkt, -" / "e"
    if re.search(r"(^|/\s?|→\s?|:\s?)(der|die|das)$", prev):
        return True  # "der/die" / "Bekannte, -n"
    if head_so_far.count("(") > head_so_far.count(")"):
        return True  # "(hat dürfen" / "als Modalverb)"
    if re.search(r"(\b(hat|ist)|,\s*es)$", prev):
        return True  # participle on its own line: "legen, legt, legte, hat" / "gelegt"
    # Soft hyphenation inside verb forms ("buchsta-"/"biert") or compound nouns
    # ("das Einkaufs-"/"zentrum"); a bare "-" after a comma is a plural marker
    # ("das Abenteuer, -") and "all-" is a stem headword.
    if line.startswith("(") and not line.startswith("(sich)") and re.search(r"[a-zäöü]-,?$", head_so_far):
        return True  # "herunter-, runter-" / "(herunter-)laden, lädt"
    if line.startswith("(sich)") and re.fullmatch(r"[a-zäöü]+n", head_so_far):
        return True  # "informieren" / "(sich) (über), informiert, ..."
    if line.startswith("(") and ")" not in line:
        return True  # "(bekommen/geben/" / "sagen)"
    if (
        "→" in head_so_far
        and line[:1].islower()
        and not re.match(r"(der|die|das)\b", line)
        and re.search(r"\b(D|A|CH)(, ?(D|A|CH))*:", line)
    ):
        return True  # regional variants wrapped: "gehen/sein; D, CH: pensioniert ..."
    if (
        line[:1].islower()
        and not re.match(r"(der|die|das)\b", line)
        and re.search(r"[a-zäöüßA-ZÄÖÜ]-$", prev)
    ) and (
        "," in head_so_far or "→" in head_so_far or re.match(r"(der|die|das)\b", head_so_far)
    ):
        return True
    if re.fullmatch(r"(gewesen|geworden|gegangen)\b.*", line):
        return True
    if line.startswith(("→", ")", "/")) or re.fullmatch(r"\([^)]*\)[,;:]?", line):
        return True
    if re.match(r"\((hat|D\b|A\b|CH\b|z\. ?B\.|Bsp)", line):
        return True  # "(CH) → D, A: Eis", "(hat wollen als Modalverb)"
    if re.match(r"(D|A|CH)(, ?(D|A|CH))*:", line):
        return True  # regional variant list continued: "CH: Zivilstand"
    if _VERB_FORM_START.match(line):
        return True
    # Verb forms wrapped without a trailing comma: "abhängen, hängt ab, hing" / "ab, hat ..."
    if (
        _VERB_HEAD.match(head_so_far)
        and not re.search(r"\b(hat|ist)\s", head_so_far)
        and line[:1].islower()
        and not re.match(r"(der|die|das)\b", line)
        and (re.search(r"\b(hat|ist)\s", line) or "," in line)
    ):
        return True
    return False


def _finishes(prev: RawEntry, ex: str) -> bool:
    if not _example_open(prev):
        return False
    if not _SENT_END.search(ex.rstrip()):
        return False
    return ex[:1].islower() or len(ex.split()) <= 2


def _example_open(cur: RawEntry) -> bool:
    """True if the entry's last example line is an unfinished sentence."""
    if not cur.ex_lines:
        return False
    if _is_note(_last_group(cur)):
        return False
    return not _SENT_END.search(cur.ex_lines[-1][0].rstrip())


_NOTE = re.compile(r"^(z\. ?B\.|Bsp\.)")


def _is_note(text: str) -> bool:
    return bool(_NOTE.match(text))


def _last_group(cur: RawEntry) -> str:
    for text, new in reversed(cur.ex_lines):
        if new:
            return text
    return cur.ex_lines[0][0]


def parse_level(level: str, pdf_dir: Path) -> list[RawEntry]:
    layout = LAYOUTS[level]
    entries: list[RawEntry] = []
    cur: RawEntry | None = None
    with pdfplumber.open(pdf_dir / layout["file"]) as pdf:
        for pno in layout["pages"]:
            for col in page_lines(pdf.pages[pno], layout):
                for head, ex in col:
                    prev_entry = cur
                    if head:
                        if cur and _head_continues(
                            join_lines(cur.current_head), cur.current_head[-1], head
                        ):
                            cur.current_head.append(head)
                        elif cur and _example_open(cur) and _same_family(cur.head, head):
                            # A second headword sharing one example, typically the
                            # feminine form: "der Bekannte, -n" / "die Bekannte, -n".
                            cur.variants.append([head])
                        elif re.fullmatch(r"[A-ZÄÖÜ]", head) and not ex:
                            continue  # alphabet marker
                        else:
                            cur = RawEntry(level=level, page=pno + 1)
                            entries.append(cur)
                            cur.head_lines.append(head)
                    if ex and prev_entry is not None and prev_entry is not cur and _finishes(prev_entry, ex):
                        # The tail of the previous entry's sentence sits next to the new
                        # headword: "an die" / "See.", "Wer ist dein" / "Coiffeur?".
                        prev_entry.ex_lines.append((ex, False))
                    elif ex and cur:
                        cur.ex_lines.append((ex, _starts_new_example(cur, ex, layout)))
    return _merge_feminine(entries)


def _same_family(cur_head: str, head: str) -> bool:
    """'der Bekannte' / 'die Bekannte', 'der Abwart' / 'die Abwartin'."""
    a, b = _noun_stem(cur_head), _noun_stem(head)
    return bool(a and b and _is_gender_pair(a, b))


def _feminine_forms(stem: str) -> set[str]:
    from .normalize import umlaut

    base = stem[:-1] if stem.endswith("e") else stem
    return {stem, stem + "in", base + "in", umlaut(base) + "in", stem.replace("mann", "frau")}


def _is_gender_pair(a: str, b: str) -> bool:
    """Same word, or masculine/feminine pair: Lehrer/Lehrerin, Kollege/Kollegin, Arzt/Ärztin."""
    return b in _feminine_forms(a) or a in _feminine_forms(b)


def _noun_stem(head: str) -> str | None:
    m = re.match(r"(der|die|das) ([A-ZÄÖÜ][\wäöüß]+)", head)
    return m.group(2) if m else None


def _merge_feminine(entries: list[RawEntry]) -> list[RawEntry]:
    """Fold example-less feminine forms ("die Lehrerin, -nen") into the previous entry."""
    out: list[RawEntry] = []
    for e in entries:
        stem = _noun_stem(e.head)
        prev = out[-1] if out else None
        # Stray continuation of the previous headword ("umgezogen", "Ehemann, ¨-er").
        if prev and not e.ex_lines and (
            re.fullmatch(r"[a-zäöüß/ ]+", e.head)
            or re.match(r"(?!(der|die|das)\b)[a-zäöü]{1,3}\b", e.head)
            or prev.head.endswith(("/", " der", " die", " das", ";", ":"))
            or ("→" in join_lines(prev.current_head) and re.fullmatch(r"[A-ZÄÖÜ]\w+", e.head))
        ):
            prev.current_head.extend(e.head_lines)
            continue
        if prev and not e.ex_lines and stem:
            pstem = _noun_stem(prev.head)
            if pstem and (
                _is_gender_pair(pstem, stem)
                or stem.endswith(pstem)
                or e.head.startswith("die ")
                and stem.endswith(("in", "frau", "e"))
            ):
                prev.variants.append(e.head_lines)
                continue
        out.append(e)
    return out


def _starts_new_example(cur: RawEntry, line: str, layout) -> bool:
    if not cur.ex_lines:
        return True
    prev = cur.ex_lines[-1][0].rstrip()
    if _is_note(_last_group(cur)):
        # "z. B. Lieblingsfarbe, ..." may wrap ("Großvater") before a real example.
        return bool(_NUMBERED.match(line)) or (
            line[:1].isupper() and bool(re.search(r"[.!?]$", line.rstrip()))
        )
    if layout["numbered"]:
        # "1. Juni" inside a sentence is a date, not a list number.
        return bool(_NUMBERED.match(line)) and bool(_SENT_END.search(prev))
    if line.startswith(("–", "-", "—")):
        return False  # dialogue continuation: "Willst du ...? – Nein, ..."
    return bool(_SENT_END.search(prev)) and (
        line[:1].isupper() or line[:1].isdigit() or line[:1] in "„\"("
    )


def _groups(e: RawEntry) -> list[str]:
    groups: list[list[str]] = []
    for text, new in e.ex_lines:
        if new or not groups:
            groups.append([text])
        else:
            groups[-1].append(text)
    return [_NUMBERED.sub("", join_lines(g), count=1).strip() for g in groups]


def examples_of(e: RawEntry) -> list[str]:
    return [s for s in _groups(e) if s and not _is_note(s)]


def notes_of(e: RawEntry) -> list[str]:
    """'z. B. ...' lines printed in the example column (word-formation hints)."""
    return [s for s in _groups(e) if _is_note(s)]
