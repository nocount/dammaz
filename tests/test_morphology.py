import pytest

from dammaz.morphology import inflect


@pytest.mark.parametrize("root, tags, form", [
    # plural
    ("az", ("PL",), "azi"),
    ("dawi", ("PL",), "dawin"),
    ("skreka", ("PL",), "skrekan"),
    # tense / aspect
    ("truk", ("PST",), "trukad"),
    ("truk", ("PROG",), "truken"),
    ("zu", ("PST",), "zad"),                    # elision
    # derivation
    ("drash", ("AGT",), "drashki"),
    ("drash", ("PLACE",), "drashaz"),
    ("drash", ("CRAFT",), "drashul"),
    ("krang", ("ADV",), "krangul"),
    ("krang", ("THING",), "krangak"),
    ("iza", ("VBZ",), "izash"),                 # elision
    ("iza", ("AGT",), "izaki"),                 # consonant suffix after vowel: no change
    ("grund", ("AGT",), "grundaki"),            # epenthesis: n.d.k is illegal
    ("kurm", ("LIKE",), "kurmarak"),            # epenthesis: r.m.r is illegal
    ("zuk", ("AGT",), "zukki"),                 # geminate across boundary is fine
    ("or", ("POSS",), "ora"),
    # degree
    ("gorz", ("CMP",), "gorzar"),
    ("tuf", ("ORD",), "tufik"),
    ("thra", ("ORD",), "thrik"),
    # stacking
    ("drash", ("AGT", "PL"), "drashkin"),
    ("dammaz", ("VBZ", "PST"), "dammazashad"),
    ("iza", ("VBZ", "AGT", "PL"), "izashkin"),
])
def test_inflect(root, tags, form):
    assert inflect(root, *tags) == form


@pytest.mark.parametrize("tags", [
    ("PL", "PST"),          # two inflections
    ("PL", "AGT"),          # derivation after inflection
    ("CMP", "ORD"),         # two degree suffixes
    ("CMP", "AGT"),         # derivation after degree
    ("NOPE",),
])
def test_bad_suffix_orders(tags):
    with pytest.raises(ValueError):
        inflect("krang", *tags)


@pytest.mark.parametrize("root, tags, form", [
    ("dawi", ("DIM",), "dawit"),               # elision
    ("zaka", ("DIM",), "zakit"),
    ("grund", ("DIM",), "grundit"),
    ("dawi", ("DIM", "PL"), "dawiti"),         # plural after the diminutive
])
def test_diminutive(root, tags, form):
    assert inflect(root, *tags) == form


def test_roots_cannot_end_in_diminutive():
    from dammaz.phonology import check_root
    assert any("reserved suffix '-it'" in p for p in check_root("zakit"))
