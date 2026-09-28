import pytest

from klazan.lexicon import load_content, paradigm, validate


def _lex(tmp_path, body: str):
    """body: one YAML flow-mapping entry per line, any indentation."""
    lines = [l.strip() for l in body.strip().splitlines() if l.strip()]
    (tmp_path / "core.yaml").write_text(
        "entries:\n" + "".join(f"  {l}\n" for l in lines), encoding="utf-8")
    return load_content(("core.yaml",), tmp_path)


def _errors(tmp_path, body: str) -> list[str]:
    return validate(_lex(tmp_path, body)).errors


def test_real_lexicon_is_valid():
    rep = validate()
    assert rep.ok, rep.errors


def test_clean_entries_pass(tmp_path):
    assert _errors(tmp_path, """
        - {kz: drash, en: [forge/VERB], origin: invented}
        - {kz: drashki, en: [smith/NOUN], origin: derived, base: drash+AGT}
        - {kz: dawi, en: [dwarf/NOUN], origin: borrowed, from: "Khazalid dawi"}
        - {kz: glok, en: [drink/VERB, drink/NOUN], origin: invented}
    """) == []


def test_paradigm_by_pos(tmp_path):
    e = _lex(tmp_path, "- {kz: glok, en: [drink/VERB, drink/NOUN], origin: invented}")[0]
    assert paradigm(e) == {"gloki": ("PL",), "glokad": ("PST",), "gloken": ("PROG",)}


@pytest.mark.parametrize("body, needle", [
    ("- {kz: ta, en: [tea/NOUN], origin: invented}", "spelling already used"),
    ("""- {kz: glok, en: [drink/VERB], origin: invented}
        - {kz: brog, en: [drink/VERB], origin: invented}""", "mapped to both"),
    ("- {kz: dawi, en: [dwarf/NOUN], origin: invented}", "illegal root"),
    ("- {kz: dawi, en: [dwarf/NOUN], origin: borrowed}", "needs a 'from'"),
    ("- {kz: drashki, en: [smith/NOUN], origin: derived, base: nope+AGT}", "not in the lexicon"),
    ("""- {kz: drash, en: [forge/VERB], origin: invented}
        - {kz: drashak, en: [smith/NOUN], origin: derived, base: drash+AGT}""", "gives"),
    ("- {kz: sald, en: [give/VERB], origin: invented}", "one letter apart"),   # vs 'sal'
    ("""- {kz: brak, en: [rock/NOUN], origin: invented}
        - {kz: braki, en: [bread/NOUN], origin: invented}""", "already a lexicon word"),
    ("- {kz: mur, en: [wall/NOUN], origin: invented}", "spelling already used"),
])
def test_errors(tmp_path, body, needle):
    errs = _errors(tmp_path, body)
    assert any(needle in e for e in errs), errs


def test_bad_sense_format(tmp_path):
    with pytest.raises(ValueError):
        _lex(tmp_path, "- {kz: glok, en: [drink], origin: invented}")


def test_yaml_booleans_rejected(tmp_path):
    with pytest.raises(ValueError):
        _lex(tmp_path, "- {kz: glok, en: [no], origin: invented}")


def test_english_inflected_form_is_a_warning(tmp_path):
    rep = validate(_lex(tmp_path, "- {kz: tax, en: [tax/NOUN], origin: borrowed, from: test}"))
    assert rep.ok, rep.errors
    assert any("'taxi'" in w for w in rep.warnings)
