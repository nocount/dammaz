"""Is this valid Dammaz? Every word must be a lexicon word (+ legal suffixes), a
loan, a name or a number. Anything else is a translator bug.

    uv run python -m dammaz.validate data/dz/sample300.jsonl      # JSONL with a "dz" field
    uv run python -m dammaz.validate "Ta dawi dhal drashad un az krang."
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from dammaz.gloss import Glosser


@dataclass
class Report:
    counts: Counter = field(default_factory=Counter)       # kind -> tokens
    unknown: Counter = field(default_factory=Counter)

    @property
    def words(self) -> int:
        return sum(self.counts.values())

    @property
    def ok(self) -> bool:
        return not self.unknown

    def summary(self) -> str:
        w = self.words or 1
        parts = [f"{k} {n:,} ({n / w:.2%})" for k, n in self.counts.most_common()]
        s = f"{self.words:,} words: " + ", ".join(parts)
        if self.unknown:
            s += "\nUNKNOWN: " + ", ".join(f"{t} {n}" for t, n in self.unknown.most_common(30))
        return s


def validate_text(text: str, glosser: Glosser | None = None, report: Report | None = None) -> Report:
    g = glosser or Glosser()
    rep = report or Report()
    initial = True
    for tok in re.findall(r"[\w\-]+|[^\w\s]", text):
        if not re.match(r"\w", tok):
            initial = initial or tok in ".!?\"“"
            continue
        a = g.analyze(tok, initial)
        rep.counts[a.kind] += 1
        if a.kind == "unknown":
            rep.unknown[tok] += 1
        initial = False
    return rep


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    arg = " ".join(sys.argv[1:])
    g, rep = Glosser(), Report()
    path = Path(arg)
    if arg and path.exists():
        for line in path.open(encoding="utf-8"):
            validate_text(json.loads(line)["dz"], g, rep)
    else:
        validate_text(arg or sys.stdin.read(), g, rep)
    print(rep.summary())
    sys.exit(0 if rep.ok else 1)


if __name__ == "__main__":
    main()
