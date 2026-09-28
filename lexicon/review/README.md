# Reviewing a lexicon batch

Each batch is a CSV that opens in Excel. One row = one English sense
(`lemma` + part of speech) and the Dammaz word proposed for it. Rows are in
frequency order (`rank` 1 = the most common content word in TinyStories), so the
top of the sheet matters most.

**You only need to touch rows you want to change.** A blank `decision` means
"accept".

## Columns

| column | meaning |
|---|---|
| `rank`, `count` | frequency rank / raw count in TinyStories (blank for dwarf-genre extras) |
| `english`, `pos` | the English sense (NOUN, VERB, ADJ, ADV, INTJ) |
| `example` | the first TinyStories sentence it appeared in |
| `proposed` | the proposed Dammaz word |
| `origin` | `invented` (generated), `borrowed` (Khazalid), `derived` (root + suffix), `shared` (same word as another sense) |
| `from_or_base` | for borrowed: the source; for derived: the base (e.g. `@friend/NOUN+LIKE` = friend + `-rak`); for shared: which sense it shares with |
| `alt1`–`alt3` | alternative generated words; each one is safe to pick on its own |
| `decision` | **your call** (see below) |
| `note` | extra context (`sound check v0` = a word from the approved sound check) |

## Decisions

| type in `decision` | effect |
|---|---|
| *(leave blank)*, `ok` | accept `proposed` |
| `1`, `2`, `3` | use `alt1` / `alt2` / `alt3` instead |
| `x` | reject; the sense is re-proposed in the next batch with a new word |
| any word, e.g. `glimrak` | use your own word (must follow `spec/phonology.md`; `apply` tells you if it doesn't) |

**Shared and derived words follow their base.** If you change `friend`, then
`friendly` (friend + `-rak`) changes with it, and changing *dog* changes *puppy*
(dog + the diminutive `-it`). If you reject a base, its derived
words are rejected too (`apply` tells you which ones).

**To split a shared word** (e.g. you want *fun* the noun and *fun* the adjective
to be different words), type a new word, or `x`, in the shared row.

## Applying

Save the CSV, keeping the CSV format (Excel: "CSV UTF-8"). Then:

```bash
uv run python tools/review.py apply lexicon/review/core_batch01.csv --dry-run
```

```bash
uv run python tools/review.py apply lexicon/review/core_batch01.csv
```

`apply` validates the whole lexicon first and writes nothing if there's a
problem, with a message saying which rows to fix. Swapping in two alternatives
that happen to be one letter apart is the typical case. The accepted words land
in `lexicon/core.yaml`, which you can also edit by hand afterwards.

Check progress against the coverage target:

```bash
uv run python -m dammaz.lexicon status
```

## Tips for skimming

- **Read the top ~150 rows out loud.** These words will be in almost every
  sentence, so they're the ones worth being picky about.
- **Watch for pairs that should sound related but don't**, like *mom*/*dad*,
  *big*/*small*, *boy*/*girl*. Swapping one of them for your own word is quick.
- **Anything that reads as an English word or name to you:** type `x` or pick an
  alternative. The filters catch dictionary words, not every name or slang term.
