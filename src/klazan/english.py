"""English-side normalization shared by tools/coverage.py and the translator.

Klazan expresses some English word classes through other words, so they need
no lexicon entry of their own:

* adverbs      quickly -> quick/ADJ + ADV (-ul);  run fast -> fast/ADJ + ADV
* participles  scared -> scare/VERB + PST;  amazing -> amaze/VERB + PROG
               (grammar.md §6.5: participles are the verb's PST/PROG form)
"""

from __future__ import annotations

from collections.abc import Container

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
