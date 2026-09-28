"""Propose lexicon batches for human review, then apply the decisions.

    uv run python tools/review.py propose --n 600 --out lexicon/review/core_batch01.csv
    uv run python tools/review.py apply lexicon/review/core_batch01.csv [--into core]

**propose** takes the next ``--n`` uncovered senses from the frequency worklist
(lexicon/targets/<target>_lemmas.tsv), adds the seeds' dwarf-genre extras and
any sense a derived seed depends on, and assigns each one a Klazan word:

    1. a seed from lexicon/review/seeds.yaml (fixed, derived, or shared synonym)
    2. the same word as the lemma's other part of speech (help/VERB = help/NOUN),
       unless the lemma is listed as a homonym
    3. a fresh root from klazan.wordgen: 1 syllable for the ~150 most frequent
       senses, mostly 2 for rarer ones; plus 3 alternatives

The batch is validated as if accepted, then written as CSV (opens in Excel).

**apply** reads the ``decision`` column:

    (blank) / ok / y   accept the proposal
    1 / 2 / 3          take alternative 1-3 instead
    x / n / skip       reject: nothing is added; it is re-proposed next batch
    <any word>         use this word instead (must pass the phonology rules)

Derived words are rebuilt from their base's *final* word, so changing
``friend`` also changes ``friendly``. Accepted entries are merged into
lexicon/<into>.yaml, and the whole lexicon is validated before anything is written.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klazan.lexicon import (LEXICON_DIR, PARADIGM, Entry,  # noqa: E402
                            function_words, load_content, validate)
from klazan.morphology import inflect  # noqa: E402
from klazan.phonology import check_root  # noqa: E402
from klazan.wordgen import PROFANE_EXACT, PROFANE_SUBSTR, WordGen, _english  # noqa: E402

SEEDS = LEXICON_DIR / "review" / "seeds.yaml"
CORRECTIONS = LEXICON_DIR / "targets" / "corrections.yaml"
FIELDS = ["rank", "english", "pos", "count", "example", "proposed", "origin",
          "from_or_base", "alt1", "alt2", "alt3", "decision", "note"]

Sense = tuple[str, str]


def _sense(key: str) -> Sense:
    lemma, _, pos = key.rpartition("/")
    return lemma, pos


def _key(s: Sense) -> str:
    return f"{s[0]}/{s[1]}"


class FormGuard:
    """Tracks every word and inflected form assigned so far, so a new root is
    rejected if it, or any of its forms, would collide or be profane."""

    def __init__(self) -> None:
        self.words: set[str] = set()
        self.forms: set[str] = set()

    @staticmethod
    def forms_of(word: str, pos: set[str]) -> set[str]:
        return {inflect(word, *tags) for p in pos for tags in PARADIGM[p]}

    def ok(self, word: str, pos: set[str]) -> bool:
        fs = self.forms_of(word, pos)
        if word in self.forms or fs & (self.words | self.forms):
            return False
        english, _ = _english()
        return not any(f in english or f in PROFANE_EXACT or any(b in f for b in PROFANE_SUBSTR)
                       for f in fs)

    def add(self, word: str, pos: set[str]) -> None:
        self.words.add(word)
        self.forms |= self.forms_of(word, pos) - {word}


def _candidates(gen: WordGen, n: int, syllables: int, pos: set[str], guard: FormGuard):
    """n acceptable candidates, relaxing the dwarvishness floor and then
    growing the word by a syllable when the short-word space is exhausted."""
    got: list = []
    for syl, floor in ((syllables, 35), (syllables, 15), (syllables + 1, 35), (syllables + 2, 25)):
        for c in gen.candidates(n * 3, syllables=syl, min_dwarvishness=floor, max_tries=n * 2000):
            if guard.ok(c.word, pos) and c.word not in {g.word for g in got}:
                got.append(c)
            if len(got) == n:
                return got
    raise SystemExit(f"could not generate {n} candidates near {syllables} syllables")


def _syllables(rank: int | None, rng: random.Random) -> int:
    """Zipf-ish length budget: the ~100 most frequent senses get one syllable,
    the next few hundred a mix, the long tail mostly two."""
    if rank is None:
        return rng.choice((1, 2, 2))
    if rank <= 100:
        return 1
    if rank <= 300:
        return rng.choices((1, 2), weights=(50, 50))[0]
    if rank <= 800:
        return rng.choices((1, 2, 3), weights=(25, 60, 15))[0]
    return rng.choices((1, 2, 3), weights=(10, 65, 25))[0]


# ---------------------------------------------------------------------------
# propose
# ---------------------------------------------------------------------------

def propose(n: int, out: Path, target: str, seed: int) -> None:
    rows = list(csv.DictReader((LEXICON_DIR / "targets" / f"{target}_lemmas.tsv")
                               .open(encoding="utf-8"), delimiter="\t"))
    info = {(r["lemma"], r["pos"]): r for r in rows}
    seeds = yaml.safe_load(SEEDS.read_text(encoding="utf-8"))
    seed_senses = {_sense(k): v for k, v in seeds["senses"].items()}
    homonyms = set(seeds.get("homonyms") or [])

    lexicon = load_content()
    covered: dict[Sense, str] = {s: e.kz for e in lexicon for s in e.senses}
    corr = yaml.safe_load(CORRECTIONS.read_text(encoding="utf-8"))
    for k in corr.get("function") or []:              # handled by function words
        covered[_sense(k)] = "(function)"
    fixed_words = {w.kz for w in function_words()} | {e.kz for e in lexicon}

    # -- which senses go in this batch -----------------------------------------
    selected: list[Sense] = []
    for r in rows:
        s = (r["lemma"], r["pos"])
        if s not in covered:
            selected.append(s)
        if len(selected) >= n:
            break
    extras = [_sense(k) for k in seeds.get("extra") or []]
    selected += [s for s in extras if s not in covered and s not in selected]

    def deps(s: Sense) -> list[Sense]:
        sd = seed_senses.get(s) or {}
        ref = sd.get("same") or (sd.get("base", "")[1:].split("+")[0]
                                 if sd.get("base", "").startswith("@") else None)
        return [_sense(ref)] if ref else []

    i = 0
    while i < len(selected):                 # pull in dependencies, transitively
        for d in deps(selected[i]):
            if d not in covered and d not in selected:
                selected.append(d)
        i += 1

    # -- assign words ------------------------------------------------------------
    prop: dict[Sense, dict] = {}
    for s in selected:                       # 1. fixed seeds
        sd = seed_senses.get(s)
        if sd and "kz" in sd:
            prop[s] = {"proposed": sd["kz"], "origin": sd["origin"],
                       "from_or_base": sd.get("from", ""),
                       "note": "sound check v0" if sd["origin"] == "invented" else ""}

    # 2. share across POS for the same lemma (the most frequent sense leads)
    by_lemma: dict[str, list[Sense]] = defaultdict(list)
    for s in selected:
        by_lemma[s[0]].append(s)
    share_with: dict[Sense, Sense] = {}
    for lemma, ss in by_lemma.items():
        if lemma in homonyms:
            continue
        lexicon_owner = next(((lemma, p) for (l, p) in covered if l == lemma), None)
        leader = next((x for x in ss if x in prop), None) or lexicon_owner or ss[0]
        for x in ss:
            if x != leader and x not in prop and not (seed_senses.get(x)):
                share_with[x] = leader

    # 3. generate the rest
    gen = WordGen(seed=seed, existing=fixed_words | {p["proposed"] for p in prop.values()})
    rng = random.Random(seed)
    group_pos: dict[Sense, set[str]] = defaultdict(set)   # leader -> POS of all its sharers
    for s in selected:
        group_pos[share_with.get(s, s)].add(s[1])
    guard = FormGuard()
    for w in function_words():
        guard.words.add(w.kz)
    for e in lexicon:
        guard.add(e.kz, e.pos)
    for s, p in prop.items():
        guard.add(p["proposed"], group_pos[s] or {s[1]})
    for s in selected:
        if s in prop or s in share_with or (seed_senses.get(s) or {}).keys() & {"base", "same"}:
            continue
        rank = int(info[s]["rank"]) if s in info else None
        pos = group_pos[s] or {s[1]}
        cands = _candidates(gen, 4, _syllables(rank, rng), pos, guard)
        prop[s] = {"proposed": cands[0].word, "origin": "invented", "from_or_base": "",
                   "alts": [c.word for c in cands[1:4]], "note": ""}
        gen.add_existing(cands[0].word)
        guard.add(cands[0].word, pos)
    for s in selected:                       # alternatives for seeded fixed words too
        if s in prop and "alts" not in prop[s] and prop[s]["origin"] == "invented":
            rank = int(info[s]["rank"]) if s in info else None
            prop[s]["alts"] = [c.word for c in _candidates(
                gen, 3, _syllables(rank, rng), group_pos[s] or {s[1]}, guard)]

    # 4. resolve shared and derived
    def word_of(s: Sense) -> str | None:
        if s in prop:
            return prop[s]["proposed"]
        return covered.get(s)

    for _ in range(3):                       # derived-of-shared chains resolve in a few passes
        for s in selected:
            sd = seed_senses.get(s) or {}
            if "same" in sd and word_of(_sense(sd["same"])):
                ref = _sense(sd["same"])
                prop[s] = {"proposed": word_of(ref), "origin": "shared",
                           "from_or_base": "@" + _key(ref), "note": f"synonym of {ref[0]}"}
            elif s in share_with and word_of(share_with[s]):
                ref = share_with[s]
                prop[s] = {"proposed": word_of(ref), "origin": "shared",
                           "from_or_base": "@" + _key(ref), "note": f"same word as {_key(ref)}"}
            elif "base" in sd:
                base = sd["base"]
                root_ref, *tags = base.split("+")
                root = word_of(_sense(root_ref[1:])) if root_ref.startswith("@") else root_ref
                if root:
                    prop[s] = {"proposed": inflect(root, *tags), "origin": "derived",
                               "from_or_base": base, "note": f"{root}+{'+'.join(tags)}"}
    # Alternatives were generated before later words were assigned; replace any
    # that now clash with a final proposal, so every listed alternative is safe.
    from klazan.wordgen import NearIndex
    finals = NearIndex(p["proposed"] for p in prop.values() if p["origin"] != "derived")
    final_set = {p["proposed"] for p in prop.values()}

    def alt_ok(a: str, own: str) -> bool:
        near = finals.near(a) - {own}
        return a not in final_set and not (len(a) >= 3 and any(len(x) >= 3 for x in near))

    for s in selected:
        p = prop.get(s)
        if not p or not p.get("alts"):
            continue
        keep = [a for a in p["alts"] if alt_ok(a, p["proposed"])]
        rank = int(info[s]["rank"]) if s in info else None
        while len(keep) < 3:
            for c in _candidates(gen, 3, _syllables(rank, rng), group_pos[s] or {s[1]}, guard):
                if alt_ok(c.word, p["proposed"]) and c.word not in keep:
                    keep.append(c.word)
        p["alts"] = keep[:3]

    missing = [s for s in selected if s not in prop]
    if missing:
        raise SystemExit(f"unresolved senses: {missing}")

    # -- validate as if accepted ----------------------------------------------------
    trial = merge(list(lexicon), [(s, prop[s]["proposed"], prop[s]["origin"],
                                   prop[s]["from_or_base"]) for s in selected], word_of)
    rep = validate(tuple(trial))
    for e in rep.errors:
        print("ERROR:", e)

    # -- write CSV --------------------------------------------------------------------
    extra_set = set(extras)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for s in selected:
            p, r = prop[s], info.get(s, {})
            alts = p.get("alts", []) + ["", "", ""]
            note = p.get("note", "")
            if s in extra_set and s not in info:
                note = (note + "; " if note else "") + "dwarf extra"
            w.writerow({"rank": r.get("rank", ""), "english": s[0], "pos": s[1],
                        "count": r.get("count", ""), "example": r.get("example", ""),
                        "proposed": p["proposed"], "origin": p["origin"],
                        "from_or_base": p["from_or_base"], "alt1": alts[0],
                        "alt2": alts[1], "alt3": alts[2], "decision": "", "note": note})
    from collections import Counter
    words = {prop[s]["proposed"] for s in selected}
    print(f"wrote {out}: {len(selected)} senses -> {len(words)} words; "
          f"origins {dict(Counter(prop[s]['origin'] for s in selected))}; "
          f"{len(rep.errors)} errors, {len(rep.warnings)} warnings")
    for wmsg in rep.warnings:
        print("warning:", wmsg)


def merge(existing: list[Entry], rows: list[tuple[Sense, str, str, str]], word_of,
          tier: str = "core") -> list[Entry]:
    """Merge (sense, kz, origin, from_or_base) rows into the existing entries.
    Senses whose word already exists are added to that entry; the rest become
    new entries in ``tier``."""
    from dataclasses import replace
    by_kz: dict[str, dict] = {}
    for s, kz, origin, fb in rows:
        e = by_kz.setdefault(kz, {"senses": [], "origin": None, "source": "", "base": ""})
        e["senses"].append(s)
        if origin == "shared":
            continue
        e["origin"] = origin
        if origin == "borrowed":
            e["source"] = fb
        elif origin == "derived":
            root_ref, *tags = fb.split("+")
            root = word_of(_sense(root_ref[1:])) if root_ref.startswith("@") else root_ref
            e["base"] = "+".join([root, *tags])
    out: list[Entry] = []
    for old in existing:
        if old.kz in by_kz:
            add = [x for x in by_kz.pop(old.kz)["senses"] if x not in old.senses]
            old = replace(old, senses=old.senses + tuple(add))
        out.append(old)
    for kz, e in by_kz.items():
        out.append(Entry(kz=kz, senses=tuple(e["senses"]), origin=e["origin"] or "invented",
                         tier=tier, source=e["source"], base=e["base"]))
    return out


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

def apply(path: Path, into: str, dry_run: bool = False) -> None:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    final: dict[Sense, tuple[str, str, str]] = {}      # sense -> (kz, origin, from_or_base)
    rejected = 0
    for r in rows:
        s = (r["english"], r["pos"])
        d = (r.get("decision") or "").strip().lower()
        if d in ("", "ok", "y", "yes"):
            final[s] = (r["proposed"], r["origin"], r["from_or_base"])
        elif d in ("1", "2", "3"):
            alt = r[f"alt{d}"]
            if not alt:
                raise SystemExit(f"{_key(s)}: no alternative {d}")
            final[s] = (alt, "invented", "")
        elif d in ("x", "n", "no", "skip"):
            rejected += 1
        else:
            if problems := check_root(d):
                raise SystemExit(f"{_key(s)}: custom word {d!r} breaks the rules: {problems}")
            final[s] = (d, "invented", "")

    covered = {s: e.kz for e in load_content() for s in e.senses}

    def word_of(s: Sense) -> str | None:
        return final[s][0] if s in final else covered.get(s)

    # re-resolve shared + derived against the final choices
    for _ in range(3):
        for s, (kz, origin, fb) in list(final.items()):
            if origin == "shared" and fb.startswith("@"):
                ref = word_of(_sense(fb[1:]))
                if ref is None:
                    raise SystemExit(f"{_key(s)}: shares with {fb[1:]}, which was rejected")
                final[s] = (ref, origin, fb)
            elif origin == "derived":
                root_ref, *tags = fb.split("+")
                root = word_of(_sense(root_ref[1:])) if root_ref.startswith("@") else root_ref
                if root is None:
                    raise SystemExit(f"{_key(s)}: derived from {root_ref[1:]}, which was rejected")
                final[s] = (inflect(root, *tags), origin, fb)

    existing = list(load_content())
    merged = merge(existing, [(s, *v) for s, v in final.items()], word_of, tier=into)
    rep = validate(tuple(merged))
    if not rep.ok:
        for e in rep.errors:
            print("ERROR:", e)
        raise SystemExit("not written: fix the decisions above and re-run apply")

    for w in rep.warnings:
        print("warning:", w)
    if dry_run:
        print(f"dry run: {len(final)} senses -> {len(merged)} words valid "
              f"({len(rep.warnings)} warnings, {rejected} rejected); nothing written")
        return
    target = LEXICON_DIR / f"{into}.yaml"
    header = [f"# Klazan content lexicon: {into}. Edit freely; validate with",
              "#   uv run python -m klazan.lexicon check",
              "# en: lemma/POS senses. origin: invented | borrowed (from) | derived (base).",
              "", "entries:"]
    body = [_fmt(e) for e in merged if e.tier == into]
    target.write_text("\n".join(header + body) + "\n", encoding="utf-8")
    print(f"{target.relative_to(ROOT)}: now {len(body)} words; applied {len(final)} senses, "
          f"{rejected} rejected; {len(rep.warnings)} warnings")


def _q(s: str) -> str:
    return '"' + s.replace('"', '\\"') + '"'


def _fmt(e: Entry) -> str:
    en = ", ".join(_q(f"{l}/{p}") for l, p in e.senses)
    parts = [f"kz: {e.kz}", f"en: [{en}]", f"origin: {e.origin}"]
    if e.source:
        parts.append(f"from: {_q(e.source)}")
    if e.base:
        parts.append(f"base: {_q(e.base)}")
    if e.notes:
        parts.append(f"notes: {_q(e.notes)}")
    return "  - {" + ", ".join(parts) + "}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--n", type=int, default=600)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--target", default="tinystories")
    p.add_argument("--seed", type=int, default=1)
    a = sub.add_parser("apply")
    a.add_argument("csv", type=Path)
    a.add_argument("--into", default="core")
    a.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.cmd == "propose":
        propose(args.n, args.out, args.target, args.seed)
    else:
        apply(args.csv, args.into, args.dry_run)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
