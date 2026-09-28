"""Every ```kz example in spec/grammar.md must be consistent with the code.

Each example is two or three lines: Klazan, interlinear gloss, optional English.
Checks: one gloss per word; every word is a function word, a placeholder
vocabulary word (samples/vocab_v0.yaml), a name or a digit; and every
``lemma-TAG`` gloss equals ``morphology.inflect(lemma's form, TAG...)``.
"""

import re
from pathlib import Path

import pytest
import yaml

from klazan.lexicon import function_words
from klazan.morphology import SUFFIXES, inflect

ROOT = Path(__file__).resolve().parents[1]
GRAMMAR = (ROOT / "spec" / "grammar.md").read_text(encoding="utf-8")
VOCAB: dict[str, str] = yaml.safe_load(
    (ROOT / "samples" / "vocab_v0.yaml").read_text(encoding="utf-8"))["words"]

FUNCTION = {w.kz for w in function_words()}
LEMMAS = dict(VOCAB)                             # English gloss lemma -> Klazan form
for w in function_words():
    for e in w.en:
        if " " not in e:
            LEMMAS.setdefault(e, w.kz)
LEMMAS |= {"Q": "wan", "FUT": "an", "COND": "sar", "NEG": "nai", "REL": "zo"}
KNOWN = FUNCTION | set(VOCAB.values())
PUNCT = ".,!?;:\"“”()"


def _examples() -> list:
    out = []
    for block in re.findall(r"```kz\n(.*?)```", GRAMMAR, re.S):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        out.append(pytest.param(lines[0], lines[1], id=lines[0][:40]))
    return out


def _tokens(line: str) -> list[str]:
    return [t.strip(PUNCT) for t in line.split() if t.strip(PUNCT)]


def test_there_are_examples():
    assert len(list(_examples())) >= 30


@pytest.mark.parametrize("kz, gloss", _examples())
def test_example(kz, gloss):
    kz_toks, gl_toks = _tokens(kz), _tokens(gloss)
    assert len(kz_toks) == len(gl_toks), f"{len(kz_toks)} words vs {len(gl_toks)} glosses"
    for tok, gl in zip(kz_toks, gl_toks):
        if tok.isdigit() or (tok[0].isupper() and tok == gl):          # digit or name
            continue
        word = tok.lower()
        parts = gl.split("-")
        tags = parts[1:]
        if tags and all(t in SUFFIXES for t in tags):
            assert parts[0] in LEMMAS, f"gloss lemma {parts[0]!r} unknown"
            expected = inflect(LEMMAS[parts[0]], *tags)
            assert word == expected, f"{gl}: expected {expected!r}, got {word!r}"
        elif tags:                                                   # compound: two-ten
            assert [LEMMAS.get(p) for p in parts] == word.split("-"), f"{gl} vs {word}"
        else:
            assert word in KNOWN, f"unknown word {word!r} (gloss {gl!r})"
