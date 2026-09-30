# Klazan: plan for a homebrew dwarf language for dwarfgpt

**Goal:** a dwarf language, *Klazan* (working name *Dammaz* until 2026-09-28), that (1) sounds like a blend of
Khazalid and Zharralid, (2) is quick for a human to learn because its grammar
sits close to English and Romance languages, and (3) is **fully machine-generable**.
A deterministic English→Klazan translator can turn any English corpus into
unlimited, perfectly consistent synthetic training data for dwarfgpt.

**Decisions locked so far (2026-09-27):**

| Area | Decision |
|---|---|
| Grammar | "Romance-lite": SVO, articles, adjectives **after** nouns, `X a Y` = "X of Y", tense via verb suffixes. No grammatical gender, no noun cases, no irregulars (or as few as possible). |
| Vocabulary | Copy the *sound palette* and *suffix system*. Borrow only about 30–60 iconic words (dawi, karak, az, khaz, grund, rik, dammaz…). Invent the rest. |
| Sound | Blend: a Khazalid core (hard k/g/r/z, gr-/dr-/kh-/thr-, closed syllables) plus Zharralid's sh/zh, `-ash`, and some open vowel endings (-a, -u, -o) so it flows aloud. |
| Data generation | Deterministic, rule-based English→Klazan translation of existing English corpora. No LLM writes Klazan directly. |

Target sentence shape (from the design discussion):

```
Ta dawi gorm grunad un az grom bin ta karak.
the dwarf old forge-PAST a axe strong in the mountain
"The old dwarf forged a strong axe in the mountain."
```

## Status (updated 2026-09-30)

| Phase | State | Where |
|---|---|---|
| 1. Phonology | **Done.** Sound approved. | `spec/phonology.md`, `klazan.wordgen` |
| 2. Grammar | **Done** (draft v0.1, all §12 decisions made; formal `uzar` and diminutive `-it` added). | `spec/grammar.md`, `lexicon/function.yaml` |
| 3. Lexicon | **Gate met.** 3,058 content words + 113 function words: 98.44% TinyStories coverage, and 95% on Cosmopedia's young-children stories and on fairy tales and myths (batch 3, 2026-09-30). | `lexicon/core.yaml`, `lexicon/extended.yaml`, `reports/coverage_*.md` |
| 4. Translator | **Done.** 39/40 grammar examples exact; 0 unknown tokens; 2.65% loans before filtering; ~10K words/s per process. | `klazan.translate`, `.gloss`, `.validate`, `.loan` |
| 5. Corpus | **Tooling built and tested; the full run is pending** (to be done on the desktop). | `tools/corpus.py`, `docs/corpus_runbook.md` |
| 6. Learning materials | Not started. | — |

The sketches in the phase sections below were written before the work. Where the
two differ, the spec files and the status notes win.

---

## Why this beats the Neo-Khuzdul route for dwarfgpt

- **No fidelity ceiling.** The language's grammar is whatever `grammar.md` says,
  and the translator implements exactly that. The whole Stage B/Stage C LLM
  naturalization and round-trip stack from `dwarfgpt/khuzdul_nanochat_plan.md`,
  along with its BLEU gates, becomes unnecessary.
- **Unlimited, near-free data.** TinyStories alone is about 470M English tokens, and
  translating it costs CPU time rather than API spend.
- **Exact evaluation.** Every Klazan word is either in the lexicon or produced by a
  documented rule, so a "grammar checker" is a parser, not a heuristic.
- **Cheap to change your mind.** If you rename a word or change a suffix, you rebuild
  the lexicon and regenerate the corpus in hours. Version the lexicon (`v0.1`, `v0.2`…)
  and stamp every corpus shard with the version it was built from.
- **No third-party scholar to coordinate with.** The remaining IP posture is only
  "don't lean on Games Workshop names" (see *Release posture*).

**Caveat to keep in mind for the writeup:** a deterministic, English-ordered
translation is structurally close to a *relexified English*. That is great for
learnability and for dwarfgpt's bilingual transfer, but the model can learn it
partly as "English in disguise". The Romance-lite choices help here: adjective order,
`a` genitives, no do-support, and a sentence-initial question particle all break
pure word-for-word alignment. The experiment then measures something closer to
*"how fast does a small LM pick up a regular, English-adjacent synthetic
language"*, which is a legitimate and interesting question. Frame it that way.

