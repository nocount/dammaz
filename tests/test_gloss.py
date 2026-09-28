import pytest

from klazan.gloss import Glosser
from klazan.lexicon import load_content, paradigm
from klazan.validate import validate_text


@pytest.fixture(scope="module")
def g():
    return Glosser()


@pytest.mark.parametrize("word, gloss", [
    ("zad", "be-PST"),
    ("uzara", "your.FML"),
    ("dawit", "beardling"),          # lexicalized dwarf+DIM wins over re-deriving it
    ("dawiti", "beardling-PL"),
    ("ora", "my"),
    ("woraz", "where"),
    ("tuf-zer", "two-ten"),
])
def test_gloss_words(g, word, gloss):
    assert g.gloss_word(word) == gloss


def test_lexicalized_derivation_beats_rederiving(g):
    smith = next(e for e in load_content() if ("smith", "NOUN") in e.senses)
    assert g.gloss_word(smith.kz + ("n" if smith.kz[-1] in "aeiou" else "i")) == "smith-PL"


def test_every_paradigm_form_analyzes_back(g):
    """Round trip: each inflected form of each lexicon word decomposes to it."""
    bad = []
    for e in load_content():
        for form, tags in paradigm(e).items():
            if (e.kz, tags) not in g.analyses(form):
                bad.append((e.kz, tags, form))
    assert not bad, bad[:10]


def test_names_loans_numbers(g):
    assert g.analyze("Lily").kind == "name"
    assert g.analyze("bananuzi").kind == "loan"
    assert g.analyze("42").kind == "number"
    assert g.analyze("blueberry").kind == "unknown"


def test_validate_text():
    rep = validate_text("Ta dawi dhal drashad un az krang bin ta karak.")
    assert rep.ok and rep.counts["word"] == 10
    assert not validate_text("The dwarf is here.").ok


def test_translator_output_validates():
    spacy = pytest.importorskip("spacy")  # noqa: F841
    from klazan.translate import Translator
    t = Translator()
    text = ('Once upon a time, there was a little girl named Lily. She loved her puppy. '
            '"Can we play in the park?" she asked. "Yes, we can," said Dad.')
    rep = validate_text(t.translate(text))
    assert rep.ok, rep.unknown
