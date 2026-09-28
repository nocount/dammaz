"""Load, validate and compile the lexicon (source of truth: lexicon/*.yaml).

Files:
    lexicon/function.yaml   closed class (grammar.md); entries with dz/en/cat
    lexicon/core.yaml       content words, tier 1   } entries with dz/en/origin
    lexicon/extended.yaml   content words, tier 2   }

A content entry is one Dammaz word with one or more English senses written
``lemma/POS`` (POS in NOUN VERB ADJ ADV INTJ)::

    - {dz: drash,   en: [forge/VERB],                  origin: invented}
    - {dz: drashki, en: [smith/NOUN, blacksmith/NOUN], origin: derived, base: drash+AGT}
    - {dz: dawi,    en: [dwarf/NOUN],                  origin: borrowed, from: "Khazalid dawi"}

CLI::

    uv run python -m dammaz.lexicon check     # validate; exit 1 on errors
    uv run python -m dammaz.lexicon build     # validate + write build/lexicon.json
    uv run python -m dammaz.lexicon status    # coverage against lexicon/targets/
    uv run python -m dammaz.lexicon fingerprint   # version hashes stamped on corpora
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LEXICON_DIR = ROOT / "lexicon"
CONTENT_FILES = ("core.yaml", "extended.yaml")
BUILD = ROOT / "build" / "lexicon.json"

CONTENT_POS = ("NOUN", "VERB", "ADJ", "ADV", "INTJ")
ORIGINS = ("invented", "borrowed", "derived")
MAX_BORROWED = 60                     # PLAN.md: "inspired + iconic few"

# Inflections every word of a POS can take; checked for collisions.
PARADIGM = {
    "NOUN": (("PL",),),
    "VERB": (("PST",), ("PROG",)),
    "ADJ": (("CMP",), ("ADV",)),
    "ADV": (),
    "INTJ": (),
}


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def _strings(entry: dict, key: str) -> tuple[str, ...]:
    """YAML 1.1 reads bare yes/no/on/off as booleans: insist on quoting them."""
    vals = entry[key]
    bad = [v for v in vals if not isinstance(v, str)]
    if bad:
        raise ValueError(f"{entry['dz']}: non-string {key} values {bad} "
                         "(quote yes/no/on/off/true/false in the YAML)")
    return tuple(vals)


@dataclass(frozen=True)
class FunctionWord:
    dz: str
    en: tuple[str, ...]
    cat: str
    origin: str
    source: str = ""
    notes: str = ""

    @property
    def gloss(self) -> str:
        return self.en[0]


@dataclass(frozen=True)
class Entry:
    dz: str
    senses: tuple[tuple[str, str], ...]        # ((lemma, POS), ...)
    origin: str
    tier: str
    source: str = ""                           # borrowed: where from
    base: str = ""                             # derived: "root+TAG+TAG"
    notes: str = ""

    @property
    def pos(self) -> set[str]:
        return {p for _, p in self.senses}

    @property
    def gloss(self) -> str:
        return self.senses[0][0]


def _load_yaml(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("entries") or []


@cache
def function_words() -> tuple[FunctionWord, ...]:
    return tuple(
        FunctionWord(dz=e["dz"], en=_strings(e, "en"), cat=e["cat"], origin=e["origin"],
                     source=e.get("from", ""), notes=e.get("notes", ""))
        for e in _load_yaml(LEXICON_DIR / "function.yaml")
    )


def function_word_map() -> dict[str, FunctionWord]:
    return {w.dz: w for w in function_words()}


def _parse_sense(s: str, dz: str) -> tuple[str, str]:
    lemma, _, pos = s.rpartition("/")
    if not lemma or pos not in CONTENT_POS:
        raise ValueError(f"{dz}: bad sense {s!r} (want lemma/POS, POS in {CONTENT_POS})")
    return lemma, pos


def load_content(files: tuple[str, ...] = CONTENT_FILES,
                 lexicon_dir: Path | None = None) -> tuple[Entry, ...]:
    out: list[Entry] = []
    for name in files:
        for e in _load_yaml((lexicon_dir or LEXICON_DIR) / name):
            out.append(Entry(
                dz=e["dz"],
                senses=tuple(_parse_sense(s, e["dz"]) for s in _strings(e, "en")),
                origin=e["origin"], tier=name.removesuffix(".yaml"),
                source=e.get("from", ""), base=e.get("base", ""), notes=e.get("notes", ""),
            ))
    return tuple(out)


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _within_one(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1 or a == b:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1
                                  and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def paradigm(entry: Entry) -> dict[str, tuple[str, ...]]:
    """All inflected forms of a content entry: form -> tags."""
    from dammaz.morphology import inflect
    forms: dict[str, tuple[str, ...]] = {}
    for pos in sorted(entry.pos):
        for tags in PARADIGM[pos]:
            forms[inflect(entry.dz, *tags)] = tags
    return forms


def validate(content: tuple[Entry, ...] | None = None,
             functions: tuple[FunctionWord, ...] | None = None) -> Report:
    from dammaz.morphology import inflect
    from dammaz.phonology import check_root
    from dammaz.wordgen import PROFANE_EXACT, PROFANE_SUBSTR, _english

    content = load_content() if content is None else content
    functions = function_words() if functions is None else functions
    rep = Report()
    english, _ = _english()

    def profane(w: str) -> bool:
        return w in PROFANE_EXACT or any(s in w for s in PROFANE_SUBSTR)

    # 1. unique spellings across the whole lexicon
    seen: dict[str, str] = {}
    for w in functions:
        seen[w.dz] = "function"
    for e in content:
        if e.dz in seen:
            rep.errors.append(f"{e.dz}: spelling already used ({seen[e.dz]})")
        seen[e.dz] = e.tier

    # 2. each English lemma/POS maps to exactly one content word
    sense_owner: dict[tuple[str, str], str] = {}
    for e in content:
        for s in e.senses:
            if s in sense_owner and sense_owner[s] != e.dz:
                rep.errors.append(f"{s[0]}/{s[1]}: mapped to both {sense_owner[s]} and {e.dz}")
            sense_owner[s] = e.dz

    by_dz = {e.dz: e for e in content} | {w.dz: w for w in functions}
    n_borrowed = sum(w.origin == "borrowed" for w in functions)
    for e in content:
        # 3. origin rules
        if e.origin not in ORIGINS:
            rep.errors.append(f"{e.dz}: unknown origin {e.origin!r}")
        elif e.origin == "invented":
            if problems := check_root(e.dz):
                rep.errors.append(f"{e.dz}: illegal root ({'; '.join(problems)})")
            if e.dz in english:
                rep.errors.append(f"{e.dz}: invented root is an English word")
        elif e.origin == "borrowed":
            n_borrowed += 1
            if not e.source:
                rep.errors.append(f"{e.dz}: borrowed word needs a 'from'")
        elif e.origin == "derived":
            root, *tags = e.base.split("+") if e.base else ("",)
            if root not in by_dz:
                rep.errors.append(f"{e.dz}: base root {root!r} is not in the lexicon")
            else:
                try:
                    if inflect(root, *tags) != e.dz:
                        rep.errors.append(f"{e.dz}: {e.base} gives {inflect(root, *tags)!r}")
                except ValueError as err:
                    rep.errors.append(f"{e.dz}: bad derivation {e.base!r} ({err})")
            if e.dz in english:
                rep.warnings.append(f"{e.dz} ({e.base}) is an English word")
        if profane(e.dz):
            rep.errors.append(f"{e.dz}: profane")

    if n_borrowed > MAX_BORROWED:
        rep.warnings.append(f"{n_borrowed} borrowed words (budget {MAX_BORROWED})")

    # 4. roots of 3+ letters must be >1 edit apart (derived words are exempt:
    #    they're transparent). Function words count as roots here.
    roots = sorted({e.dz for e in content if e.origin != "derived"}
                   | {w.dz for w in functions if w.origin != "derived"})
    by_len: dict[int, list[str]] = defaultdict(list)
    for r in roots:
        by_len[len(r)].append(r)
    content_roots = {e.dz for e in content if e.origin != "derived"}
    for r in roots:
        if len(r) < 3:
            continue
        for L in (len(r), len(r) + 1):
            for other in by_len.get(L, []):
                if other > r or L > len(r):
                    if len(other) >= 3 and _within_one(r, other) and (
                            r in content_roots or other in content_roots):
                        rep.errors.append(f"{r} / {other}: roots only one letter apart")

    # 5. inflected forms: no clashes, nothing profane; English = warning
    form_owner: dict[str, str] = {}
    for e in content:
        for form, tags in paradigm(e).items():
            label = f"{e.dz}+{'+'.join(tags)}"
            if form in seen and form != e.dz:
                rep.errors.append(f"{label} = {form!r}, which is already a lexicon word")
            if form in form_owner and form_owner[form] != label:
                rep.errors.append(f"{label} and {form_owner[form]} both give {form!r}")
            form_owner[form] = label
            if profane(form):
                rep.errors.append(f"{label} = {form!r} is profane")
            elif form in english:
                rep.warnings.append(f"{label} = {form!r} is an English word")
    return rep


# ---------------------------------------------------------------------------
# fingerprint: which exact language version produced a corpus
# ---------------------------------------------------------------------------

FINGERPRINT_FILES = ("function.yaml", "core.yaml", "extended.yaml", "phrases.yaml",
                     "targets/corrections.yaml")
CODE_FILES = ("translate.py", "morphology.py", "english.py", "loan.py", "phonology.py",
              "lexicon.py")


def _hash_files(paths: list[Path], labels: list[str]) -> str:
    import hashlib
    h = hashlib.sha256()
    for path, label in zip(paths, labels):
        if path.exists():
            # normalize line endings so Windows (CRLF) and Linux checkouts agree
            h.update(label.encode() + b"\0" + path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()[:12]


def fingerprint() -> dict[str, str]:
    """Short hashes of the lexicon data and of the translator code. Two corpora
    with the same fingerprint were produced by the same language + pipeline."""
    src = Path(__file__).resolve().parent
    return {
        "lexicon": _hash_files([LEXICON_DIR / f for f in FINGERPRINT_FILES],
                               list(FINGERPRINT_FILES)),
        "code": _hash_files([src / f for f in CODE_FILES], list(CODE_FILES)),
    }


# ---------------------------------------------------------------------------
# build + status
# ---------------------------------------------------------------------------

def build(path: Path = BUILD) -> Path:
    content = load_content()
    rep = validate(content)
    if not rep.ok:
        raise SystemExit("lexicon has errors; run `python -m dammaz.lexicon check`")
    en_index: dict[str, str] = {}
    for e in content:
        for lemma, pos in e.senses:
            en_index[f"{lemma}/{pos}"] = e.dz
    out = {
        "function": [asdict(w) for w in function_words()],
        "content": [asdict(e) | {"forms": paradigm(e)} for e in content],
        "en_index": en_index,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def status(target: str = "tinystories", show: int = 40) -> str:
    tsv = LEXICON_DIR / "targets" / f"{target}_lemmas.tsv"
    rows = list(csv.DictReader(tsv.open(encoding="utf-8"), delimiter="\t"))
    covered = {s for e in load_content() for s in e.senses}
    first = rows[0]
    free = float(first["cum_coverage"]) - float(first["per_million"]) / 1e6
    got = free + sum(float(r["per_million"]) for r in rows
                     if (r["lemma"], r["pos"]) in covered) / 1e6
    missing = [r for r in rows if (r["lemma"], r["pos"]) not in covered]
    lines = [f"{target}: {len(covered):,} senses in lexicon -> {got:.2%} of word tokens "
             f"(function/absorbed/names/numbers alone: {free:.2%})",
             f"next {show} uncovered by frequency:"]
    lines += [f"  {r['rank']:>5} {r['lemma']}/{r['pos']} ({r['count']})" for r in missing[:show]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    cmd = (argv or sys.argv[1:] or ["check"])[0]
    if cmd == "status":
        print(status())
        return
    if cmd == "fingerprint":
        print(json.dumps(fingerprint()))
        return
    rep = validate()
    for w in rep.warnings:
        print("warning:", w)
    for e in rep.errors:
        print("ERROR:", e)
    n = len(load_content())
    print(f"{n} content entries, {len(function_words())} function words: "
          f"{len(rep.errors)} errors, {len(rep.warnings)} warnings")
    if cmd == "build" and rep.ok:
        print("wrote", build().relative_to(ROOT))
    sys.exit(0 if rep.ok else 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