---

## Repository layout (target)

```
klazan/
├── PLAN.md                    this file
├── README.md
├── spec/
│   ├── phonology.md           inventory, phonotactics, stress, orthography
│   └── grammar.md             the normative grammar (translator implements this)
├── lexicon/                   SOURCE OF TRUTH, hand-editable YAML
│   ├── function.yaml          ~150 function words (pronouns, articles, preps…)
│   ├── core.yaml              ~500 hand-curated content roots
│   └── extended.yaml          generated + reviewed long tail
├── references/
│   ├── sources.md             links + structural notes on Khazalid/Zharralid
│   └── raw/                   (gitignored) local copies of the fan lexicons
├── src/klazan/
│   ├── phonology.py           phonotactic rules, syllabifier, legality checks
│   ├── wordgen.py             candidate-root generator + "sounds dwarvish" scorer
│   ├── lexicon.py             load/validate/compile YAML → build/lexicon.json
│   ├── morphology.py          plural, tense, derivation suffixes (+ inverse)
│   ├── loan.py                deterministic English→Klazan loanword rule
│   ├── translate.py           English → Klazan (spaCy-based)
│   ├── gloss.py               Klazan → interlinear English gloss (for validation)
│   └── validate.py            "is this valid Klazan?" checker
├── tools/
│   ├── coverage.py            lemma-frequency + coverage report over a corpus
│   ├── review.py              batch review of proposed words (CSV in/out)
│   └── export_anki.py         flashcards for learning
├── tests/                     unit tests + golden sentence set
└── learn/                     cheat sheet, phrasebook, graded readers
```

The package is pip-installable (uv, Python ≥3.12, matching dwarfgpt). dwarfgpt
consumes it as a path dependency (`uv add --editable ../klazan`).

---

## Phase 1: Phonology and orthography (week 1)

**Deliverables:** `spec/phonology.md`, `src/klazan/phonology.py`, `src/klazan/wordgen.py`

1. **Measure the sources.** Tokenize the Khazalid and Zharralid word lists from
   `references/raw/`. Compute letter and digraph frequencies, onset and coda cluster
   inventories, syllable counts, and word-final distributions. This turns
   "sounds like Khazalid" into numbers.
2. **Fix the inventory.** Proposed starting point, to confirm against step 1:
   - Consonants: `b d g k t (p rare) f v s z sh zh th kh h m n ng l r w y`
     (`kh` = /x/, `r` rolled)
   - Vowels: `a e i o u`, weighted toward a / u / o
   - Onsets: single C, or `br dr gr kr tr thr bl gl kl sk st sh zh kh dh`
   - Codas: `k g z r n l m d t th sh zh rn rk rg nd ng nk st zk`
   - Syllable: (C)(C)V(C)(C). Roots are mostly 1–2 syllables.
   - Stress: always on the first syllable of the root (suffixes never take stress)
3. **Orthography:** plain ASCII Latin only, with the digraphs `kh zh sh th dh ng` and
   no diacritics. This is good for the BPE tokenizer and for typing. Runes can come
   later as a pure display post-processor, as Cirth was planned for NKh.
4. **Word generator.** Generate candidates from the phonotactic grammar, then
   filter and rank them by:
   - legality (phonotactics)
   - **dwarvishness**: character-trigram log-likelihood under a model trained on the
     Khazalid+Zharralid lists
   - **distinctness**: edit distance ≥2 from every existing Klazan word (≥3 for
     the 500 most frequent words)
   - **not accidentally English**: reject candidates that are English words, or close
     to them, and anything offensive
   - **not accidentally Games Workshop**: reject exact matches to source words
     unless the word is on the borrow list
   - **length by frequency** (Zipf): the most frequent meanings get the shortest forms
5. **Listening check.** Generate about 20 sample sentences for you to read aloud.
   Optionally pipe them through `espeak-ng` with a phoneme mapping so you can hear them.

**Gate:** you read the samples and say "yes, that's the sound". Iterate on the
weights and inventory until that's true. This is the cheapest place to change course.

---

## Phase 2: Grammar spec (week 1–2)

