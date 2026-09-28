from collections import Counter

from klazan.lexicon import function_words
from klazan.morphology import inflect
from klazan.phonology import check_root

WORDS = function_words()
BY_CAT: dict[str, list] = {}
for w in WORDS:
    BY_CAT.setdefault(w.cat, []).append(w)


def test_forms_are_unique():
    dupes = [kz for kz, n in Counter(w.kz for w in WORDS).items() if n > 1]
    assert not dupes


def test_invented_forms_are_legal_roots():
    bad = {w.kz: check_root(w.kz) for w in WORDS if w.origin == "invented" and check_root(w.kz)}
    assert not bad


def test_borrowed_words_name_their_source():
    assert all(w.source for w in WORDS if w.origin == "borrowed")


def test_no_duplicate_english_within_a_category():
    for cat, ws in BY_CAT.items():
        seen = Counter(e for w in ws for e in w.en)
        assert not [e for e, n in seen.items() if n > 1], cat


def test_possessives_are_pronoun_plus_poss():
    pronouns = [w.kz for w in BY_CAT["pronoun"] if w.kz != "keb"]
    assert sorted(inflect(p, "POSS") for p in pronouns) == sorted(w.kz for w in BY_CAT["possessive"])


def test_correlative_table_is_complete_and_regular():
    bases = [w.kz for w in BY_CAT["determiner"]]
    table = {inflect(b, t) for b in bases for t in ("THING", "AGT", "PLACE", "TIME", "ADV")}
    table |= {inflect("wor", "REASON"), inflect("zuk", "REASON")}
    assert table == {w.kz for w in BY_CAT["correlative"]}


def test_formal_you_is_greater_you():
    assert inflect("uz", "CMP") == "uzar"
    assert inflect("uzar", "POSS") == "uzara"
    assert {"uzar", "uzara"} <= {w.kz for w in WORDS}
