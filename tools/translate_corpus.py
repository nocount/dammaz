"""Translate an English story corpus into Dammaz, as parallel JSONL.

    uv run --group nlp python tools/translate_corpus.py data/raw/TinyStoriesV2-GPT4-valid.txt \\
        --limit 300 --out data/dz/tinystories_sample.jsonl

Each output line: {"id", "source", "en", "dz", "lexicon_version", "words",
"loans", "loan_rate", "unknown"}. A summary (loan rate, most frequent loans =
the lexicon's to-do list, any unknown tokens = translator gaps, throughput) is
printed at the end. Phase 5 builds the training shards on top of this.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from coverage import iter_stories  # noqa: E402

from dammaz import __version__  # noqa: E402
from dammaz.translate import Stats, Translator  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--processes", type=int, default=1)
    ap.add_argument("--source", default="tinystories")
    args = ap.parse_args()

    stories = list(iter_stories(args.corpus, args.limit))
    tr = Translator()
    total = Stats()
    t0 = time.time()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for i, (en, (dz, st)) in enumerate(zip(stories, tr.translate_many(
                stories, n_process=args.processes))):
            total.add(st)
            f.write(json.dumps({
                "id": f"{args.source}-{i}", "source": args.source, "en": en, "dz": dz,
                "lexicon_version": __version__, "words": st.tokens, "loans": st.loans,
                "loan_rate": round(st.loan_rate, 4), "unknown": st.unknown,
            }, ensure_ascii=False) + "\n")
    dt = time.time() - t0
    en_words = sum(len(s.split()) for s in stories)
    print(f"{len(stories)} stories, {en_words:,} English words in {dt:.1f}s "
          f"({en_words / dt:,.0f} words/s)")
    print(f"Dammaz words: {total.tokens:,}; loans {total.loans:,} ({total.loan_rate:.2%}); "
          f"names {total.names:,}; unknown {total.unknown:,}")
    print("top loans:", ", ".join(f"{w} {n}" for w, n in total.loan_words.most_common(40)))
    if total.unknown:
        print("unknown:", ", ".join(f"{w} {n}" for w, n in total.unknown_words.most_common(30)))
    rates = Counter(round(min(json.loads(l)["loan_rate"], 0.2), 2)
                    for l in args.out.open(encoding="utf-8"))
    print("stories by loan rate:", dict(sorted(rates.items())))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
