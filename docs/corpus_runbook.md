# Runbook: generating the Klazan corpus on another machine

This is for running Phase 5 on a different workstation (e.g. the desktop): a fresh
checkout, the TinyStories download, a resumable multi-core translation run, and
packing into the files dwarfgpt consumes. Everything here works the same on
Windows, Linux and macOS.

## What you need

| | |
|---|---|
| Git access | to `github.com/nocount/klazan` |
| [uv](https://docs.astral.sh/uv/) | Python ≥3.12. It was developed on 3.14, and uv installs Python if it's missing. |
| Disk | about 15 GB free: 2.2 GB input, ~6 GB translation shards, ~5 GB packed output |
| CPU | Throughput is ~10K English words/s per worker. The full TinyStories train split (~470M words) takes roughly 2–3 hours on 8 workers. |
| GPU | not needed |
| RAM | ~0.5 GB per worker |

Nothing here spends API money.

## 0. Before leaving the laptop

**The corpus is only as final as the lexicon it was made with.** Commit and push
every lexicon change first. Then note the fingerprint so you can confirm the desktop
has the same language:

```bash
uv run python -m klazan.lexicon fingerprint
```

At the time of writing (1,155 content words, batch 2 + *next* → `brik` applied)
this printed `{"lexicon": "a206f4c78481", ...}`. The `code` hash also changes
whenever the translator changes.

## 1. Set up the checkout

```bash
git clone https://github.com/nocount/klazan.git
```

```bash
cd klazan
```

```bash
uv sync --all-groups
```

`--all-groups` installs pytest, spaCy + `en_core_web_sm` (the `nlp` group) and
pyarrow (the `corpus` group).

Then check that the machine matches the laptop:

```bash
uv run python -m klazan.lexicon fingerprint
```

```bash
uv run python -m klazan.lexicon check
```

```bash
uv run --group nlp pytest -q
```

The fingerprint must match step 0. `check` should say `0 errors`. The tests should
end with `passed, 1 xfailed`.

`references/raw/` (the Warhammer word lists) is gitignored and isn't needed. The
tests pass without it, with one warning from `wordgen`, which then skips its
"identical to a source word" check. Only copy it over if you'll be generating new
words on the desktop.

## 2. Download TinyStories

```bash
uv run python tools/fetch_data.py all
```

This downloads into `data/raw/` (gitignored), resumes if interrupted (just run it
again), checks the exact size, and records SHA-256 hashes in
`data/raw/MANIFEST.json`. For reference, the laptop's validation file hashed to
`6874bae9…c0585d`.

## 3. Dry run (2 minutes)

A quick end-to-end check on the validation split before committing hours:

```bash
uv run --group nlp python tools/corpus.py translate data/raw/TinyStoriesV2-GPT4-valid.txt --out data/corpus/dryrun --shard-size 500 --max-stories 3000
```

```bash
uv run --group corpus python tools/corpus.py pack data/corpus/dryrun
```

Expect loans around **2.7%** before filtering and **~1.9%** after, **0 unknown**,
and ~82% of stories kept. Then delete `data/corpus/dryrun`.

## 4. The real run

```bash
uv run --group nlp python tools/corpus.py translate data/raw/TinyStoriesV2-GPT4-train.txt --out data/corpus/tinystories --workers 8
```

- **`--workers`** defaults to CPU count − 1. Each worker loads spaCy once, which takes ~5 s.
- **Resumable:** stop it any time (Ctrl+C) and run the same command again. Finished
  shards (5,000 stories each) are skipped. A half-written shard is a `.tmp` file
  and gets redone.
- **Progress** is printed per shard. Check it from another terminal with:

  ```bash
  uv run python tools/corpus.py report data/corpus/tinystories
  ```

- **Version safety:** if the lexicon or translator changes between runs, `translate`
  refuses to add shards to this directory, rather than silently mixing two versions
  of the language. Use a new `--out`.
- **Only need a slice?** Add `--max-stories N`. dwarfgpt's target of 30–80M Klazan
  tokens is ~15–40% of the train split, but translating everything is only a few
  hours, and `pack` lets you choose later.

## 5. Pack

```bash
uv run --group corpus python tools/corpus.py pack data/corpus/tinystories
```

**Defaults** (all flags):

| Flag | Default | Meaning |
|---|---|---|
| `--max-loan-rate` | 0.05 | drop stories with >5% loanwords |
| `--min-words` | 20 | drop very short stories |
| `--val-frac` | 0.05 | held out for validation, chosen by a hash of the English text |
| `--rows-per-file` | 100000 | stories per Parquet file |

Exact duplicates (normalized English) are always removed.

**Output**, in `data/corpus/tinystories/packed/`:

| Path | Contents |
|---|---|
| `kz/train/shard_*.parquet`, `kz/val/shard_*.parquet` | A single `text` column of Klazan stories, zstd, row groups of 1024. This is the layout nanochat's pretraining loader reads (it iterates row groups and takes the `text` column). |
| `parallel/train.jsonl`, `parallel/val.jsonl` | `{"id", "en", "kz"}` pairs for SFT and translation evals |
| `pack_manifest.json` | fingerprint, git commit, input hash, filters, counts |
| `REPORT.md` | summary, plus the 100 most frequent loans. That list is the input for the next lexicon batch. |

## 6. Sanity checks before handing off

1. `REPORT.md` shows a loan rate under 3% (expect ~1.9%).
2. Every word validates:

   ```bash
   uv run python -m klazan.validate data/corpus/tinystories/packed/parallel/val.jsonl
   ```

   It should report no `UNKNOWN` line.
3. Read ~20 random stories with glosses (the plan's audit step):

   ```bash
   uv run python -m klazan.gloss "<paste a Klazan paragraph>"
   ```

## 7. Hand off to dwarfgpt

Copy or symlink `packed/` into the dwarfgpt workspace. Keep `pack_manifest.json`
with it. dwarfgpt Phase 4 (tokenizer) mixes it with FineWeb-EDU at the chosen ratio.
When the nanochat fork exists, check its loader against the Parquet layout above.
The one known difference is that nanochat takes its validation split from the
*last* Parquet file of a single directory, while this writes separate
`train/` and `val/` directories.

## If something goes wrong

| Symptom | Fix |
|---|---|
| `existing shards were made with fingerprint …` | The lexicon/translator changed since this directory was started. Use a new `--out` (or delete the old one). |
| `shard size must stay …` | Use the original `--shard-size` for that directory. |
| Download stops | Re-run `fetch_data.py`: it resumes from the `.part` file. |
| `OSError`/`MemoryError` with many workers | Lower `--workers`. |
| Unknown tokens > 0 in `report` | A translator gap. Those stories are dropped by `pack`; note the story ids and fix it on the laptop. |
