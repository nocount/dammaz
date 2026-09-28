import pytest

from klazan.phonology import check_root
from klazan.wordgen import NearIndex, WordGen


@pytest.fixture(scope="module")
def gen():
    return WordGen(seed=7)


def test_samples_are_legal(gen):
    for _ in range(300):
        assert check_root(gen.sample()) == []


def test_candidates_pass_filters_and_are_distinct(gen):
    cands = gen.candidates(40, min_dwarvishness=30)
    assert len(cands) == 40
    words = [c.word for c in cands]
    idx = NearIndex()
    for c in cands:
        assert gen.reject_reason(c.word) is None
        assert c.dwarvishness >= 30
        assert not idx.near(c.word), f"{c.word} too close to another candidate"
        idx.add(c.word)
    assert len(set(words)) == len(words)


def test_syllable_request(gen):
    assert {c.syllables for c in gen.candidates(15, syllables=2)} == {2}


def test_deterministic_with_seed():
    a = [c.word for c in WordGen(seed=99).candidates(10)]
    b = [c.word for c in WordGen(seed=99).candidates(10)]
    assert a == b


def test_existing_words_block_near_duplicates():
    g = WordGen(seed=1, existing={"skreka"})
    assert g.reject_reason("skreka") is not None
    assert g.reject_reason("skrekan") is not None      # one insertion away


def test_dwarvish_beats_english_like(gen):
    assert gen.score("thrund").score > gen.score("wivel").score


def test_near_index():
    idx = NearIndex(["karak"])
    assert idx.near("karag") == {"karak"}               # substitution
    assert idx.near("kara") == {"karak"}                # deletion
    assert idx.near("karakz") == {"karak"}              # insertion
    assert idx.near("zorn") == set()
