import pytest

from klazan.phonology import check_root, segment, shape


@pytest.mark.parametrize("word, segs", [
    ("khazukan", ["kh", "a", "z", "u", "k", "a", "n"]),
    ("thrund", ["th", "r", "u", "n", "d"]),
    ("grungi", ["g", "r", "u", "ng", "i"]),
    ("dammaz", ["d", "a", "m", "a", "z"]),             # geminate collapsed
    ("slotch", ["s", "l", "o", "ch"]),
    ("wazzock", ["w", "a", "z", "o", "k"]),
])
def test_segment(word, segs):
    assert segment(word) == segs


def test_segment_keeps_geminates_when_asked():
    assert segment("dammaz", collapse_geminates=False) == ["d", "a", "m", "m", "a", "z"]


def test_shape():
    s = shape("gromdal")
    assert (s.initial, s.nuclei, s.medials, s.final) == ("g.r", ("o", "a"), ("m.d",), "l")
    assert shape("uzkul").initial == ""
    assert shape("skreka").final == ""
    assert shape("bryn").nuclei == ("y",)                # y as vowel in source words


@pytest.mark.parametrize("word", [
    "karak", "grund", "thrund", "gromril", "zhorvash", "skreka", "dhrak",
    "unguz", "thaluk", "drekrazal",
])
def test_legal_roots(word):
    assert check_root(word) == []


@pytest.mark.parametrize("word, problem", [
    ("dammaz", "geminate"),
    ("dawi", "reserved suffix"),
    ("zad", "reserved suffix"),
    ("azept", "alphabet"),
    ("bryn", "'y' used as a vowel"),
    ("ngak", "illegal initial"),
    ("kaur", "vowel sequence"),
    ("ongrondror", "too many clustered consonants"),
    ("kahr", "forbidden sequence"),
])
def test_illegal_roots(word, problem):
    assert any(problem in p for p in check_root(word)), check_root(word)
