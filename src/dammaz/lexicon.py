"""Load the lexicon YAML files (source of truth under lexicon/).

Phase 2 only needs the function words; Phase 3 extends this with the content
lexicon, validation and compilation.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LEXICON_DIR = ROOT / "lexicon"


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


def _strings(entry: dict, key: str) -> tuple[str, ...]:
    """YAML 1.1 reads bare yes/no/on/off as booleans: insist on quoting them."""
    vals = entry[key]
    bad = [v for v in vals if not isinstance(v, str)]
    if bad:
        raise ValueError(f"{entry['dz']}: non-string {key} values {bad} "
                         "(quote yes/no/on/off/true/false in the YAML)")
    return tuple(vals)


@cache
def function_words() -> tuple[FunctionWord, ...]:
    raw = yaml.safe_load((LEXICON_DIR / "function.yaml").read_text(encoding="utf-8"))
    return tuple(
        FunctionWord(dz=e["dz"], en=_strings(e, "en"), cat=e["cat"],
                     origin=e["origin"], source=e.get("from", ""), notes=e.get("notes", ""))
        for e in raw["entries"]
    )


def function_word_map() -> dict[str, FunctionWord]:
    return {w.dz: w for w in function_words()}
