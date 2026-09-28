# Reference sources

Both source languages are Games Workshop IP (Warhammer Fantasy / Total War:
Warhammer III). We use them for **sound and structure inspiration** and a small,
documented set of borrowed words — see `lexicon/` `origin: borrowed`.

Raw copies live in `references/raw/` (gitignored, fetched 2026-09-27).

| Source | What it is | Size | Local copy |
|---|---|---|---|
| [Khazalid Lexicon (Bugman's Brewery)](https://www.bugmansbrewery.com/d/43504-khazalid-lexicon) — repost of Alebelly Cragfist's guide ([Wayback original](https://web.archive.org/web/20230219185211/http://www.bugmansbrewery.com/tutorials/article/114-dwarf-language-khazalid-a-definitive-guide/)) | Official + fan Khazalid words, the root+signifier system, tense system, function words, numerals | ~450 entries | `raw/khazalid_lexicon_alebelly.txt` (fetched via the forum's `/api/discussions/43504` JSON endpoint) |
| [Zharralid Dictionary (chaos-dwarfs.com)](https://discourse.chaos-dwarfs.com/t/zharralid-dictionary/26353) | Repost of the Steam guide below, plus example sentences and a rank list | ~250 entries | `raw/zharralid_lexicon_suspicious_entity.txt` (fetched via `/raw/26353`) |
| [Zharralid Steam guide (Suspicious Entity)](https://steamcommunity.com/sharedfiles/filedetails/?id=2965970849) | Reverse-engineered from TW:WH3 subtitles; many words marked `(?)` or AI-derived | same as above | — |

## Structural takeaways

**Khazalid**
- Short (often 1-syllable) roots + stackable suffix "signifiers":
  `ska` (theft) → `skaz` thief, `ski` thieves, `skit` steal, `skak` the concept of
  theft, `skul` the art of theft, `sken` stealing (ongoing), `skal` a group of thieves.
- Place suffix `-az` (`kar` big stone → `karaz`), people/profession `-i`.
- Tense: present `-it`, past `-ed`; preverbal particles `an` (will), `ad` (did),
  `sar` (may). Question particle `wan` at sentence start.
- Function words: `a` of/with, `bin` in/on, `un` and, `nai` no, `nu` now,
  `or` I, `ek` he/she/it/you, `ut` we, `af` you (pl), `um` them.
- Compounds are modifier-first: `Dammaz Kron` "grudge book", `Grobkaz` "goblin work".
- Sound: hard K/G/R/Z starts, clusters `gr- dr- kr- thr- kh- zh-`, closed
  syllables, endings `-az -ak -ul -in -i -ar -rak -ril`.
- Base-12 numerals: ong, tuk, dwe, fut, sak, siz, set, odro, nuk, don, (11?), duz.

**Zharralid**
- Mostly SVO: *Magran Gorahk zu Grat!* "My kingdom is great!"
- Copula `zu`, article `ta`, `na` no, `ba` but, `den` then, `va` now, `iez` I, `uzum` you.
- Heavy use of dwarvified English loans: `victraz`, `domitash`, `subjorgitash`,
  `intimidash`, `azept` → a precedent for a deterministic **loanword rule**.
- Sound: more `sh`/`zh`/`dh`, endings `-ash -ak -ok -u -a`, rolled R.
