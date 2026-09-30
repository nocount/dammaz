"""English-side normalization shared by tools/coverage.py and the translator.

Klazan expresses some English word classes through other words, so they need
no lexicon entry of their own:

* adverbs      quickly -> quick/ADJ + ADV (-ul);  run fast -> fast/ADJ + ADV
* participles  scared -> scare/VERB + PST;  amazing -> amaze/VERB + PROG
               (grammar.md §6.5: participles are the verb's PST/PROG form)

It also normalizes the input text itself (``normalize_english``): curly
apostrophes inside words, and Early Modern English (thou art -> you are).
"""

from __future__ import annotations

import re
from collections.abc import Container
from functools import cache

# An apostrophe inside a word (don’t, it’s, dwarf’s). spaCy only recognizes
# contractions spelled with a straight ', so a curly one silently changes the
# parse: "wasn’t" loses its negation and "they’ve gone" its tense. Curly
# quotation marks at the edges of a quote are left alone, except before the
# archaic 'tis / 'twas / 'twill.
_INNER_APOSTROPHE = re.compile(
    r"(?<=[A-Za-z])[’‘ʼ](?=[A-Za-z])|(?<![A-Za-z])[’‘](?=t(?:is|was|will)\b)", re.I)


def normalize_apostrophes(text: str) -> str:
    """Straighten apostrophes inside words: don’t -> don't."""
    return _INNER_APOSTROPHE.sub("'", text)


# --- Early Modern English (thou art, he goeth) --------------------------------
# Fairy tales and sagas from Project Gutenberg are full of it, and spaCy reads
# it badly: "thou" becomes a noun, "art" the noun art, "wilt" the verb to wilt.
# So archaic forms are rewritten to modern English before parsing.

ARCHAIC_WORDS = {
    "thou": "you", "thee": "you", "ye": "you", "thy": "your", "thyself": "yourself",
    "hath": "has", "doth": "does", "saith": "says",
    "nay": "no", "aye": "yes", "whilst": "while", "amongst": "among", "unto": "to",
    "ere": "before", "oft": "often", "hither": "here", "thither": "there",
    "whence": "where", "wherefore": "why",
    "'tis": "it is", "'twas": "it was", "'twill": "it will",
    "o'er": "over", "e'er": "ever", "ne'er": "never", "e'en": "even",
}
# Second-person verbs, rewritten only next to thou ("thou art", "art thou"):
# alone, "art" and "wilt" are ordinary modern words.
THOU_VERBS = {
    "art": "are", "wast": "were", "wert": "were", "hast": "have", "hadst": "had",
    "dost": "do", "didst": "did", "canst": "can", "couldst": "could",
    "wouldst": "would", "shouldst": "should", "shalt": "shall", "wilt": "will",
    "mayst": "may", "mayest": "may", "mightst": "might", "must": "must",
}
_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*|'[A-Za-z]+")
_ARCHAIC_HINT = re.compile(
    r"\b(?:thou|thee|thy|thine|thyself|ye|hath|doth|saith|nay|aye|whilst|amongst|unto|"
    r"ere|oft|hither|thither|whence|wherefore)\b|'t(?:is|was|will)\b|\w'er\b|\w+eth\b",
    re.I)
# "Thou, queen, art the fairest": a short vocative between thou and its verb.
_THOU_VOCATIVE = re.compile(r"\bthou\s*,[^,.;:!?]{1,30},\s*$", re.I)


@cache
def _zipf(word: str) -> float:
    from wordfreq import zipf_frequency
    return zipf_frequency(word, "en")


def _modern_stem(word: str, ending: str) -> str | None:
    """The modern verb under an archaic ending: comest -> come, sitteth -> sit."""
    base = word[: -len(ending)]
    for cand in (base + "e", base, base[:-1] if len(base) > 2 and base[-1] == base[-2] else ""):
        if len(cand) >= 2 and _zipf(cand) >= 3.0:
            return cand
    return None


def _third_person(verb: str) -> str:
    if verb == "have":
        return "has"
    if verb.endswith(("s", "sh", "ch", "x", "z", "o")):
        return verb + "es"
    if len(verb) > 2 and verb.endswith("y") and verb[-2] not in "aeiou":
        return verb[:-1] + "ies"
    return verb + "s"