> **Superseded (2026-09-27)** by the draft [`spec/grammar.md`](spec/grammar.md),
> with its function words in `lexicon/function.yaml`. The main changes from the
> sketch below:
> - numerals go *before* the noun
> - the past of `zu` is `zad`
> - question words are the `wor-` series
> - present tense is the bare root
>
> The sketch is kept for history.

**Deliverable:** `spec/grammar.md`, the normative spec. The translator, validator,
and glosser all implement exactly this document. Proposed contents; word forms
marked *TBD* get chosen in Phase 3:

**Word order and phrases**
- SVO. Adjectives, numerals-as-adjectives and relative clauses follow the noun:
  `ta dawi gorm` "the old dwarf".
- Articles: `ta` (the) and `un` (a/an), both invariant.
- Genitive: `ta khaz a ta rik` "the hall of the king". English `'s` is rewritten to this.
- Possessive determiners come before the noun and are formed regularly from
  pronoun + `-a`, e.g. `ora khaz` "my hall".
- Compounds are modifier-first and written joined (Khazalid style):
  `dammazkron` "grudge-book". The lexicon uses them for fixed concepts only.

**Nouns**
- Plural: `-i` after consonants, `-n` after vowels (`az → azi`; exact rule TBD in
  Phase 1 after listening). No case and no gender.

**Pronouns** (no case; object = subject form)
- 1sg `or`, 2sg *TBD*, 3sg `ek` (one pronoun for he/she/it, like Finnish *hän*),
  1pl `ut`, 2pl `af`, 3pl `um`. These are Khazalid function words, adapted.
- The English gender distinction is dropped on the Klazan side. This is intentional
  and simple to learn, but lossy on round-trip.

**Verbs** (one regular conjugation; no person/number agreement)
- Bare root = present / infinitive / imperative. (Decided 2026-09-27: a present
  `-it` on every verb got repetitive.)
- Past `-ad`, progressive `-en` (Khazalid "ongoing")
- Future: particle `an` + root (Khazalid). Conditional/"may": `sar` + root.
- Perfect ("has gone") collapses to past in v1. It can be added later if missed.
- Copula `zu` (Zharralid), conjugated regularly
- Passive: `zu` + past form: `ta az zad grunad` "the axe was forged"
- Negation: `nai` directly before the verb (Khazalid). No do-support.
- Questions: sentence-initial particle `wan` (Khazalid) plus declarative order.
  No inversion.

**Derivation ("signifiers")**, the vocabulary multiplier, adapted from Khazalid:

| Suffix | Meaning | Example (illustrative) |
|---|---|---|
| `-az` | place of X | `grun` forge (v) → `grunaz` smithy |
| `-ki` | person who does X (Zharralid *ki* = smith) | `grunki` smith |
| `-ul` | art / craft / discipline of X | `grunul` smithcraft |
| `-ak` | abstract quality/concept | `grom` brave → `gromak` bravery |
| `-rak` | "like X", adjective from noun (Khazalid *durak*) | `kurn` stone → `kurnrak` hard |
| `-ash` | verb from noun; also the loanword verb ending (Zharralid) | `dammaz` → `dammazash` to hold a grudge |

Every suffix is reversible, so `gloss.py` can always decompose a word.

**Numbers:** digits pass through unchanged (`3` stays `3`). Number *words* are
1–12, 100 and 1000, base 10. Keeping Khazalid's base 12 is fun but makes
translation error-prone. Listed as an open question.

**Proper nouns** pass through unchanged. The corpus filter caps how many are allowed.

**Gate:** you can translate 20 English sentences by hand using only `grammar.md` and
a draft word list, and none of them requires a judgment call the spec doesn't cover.

---

## Phase 3: Lexicon (weeks 2–3)

**Deliverables:** `lexicon/*.yaml`, `lexicon.py`, `tools/coverage.py`, `tools/review.py`

**Entry format** (YAML, one entry per sense):

```yaml
- kz: grun
  en: forge
  pos: VERB
  tier: core
  origin: invented        # borrowed | invented | derived | loan
  root: grun
  derivation: null        # e.g. "grun+az" for grunaz
  notes: "also used for 'craft' in compounds"
  added: v0.1
```

**Tiers:**

