"""Golden tests: every ```kz example in spec/grammar.md that has an English line
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

from klazan.lexicon import function_words, load_content  # noqa: E402
from klazan.morphology import SUFFIXES, inflect  # noqa: E402
from klazan.translate import Translator  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GRAMMAR = (ROOT / "spec" / "grammar.md").read_text(encoding="utf-8")
PUNCT = ".,!?;:\"“”()"

BY_POS: dict[str, dict[str, str]] = {}
for e in load_content():
    for lemma, pos in e.senses:
        BY_POS.setdefault(lemma, {}).setdefault(pos, e.kz)
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
            LEMMAS.setdefault(en, w.kz)
LEMMAS |= {"Q": "wan", "FUT": "an", "COND": "sar", "NEG": "nai", "REL": "zo"}

# Examples whose English is deliberately ambiguous or needs context the
# translator can't have; each entry says why.
KNOWN_GAPS: dict[str, str] = {
    "The beardling drank ale.": "en_core_web_sm tags the rare word 'beardling' as a verb "
                                "and 'drank' as an adjective (parser limit, not a rule gap)",
}


def _expected(kz: str, gloss: str) -> str | None:
    """Rewrite the spec's Klazan line into the current lexicon via its gloss."""
    kz_toks, gl_toks = kz.split(), gloss.split()
    out = []
    for tok, gl in zip(kz_toks, gl_toks):
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
        elif (lw := lemma_word(glc, [])) and core.lower() not in {w.kz for w in function_words()}:
            word = lw
        else:
            word = core.lower()
        if core[:1].isupper():
            word = word[:1].upper() + word[1:]
        out.append(pre + word + post)
    return " ".join(out)


def _cases():
    cases = []
    for block in re.findall(r"```kz\n(.*?)```", GRAMMAR, re.S):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        english = re.sub(r"\s*\([^)]*\)", "", lines[2].strip('"“”'))
        cases.append(pytest.param(english, lines[0], lines[1], id=english[:40]))
    return cases


@pytest.fixture(scope="module")
def translator():
    return Translator()


@pytest.mark.parametrize("english, kz, gloss", _cases())
def test_grammar_example(translator, english, kz, gloss):
    if english in KNOWN_GAPS:
        pytest.xfail(KNOWN_GAPS[english])
    expected = _expected(kz, gloss)
    if expected is None:
        pytest.skip("uses a placeholder word that is not in the lexicon yet")
    assert translator.translate(english) == expected


# Curly apostrophes (common in Gutenberg and Cosmopedia text) must parse like
# straight ones: spaCy alone drops the negation in "wasn’t" and the tense in
# "they’ve gone".
@pytest.mark.parametrize("straight", [
    "I don't know. It's late, we're tired.",
    "She wasn't there and they've gone.",
    "The dwarf's axe isn't sharp.",
])
def test_curly_apostrophes_translate_like_straight(translator, straight):
    curly = straight.replace("'", "’")
    assert translator.translate(curly) == translator.translate(straight)


def test_curly_quotation_marks_are_kept():
    from klazan.english import normalize_apostrophes
    assert normalize_apostrophes("‘Halt!’ he said, and didn’t move.") == \
        "‘Halt!’ he said, and didn't move."


# Early Modern English is rewritten before parsing (english.normalize_english).
@pytest.mark.parametrize("archaic, modern", [
    ("Thou art a fool, and thy beard is thine own.", "You are a fool, and your beard is your own."),
    ("Where art thou going? Wilt thou come?", "Where are you going? Will you come?"),
    ("He goeth to the hall and knoweth the way.", "He goes to the hall and knows the way."),
    ("Thou knowest, thou sittest, what say'st thou?", "You know, you sit, what say you?"),
    ("’Tis late; ere long they came hither.", "It is late; before long they came here."),
    ("Standeth thou here? The kingdom is thine.", "Stand you here? The kingdom is yours."),
    ("Thou, queen, art the fairest of them all.", "You, queen, are the fairest of them all."),
])
def test_archaic_english_is_modernized(archaic, modern):
    from klazan.english import normalize_english
    assert normalize_english(archaic) == modern


@pytest.mark.parametrize("text", [
    "The flowers wilt in art class.",
    "His teeth, beneath the death mask, on the fiftieth day.",
    "The eldest son rested in the forest; I must go.",
])
def test_modern_words_that_look_archaic_are_kept(text):
    from klazan.english import normalize_english
    assert normalize_english(text) == text


def test_archaic_translates_like_modern(translator):
    assert translator.translate("Thou art the king, and thou hast my axe.") == \
        translator.translate("You are the king, and you have my axe.")
