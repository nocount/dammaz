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
- [ ] Phase 3: lexicon
- [ ] Phase 4: translator
- [ ] Phase 5: corpus generation for dwarfgpt

## Layout

```
spec/                     normative specs: phonology.md, grammar.md (+ analysis report)
lexicon/function.yaml     function words (draft)
samples/                  sound checks, example texts, placeholder vocab
src/dammaz/
  phonology.py            segmenter, word-shape analysis, check_root()
  morphology.py           suffix attachment: inflect()
  lexicon.py              lexicon YAML loaders
  wordgen.py              root generator + dwarvishness scorer (CLI)
  data/phonology.yaml     machine-readable phonotactics + style knobs
  data/source_stats.json  aggregated source-language statistics (no word lists)
tools/
  extract_source_words.py references/raw/*.txt -> references/raw/source_words.tsv
  analyze_phonology.py    source_words.tsv -> spec/phonology_analysis.md + source_stats.json
references/               source links; raw/ is gitignored (local copies only)
tests/
```

## Usage

```bash
uv sync
uv run pytest
```

Generate 30 candidate two-syllable roots:

```bash
uv run python -m dammaz.wordgen -n 30 --syllables 2
```

Score and check specific words:

```bash
uv run python -m dammaz.wordgen --score karak zhorvash
```

Rebuild the statistics (needs the local copies in `references/raw/`):

```bash
uv run python tools/extract_source_words.py
uv run python tools/analyze_phonology.py
```

If `references/raw/` is missing, `wordgen` still works from the committed
`source_stats.json`. It just skips the "identical to a Khazalid/Zharralid word" check,
with a warning.

## Credits

Inspired by the dwarf languages of Warhammer Fantasy (Games Workshop). Thanks to the
fan lexicon compilers Alebelly Cragfist (Khazalid) and Suspicious Entity (Zharralid);
see [`references/sources.md`](references/sources.md).
