import csv
import importlib.util
from pathlib import Path

from klazan.lexicon import CONTENT_FILES, load_content

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("review", ROOT / "tools" / "review.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)

FIELDS = ["rank", "english", "pos", "count", "example", "proposed", "origin",
          "from_or_base", "alt1", "alt2", "alt3", "decision", "note"]


def test_apply_writes_every_tier_it_changes(tmp_path, monkeypatch):
    """A sense that shares a word living in core must be saved to core.yaml,
    even when the batch is applied --into extended (batch 3 lost 119 this way)."""
    (tmp_path / "core.yaml").write_text(
        "entries:\n  - {kz: klal, en: [\"like/VERB\"], origin: invented}\n", encoding="utf-8")
    monkeypatch.setattr(review, "LEXICON_DIR", tmp_path)
    monkeypatch.setattr(review, "load_content", lambda: load_content(CONTENT_FILES, tmp_path))
    batch = tmp_path / "batch.csv"
    with batch.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, FIELDS, restval="")
        w.writeheader()
        w.writerow({"english": "like", "pos": "ADJ", "proposed": "klal",
                    "origin": "shared", "from_or_base": "@like/VERB"})
        w.writerow({"english": "anvil", "pos": "NOUN", "proposed": "drunkaz",
                    "origin": "invented"})

    review.apply(batch, into="extended")

    got = {e.kz: (e.tier, e.senses) for e in load_content(CONTENT_FILES, tmp_path)}
    assert got["klal"] == ("core", (("like", "VERB"), ("like", "ADJ")))
    assert got["drunkaz"] == ("extended", (("anvil", "NOUN"),))