| Tier | Size | How it's made |
|---|---|---|
| Function | ~150 | Hand-picked together: pronouns, articles, prepositions, conjunctions, particles, question words, numbers. Shortest forms. Several come from Khazalid/Zharralid (`a`, `bin`, `un`, `nai`, `ta`, `zu`, `wan`, `or`, `ek`, `ut`) |
| Core | ~500 | Hand-curated with Claude: the words you learn first. Contains the 30–60 borrowed iconic words; the rest come from `wordgen` candidates, and you pick or veto them. |
| Extended | ~2K–5K | Claude proposes batches of 100–200: a **derived** form from an existing root where it's semantically natural (smithy = `grunaz`), otherwise a new `wordgen` root. You review in `review.py` (CSV: accept / reject / edit). |
| Loan fallback | ∞ | `loan.py`: deterministic Zharralid-style adaptation of any other English word (Latinate stems → dwarvish spelling + class suffix, e.g. *victory* → `viktraz`, *dominate* → `domitash`). Always produces *something*; tracked as a quality metric. |

**Which English words get entries** is driven by data, not intuition.
`coverage.py` runs spaCy over a sample of each target corpus, counts
(lemma, POS) pairs, and reports how many entries reach 95 / 97 / 99% token
coverage. Rough expectations:
- TinyStories: about 1.5K lemmas gives about 98%. This is the first corpus.
- Simple-English Wikipedia or filtered FineWeb-EDU: about 5K for 95%, plus the loan fallback

**Polysemy:** one Klazan word per (English lemma, POS) by default. Only
high-frequency, genuinely distinct senses get split, and only where spaCy POS
separates them. Real word-sense disambiguation is out of scope for v1.

**Validation run by `lexicon.py` on every build:** unique forms, phonotactic legality,
distinctness thresholds, every derivation resolves, no borrowed word outside the
allowlist, no English lemma mapped twice for the same POS.

**Gate:** ≥97% token coverage on TinyStories without the loan fallback, and the
core 500 are approved by you.

---

## Phase 4: Translator (weeks 3–4)

**Deliverables:** `translate.py`, `gloss.py`, `validate.py`, golden test set

Pipeline for English → Klazan, using the spaCy `en_core_web_trf` parse (or `_sm`
for speed at corpus scale; benchmark both):

1. **Parse**: tokens, lemmas, POS, morphology (Tense, Number, Aspect), dependencies.
2. **Restructure clauses**:
   - collapse auxiliaries: *will go* → `an git`, *did not go* → `nai gitad`,
     *was going* → progressive+past, *has gone* → past
   - drop do-support
   - questions become `wan` + declarative order
   - passives become `zu`+past
3. **Restructure noun phrases**: move `amod`/`nummod`/relative clauses after the
   head noun, turn `poss` 's into `a`-genitives, turn possessive pronouns into `-a` forms.
4. **Look up and inflect**: lemma+POS → lexicon; add plural/tense suffixes; loan
   fallback on a miss; proper nouns and digits pass through.
5. **Surface**: preserve sentence punctuation and capitalization; detokenize.

Reverse direction: `gloss.py` produces an interlinear morpheme gloss
(`ta dawi gorm grun-ad …` → `the dwarf old forge-PAST …`). It serves validation
and learning, not as a fluent back-translator.

`validate.py` checks that every token is a lexicon word plus legal suffixes, a
loan, a proper noun, a digit, or punctuation. By construction it should pass
100% of translator output. A failure means a translator bug.

**Testing:**
- unit tests per rule
- a **golden set of ~100 sentences** you hand-translate from `grammar.md` in Phase 2–3
- a regression snapshot on 1K TinyStories sentences, so grammar changes show up
  as diffs you can eyeball

**Gate:** ≥95% exact match on the golden set, loan rate <3% of tokens on
TinyStories, and throughput high enough for the corpus (target ≥5K sentences/sec
with `_sm` + `nlp.pipe` across cores).

---

## Phase 5: Corpus generation (handoff to dwarfgpt)

**Deliverable:** versioned, validated Klazan shards that dwarfgpt's tokenizer and
pretraining phases consume, plus parallel en/kz pairs for SFT.

**How to run it on any machine:** [`docs/corpus_runbook.md`](docs/corpus_runbook.md).
In short:

```
fetch_data.py all  ->  corpus.py translate  ->  corpus.py pack
```

This is fully resumable, parallel across cores, and stamped with a lexicon/code
fingerprint.

