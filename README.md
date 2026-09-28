# dammaz

A homebrew dwarf language inspired by Khazalid and Zharralid, built to be
quick for a human to learn and fully machine-generable, so it can produce
synthetic training data for [dwarfgpt](../dwarfgpt). The full roadmap is in [`PLAN.md`](PLAN.md).

```
Ta dawi dhal drashad un az krang bin ta karak.
the dwarf old forge-PST a axe strong in the mountain
"The old dwarf forged a strong axe in the mountain."
```

## Status

- [x] **Phase 1: phonology.** Measured the source languages
  ([`spec/phonology_analysis.md`](spec/phonology_analysis.md)), wrote the spec
  ([`spec/phonology.md`](spec/phonology.md)), built the root generator
  (`dammaz.wordgen`), and made a sound-check sample
  ([`samples/sound_check_v0.md`](samples/sound_check_v0.md)).
  **Sound approved 2026-09-27.**
- [/] **Phase 2: grammar.** Draft v0.1 of [`spec/grammar.md`](spec/grammar.md),
  with ~110 function words in [`lexicon/function.yaml`](lexicon/function.yaml)
  and the suffix rules in `dammaz.morphology`. Every example in the spec is
  checked by the tests. §12 decisions reviewed 2026-09-27 (formal *you* added).
- [/] **Phase 3: lexicon.** Measured TinyStories ([`reports/coverage_tinystories.md`](reports/coverage_tinystories.md)):
  function words + grammar alone cover 58% of word tokens, and ~1,160 content
  senses reach the 97% gate. Batch 1 is reviewed and applied: **641 words / 674
  senses, 94.1% coverage**. Batch 2 ([`lexicon/review/core_batch02.csv`](lexicon/review/core_batch02.csv),
  540 senses) takes it to **97.1%** once reviewed and applied (see [`lexicon/review/README.md`](lexicon/review/README.md)).
- [x] **Phase 4: translator.** `dammaz.translate` (English → Dammaz on spaCy
  parses), `dammaz.gloss` (Dammaz → interlinear gloss), `dammaz.validate`, and
  the loanword fallback `dammaz.loan`. Every example in `spec/grammar.md` is a
  golden test (39/40; the one gap is a parser limit). On 300 TinyStories:
  0 unknown tokens, 5.6% loans (≈3% after batch 2), ~6,800 English words/s per
  process.
- [ ] Phase 5: corpus generation for dwarfgpt

## Layout

```
spec/                     normative specs: phonology.md, grammar.md (+ analysis report)
lexicon/
  function.yaml           function words (draft)
  phrases.yaml            multi-word expressions (once upon a time, a lot of...)
  core.yaml               content words, tier 1 (written by tools/review.py apply)
  targets/                frequency worklists + spaCy corrections
  review/                 seeds, review batches (CSV) and how-to
samples/                  sound checks, example texts, placeholder vocab
src/dammaz/
  phonology.py            segmenter, word-shape analysis, check_root()
  morphology.py           suffix attachment: inflect()
  lexicon.py              lexicon load / validate / build / status (CLI)
  english.py              English-side folding rules (adverbs, participles)
  translate.py            English -> Dammaz translator (CLI)
  gloss.py                Dammaz -> interlinear gloss (CLI)
  validate.py             every word known / loan / name / number? (CLI)
  loan.py                 loanword fallback for words not in the lexicon
  wordgen.py              root generator + dwarvishness scorer (CLI)
  data/phonology.yaml     machine-readable phonotactics + style knobs
  data/source_stats.json  aggregated source-language statistics (no word lists)
tools/
  extract_source_words.py references/raw/*.txt -> references/raw/source_words.tsv
  analyze_phonology.py    source_words.tsv -> spec/phonology_analysis.md + source_stats.json
  coverage.py             corpus -> lemma worklist + coverage report (needs --group nlp)
  review.py               propose review batches / apply decisions
  translate_corpus.py     corpus -> parallel en/dz JSONL + loan/throughput summary
reports/                  generated coverage reports
references/               source links; raw/ is gitignored (local copies only)
tests/
```

## Usage

```bash
uv sync --all-groups
```

```bash
uv run --group nlp pytest
```

Translate, gloss, and validate:

```bash
uv run --group nlp python -m dammaz.translate "The old dwarf forged a strong axe."
```

```bash
uv run python -m dammaz.gloss "Ta dawi dhal drashad un az krang."
```

```bash
uv run python -m dammaz.validate "Ta dawi dhal drashad un az krang."
```

Translate a sample of TinyStories to parallel JSONL (needs
`data/raw/TinyStoriesV2-GPT4-valid.txt`, see Phase 3):

```bash
uv run --group nlp python tools/translate_corpus.py data/raw/TinyStoriesV2-GPT4-valid.txt --limit 300 --out data/dz/sample300.jsonl
```

Lexicon work:

```bash
uv run python -m dammaz.lexicon status
```

```bash
uv run python tools/review.py apply lexicon/review/core_batch02.csv --dry-run
```

Generate candidate roots:

```bash
uv run python -m dammaz.wordgen -n 30 --syllables 2
```

Rebuild the phonology statistics (needs the local copies in `references/raw/`):

```bash
uv run python tools/extract_source_words.py
```

```bash
uv run python tools/analyze_phonology.py
```

If `references/raw/` is missing, `wordgen` still works from the committed
`source_stats.json`. It just skips the "identical to a Khazalid/Zharralid word" check,
with a warning.

## Credits

Inspired by the dwarf languages of Warhammer Fantasy (Games Workshop). Thanks to the
fan lexicon compilers Alebelly Cragfist (Khazalid) and Suspicious Entity (Zharralid);
see [`references/sources.md`](references/sources.md).
