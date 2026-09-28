"""Orthographic segmentation and word shape analysis.

Klazan is written in plain ASCII. A *segment* is one sound as spelled: a single
letter, or one of the digraphs in ``DIGRAPHS`` (``kh`` = one sound, not k+h).

Every word decomposes into a **shape**::

    initial-cluster  V  (medial-cluster V)*  final-cluster
         "gr"       "o"    "md"     "a"         "l"        <- gromdal

Clusters may be empty. Vowel runs (``ai``, ``ua``) count as one nucleus.
The same segmenter is used to analyze the Khazalid/Zharralid source words
and to generate / validate Klazan words.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib import resources

import yaml

VOWELS = frozenset("aeiou")

# Longest match first. 'tch'/'ck' only occur in source words (slotch, wazzock);
# they normalize to 'ch' and 'k'.
DIGRAPHS = ("tch", "kh", "zh", "sh", "th", "dh", "gh", "rh", "ch", "ng", "ph", "ck")
_NORMALIZE = {"tch": "ch", "ck": "k"}


def segment(word: str, collapse_geminates: bool = True) -> list[str]:
    """Split a word into segments. 'khazukan' -> ['kh','a','z','u','k','a','n'].

    'y' is a vowel unless it precedes a vowel ('yar' -> y,a,r; 'bryn' -> b,r,y,n).
    With ``collapse_geminates`` a doubled segment ('zz', 'rr') is written once.
    """
    w = word.lower()
    segs: list[str] = []
    i = 0
    while i < len(w):
        for d in DIGRAPHS:
            if w.startswith(d, i):
                segs.append(_NORMALIZE.get(d, d))
                i += len(d)
                break
        else:
            segs.append(w[i])
            i += 1
    if collapse_geminates:
        segs = [s for j, s in enumerate(segs)
                if j == 0 or s != segs[j - 1] or is_vowel(s, segs, j)]
    return segs


def is_vowel(seg: str, segs: list[str] | None = None, idx: int | None = None) -> bool:
    if seg in VOWELS:
        return True
    if seg == "y" and segs is not None and idx is not None:
        nxt = segs[idx + 1] if idx + 1 < len(segs) else None
        return nxt is None or nxt not in VOWELS
    return False


def has_geminate(word: str) -> bool:
    segs = segment(word, collapse_geminates=False)
    return any(a == b and not is_vowel(a, segs, i)
               for i, (a, b) in enumerate(zip(segs, segs[1:])))


@dataclass(frozen=True)
class Shape:
    initial: str               # onset cluster of the word, '' if vowel-initial
    nuclei: tuple[str, ...]    # vowel runs, one per syllable
    medials: tuple[str, ...]   # consonant clusters between nuclei (len = syllables-1)
    final: str                 # coda cluster of the word, '' if vowel-final

    @property
    def syllables(self) -> int:
        return len(self.nuclei)


def shape(word: str) -> Shape:
    """Decompose a word into its C/V shape. Clusters are joined with '.' between
    segments so digraphs stay unambiguous: 'thr' onset -> 'th.r'."""
    segs = segment(word)
    runs: list[tuple[bool, list[str]]] = []
    for i, s in enumerate(segs):
        v = is_vowel(s, segs, i)
        if runs and runs[-1][0] == v:
            runs[-1][1].append(s)
        else:
            runs.append((v, [s]))
    initial = final = ""
    if runs and not runs[0][0]:
        initial = ".".join(runs.pop(0)[1])
    if runs and not runs[-1][0]:
        final = ".".join(runs.pop()[1])
    nuclei = tuple("".join(r[1]) for r in runs if r[0])
    medials = tuple(".".join(r[1]) for r in runs if not r[0])
    return Shape(initial, nuclei, medials, final)


# ---------------------------------------------------------------------------
# Normative Klazan phonotactics (data/phonology.yaml)
# ---------------------------------------------------------------------------

def _clusters(spec_lists: list) -> frozenset[str]:
    """yaml cluster lists ('' or lists of spelled clusters) -> '.'-joined segment form."""
    out: set[str] = set()
    for item in spec_lists:
        for c in ([item] if isinstance(item, str) else item):
            out.add(".".join(segment(c, collapse_geminates=False)) if c else "")
    return frozenset(out)


@dataclass(frozen=True)
class Spec:
    raw: dict
    initials: frozenset[str]
    finals: frozenset[str]
    medial_codas: frozenset[str]
    max_medial: int
    forbidden: frozenset[tuple[str, str]]
    reserved_finals: tuple[str, ...]
    alphabet: frozenset[str]

    def legal_medial(self, cluster: str) -> bool:
        segs = cluster.split(".") if cluster else []
        if not segs or len(segs) > self.max_medial:
            return False
        for cut in range(len(segs) + 1):
            coda, onset = segs[:cut], ".".join(segs[cut:])
            if len(coda) > 1 or (coda and coda[0] not in self.medial_codas):
                continue
            if onset in self.initials:
                return True
        return False

    def legal_medials(self) -> list[str]:
        """Every legal medial cluster (used by the generator)."""
        onsets = [o for o in self.initials]
        out = set()
        for c in [""] + sorted(self.medial_codas):
            for o in onsets:
                cl = ".".join(p for p in (c, o) if p)
                if cl and self.legal_medial(cl) and not self._has_forbidden(cl.split(".")):
                    out.add(cl)
        return sorted(out)

    def _has_forbidden(self, segs: list[str]) -> bool:
        return any((a, b) in self.forbidden or a == b for a, b in zip(segs, segs[1:]))


@cache
def spec() -> Spec:
    raw = yaml.safe_load(resources.files("klazan.data").joinpath("phonology.yaml")
                         .read_text(encoding="utf-8"))
    return Spec(
        raw=raw,
        initials=_clusters(raw["initials"]),
        finals=_clusters(raw["finals"]),
        medial_codas=frozenset(raw["medial_codas"]),
        max_medial=raw["max_medial_consonants"],
        forbidden=frozenset(tuple(p) for p in raw["forbidden_sequences"]),
        reserved_finals=tuple(raw["reserved_final_strings"]),
        alphabet=frozenset(raw["alphabet"]),
    )


def check_root(word: str) -> list[str]:
    """Return the list of phonotactic violations for a native Klazan root
    (empty list = legal). Borrowed words and suffixed forms are not checked here."""
    sp = spec()
    problems: list[str] = []
    if not word or set(word) - sp.alphabet:
        return [f"letters outside alphabet: {sorted(set(word) - sp.alphabet)}"]
    raw_segs = segment(word, collapse_geminates=False)
    if any(s == "y" and is_vowel(s, raw_segs, i) for i, s in enumerate(raw_segs)):
        problems.append("'y' used as a vowel")
    for a, b in zip(raw_segs, raw_segs[1:]):
        if a == b and a not in VOWELS:
            problems.append(f"geminate '{a}{b}'")
        elif (a, b) in sp.forbidden:
            problems.append(f"forbidden sequence '{a}{b}'")
    sh = shape(word)
    if not sh.nuclei:
        problems.append("no vowel")
    if any(len(n) > 1 for n in sh.nuclei):
        problems.append("vowel sequence")
    if sh.initial not in sp.initials:
        problems.append(f"illegal initial '{sh.initial}'")
    if sh.final not in sp.finals:
        problems.append(f"illegal final '{sh.final}'")
    for m in sh.medials:
        if not sp.legal_medial(m):
            problems.append(f"illegal medial '{m}'")
    clusters = [sh.initial, *sh.medials, sh.final]
    extra = sum(len(c.split(".")) - 1 for c in clusters if c)
    if extra > sp.raw["max_extra_cluster_consonants"]:
        problems.append(f"too many clustered consonants ({extra} extra)")
    for r in sp.reserved_finals:
        if word.endswith(r):
            problems.append(f"ends in reserved suffix '-{r}'")
            break
    return problems
