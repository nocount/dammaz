"""Merge coverage worklists from several corpora into one review target.

    uv run python tools/merge_targets.py cand_cosmo_kids cand_gutenberg_tales \
        --name cosmo_tales --goal 0.95

Each input is lexicon/targets/<name>_lemmas.tsv as written by tools/coverage.py.
Corpora are weighted equally: a sense's rate is the mean of its per-million
rates, so a larger sample does not outvote a smaller one. The output has the
same columns, so `tools/review.py propose --target <name>` reads it unchanged.

With --goal, it also prints how many new senses (taken in merged order) bring
*every* input corpus to that share of word tokens: the --n for propose.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from klazan.lexicon import LEXICON_DIR, load_content  # noqa: E402

TARGETS = LEXICON_DIR / "targets"
Sense = tuple[str, str]


def load(name: str) -> list[dict]:
    path = TARGETS / f"{name}_lemmas.tsv"
    return list(csv.DictReader(path.open(encoding="utf-8"), delimiter="\t"))


def free_share(rows: list[dict]) -> float:
    """Share of tokens needing no content entry (function words, names...)."""
    return float(rows[0]["cum_coverage"]) - float(rows[0]["per_million"]) / 1e6


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("inputs", nargs="+", help="target names, e.g. cand_cosmo_kids")
    ap.add_argument("--name", required=True, help="output target name")
    ap.add_argument("--goal", type=float, help="report the --n that reaches this coverage")
    args = ap.parse_args()

    tables = [{(r["lemma"], r["pos"]): r for r in load(n)} for n in args.inputs]
    frees = [free_share(load(n)) for n in args.inputs]
    rate = lambda t, s: float(t[s]["per_million"]) if s in t else 0.0
    mean = lambda s: sum(rate(t, s) for t in tables) / len(tables)

    senses = sorted(set().union(*tables), key=lambda s: (-mean(s), s))
    cum = sum(frees) / len(frees)
    out = TARGETS / f"{args.name}_lemmas.tsv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["rank", "lemma", "pos", "count", "per_million", "cum_coverage", "example"])
        for i, s in enumerate(senses, 1):
            cum += mean(s) / 1e6
            count = sum(int(t[s]["count"]) for t in tables if s in t)
            example = max((t for t in tables if s in t), key=lambda t: rate(t, s))[s]["example"]
            w.writerow([i, s[0], s[1], count, f"{mean(s):.1f}", f"{cum:.4f}", example])
    print(f"wrote {out.relative_to(ROOT)}: {len(senses):,} senses from {len(tables)} corpora")

    if args.goal:
        covered: set[Sense] = {s for e in load_content() for s in e.senses}
        corr = yaml.safe_load((TARGETS / "corrections.yaml").read_text(encoding="utf-8"))
        covered |= {tuple(k.rsplit("/", 1)) for k in corr.get("function") or []}
        cov = [fr + sum(rate(t, s) for s in covered if s in t) / 1e6
               for t, fr in zip(tables, frees)]
        start = ", ".join(f"{n} {c:.2%}" for n, c in zip(args.inputs, cov))
        n = 0
        for s in senses:
            if min(cov) >= args.goal:
                break
            if s in covered:
                continue
            n += 1
            cov = [c + rate(t, s) / 1e6 for c, t in zip(cov, tables)]
        end = ", ".join(f"{n_} {c:.2%}" for n_, c in zip(args.inputs, cov))
        print(f"now: {start}\n--n {n} reaches {args.goal:.0%} on all: {end}")


if __name__ == "__main__":
    main()
