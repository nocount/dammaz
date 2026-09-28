"""Parse the raw fan lexicons in references/raw/ into a single word table.

Output: references/raw/source_words.tsv (gitignored, like its inputs), columns:

    word    source      kind     tag           gloss
    karak   khazalid    native   official      Mountain, stronghold ...
    victraz zharralid   calque   zharralid     Victory

``kind`` is one of
    native  - a genuine-looking dwarf word; used for phonotactic statistics
    calque  - a dwarvified English/Latin word (victraz, domitash); excluded
              from the native statistics but kept as data for the loanword rule
    exclude - AI-invented, plain English, or otherwise not usable

Multi-word / hyphenated / slash-separated headwords are split into their
component words. Usage:

    uv run python tools/extract_source_words.py
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "references" / "raw"
KHAZ = RAW / "khazalid_lexicon_alebelly.txt"
ZHAR = RAW / "zharralid_lexicon_suspicious_entity.txt"
OUT = RAW / "source_words.tsv"

# Zharralid entries that are transparently English (or Latin/Arabic/French)
# words re-spelled: useful for the loan rule, bad for "native" statistics.
ZHAR_CALQUES = {
    "azept", "intimidash", "subjorgitash", "subjagitaz", "domitash", "victraz",
    "lejionoral", "mortash", "kall", "bes", "hungra", "frosh", "shad", "grat",
    "magmaz", "annil", "nozingt", "anoth", "av", "fas", "sepus", "surplaz",
    "zempel", "sempel", "kastalan", "orci", "bout", "fallosh", "arrack",
    "haltaz", "obgri", "tahk", "bendat", "kalz", "invagash", "thret",
    "forsook", "gran", "karps", "awmrak", "minou", "elgramus", "intrez",
    "fowmancy", "progni", "sich", "den", "dem", "haz", "sa", "fa", "gar",
    "vanama", "akazak", "garuz", "shuti", "fagi", "zall", "valgras", "gras",
    "ultsi", "reekvol", "demok", "waddel", "wil", "aro", "peri", "tarace",
}
# Plain English words that appear as headwords in either list.
ENGLISH = {"troll", "just", "beg", "lash", "kith", "wand", "dunkin", "boga",
           "hirn", "tusk", "kro", "gnem"}
# Proper names (gods, places) - native-sounding, keep but tag.
NAMES = {"gazul", "grimnir", "grungni", "morgrim", "smednir", "thungni", "valaya",
         "hashut", "katalhuyk", "zhufbar"}

WORD_RE = re.compile(r"[a-z]+")


@dataclass
class Row:
    word: str
    source: str
    kind: str
    tag: str
    gloss: str


def split_head(head: str) -> list[str]:
    """'Bar, Barak' / 'Az-Dreugi' / "Doki'dum" / 'Z(s)empel' -> component words."""
    head = head.replace("’", "'").lower()
    head = re.sub(r"\((\w+)\)", "", head)          # z(s)empel -> zempel
    return [w for w in WORD_RE.findall(head) if len(w) >= 1]


def parse_khazalid() -> list[Row]:
    lines = [l.strip() for l in KHAZ.read_text(encoding="utf-8").splitlines()]
    start = next(i for i, l in enumerate(lines) if "Section 3: Khazalid Lexicon" in l)
    rows: list[Row] = []
    in_numerals = False
    for line in lines[start + 1:]:
        if line.startswith("Numerals"):
            in_numerals = True
            continue
        if line.startswith("I have scoured"):
            break
        if ":" not in line:
            continue
        head, gloss = line.split(":", 1)
        head, gloss = head.strip(), gloss.strip()
        if in_numerals:                             # "One (1): Ong" is reversed
            head, gloss = gloss, head
        if not head or not head[0].isalpha() or len(head) > 60:
            continue
        tag = "unofficial" if "unofficial" in gloss.lower() else "official"
        for w in split_head(head):
            kind = "exclude" if w in ENGLISH else "native"
            rows.append(Row(w, "khazalid", kind, "name" if w in NAMES else tag, gloss))
    return rows


def split_zhar_line(line: str) -> tuple[str, str, str] | None:
    """'Word (Tag): gloss' | 'Word: gloss' | 'Word (?) gloss' -> (head, tag, gloss)."""
    cut = min((i for i in (line.find("("), line.find(":"), line.find("”"))
               if i > 0), default=-1)
    if cut < 0:
        return None
    head, rest = line[:cut].strip(), line[cut:]
    tag = ""
    if rest.startswith("("):
        close = rest.find(")")
        tag, rest = rest[1:close], rest[close + 1:]
    gloss = rest.lstrip(" :”").strip()
    return head, tag, gloss


def parse_zharralid() -> list[Row]:
    lines = [l.strip() for l in ZHAR.read_text(encoding="utf-8").splitlines()]
    start = next(i for i, l in enumerate(lines) if l.startswith("What we know"))
    rows: list[Row] = []
    for line in lines[start + 1:]:
        if line.startswith("Numbering") or line.startswith("Sentence structures"):
            break
        if not line or line.startswith("("):
            continue
        parts = split_zhar_line(line)
        if not parts or not parts[0][:1].isupper():
            continue
        head, tag, gloss = parts
        tag_l = tag.lower()
        if tag_l == "ai":
            kind = "exclude"
        elif "khazalid" in tag_l and "zharralid" not in tag_l:
            kind = "dup_khazalid"
        else:
            kind = "native"
        norm_tag = ("zharralid" if "zhar" in tag_l or "zharal" in tag_l else
                    "khazalid" if "khaz" in tag_l else
                    "speculative" if "specul" in tag_l else "uncertain")
        for w in split_head(head):
            k = kind
            if k == "native" and w in ZHAR_CALQUES:
                k = "calque"
            if w in ENGLISH or len(w) == 1:     # 'Z(s)empel' leaves a stray 'z'
                k = "exclude"
            rows.append(Row(w, "zharralid", k, norm_tag, gloss))
    return rows


def main() -> None:
    rows = parse_khazalid() + parse_zharralid()
    # Drop Zharralid rows that just repeat a Khazalid word.
    khaz_words = {r.word for r in rows if r.source == "khazalid"}
    out: list[Row] = []
    seen: set[tuple[str, str]] = set()
    for r in rows:
        if r.kind == "dup_khazalid" or (r.source == "zharralid" and r.word in khaz_words
                                          and r.kind == "native"):
            continue
        key = (r.word, r.source)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["word", "source", "kind", "tag", "gloss"])
        for r in out:
            w.writerow([r.word, r.source, r.kind, r.tag, r.gloss])
    from collections import Counter
    c = Counter((r.source, r.kind) for r in out)
    for k in sorted(c):
        print(f"{k[0]:10s} {k[1]:8s} {c[k]:4d}")
    print(f"wrote {len(out)} rows -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
