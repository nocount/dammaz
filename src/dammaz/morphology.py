"""Suffix attachment: the normative implementation of spec/grammar.md §2.

    >>> inflect("dawi", "PL")
    'dawin'
    >>> inflect("skreka", "PST")
    'skrekad'
    >>> inflect("grund", "AGT")
    'grundaki'
    >>> inflect("drash", "AGT", "PL")
    'drashkin'

Junction rules, applied one suffix at a time:

1. **Plural** is ``-i`` after a consonant and ``-n`` after a vowel.
2. **Elision**: a vowel-initial suffix drops a stem-final vowel
   (``skreka + ad -> skrekad``), as in Khazalid (``ska + az -> skaz``).
3. **Epenthesis**: a consonant-initial suffix that would create an illegal
   consonant cluster gets a linking ``a`` (``grund + ki -> grundaki``).
   Identical consonants across the boundary are fine (``drak + ki -> drakki``).

Order is fixed: derivational suffixes first (any number, in the order given),
then at most one of CMP/ORD, then at most one inflection (PL/PST/PROG).
"""

from __future__ import annotations

from dammaz.phonology import VOWELS, segment, spec

# tag -> (form, gloss label, slot). Several tags may share a form.
SUFFIXES: dict[str, tuple[str, str, str]] = {
    # derivation
    "AGT":    ("ki",  "AGT",    "deriv"),   # person who does X: drashki smith
    "PLACE":  ("az",  "PLACE",  "deriv"),   # place of X: drashaz smithy, zidaz here
    "CRAFT":  ("ul",  "CRAFT",  "deriv"),   # art/craft of X: drashul smithcraft
    "ADV":    ("ul",  "ADV",    "deriv"),   # in an X manner: krangul strongly
    "THING":  ("ak",  "THING",  "deriv"),   # thing / quality of X: krangak strength
    "LIKE":   ("rak", "LIKE",   "deriv"),   # X-like (adj from noun): kurmrak stony, hard
    "VBZ":    ("ash", "VBZ",    "deriv"),   # verb from noun: dammazash hold a grudge
    "TIME":   ("ur",  "TIME",   "deriv"),   # correlatives: zidur now, wanur when
    "REASON": ("os",  "REASON", "deriv"),   # correlatives: zukos therefore
    "POSS":   ("a",   "POSS",   "deriv"),   # pronoun -> possessive: or -> ora
    # degree / order
    "CMP":    ("ar",  "CMP",    "degree"),  # gorzar bigger; ta gorzar the biggest
    "ORD":    ("ik",  "ORD",    "degree"),  # tufik second
    # inflection
    "PL":     ("i",   "PL",     "infl"),    # -n after a vowel
    "PST":    ("ad",  "PST",    "infl"),
    "PROG":   ("en",  "PROG",   "infl"),
}

EPENTHETIC_VOWEL = "a"
_SLOT_RANK = {"deriv": 0, "degree": 1, "infl": 2}


def _ends_in_vowel(stem: str) -> bool:
    return stem[-1] in VOWELS


def _final_consonants(stem: str) -> list[str]:
    segs = segment(stem, collapse_geminates=False)
    out: list[str] = []
    for s in reversed(segs):
        if s in VOWELS:
            break
        out.insert(0, s)
    return out


def _initial_consonants(suffix: str) -> list[str]:
    segs = segment(suffix, collapse_geminates=False)
    out: list[str] = []
    for s in segs:
        if s in VOWELS:
            break
        out.append(s)
    return out


def _junction_ok(stem: str, suffix: str) -> bool:
    """Is the consonant cluster formed across the boundary a legal medial?"""
    cluster = _final_consonants(stem) + _initial_consonants(suffix)
    if not cluster:
        return True
    return spec().legal_medial(".".join(cluster))


def attach(stem: str, tag: str) -> str:
    form = SUFFIXES[tag][0]
    if tag == "PL":
        return stem + ("n" if _ends_in_vowel(stem) else "i")
    if form[0] in VOWELS:
        if _ends_in_vowel(stem):
            stem = stem[:-1]                              # elision
        return stem + form
    if not _ends_in_vowel(stem) and not _junction_ok(stem, form):
        return stem + EPENTHETIC_VOWEL + form             # epenthesis
    return stem + form


def inflect(root: str, *tags: str) -> str:
    """Apply suffix tags in order, enforcing deriv* -> degree? -> infl?."""
    rank = -1
    seen_degree = seen_infl = False
    word = root
    for t in tags:
        if t not in SUFFIXES:
            raise ValueError(f"unknown suffix tag {t!r}")
        slot = SUFFIXES[t][2]
        if _SLOT_RANK[slot] < rank:
            raise ValueError(f"suffix {t} cannot follow a {list(_SLOT_RANK)[rank]} suffix")
        if slot == "degree":
            if seen_degree:
                raise ValueError("at most one CMP/ORD suffix")
            seen_degree = True
        if slot == "infl":
            if seen_infl:
                raise ValueError("at most one inflectional suffix (PL/PST/PROG)")
            seen_infl = True
        rank = _SLOT_RANK[slot]
        word = attach(word, t)
    return word