### 5a. TinyStories (ready to run)

- **Input:** `TinyStoriesV2-GPT4-train.txt` (2.2 GB, about 2.7M stories, about 470M words).
  Translating all of it takes roughly 2–3 hours on 8 workers.
- **Measured on 2,000 validation stories** with the current lexicon:

  | | Loan rate | Stories kept |
  |---|---|---|
  | Before filtering | 2.65% (median story 2.1%) | — |
  | Per-story cap 5% (**the default**) | **1.9%** | 82% |
  | Per-story cap 3% | 1.2% | 63% |

  The unknown token count was 0.
- **Filters** (`corpus.py pack`):
  - loan rate ≤ 5% per story
  - ≥ 20 words
  - no unknown tokens
  - exact dedupe on normalized English
  - 5% held out for validation, chosen by a hash of the English text, so it's stable across re-packs
- **Output:**

  | Path | Contents |
  |---|---|
  | `packed/kz/{train,val}/shard_*.parquet` | A `text` column, row groups of 1024, the nanochat pretraining layout. |
  | `packed/parallel/{train,val}.jsonl` | `{id, en, kz}` pairs |
  | `pack_manifest.json` | fingerprint, git commit, input SHA-256, filters, counts |
  | `REPORT.md` | stats, plus the top 100 loans. That's the worklist for an optional lexicon batch 3. |

- **Volume:** dwarfgpt's target of 30–80M Klazan tokens is roughly the first
  15–40% of the packed train split. The mix ratio is chosen on the dwarfgpt side.

### 5b. Dwarf-genre English (not built yet; needs an API budget decision)

Claude writes short English texts in the dwarf genres, and they're then translated
deterministically, so no model ever writes Klazan. The genres are the 9 buckets from
the dwarfgpt plan: mining, lineages, oaths/curses, sagas, songs, smithing, riddles,
greetings and chronicles.

- **Vocabulary:** prompts are restricted to the lexicon's English side (the
  `lexicon status` word list, plus the dwarf extras), so the loan rate stays low.
- **Cost:** about $20–60 via the Batch API, for a few million words.
- **Tooling:** would be `tools/genre.py`, writing TinyStories-format text into
  `data/raw/genre.txt`. `corpus.py translate --source genre` then handles the rest
  unchanged.

**Decision needed from you before building it:** the budget, and whether genre text is a
separate shard set (recommended, so its share can be tuned in the mix) or folded into
TinyStories.

### 5c. Broader English (later, optional)

Simple Wikipedia or FineWeb-EDU slices, filtered by the same loan-rate cap. The
current lexicon is TinyStories-shaped, so expect much higher loan rates here until
the lexicon grows an extended tier.

### Freezing the language for a run

A corpus is tied to one fingerprint. The workflow is:

1. finish any lexicon edits
2. commit and push
3. note `python -m klazan.lexicon fingerprint`
4. run

`corpus.py translate` refuses to add shards made with a different fingerprint to an
existing output directory. Changing the language later is cheap: re-run into a new
directory, since translation is deterministic.

---

## Phase 6: Learning materials (parallel, low effort)

These are generated from the lexicon and translator, so they stay in sync automatically:
- 1-page grammar cheat sheet (from `grammar.md`)
- Anki deck of the function + core words (`export_anki.py`)
- Phrasebook: greetings, oaths, insults, toasts, drinking songs
- Graded readers: TinyStories in Klazan with an interlinear gloss toggle

---

## Changes to the dwarfgpt plan

