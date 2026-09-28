"""Deterministic English -> Dammaz loanwords for lemmas not in the lexicon.

Zharralid already does this (victory -> victraz, dominate -> domitash). The
rule: re-spell the English lemma in the Dammaz alphabet, then add a class
ending so the part of speech is audible:

    NOUN  -uz     banana -> bananuz
    VERB  -ash    dominate -> dominash   (Zharralid; -ate is dropped)
    ADJ   -rak    purple -> burblrak     ("X-like", the LIKE suffix)
    other  bare

Loans are a fallback, not vocabulary: the corpus filter caps their rate, and
every loan is a signal that the lexicon needs another word.
"""

from __future__ import annotations

import re

from dammaz.phonology import VOWELS

LOAN_ENDINGS = {"NOUN": "uz", "VERB": "ash", "ADJ": "rak"}

_SPELL = [                         # applied in order, on the lowercased lemma
    ("tch", "ch"), ("ph", "f"), ("ck", "k"), ("qu", "kv"), ("q", "k"),
    ("x", "ks"), ("wh", "w"), ("gh", ""),
    ("ce", "se"), ("ci", "si"), ("cy", "si"), ("ch", "tsh"), ("c", "k"),
    ("j", "zh"), ("p", "b"),
    ("ee", "i"), ("ea", "e"), ("oo", "u"), ("ou", "u"), ("ai", "a"), ("ay", "a"),
    ("oa", "o"), ("ie", "i"), ("ey", "i"),
]


def respell(lemma: str) -> str:
    w = re.sub(r"[^a-z]", "", lemma.lower())
    if len(w) > 3 and w.endswith("e") and w[-2] not in VOWELS:
        w = w[:-1]                                   # silent final e
    for a, b in _SPELL:
        w = w.replace(a, b)
    w = w.replace("tsh", "sh")                       # ch -> sh (no 'ch' in Dammaz)
    w = re.sub(r"y(?=[^aeiou]|$)", "i", w)           # vowel y -> i
    w = re.sub(r"([aeiou])[aeiou]+", r"\1", w)       # no vowel sequences
    w = re.sub(r"([^aeiou])\1+", r"\1", w)           # no doubled consonants
    return w or "u"


def loan(lemma: str, pos: str) -> str:
    """The loan stem for an English lemma (inflect it like any other root)."""
    w = respell(lemma)
    if pos == "VERB" and w.endswith("at") and len(w) > 4:
        w = w[:-2]                                   # dominate -> domin-ash
    ending = LOAN_ENDINGS.get(pos, "")
    if ending and w[-1] in VOWELS and ending[0] in VOWELS:
        w = w[:-1]                                   # elision, as for suffixes
    return w + ending