def _modern_word(low: str, prev: str, nxt: str) -> str | None:
    if low in ARCHAIC_WORDS:
        return ARCHAIC_WORDS[low]
    if low == "thine":                       # thine eyes -> your eyes; is thine -> yours
        return "your" if nxt else "yours"
    beside_thou = "thou" in (prev, nxt)
    if beside_thou and low in THOU_VERBS:
        return THOU_VERBS[low]
    if beside_thou and low.endswith("'st"):  # say'st -> say
        return low[:-3]
    if beside_thou and low.endswith("est") and len(low) >= 5:   # knowest -> know
        return _modern_stem(low, "est")
    # goeth -> goes, unless the -eth word is modern (teeth, beneath) or an ordinal
    if low.endswith("eth") and len(low) >= 5 and not low.endswith("ieth") and _zipf(low) < 2.5:
        stem = _modern_stem(low, "eth")
        if stem and beside_thou:             # "Standeth thou" is second person
            return stem
        return _third_person(stem) if stem else None
    return None


def modernize_archaic(text: str) -> str:
    """Rewrite Early Modern English into modern: "Thou art" -> "You are"."""
    if not _ARCHAIC_HINT.search(text):       # the common case: modern text
        return text
    words = list(_WORD.finditer(text))
    lows = [m.group().lower() for m in words]
    out, last = [], 0
    for i, m in enumerate(words):
        prev = lows[i - 1] if i and text[words[i - 1].end():m.start()].isspace() else ""
        nxt = lows[i + 1] if i + 1 < len(words) and \
            text[m.end():words[i + 1].start()].isspace() else ""
        if not prev and _THOU_VOCATIVE.search(text[max(0, m.start() - 45):m.start()]):
            prev = "thou"
        new = _modern_word(lows[i], prev, nxt)
        if new is None:
            continue
        if m.group()[0].isupper() or m.group()[:2] == "'T":
            new = new[0].upper() + new[1:]
        out += [text[last:m.start()], new]
        last = m.end()
    return "".join(out) + text[last:]


def normalize_english(text: str) -> str:
    """Everything the translator does to English before parsing it."""
    return modernize_archaic(normalize_apostrophes(text))


# Irregular past participles used as adjectives.
IRREGULAR_PARTICIPLES = {
    "broken": "break", "lost": "lose", "hidden": "hide", "frozen": "freeze",
    "stuck": "stick", "fallen": "fall", "grown": "grow", "torn": "tear",
    "stolen": "steal", "forgotten": "forget", "beaten": "beat", "bitten": "bite",
    "shaken": "shake", "sunk": "sink", "spent": "spend", "built": "build",
    "burnt": "burn", "made": "make", "known": "know", "worn": "wear",
    "written": "write", "chosen": "choose", "woken": "wake", "hurt": "hurt",
    "tied": "tie", "dried": "dry",
}


def ly_base(lemma: str) -> list[str]:
    """Candidate adjective bases for an -ly adverb, most likely first."""
    if not lemma.endswith("ly") or len(lemma) < 5:
        return []
    stem = lemma[:-2]
    out = []
    if stem.endswith("i"):                              # happily -> happy
        out.append(stem[:-1] + "y")
    if lemma.endswith("ically"):                        # basically -> basic
        out.append(lemma[:-4])
    if lemma.endswith(("bly", "ply", "tly", "dly")):    # gently -> gentle
        out.append(lemma[:-1] + "e")
    if lemma.endswith("lly"):                           # fully -> full
        out.append(lemma[:-1])
    out.append(stem)                                    # quickly -> quick
    return out


def _dedouble(stem: str) -> list[str]:
    return [stem[:-1]] if len(stem) > 2 and stem[-1] == stem[-2] else []


def participle_verb(adj: str, verbs: Container[str]) -> tuple[str, str] | None:
    """If ``adj`` is a participle of a verb in ``verbs``, return (verb, tag)
    with tag PST (-ed/-en) or PROG (-ing); else None."""
    if adj in IRREGULAR_PARTICIPLES and IRREGULAR_PARTICIPLES[adj] in verbs:
        return IRREGULAR_PARTICIPLES[adj], "PST"
    cands: list[tuple[str, str]] = []
    if adj.endswith("ied") and len(adj) > 4:
        cands.append((adj[:-3] + "y", "PST"))                         # worried
    if adj.endswith("ed") and len(adj) > 4:
        stem = adj[:-2]
        cands += [(stem, "PST"), (stem + "e", "PST"), (adj[:-1], "PST")]
        cands += [(s, "PST") for s in _dedouble(stem)]                # stopped
    if adj.endswith("ing") and len(adj) > 5:
        stem = adj[:-3]
        cands += [(stem, "PROG"), (stem + "e", "PROG")]
        cands += [(s, "PROG") for s in _dedouble(stem)]               # running
    for verb, tag in cands:
        if verb in verbs:
            return verb, tag
    return None
