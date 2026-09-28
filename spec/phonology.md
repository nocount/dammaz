# Klazan phonology and orthography (v0.1, draft)

The machine-readable version is [`src/klazan/data/phonology.yaml`](../src/klazan/data/phonology.yaml).
`klazan.phonology.check_root()` enforces it. The measurements behind the choices are in
[`phonology_analysis.md`](phonology_analysis.md).

## Design summary

The sound is a **Khazalid core with Zharralid color**:

- **From Khazalid:**
  - hard k, g, r, z
  - opening clusters like `gr- dr- kr- thr- skr-`
  - mostly closed, 1–2 syllable roots
  - endings like `-az -ak -ul -ar -ung -und`
- **From Zharralid:**
  - `sh`, `zh`, `dh` (boosted well above their source frequency)
  - more words ending in a vowel, especially `-a` and `-u`. About 1 root in 4 ends in a vowel, vs. 1 in 5 in Khazalid and 2 in 5 in Zharralid.

## Letters

Plain ASCII. 21 letters: `a b d e f g h i k l m n o r s t u v w y z`.
There is no `c`, `j`, `p`, `q` or `x`. Borrowed words may keep their source spelling
(`dammaz`).

| | |
|---|---|
| Vowels | `a` (*father*), `e` (*bed*), `i` (*machine*), `o` (*more*), `u` (*rule*). They are always pronounced, never silent. `a` is by far the most common (target ~38%), then `u`, `o`, `i`, `e`. |
| Plain consonants | `b d g k t f v s z h m n l r w y`. `g` is always hard, `s` always voiceless, `r` rolled or tapped, `y` always a consonant (*yes*). |
| Digraphs | `kh` (*loch*), `zh` (*measure*), `sh` (*ship*), `th` (*thin*), `dh` (*this*), `ng` (*sing*). Each digraph is one sound. |

## Stress

Stress always falls on the **first syllable of the root**. Suffixes are never
stressed: `KA-rak`, `DRASH-ad`, `UN-guz-ad`.

## Root shape

```
root = initial  V  (medial V)*  final
```

| Slot | Legal values |
|---|---|
| **initial** | nothing (vowel-initial), any single consonant except `ng`, or one of: `gr dr kr br tr fr thr khr dhr kl gl fl sk skr st str sl sm dw kv` |
| **V** | exactly one vowel. There are no diphthongs and no vowel-vowel sequences. |
| **medial** | an optional coda consonant followed by an optional legal initial, at most 3 consonants in total (e.g. `r`, `zk`, `ng.r`, `n.dr`, `l.kh.r`) |
| **final** | nothing (vowel-final), a single consonant from `k g z d t n m l r ng f s sh zh th kh b`, or one of: `nd nk nt rn rk rg rm rl rd ld lk lg zk rz` |

Additional constraints:

- **No doubled consonants** (`zz`, `rr`) in native roots.
- **No spellings that misparse as digraphs**, e.g. `n`+`g`, `s`+`h`, `k`+`h`.
  `h` only appears word-initially or between vowels.
- **Weight limit:** across a whole word, the "extra" consonants in clusters
  (cluster size minus 1) may total at most **2**. So `drekrazal` is fine, and
  `ongrondror` is too heavy.
- **Reserved endings:** roots may not end in `-i`, `-ad`, `-en`, `-ki` or `-it`,
  because those are inflectional or agent suffixes. This keeps every inflected
  form unambiguous. The list will be revisited when `grammar.md` is written.

## Word length (Zipf)

The most frequent meanings get the shortest forms:

| Word type | Typical shape |
|---|---|
| Function words | 1 syllable, often just V, VC or CV |
| Core vocabulary | 1–2 syllables |
| Rarer words | 2–3 syllables, or built from roots by derivation |

## Word generation

`klazan.wordgen` samples roots slot by slot. Frequencies come from the measured
Khazalid/Zharralid statistics, blended 70/30 and re-weighted by the `style` knobs
in the yaml. Every candidate must then pass these checks:

| Check | What it does |
|---|---|
| Legality | Must satisfy `check_root`. |
| Dwarvishness | A segment-trigram model trained on the source words scores each word. The score is reported as a 0–100 percentile against typical generator output, and candidates below 30 are dropped. Selection above that floor is *random*, not top-ranked, so the Zharralid-flavored words aren't crowded out. |
| Not English | Not in the wordfreq top 50K, and not profane or a sound-alike. |
| Not a copy | Not identical to any Khazalid/Zharralid word. Borrowing is a deliberate lexicon decision. |
| Distinct | Edit distance ≥2 from every existing Klazan word. |
| Soft flags | Shown to the reviewer, not rejected: within one edit of a common English word (5+ letters only) or of a source word (4+ letters only). |

## Open items

- **Inflected forms** also need English/profanity checks. The plural of `khaz` is `khazi`
  (British slang for toilet), so this goes into the lexicon validator in Phase 3.
- **Suffixes after consonant clusters** (e.g. `zint` + `-ki` gives `ntk`) may need an
  epenthetic vowel. This gets decided in `grammar.md`.
- **Runes** are a later, display-only layer.
