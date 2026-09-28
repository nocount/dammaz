"""Generate and rank candidate Dammaz roots.

Two parts:

* **Sampler**: builds words as ``initial V (medial V)* final``, drawing each
  cluster from the Khazalid/Zharralid frequencies in ``data/source_stats.json``,
  blended and re-weighted by the style knobs in ``data/phonology.yaml``, and
  restricted to what the yaml says is legal.
* **Scorer**: a segment-trigram language model trained on the same (blended)
  source statistics. ``score`` = mean log2-probability per segment; higher =
  more dwarvish. ``dwarvishness`` maps that to a 0-100 percentile against a
  fixed reference sample from the sampler, so 50 = a typical generated word.

Candidates are then filtered:

* phonotactically illegal (``phonology.check_root``) -> dropped
* an English word (wordfreq top 50K) or profane -> dropped
* identical to a Khazalid/Zharralid word -> dropped (borrowing is a deliberate
  lexicon decision, not an accident). Needs references/raw/source_words.tsv;
  skipped with a warning if absent.
* within edit distance 1 of an existing Dammaz word -> dropped
* within edit distance 1 of a common English word or a source word -> flagged
  (kept, but shown so a human can judge)

CLI::

    uv run python -m dammaz.wordgen -n 30 --syllables 2
    uv run python -m dammaz.wordgen --score karak grund zhorvash
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import random
import sys
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path

from dammaz.phonology import check_root, segment, spec

ROOT = Path(__file__).resolve().parents[2]
SOURCE_WORDS = ROOT / "references" / "raw" / "source_words.tsv"

# Exact-match rejects plus substrings that are never acceptable inside a word.
PROFANE_EXACT = {"ass", "arse", "cock", "dick", "cum", "piss", "tit", "tits", "slut",
                 "whore", "bitch", "twat", "wank", "fag", "homo", "spic", "kike",
                 "gook", "coon", "dyke", "negro", "nazi", "rape", "anal", "anus",
                 "damn", "hell", "crap", "turd", "porn", "sex", "poo", "poop",
                 # sound-alikes
                 "dik", "dikk", "kok", "fuk", "fak", "kunt", "shat", "azz", "tit"}
PROFANE_SUBSTR = ("fuck", "shit", "cunt", "nig", "fag", "kkk", "rape", "nazi",
                  "porn", "whore", "slut", "wank")


# ---------------------------------------------------------------------------
# data loading
# ---------------------------------------------------------------------------

@cache
def _stats() -> dict:
    return json.loads(resources.files("dammaz.data").joinpath("source_stats.json")
                      .read_text(encoding="utf-8"))


def _blend(key: str) -> Counter:
    """Blend a per-source counter by the yaml weights, normalising each source
    by its word count so the smaller Zharralid list still gets its share."""
    st, blend = _stats(), spec().raw["style"]["blend"]
    out: Counter = Counter()
    for src, w in blend.items():
        n = st[src]["n"]
        for k, v in st[src][key].items():
            out[k] += w * v / n
    return out


def _boost(cluster: str) -> float:
    boosts = spec().raw["style"]["boost_segments"]
    f = 1.0
    for s in cluster.split("."):
        f *= boosts.get(s, 1.0)
    return f


class _Categorical:
    def __init__(self, weights: dict[str, float]):
        items = [(k, w) for k, w in weights.items() if w > 0]
        self.keys = [k for k, _ in items]
        total = sum(w for _, w in items)
        acc, self.cum = 0.0, []
        for _, w in items:
            acc += w / total
            self.cum.append(acc)

    def sample(self, rng: random.Random) -> str:
        return self.keys[min(bisect.bisect(self.cum, rng.random()), len(self.keys) - 1)]


def _position_dist(measured: Counter, legal: list[str], mass: float,
                   vowel_final_boost: float = 1.0) -> _Categorical:
    legal_set = set(legal)
    attested = {k: v * _boost(k) for k, v in measured.items() if k in legal_set}
    if "" in attested:
        attested[""] *= vowel_final_boost
    total = sum(attested.values())
    weights = {k: (1 - mass) * v / total for k, v in attested.items()}
    unattested = [k for k in legal if k not in attested]
    for k in unattested:
        weights[k] = mass / len(unattested) * _boost(k)
    return _Categorical(weights)


# ---------------------------------------------------------------------------
# trigram scorer
# ---------------------------------------------------------------------------

class TrigramModel:
    """Interpolated segment trigram model over '<' + segments + '>'."""

    L3, L2, L1 = 0.6, 0.3, 0.1

    def __init__(self, trigrams: Counter):
        self.tri = trigrams
        self.bi_ctx: Counter = Counter()      # (a, b) -> count as a context
        self.bi: Counter = Counter()          # (b, c)
        self.uni_ctx: Counter = Counter()     # b as a context
        self.uni: Counter = Counter()         # c
        for key, v in trigrams.items():
            a, b, c = key.split(" ")
            self.bi_ctx[(a, b)] += v
            self.bi[(b, c)] += v
            self.uni_ctx[b] += v
            self.uni[c] += v
        self.total = sum(self.uni.values())
        self.vocab = len(self.uni) + 1

    def logprob(self, word: str) -> float:
        """Mean log2 P(segment | two previous) over the word, end marker included."""
        segs = ["<", "<"] + segment(word, collapse_geminates=False) + [">"]
        lp = 0.0
        for i in range(2, len(segs)):
            a, b, c = segs[i - 2:i + 1]
            p3 = self.tri.get(f"{a} {b} {c}", 0) / self.bi_ctx[(a, b)] if self.bi_ctx[(a, b)] else 0
            p2 = self.bi[(b, c)] / self.uni_ctx[b] if self.uni_ctx[b] else 0
            p1 = (self.uni[c] + 1) / (self.total + self.vocab)
            lp += math.log2(self.L3 * p3 + self.L2 * p2 + self.L1 * p1)
        return lp / (len(segs) - 2)


# ---------------------------------------------------------------------------
# distance helpers (edit distance <= 1 via deletion neighbourhoods)
# ---------------------------------------------------------------------------

def _deletes(w: str) -> set[str]:
    return {w[:i] + w[i + 1:] for i in range(len(w))}


class NearIndex:
    """Finds words within edit distance ~1 (insert/delete/substitute, plus
    adjacent transpositions) of a query."""

    def __init__(self, words=()):
        self.idx: defaultdict[str, set[str]] = defaultdict(set)
        for w in words:
            self.add(w)

    def add(self, w: str) -> None:
        for k in {w} | _deletes(w):
            self.idx[k].add(w)

    def near(self, q: str) -> set[str]:
        hits: set[str] = set()
        for k in {q} | _deletes(q):
            hits |= self.idx.get(k, set())
        return hits


# ---------------------------------------------------------------------------
# generator
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    word: str
    syllables: int
    score: float
    dwarvishness: float                    # 0-100 percentile vs. reference sample
    flags: list[str] = field(default_factory=list)


class WordGen:
    def __init__(self, seed: int | None = None, existing: set[str] | None = None):
        sp = spec()
        style = sp.raw["style"]
        mass = style["unattested_mass"]
        self.rng = random.Random(seed)
        self.initial = _position_dist(_blend("initial"), sorted(sp.initials), mass["initial"])
        self.final = _position_dist(_blend("final"), sorted(sp.finals), mass["final"],
                                    style["boost_vowel_final"])
        self.medial = _position_dist(_blend("medial"), sp.legal_medials(), mass["medial"])
        self.vowel = _Categorical(style["vowel_weights"])
        self.syll = _Categorical({str(k): v for k, v in _blend("syllables").items()})
        self.model = TrigramModel(_blend("trigram"))

        self.existing = NearIndex(existing or ())
        self.existing_exact = set(existing or ())
        self.english, self.english_near = _english()
        self.source_exact, self.source_near = _source_words()
        # reference distribution for the dwarvishness percentile
        ref_rng = random.Random(12345)
        self._ref = sorted(self.model.logprob(self._raw(ref_rng)) for _ in range(3000))

    # -- sampling ----------------------------------------------------------
    def _raw(self, rng: random.Random, syllables: int | None = None) -> str:
        n = syllables or int(self.syll.sample(rng))
        parts = [self.initial.sample(rng), self.vowel.sample(rng)]
        for _ in range(n - 1):
            parts += [self.medial.sample(rng), self.vowel.sample(rng)]
        parts.append(self.final.sample(rng))
        return "".join(p.replace(".", "") for p in parts)

    def sample(self, syllables: int | None = None, max_tries: int = 200) -> str:
        """One phonotactically legal root (no other filters)."""
        for _ in range(max_tries):
            w = self._raw(self.rng, syllables)
            if not check_root(w):
                return w
        raise RuntimeError("could not sample a legal word; check phonology.yaml")

    # -- scoring -----------------------------------------------------------
    def score(self, word: str) -> Candidate:
        lp = self.model.logprob(word)
        pct = 100 * bisect.bisect(self._ref, lp) / len(self._ref)
        return Candidate(word, len(segment_nuclei(word)), lp, pct, self.flags(word))

    def reject_reason(self, word: str) -> str | None:
        if problems := check_root(word):
            return "illegal: " + "; ".join(problems)
        if word in self.english:
            return "english word"
        if word in PROFANE_EXACT or any(s in word for s in PROFANE_SUBSTR):
            return "profane"
        if word in self.source_exact:
            return "identical to a Khazalid/Zharralid word"
        if word in self.existing_exact or self.existing.near(word):
            return "too close to an existing Dammaz word"
        return None

    def flags(self, word: str) -> list[str]:
        """Soft warnings. Every 3-4 letter string is one edit from *some*
        English word, so near-English is only reported for 5+ letters."""
        f = []
        if len(word) >= 5 and (near := sorted(self.english_near.near(word))):
            f.append("near-english:" + ",".join(near[:3]))
        if len(word) >= 4 and (near := sorted(self.source_near.near(word) - {word})):
            f.append("near-source:" + ",".join(near[:3]))
        return f

    def candidates(self, n: int, syllables: int | None = None,
                   min_dwarvishness: float = 30.0, drop_flagged: bool = False,
                   max_tries: int | None = None) -> list[Candidate]:
        """``n`` distinct candidates that pass every filter and score at least
        ``min_dwarvishness``. Selection above the floor is random, not
        top-scored: ranking purely by the trigram model would squeeze out the
        Zharralid-flavoured sh/zh words and open endings the style asks for,
        and make every word look like gr-/dr- Khazalid."""
        chosen: list[Candidate] = []
        taken = NearIndex()
        for _ in range(max_tries or n * 400):
            w = self._raw(self.rng, syllables)
            if taken.near(w) or self.reject_reason(w):
                continue
            c = self.score(w)
            if c.dwarvishness < min_dwarvishness or (drop_flagged and c.flags):
                continue
            chosen.append(c)
            taken.add(w)
            if len(chosen) == n:
                break
        return chosen

    def add_existing(self, word: str) -> None:
        self.existing.add(word)
        self.existing_exact.add(word)


def segment_nuclei(word: str) -> list[str]:
    from dammaz.phonology import shape
    return list(shape(word).nuclei)


@cache
def _english() -> tuple[frozenset[str], NearIndex]:
    from wordfreq import top_n_list
    words = [w for w in top_n_list("en", 50_000) if w.isalpha() and w.isascii()]
    common = [w for w in words[:5_000] if len(w) >= 3]
    return frozenset(words), NearIndex(common)


@cache
def _source_words() -> tuple[frozenset[str], NearIndex]:
    if not SOURCE_WORDS.exists():
        warnings.warn(f"{SOURCE_WORDS} not found: skipping Khazalid/Zharralid "
                      "collision checks (run tools/extract_source_words.py)")
        return frozenset(), NearIndex()
    with SOURCE_WORDS.open(encoding="utf-8") as f:
        words = {r["word"] for r in csv.DictReader(f, delimiter="\t") if len(r["word"]) > 1}
    return frozenset(words), NearIndex(w for w in words if len(w) >= 3)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _fmt(c: Candidate) -> str:
    return f"{c.word:14s} {c.syllables}  {c.score:6.2f}  {c.dwarvishness:5.1f}  {' '.join(c.flags)}"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-n", type=int, default=30, help="number of candidates")
    ap.add_argument("--syllables", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--clean", action="store_true", help="drop flagged candidates")
    ap.add_argument("--min", type=float, default=30.0, dest="min_dwarvishness",
                    help="dwarvishness floor, 0-100 (default 30)")
    ap.add_argument("--score", nargs="+", metavar="WORD", help="score given words instead")
    args = ap.parse_args(argv)

    gen = WordGen(seed=args.seed)
    print(f"{'word':14s} σ  logp    dwarf  flags")
    if args.score:
        for w in args.score:
            c = gen.score(w)
            why = gen.reject_reason(w)
            print(_fmt(c) + (f"  [{why}]" if why else ""))
        return
    for c in gen.candidates(args.n, args.syllables, args.min_dwarvishness,
                            drop_flagged=args.clean):
        print(_fmt(c))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
