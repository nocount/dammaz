import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("corpus", ROOT / "tools" / "corpus.py")
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)


def rec(i, en, words=50, loans=0, unknown=0):
    return {"id": f"t-{i}", "en": en, "kz": f"kz {i}", "words": words, "loans": loans,
            "loan_rate": loans / words, "unknown": unknown}


def test_pack_filters_and_dedupes():
    records = [
        rec(0, "A story about a dog."),
        rec(1, "a  story about a DOG."),              # duplicate after normalization
        rec(2, "Too many loans.", loans=10),          # 20% loans
        rec(3, "Has an unknown token.", unknown=1),
        rec(4, "Short.", words=5),
        rec(5, "Another fine story."),
    ]
    kept = list(corpus.pack_records(records, max_loan_rate=0.05, min_words=20, val_frac=0.0))
    assert [r["id"] for _, r in kept] == ["t-0", "t-5"]
    assert corpus.pack_records.drops == {"duplicate": 1, "loan rate > 5%": 1,
                                         "unknown tokens": 1, "< 20 words": 1}


def test_val_split_is_deterministic_and_about_right():
    texts = [f"story number {i}" for i in range(20_000)]
    val = [t for t in texts if corpus._is_val(t, 0.05)]
    assert 0.04 < len(val) / len(texts) < 0.06
    assert val == [t for t in texts if corpus._is_val(t, 0.05)]
    assert corpus._is_val("Story Number 7", 0.05) == corpus._is_val("story number 7", 0.05)


def test_iter_stories(tmp_path):
    f = tmp_path / "s.txt"
    f.write_text("One.\nTwo lines.\n<|endoftext|>\n\n<|endoftext|>\nThree.\n", encoding="utf-8")
    assert list(corpus.iter_stories(f)) == ["One.\nTwo lines.", "Three."]


def test_fingerprint_ignores_line_endings(tmp_path):
    from klazan.lexicon import _hash_files
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_bytes(b"x: 1\ny: 2\n")
    b.write_bytes(b"x: 1\r\ny: 2\r\n")
    assert _hash_files([a], ["f"]) == _hash_files([b], ["f"])
