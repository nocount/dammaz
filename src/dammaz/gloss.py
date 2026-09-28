"""Dammaz -> interlinear English gloss, by morphological analysis.

    >>> Glosser().gloss_word("drashkin")
    'forge-AGT-PL'

A word is analyzed by stripping suffixes right to left (undoing elision and
epenthesis, grammar.md §2.3) until a lexicon word remains; each candidate
analysis is confirmed by re-inflecting it with ``morphology.inflect``.
Lexicalized derived words (drashki "smith") are preferred over
re-deriving them, and fewer suffixes beat more.

CLI::

    uv run python -m dammaz.gloss "Ta dawi dhal drashad un az krang."
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from functools import cached_property

from dammaz.lexicon import function_words, load_content
from dammaz.loan import LOAN_ENDINGS
from dammaz.morphology import SUFFIXES, inflect
from dammaz.phonology import VOWELS

PARTICLE_GLOSS = {"wan": "Q", "an": "FUT", "sar": "COND", "nai": "NEG", "zo": "REL",
                  "zu": "be", "uzar": "you.FML", "uzara": "your.FML"}
MAX_SUFFIXES = 4


@dataclass(frozen=True)
class Analysis:
    root: str
    tags: tuple[str, ...]
    kind: str          # word | name | number | loan | unknown

    def gloss(self, glosses: dict[str, str]) -> str:
        if self.kind == "name":
            return self.root
        if self.kind == "number":
            return "-".join(glosses.get(p, p) for p in self.root.split("-"))
        base = glosses.get(self.root, self.root.upper() if self.kind == "loan" else "?")
        if self.kind == "loan":
            base = f"LOAN:{self.root}"
        return "-".join([base, *self.tags])


class Glosser:
    @cached_property
    def glosses(self) -> dict[str, str]:
        g: dict[str, str] = {}
        for w in function_words():
            g[w.dz] = PARTICLE_GLOSS.get(w.dz, w.en[0].split(" (")[0].replace(" ", "."))
        for e in load_content():
            g[e.dz] = e.senses[0][0].replace(" ", ".")
        return g

    @cached_property
    def uninflectable(self) -> set[str]:
        """Function words that never take a suffix (zo, ta, bin, wan...)."""
        return {w.dz for w in function_words()
                if w.cat in ("conjunction", "particle", "preposition", "article", "interjection")}

    @cached_property
    def lexicalized(self) -> set[str]:
        return {e.dz for e in load_content() if e.origin == "derived"}

    def analyses(self, word: str) -> list[tuple[str, tuple[str, ...]]]:
        """Every (root, tags) with inflect(root, *tags) == word."""
        found: set[tuple[str, tuple[str, ...]]] = set()
        roots = self.glosses

        def rec(w: str, tags: tuple[str, ...]) -> None:
            if w in roots:
                found.add((w, tags))
            if len(tags) >= MAX_SUFFIXES:
                return
            for tag, (form, _, _) in SUFFIXES.items():
                for f in (("i", "n") if tag == "PL" else (form,)):
                    if not word or not w.endswith(f) or len(w) <= len(f):
                        continue
                    stem = w[:-len(f)]
                    cands = {stem}
                    if f[0] in VOWELS:
                        cands |= {stem + v for v in "aeou"}          # undo elision
                    elif stem.endswith("a"):
                        cands.add(stem[:-1])                          # undo epenthesis
                    for c in cands:
                        rec(c, (tag,) + tags)

        rec(word, ())
        good = []
        for root, tags in found:
            if tags and root in self.uninflectable:
                continue
            try:
                if not tags or inflect(root, *tags) == word:
                    good.append((root, tags))
            except ValueError:
                pass
        return good

    def analyze(self, token: str, sentence_initial: bool = False) -> Analysis:
        if re.fullmatch(r"[\d.,]+", token):
            return Analysis(token, (), "number")
        low = token.lower()
        if "-" in low and all(p in self.glosses for p in low.split("-")):   # tuf-zer
            return Analysis(low, (), "number")
        cands = self.analyses(low)
        if cands:
            # prefer: lexicalized derived word, then fewest suffixes
            root, tags = min(cands, key=lambda a: (len(a[1]) - (a[0] in self.lexicalized), a[0]))
            return Analysis(root, tags, "word")
        if token[:1].isupper():
            # capitalized and not a Dammaz word: a name, unless (sentence-initially)
            # it carries a loan class ending
            loan = self._loan(low, short_ok=False) if sentence_initial else None
            return loan or Analysis(token, (), "name")
        return self._loan(low, short_ok=True) or Analysis(low, (), "unknown")

    @staticmethod
    def _loan(low: str, short_ok: bool = True) -> Analysis | None:
        """Loans end in a class ending, possibly followed by inflections."""
        tails = [("", ())]
        for tag in ("PL", "PST", "PROG", "ADV", "CMP"):
            form = SUFFIXES[tag][0]
            for f in (("i",) if tag == "PL" else (form,)):
                tails.append((f, (tag,)))
        for f, tags in tails:
            stem = low[: len(low) - len(f)] if f else low
            if f and not low.endswith(f):
                continue
            for ending in LOAN_ENDINGS.values():
                if stem.endswith(ending) and len(stem) > len(ending):
                    return Analysis(stem, tags, "loan")
        if short_ok and re.fullmatch(r"[abdefghiklmnorstuvwyz]{1,4}", low):
            return Analysis(low, (), "loan")          # short sound-word: ow, moo, ha
        return None

    def gloss_word(self, token: str, sentence_initial: bool = False) -> str:
        return self.analyze(token, sentence_initial).gloss(self.glosses)

    def gloss_text(self, text: str) -> list[tuple[str, str]]:
        """[(token, gloss)] for every word of a Dammaz text (punctuation kept)."""
        out = []
        initial = True
        for tok in re.findall(r"[\w\-]+|[^\w\s]", text):
            if not re.match(r"[\w]", tok):
                out.append((tok, tok))
                initial = initial or tok in ".!?\"“"
                continue
            out.append((tok, self.gloss_word(tok, initial)))
            initial = False
        return out


def interlinear(text: str, width: int = 100) -> str:
    """Two aligned lines (Dammaz over gloss), wrapped at ``width``."""
    pairs = [p for p in Glosser().gloss_text(text) if re.match(r"\w", p[0])]
    lines, top, bot = [], "", ""
    for w, g in pairs:
        col = max(len(w), len(g)) + 1
        if len(top) + col > width and top:
            lines += [top.rstrip(), bot.rstrip(), ""]
            top, bot = "", ""
        top += w.ljust(col)
        bot += g.ljust(col)
    lines += [top.rstrip(), bot.rstrip()]
    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print(interlinear(" ".join(sys.argv[1:]) or sys.stdin.read()))


if __name__ == "__main__":
    main()
