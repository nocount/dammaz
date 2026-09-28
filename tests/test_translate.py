"""Golden tests: every ```dz example in spec/grammar.md that has an English line
must be produced by the translator from that English.

The spec's examples use the placeholder vocabulary (samples/vocab_v0.yaml);
the expected output is rebuilt in the *current* lexicon from the gloss line
(``forge-PST`` -> current word for forge + PST), so the test tracks lexicon
changes but still pins down the grammar.
"""

import re
from pathlib import Path

import pytest

spacy = pytest.importorskip("spacy")

from dammaz.lexicon import function_words, load_content  # noqa: E402
from dammaz.morphology import SUFFIXES, inflect  # noqa: E402
from dammaz.translate import Translator  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GRAMMAR = (ROOT / "spec" / "grammar.md").read_text(encoding="utf-8")
PUNCT = ".,!?;:\"“”()"

BY_POS: dict[str, dict[str, str]] = {}
for e in load_content():
    for lemma, pos in e.senses:
        BY_POS.setdefault(lemma, {}).setdefault(pos, e.dz)
# which part of speech a gloss tag implies (forge-PST is the verb, not the smithy)
TAG_POS = {"PST": "VERB", "PROG": "VERB", "AGT": "VERB", "PLACE": "VERB", "CRAFT": "VERB",
           "PL": "NOUN", "DIM": "NOUN", "VBZ": "NOUN", "LIKE": "NOUN",
           "CMP": "ADJ", "ADV": "ADJ", "THING": "ADJ"}
PREF = ("NOUN", "VERB", "ADJ", "ADV", "INTJ")


def lemma_word(lemma: str, tags: list[str]) -> str | None:
    if lemma in BY_POS:
        want = [TAG_POS[t] for t in tags if t in TAG_POS][:1]
        for pos in want + list(PREF):
            if pos in BY_POS[lemma]:
                return BY_POS[lemma][pos]
    return LEMMAS.get(lemma)


LEMMAS: dict[str, str] = {}
for w in function_words():
    for en in w.en:
        if " " not in en:
            LEMMAS.setdefault(en, w.dz)
LEMMAS |= {"Q": "wan", "FUT": "an", "COND": "sar", "NEG": "nai", "REL": "zo"}

# Examples whose English is deliberately ambiguous or needs context the
# translator can't have; each entry says why.
KNOWN_GAPS: dict[str, str] = {
    "The beardling drank ale.": "en_core_web_sm tags the rare word 'beardling' as a verb "
                                "and 'drank' as an adjective (parser limit, not a rule gap)",
}


def _expected(dz: str, gloss: str) -> str | None:
    """Rewrite the spec's Dammaz line into the current lexicon via its gloss."""
    dz_toks, gl_toks = dz.split(), gloss.split()
    out = []
    for tok, gl in zip(dz_toks, gl_toks):
        core = tok.strip(PUNCT)
        pre, post = tok[:len(tok) - len(tok.lstrip(PUNCT))], tok[len(tok.rstrip(PUNCT)):]
        glc = gl.strip(PUNCT)
        parts = glc.split("-")
        if core[:1].isupper() and core == glc:               # a name
            word = core
        elif len(parts) > 1 and all(p in SUFFIXES for p in parts[1:]):
            root = lemma_word(parts[0], parts[1:])
            if root is None:
                return None
            word = inflect(root, *parts[1:])
        elif len(parts) > 1:                                  # two-ten compound numeral
            word = "-".join(LEMMAS[p] for p in parts)
        elif (lw := lemma_word(glc, [])) and core.lower() not in {w.dz for w in function_words()}:
            word = lw
        else:
            word = core.lower()
        if core[:1].isupper():
            word = word[:1].upper() + word[1:]
        out.append(pre + word + post)
    return " ".join(out)


def _cases():
    cases = []
    for block in re.findall(r"```dz\n(.*?)```", GRAMMAR, re.S):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        english = re.sub(r"\s*\([^)]*\)", "", lines[2].strip('"“”'))
        cases.append(pytest.param(english, lines[0], lines[1], id=english[:40]))
    return cases


@pytest.fixture(scope="module")
def translator():
    return Translator()


@pytest.mark.parametrize("english, dz, gloss", _cases())
def test_grammar_example(translator, english, dz, gloss):
    if english in KNOWN_GAPS:
        pytest.xfail(KNOWN_GAPS[english])
    expected = _expected(dz, gloss)
    if expected is None:
        pytest.skip("uses a placeholder word that is not in the lexicon yet")
    assert translator.translate(english) == expected
