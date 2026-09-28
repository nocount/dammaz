"""Lemma frequency + lexicon coverage over an English corpus.

Every word token is put in one bucket:

    number    NUM / digits: handled by numerals (grammar.md §9)
    name      PROPN: passes through unchanged
    function  covered by lexicon/function.yaml (category-compatible POS)
    absorbed  English grammar that Klazan expresses without a word of its own
              (do-support, perfect 'have', 'will' -> an, 'to' before verbs...)
    content   needs a lexicon entry; keyed by (lemma, POS)
    fgap      a closed-class word (ADP, PART, ...) NOT covered by function.yaml

'-ly' adverbs are folded into their adjective (quickly -> quick/ADJ), because
Klazan derives them with -ul. Punctuation, whitespace and symbols are ignored.

Writes (default names for TinyStories):
    lexicon/targets/<name>_lemmas.tsv   content worklist, ranked, with coverage
    reports/coverage_<name>.md          summary + coverage curve + gaps

    uv run --group nlp python tools/coverage.py data/raw/TinyStoriesV2-GPT4-valid.txt \
        --name tinystories
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from klazan.english import ly_base, participle_verb  # noqa: E402
from klazan.lexicon import function_words  # noqa: E402

CORRECTIONS = ROOT / "lexicon" / "targets" / "corrections.yaml"

CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV", "INTJ"}
IGNORE_POS = {"PUNCT", "SPACE", "SYM", "X"}

# function.yaml category -> spaCy POS tags it may cover
CAT_POS = {
    "article": {"DET", "NUM", "PRON"},
    "pronoun": {"PRON", "NOUN"},
    "possessive": {"PRON", "DET"},
    "determiner": {"DET", "PRON", "ADJ"},
    "correlative": {"ADV", "PRON", "SCONJ", "DET", "NOUN"},
    "quantifier": {"DET", "ADJ", "PRON", "ADV", "NOUN"},
    "numeral": {"NUM"},
    "preposition": {"ADP", "SCONJ", "ADV", "PART"},
    "conjunction": {"CCONJ", "SCONJ", "PRON", "DET", "ADP"},
    "particle": {"PART", "AUX", "ADV", "INTJ"},
    "interjection": {"INTJ", "ADV"},
    "verb": {"VERB", "AUX"},
}

# English grammar words Klazan absorbs into structure (grammar.md §6, §11).
ABSORBED = {
    ("be", "AUX"), ("have", "AUX"), ("do", "AUX"), ("will", "AUX"), ("would", "AUX"),
    ("shall", "AUX"), ("should", "AUX"), ("may", "AUX"), ("might", "AUX"),
    ("must", "AUX"), ("can", "AUX"), ("could", "AUX"), ("to", "PART"),
    ("not", "PART"), ("n't", "PART"), ("'s", "PART"), ("’s", "PART"), ("'", "PART"),
    ("there", "PRON"), ("let", "AUX"), ("be", "VERB"),
    ("ought", "AUX"), ("need", "AUX"), ("dare", "AUX"),
    ("’ll", "AUX"), ("’d", "AUX"), ("’ve", "AUX"), ("’m", "AUX"), ("’re", "AUX"),
    ("n’t", "PART"), ("n’t", "PRON"), ("’s", "PRON"), ("’s", "DET"),
    # reflexives = possessive + keb (grammar.md §4)
    *((r, "PRON") for r in ("myself", "yourself", "himself", "herself", "itself",
                           "ourselves", "yourselves", "themselves")),
}


def function_index() -> dict[str, set[str]]:
    """lowercased English word -> set of POS it may cover."""
    idx: dict[str, set[str]] = defaultdict(set)
    for w in function_words():
        for e in w.en:
            e = e.lower()
            if " " in e or "(" in e:                     # 'you all', 'by (agent)'
                e = e.split(" (")[0]
                if " " in e:
                    continue
            idx[e] |= CAT_POS[w.cat]
    return idx


def iter_stories(path: Path, limit: int | None):
    buf: list[str] = []
    n = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            if "<|endoftext|>" in line:
                if buf:
                    yield "".join(buf).strip()
                    n += 1
                    if limit and n >= limit:
                        return
                buf = []
            else:
                buf.append(line)
    if buf:
        yield "".join(buf).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--name", default="tinystories")
    ap.add_argument("--limit", type=int, default=None, help="max stories")
    ap.add_argument("--processes", type=int, default=1)
    args = ap.parse_args()

    import spacy
    nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
    fidx = function_index()

    buckets: Counter = Counter()
    content: Counter = Counter()
    fgaps: Counter = Counter()
    examples: dict[tuple[str, str], str] = {}
    n_stories = 0

    stories = iter_stories(args.corpus, args.limit)
    for doc in nlp.pipe(stories, batch_size=64, n_process=args.processes):
        n_stories += 1
        for sent in doc.sents if doc.has_annotation("SENT_START") else [doc]:
            for t in sent:
                pos = t.pos_
                if pos in IGNORE_POS or t.is_space or t.is_punct:
                    continue
                lemma = t.lemma_.lower()
                if pos == "NUM" or t.like_num:
                    buckets["number"] += 1
                elif pos == "PROPN":
                    buckets["name"] += 1
                elif (lemma, pos) in ABSORBED:
                    buckets["absorbed"] += 1
                elif pos in fidx.get(lemma, ()):
                    buckets["function"] += 1
                elif pos in CONTENT_POS:
                    buckets["content"] += 1
                    content[(lemma, pos)] += 1
                    if (lemma, pos) not in examples:
                        examples[(lemma, pos)] = sent.text.strip().replace("\n", " ")[:120]
                else:
                    buckets["fgap"] += 1
                    fgaps[(lemma, pos)] += 1
        if n_stories % 2000 == 0:
            print(f"  {n_stories} stories", file=sys.stderr)

    # spaCy corrections: aliases merge into their target; skipped items are
    # names or idiom fragments handled by the translator's phrase table.
    corr = yaml.safe_load(CORRECTIONS.read_text(encoding="utf-8"))
    for src, dst in (corr.get("alias") or {}).items():
        s, d = tuple(src.rsplit("/", 1)), tuple(dst.rsplit("/", 1))
        if s in content:
            content[d] += content.pop(s)
            examples.setdefault(d, examples.get(s, ""))
    for item in corr.get("function") or []:
        k = tuple(item.rsplit("/", 1))
        if k in content:
            n = content.pop(k)
            buckets["content"] -= n
            buckets["function"] += n
    for item in corr.get("skip") or []:
        k = tuple(item.rsplit("/", 1))
        if k in content:
            n = content.pop(k)
            buckets["content"] -= n
            buckets["absorbed"] += n

    # Fold adverbs into their adjective: -ly adverbs (quickly -> quick) and
    # flat adverbs with the same lemma (run fast -> fast/ADJ). Klazan derives
    # both with -ul, so they need no entry of their own.
    folded = 0
    for (lemma, pos), c in list(content.items()):
        if pos != "ADV":
            continue
        for base in [lemma] + ly_base(lemma):
            if (base, "ADJ") in content:
                content[(base, "ADJ")] += c
                del content[(lemma, pos)]
                folded += c
                break

    # Fold participle adjectives into their verb (scared -> scare/VERB,
    # amazing -> amaze/VERB): Klazan uses the verb's PST/PROG form (§6.5).
    verbs = {l for (l, p) in content if p == "VERB"}
    part_folded = 0
    for (lemma, pos), c in list(content.items()):
        if pos == "ADJ" and (hit := participle_verb(lemma, verbs)):
            content[(hit[0], "VERB")] += c
            del content[(lemma, pos)]
            part_folded += c

    words = sum(buckets.values())
    free = words - buckets["content"] - buckets["fgap"]      # covered with no content entries
    ranked = content.most_common()

    out_tsv = ROOT / "lexicon" / "targets" / f"{args.name}_lemmas.tsv"
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    cum = free
    curve: list[tuple[int, float]] = []
    with out_tsv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["rank", "lemma", "pos", "count", "per_million", "cum_coverage", "example"])
        for i, ((lemma, pos), c) in enumerate(ranked, 1):
            cum += c
            cov = cum / words
            curve.append((i, cov))
            w.writerow([i, lemma, pos, c, round(1e6 * c / words, 1), f"{cov:.4f}",
                        examples.get((lemma, pos), "")])

    def need(target: float) -> str:
        for i, cov in curve:
            if cov >= target:
                return f"{i:,}"
        return f"not reached (max {curve[-1][1]:.2%})" if curve else "-"

    def at(k: int) -> str:
        return f"{curve[min(k, len(curve)) - 1][1]:.2%}" if curve else "-"

    pos_top = Counter(p for (_, p), _ in ranked[:2000])
    lines = [
        f"# Coverage report: {args.name}", "",
        f"Generated by `tools/coverage.py` over `{args.corpus.name}`"
        + (f" (first {args.limit:,} stories)" if args.limit else "") + ".", "",
        f"- stories: {n_stories:,}",
        f"- word tokens (excl. punctuation): {words:,}",
        f"- distinct content lemmas (lemma, POS): {len(content):,}",
        f"- adverb tokens folded into their adjective (-ly and flat): {folded:,}",
        f"- participle-adjective tokens folded into their verb: {part_folded:,}", "",
        "## Token buckets", "", "| bucket | tokens | share |", "|---|---:|---:|",
    ]
    for b in ("content", "function", "absorbed", "name", "number", "fgap"):
        lines.append(f"| {b} | {buckets[b]:,} | {buckets[b] / words:.2%} |")
    lines += [
        "", f"Covered with **zero** content entries (function + absorbed + names + "
        f"numbers): **{free / words:.2%}**.", "",
        "## How many content entries are needed", "",
        "| target coverage of all word tokens | content entries needed |", "|---|---:|",
    ]
    for tgt in (0.90, 0.95, 0.97, 0.98, 0.99, 0.995):
        lines.append(f"| {tgt:.1%} | {need(tgt)} |")
    lines += ["", "| top-K content entries | coverage |", "|---:|---:|"]
    for k in (100, 250, 500, 750, 1000, 1500, 2000, 3000, 5000):
        if k <= len(curve):
            lines.append(f"| {k:,} | {at(k)} |")
    lines += ["", "POS mix of the top 2,000 content entries: "
              + ", ".join(f"{p} {n}" for p, n in pos_top.most_common()), "",
              "## Function-word gaps", "",
              "Closed-class tokens not covered by `lexicon/function.yaml` "
              f"({buckets['fgap']:,} tokens, {buckets['fgap'] / words:.2%}). "
              "Top 60:", "", "| lemma | POS | count |", "|---|---|---:|"]
    for (lemma, pos), c in fgaps.most_common(60):
        lines.append(f"| {lemma} | {pos} | {c:,} |")
    rep = ROOT / "reports" / f"coverage_{args.name}.md"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_tsv.relative_to(ROOT)} and {rep.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
