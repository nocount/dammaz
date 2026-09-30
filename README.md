# klazan

A homebrew dwarf language inspired by Khazalid and Zharralid, built to be
quick for a human to learn and fully machine-generable, so it can produce
synthetic training data for [dwarfgpt](../dwarfgpt). The full roadmap is in [`PLAN.md`](PLAN.md).

The name is its own: `klazandof` is Klazan for *word*, so *Klazan* is roughly
"the word". Until 2026-09-28 it went by the working name *Dammaz*, which is
Khazalid for *grudge*; `dammaz` survives in the lexicon as exactly that.

```
Ta dawi dhal drashad un az krang bin ta karak.
the dwarf old forge-PST a axe strong in the mountain
"The old dwarf forged a strong axe in the mountain."
```

## Status

- [x] **Phase 1: phonology.** Measured the source languages
  ([`spec/phonology_analysis.md`](spec/phonology_analysis.md)), wrote the spec
  ([`spec/phonology.md`](spec/phonology.md)), built the root generator
  (`klazan.wordgen`), and made a sound-check sample
  ([`samples/sound_check_v0.md`](samples/sound_check_v0.md)).
  **Sound approved 2026-09-27.**
- [x] **Phase 2: grammar.** Draft v0.1 of [`spec/grammar.md`](spec/grammar.md),
  with ~110 function words in [`lexicon/function.yaml`](lexicon/function.yaml)
  and the suffix rules in `klazan.morphology`. Every example in the spec is
  checked by the tests. §12 decisions reviewed 2026-09-27 (formal *you* added).
- [x] **Phase 3: lexicon.** 3,058 content words (1,155 in `core.yaml`, 1,903 in
  `extended.yaml`) + 113 function words, from three reviewed batches. TinyStories
  token coverage is **98.44%** (the gate was 97%). Batch 3 (2026-09-30) reached
  past children's stories: **95%** on Cosmopedia's young-children stories and on
  public-domain fairy tales and myths
  ([`reports/coverage_tinystories.md`](reports/coverage_tinystories.md),
  `reports/coverage_cand_*.md`, [`lexicon/review/README.md`](lexicon/review/README.md)).
- [x] **Phase 4: translator.** `klazan.translate` (English → Klazan on spaCy
  parses), `klazan.gloss` (Klazan → interlinear gloss), `klazan.validate`, and
  the loanword fallback `klazan.loan`. Every example in `spec/grammar.md` is a
  golden test (39/40; the one gap is a parser limit). On 2,000 TinyStories:
  0 unknown tokens, 2.65% loans before filtering, ~10K English words/s per process.
- [/] **Phase 5: corpus.** `tools/fetch_data.py` + `tools/corpus.py`
  (resumable parallel translation, fingerprinted, packed to Parquet + parallel
  JSONL) are built and tested. **Full run pending:** see
  [`docs/corpus_runbook.md`](docs/corpus_runbook.md).

## Layout

```
spec/                     normative specs: phonology.md, grammar.md (+ analysis report)
docs/corpus_runbook.md    how to generate the corpus on any machine
lexicon/
  function.yaml           function words (draft)
  phrases.yaml            multi-word expressions (once upon a time, a lot of...)
  core.yaml               content words, tier 1 (written by tools/review.py apply)
  extended.yaml           content words, tier 2: the long tail beyond TinyStories
  targets/                frequency worklists + spaCy corrections
  review/                 seeds, review batches (CSV) and how-to
samples/                  sound checks, example texts, placeholder vocab
src/klazan/
  phonology.py            segmenter, word-shape analysis, check_root()
  morphology.py           suffix attachment: inflect()
  lexicon.py              lexicon load / validate / build / status (CLI)
  english.py              English-side rules: input normalization (apostrophes, archaic
                          English), adverb and participle folding
  translate.py            English -> Klazan translator (CLI)
  gloss.py                Klazan -> interlinear gloss (CLI)
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
  merge_targets.py        several corpora's worklists -> one review target
  translate_corpus.py     quick sample: corpus -> parallel en/kz JSONL + loan summary
  fetch_data.py           download TinyStories into data/raw/ (resumable, hashed)
  corpus.py               Phase 5: translate (sharded, resumable) / report / pack
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
uv run --group nlp python -m klazan.translate "The old dwarf forged a strong axe."
```

```bash
uv run python -m klazan.gloss "Ta dawi dhal drashad un az krang."
```

```bash
uv run python -m klazan.validate "Ta dawi dhal drashad un az krang."
```

Build the training corpus: follow [`docs/corpus_runbook.md`](docs/corpus_runbook.md).
For a quick sample of TinyStories as parallel JSONL (after
`uv run python tools/fetch_data.py tinystories-valid`):

```bash
uv run --group nlp python tools/translate_corpus.py data/raw/TinyStoriesV2-GPT4-valid.txt --limit 300 --out data/kz/sample300.jsonl
```

Lexicon work:

```bash
uv run python -m klazan.lexicon status
```

```bash
uv run python tools/review.py apply lexicon/review/core_batch02.csv --dry-run
```

Generate candidate roots:

```bash
uv run python -m klazan.wordgen -n 30 --syllables 2
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