| dwarfgpt phase | Change |
|---|---|
| 0: Sentence Maker port | **Retired.** Tag the last NKh commit (e.g. `nkh-final`) and move `khuzdul_translator/`, the `.xlsm` files and NKh `data/` to an `archive/` folder or leave them on a branch. The nanochat-baseline half of Phase 0 is unchanged. |
| 1: Corpus assembly | **Replaced** by Klazan Phases 1–3. The seed corpus is no longer needed. |
| 2: Translator pipeline | **Stage A only** = `klazan.translate`. Stage B (LLM naturalization) and Stage C (cross-provider round-trip) are dropped. New gate: Phase 4 gates above instead of BLEU ≥25. |
| 3: Synthetic data | Becomes Klazan Phase 5. API spend drops from ~$80 to ~$20–60 (English dwarf-genre text only). |
| 4: Tokenizer | Unchanged. The ASCII orthography and regular suffixes should compress well, so recheck the ≥4.0 chars/token target. |
| 5: Training runs | Unchanged (control, 5/10/20% mix, SFT, optional d26). |
| 6: Eval harness | Layer 2 (grammar checker) becomes `klazan.validate`, which is exact. Layer 3 (LLM judge) is dropped, since no LLM knows Klazan; use a **gloss-based** check instead. Layer 4 round-trip: model translates EN→KZ and is scored against `klazan.translate` output (exact match / chrF), which works because the reference translator is deterministic. |
| 7: Human eval | Shrinks to *you* (the only speaker) plus maybe a few Warhammer-fan friends reading glossed samples. |
| 8: Writeup | Reframe as "a small LM learns a synthetic, English-adjacent dwarf language". Include an ablation on how many Klazan tokens it takes to reach X% exact-match translation. |

---

## Release posture

- Keep "Warhammer", "Khazalid", "Zharralid" and "Games Workshop" out of model, repo,
  dataset, and org names. Describe the language as *"inspired by fan-documented
  dwarf languages in tabletop fantasy"* and credit the fan lexicon compilers
  (Alebelly Cragfist, Suspicious Entity) in the README.
- Keep borrowed words to a small, explicit `origin: borrowed` allowlist so
  the exposure is auditable and easy to swap out if ever needed.
- Don't redistribute `references/raw/` (it's gitignored).
- Lexicon/spec: CC BY 4.0 (or your preference). Code: MIT. Weights: as in the dwarfgpt plan.

---

## Milestones

| Milestone | Gate | Status |
|---|---|---|
| Phonology spec + `wordgen` + ~20 sample sentences | You approve the sound | ✅ approved |
| `grammar.md` v0.1 + function words + first ~150 core words | Hand-translate 20 sentences with no spec gaps | ✅ 39 spec examples are machine-checked instead |
| Core 500 approved, extended tier to ~1.5K, `coverage.py` | ≥97% TinyStories coverage | ✅ 97.08% (1,155 words) |
| Translator + gloss + validator + golden set | ≥95% golden exact match, <3% loans | ✅ 97.5% exact, 2.65% loans. The golden set is the spec's 40 examples; your 100 hand-translated sentences are still open. |
| TinyStories shards generated (+ genre shards) | Audit passes; handed to dwarfgpt Phase 4 | ⏳ tooling ready; run on the desktop via the runbook |

---

## Open questions (non-blocking; decide as we go)

1. ~~**Name of the language.**~~ **Decided 2026-09-28: Klazan.** The working name
   was *Dammaz*, which is Khazalid for *grudge* and a well-known GW word. The new
   name comes from our own lexicon: `klazandof` is *word*, so `klazan` reads as
   "the word". `dammaz` stays in the lexicon as the borrowed word for *grudge*.
2. **Runes.** Should there be a Klazan rune script (display-only), and should it
   reuse the Klinkarun idea?
3. **Dwarf-genre budget** (Phase 5b): how much API spend, and a separate shard set or not.
4. **Transformer parser.** `en_core_web_trf` would fix the small model's rarer tagging
   errors (e.g. *beardling* read as a verb), at maybe 5–10× the translation time. It's
   worth an A/B on 1,000 stories before a final corpus.

Resolved since the first draft:

| Question | Resolution |
|---|---|
| Number base | Base 10 |
| Formal *you* | `uzar` |
| Perfect aspect | Merged into the past |
| Diminutive | `-it` |

## Immediate next steps

1. **On the desktop:** follow [`docs/corpus_runbook.md`](docs/corpus_runbook.md),
   i.e. set up, fetch, dry run, full TinyStories run, pack, sanity checks.
2. **Hand off** `packed/` to dwarfgpt and start its Phase 0 (nanochat fork +
   baseline) and Phase 4 (tokenizer) there.
3. **Optional, any time:** lexicon batch 3 from the `REPORT.md` loan list
   (`tools/review.py propose`), which pushes the loan rate below ~2% before filtering. It
   needs a fresh corpus run afterwards (new fingerprint).
4. **Decide Phase 5b** (dwarf-genre text): budget and shard layout.
