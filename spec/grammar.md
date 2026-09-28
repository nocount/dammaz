# Dammaz grammar (v0.1, draft)

This is the **normative** grammar. The translator (`dammaz.translate`), the
glosser and the validator implement exactly what this document says, and
anything they do that isn't written here is a bug in one or the other. It
supersedes the Phase 2 sketch in `PLAN.md`.

| | Lives in |
|---|---|
| Suffix mechanics | [`src/dammaz/morphology.py`](../src/dammaz/morphology.py) |
| Function words | [`lexicon/function.yaml`](../lexicon/function.yaml) |
| Sounds and spelling | [`phonology.md`](phonology.md) |

**Examples** use the placeholder vocabulary in
[`samples/vocab_v0.yaml`](../samples/vocab_v0.yaml). Every `dz` example block is
checked by `tests/test_grammar_examples.py`: each word must be known, each
`word-TAG` gloss must match what `morphology.inflect` produces, and the gloss must
have one entry per word.

**Gloss abbreviations:**

| Tag | Meaning | Tag | Meaning |
|---|---|---|---|
| PL | plural | PST | past |
| PROG | progressive | FUT | future (`an`) |
| COND | conditional (`sar`) | Q | yes/no question (`wan`) |
| NEG | negation (`nai`) | REL | relativizer (`zo`) |
| AGT | agent | PLACE | place |
| CRAFT | craft | ADV | manner adverb |
| THING | thing/quality | LIKE | X-like |
| VBZ | verbalizer | TIME | time |
| REASON | reason | POSS | possessive |
| CMP | comparative | ORD | ordinal |
| FML | formal (`uzar`, §4.1) | DIM | diminutive (§3.7) |

---

## 1. At a glance

- **Word order:** Subject–Verb–Object, prepositions, and nouns *before* their
  adjectives: `ta dawi dhal` "the old dwarf".
- **No agreement:** verbs don't change for person or number, and adjectives and
  articles don't change at all.
- **No grammatical gender, no case:** `or` is both "I" and "me", and `ek` is "he", "she" and "it".
- **Suffixes only**, each with one job, attached in a fixed order (§2).
- **No irregular forms.** Even the copula `zu` is regular (`zu`, past `zad`).

```dz
Ta dawi dhal drashad un az krang bin ta karak.
the dwarf old forge-PST a axe strong in the mountain
"The old dwarf forged a strong axe in the mountain."
```

In glosses, `forge-PST` means "the word for *forge* + the past suffix". Written
Dammaz never hyphenates suffixes.

---

## 2. Words and suffixes

### 2.1 Suffix inventory

| Suffix | Tag | Meaning | Example |
|---|---|---|---|
| `-i` / `-n` | PL | plural (`-n` after a vowel) | `az → azi`, `dawi → dawin` |
| `-ad` | PST | past | `truk → trukad` |
| `-en` | PROG | ongoing, "is ...ing" | `truk → truken` |
| `-ki` | AGT | person who does X | `drash → drashki` smith |
| `-az` | PLACE | place of X | `drash → drashaz` smithy |
| `-ul` | CRAFT | art or craft of X | `drash → drashul` smithcraft |
| `-ul` | ADV | in an X way (adverb) | `krang → krangul` strongly |
| `-ak` | THING | thing, quality or concept of X | `krang → krangak` strength |
| `-rak` | LIKE | X-like (adjective from noun) | `kurm → kurmarak` stony |
| `-ash` | VBZ | verb from noun | `iza → izash` to sing |
| `-ur` | TIME | time (correlatives, §5) | `zid → zidur` now |
| `-os` | REASON | reason (correlatives, §5) | `wor → woros` why |
| `-a` | POSS | possessive (pronouns, §4) | `or → ora` my |
| `-it` | DIM | small, young or dear X (§3.7) | `dawi → dawit` little dwarf |
| `-ar` | CMP | comparative (§7) | `gorz → gorzar` bigger |
| `-ik` | ORD | ordinal (§9) | `tuf → tufik` second |

CRAFT and ADV share the form `-ul`: both mean "the way of X".

### 2.2 Order

```
root  +  derivation*  +  (CMP | ORD)?  +  (PL | PST | PROG)?
```

Any number of derivational suffixes come first, then at most one degree
suffix, then at most one inflection. There is never more than one inflectional
suffix, so a plural past is impossible, and a past-tense noun isn't a thing.

```dz
Ta drashkin krez.
the forge-AGT-PL work
"The smiths work."
```

### 2.3 Joining rules

1. **Plural**: add `-i` after a consonant, `-n` after a vowel.
2. **Elision**: a suffix starting with a vowel drops a vowel at the end of the
   stem: `iza + ash → izash`, `zu + ad → zad`. This is the Khazalid rule
   (*ska + az → skaz*).
3. **Epenthesis**: a suffix starting with a consonant that would create an
   illegal consonant cluster (by the medial-cluster rules in `phonology.md`) gets
   a linking **`a`**: `grund + ki → grundaki`, `kurm + rak → kurmarak`.
4. Identical consonants may meet across a boundary: `zuk + ki → zukki`.
5. No suffix begins with `h` or `g`, so a suffix can never accidentally form a
   digraph with the stem.

**Stress** stays on the first syllable of the root: `DRASH-ki-n`, `I-zash-ad`.

**Uniqueness:** the Phase 3 lexicon validator generates every inflected and
derived form of every word. It rejects the lexicon if two different analyses
produce the same spelling, or if a form is an English or profane word
(e.g. `khaz + PL = khazi`).

---

## 3. Nouns and noun phrases

### 3.1 Order inside a noun phrase

```
[determiner | possessive | quantifier]  [numeral]  NOUN  [adjective*]  [a + noun phrase]  [relative clause]
```

Things that *count or point* go before the noun. Things that *describe* go after it.

```dz
ta tuf azi krang
the two axe-PL strong
"the two strong axes"
```

```dz
zid khaz orn a ta rik
this hall deep of the king
"this deep hall of the king"
```

Several adjectives keep their English order (`ta az gorz dhal` "the big old axe").
Adjectives never agree with the noun.

### 3.2 Articles

`ta` "the" and `un` "a/an, one" are invariant. English "some" and a bare plural
are both expressed with no article. `un` is also the numeral 1.

### 3.3 Plural

Plural is marked on the noun, always, even after numerals and quantifiers:
`tuf azi`, `gom dawin`, `drur skrekan`.

### 3.4 Possession ("of", 's)

The possessed thing comes first, then `a` + the possessor. English `'s` is
rewritten this way.

```dz
Ta grund a ta rik zu gorz.
the hammer of the king be big
"The king's hammer is big."
```

```dz
ta az a Borin
the axe of Borin
"Borin's axe"
```

### 3.5 Noun + noun compounds

English noun-noun compounds become an `a` phrase **without an article**:
*stone gate* becomes `dwan a kurm` "gate of stone". Fixed, lexicalized concepts
are single words in the lexicon (written joined, modifier first, Khazalid style,
e.g. `dammazkron` "grudge-book").

### 3.6 Proper nouns

Names pass through unchanged and keep their capital letter: `Borin`, `Lily`,
`Karak Azgal`. They never take suffixes; possession uses `a` + name (§3.4).

### 3.7 Diminutives: `-it`

`-it` makes a **small, young or dear** version of a noun, like Spanish *-ito/-ita*.
It is a derivational suffix, so the plural comes after it (`dawit → dawiti`):

| Diminutive | Meaning |
|---|---|
| `dawi → dawit` | little dwarf, dwarf child |
| dog → *puppy* | young animal |
| cat → *kitten* | young animal |
| child → *kid* | young/informal |
| mom → *mommy* | affectionate (hypocoristic) |

```dz
Ta dawit glokad bral.
the dwarf-DIM drink-PST ale
"The beardling drank ale."
```

```dz
Ora glangit an truk zol ut.
I-POSS dog-DIM FUT go with we
"My puppy will go with us."
```

**Lexicalized vs. productive.** English words that are diminutives (*puppy*, *kitten*,
*bunny*, *mommy*) are `-it` words in the lexicon, derived from their base. The
translator does **not** turn *little X* or *tiny X* into `-it`. Those stay as an
adjective, so size and affection remain the writer's choice.

The same stem can't also be a root: roots never end in `-it` (`phonology.md`).

---

## 4. Pronouns

| | Singular | Plural |
|---|---|---|
| 1st person | `or` I/me | `ut` we/us |
| 2nd person | `uz` you | `af` you (plural) |
| 2nd person, formal | `uzar` you | `uzar` you |
| 3rd person | `ek` he/she/it/him/her | `um` they/them |

- **No case, no gender.** English *he*, *she* and *it* all become `ek`.
- **Possessives** are the pronoun + POSS: `ora` my/mine, `uza` your, `uzara`
  your (formal), `eka` his/her/its, `uta` our, `afa` your (pl), `uma` their. They
  go before the noun, or stand alone: `Ta az zu ora.` "The axe is mine."
- **Reflexive** = possessive + `keb` "self": `ora keb` "myself", `eka keb`
  "himself/herself/itself".
- **Dummy subjects** (*it* in *it is dark*, *there* in *there was a dwarf*) are
  dropped, and the sentence starts with the verb (§6.3).

```dz
Or thizad ora keb bin ta gleth.
I see-PST I-POSS self in the gold
"I saw myself in the gold."
```

### 4.1 Formal *you*: `uzar`

`uzar` is `uz` + the comparative `-ar`, literally "greater you". It is the respectful
form of address, for **one person or many**, like German *Sie*. Its possessive is
`uzara` and its reflexive is `uzara keb`. Like every pronoun, it never changes the verb.

| Use `uzar` for | Use `uz` / `af` for |
|---|---|
| Kings, thanes, lords and clan elders | Friends, kin and equals |
| Ancestors and the gods | Children |
| Anyone owed respect for age (a long beard) | Enemies. Using `uz` to someone who is owed `uzar` is an insult. |
| Strangers of rank | |
| The words of an oath | |

```dz
Uzar zu ta rik a zid karak.
you.FML be the king of this mountain
"You are the king of this mountain."
```

```dz
Ora rik, wan uzar narg uzara az?
I-POSS king Q you.FML want your.FML axe
"My king, do you want your axe?"
```

**Translator note:** English doesn't mark formality, so the translator chooses.
The default is familiar `uz` / `af`. It uses `uzar` inside a stretch of dialogue
when the addressee is marked as someone owed respect:

- a vocative or title: *sir, madam, my lord, my lady, your majesty, your highness,
  king, queen, elder, master*
- a dialogue tag naming such a person as the addressee (*"…," she said to the king*)

Phase 4 will make the exact list and scope rules precise.

---

## 5. Correlatives: this / that / which / some / all / no

Six bases combine with five suffixes into one regular table. This is the
Dammaz version of *this, here, now, what, where, when, nobody, never…* The bare
base is a determiner (`zid az` "this axe", `wor az` "which axe").

| Base | + `-ak` thing | + `-ki` person | + `-az` place | + `-ur` time | + `-ul` manner |
|---|---|---|---|---|---|
| **`zid`** this | `zidak` this thing | `zidki` this person | `zidaz` here | `zidur` now | `zidul` like this |
| **`zuk`** that | `zukak` that thing | `zukki` that person | `zukaz` there | `zukur` then | `zukul` like that, so |
| **`wor`** which? | `worak` what | `worki` who | `woraz` where | `worur` when | `worul` how |
| **`sal`** some | `salak` something | `salki` someone | `salaz` somewhere | `salur` sometimes, ever | `salul` somehow |
| **`gom`** all | `gomak` everything | `gomki` everyone | `gomaz` everywhere | `gomur` always | `gomul` in every way |
| **`nar`** no | `narak` nothing | `narki` nobody | `naraz` nowhere | `narur` never | `narul` not at all |

Plus the reason words: `woros` "why", `zukos` "so, therefore", and the
conjunction `os` "because".

**Negative words:**

- **No double negatives.** A `nar-` word already negates. English *not ... any-*
  becomes either `nai ... sal-` or a `nar-` word, whichever the English used:

  ```dz
  Or nai thiz salak.
  I NEG see some-THING
  "I don't see anything."
  ```

  ```dz
  Or thiz narak.
  I see no-THING
  "I see nothing."
  ```

- **`nai` vs. `nar`:** `nai` negates a verb (and an adjective, §7.1), while `nar`
  is a determiner ("no dwarf" = `nar dawi`).

---

## 6. Verbs

### 6.1 Forms

| Form | Marking | `truk` "go" | Covers English |
|---|---|---|---|
| Plain | bare root | `truk` | present *go/goes*, infinitive *to go*, imperative *go!*, gerund *going* |
| Past | `-ad` | `trukad` | *went*, *was going*, *has gone*, *had gone* |
| Progressive | `-en` | `truken` | *is going* (present only) |
| Future | `an` + plain | `an truk` | *will go*, *is going to go*, *shall go* |
| Conditional | `sar` + plain | `sar truk` | *would go*, *might go*, *may go*, *could go* (hypothetical) |

Verbs never agree with their subject: `or truk`, `ek truk`, `um truk`.

```dz
Ta grobin vunad rof ta skungi skom.
the goblin-PL come-PST from the tunnel-PL dark
"The goblins came from the dark tunnels."
```

```dz
Ta skrekan khurken uta zakan!
the enemy-PL slay-PROG we-POSS brother-PL
"The enemies are slaying our brothers!"
```

```dz
Ut an unguz ta dammaz.
we FUT remember the grudge
"We will remember the grudge."
```

### 6.2 The copula `zu` "be"

`zu` is regular: present `zu`, past `zad`, future `an zu`, conditional
`sar zu`. It links a subject to an adjective, noun or place:

```dz
Ta khaz a ta rik zad orn.
the hall of the king be-PST deep
"The hall of the king was deep."
```

The English progressive's "be" disappears into `-en`: *he is going* becomes `ek truken`,
not `ek zu truken`.

### 6.3 Existentials and dummy subjects: verb first

*There is/was ...* and weather-type *it is ...* have no subject in Dammaz. The
sentence simply starts with the verb:

```dz
Zad un dawi dhal.
be-PST a dwarf old
"There was an old dwarf."
```

```dz
Zu skom.
be dark
"It is dark."
```

### 6.4 Verb chains: modals and "want to"

The Dammaz modals are ordinary verbs: `throk` "can", `dret` "must, have to",
`narg` "want", `harg` "have". They take a **plain** verb directly, with no "to":

```dz
Or narg truk dra ta karak.
I want go to the mountain
"I want to go to the mountain."
```

**Tense is marked once, on the first verb of the chain:** `Ek throkad drash`
"He could forge" (past ability), `Or an throk truk` "I will be able to go".
*Should* is `sar dret` (would-must).

**Purpose** uses `dra` + plain verb ("in order to"):

```dz
Ek trukad dra ta karak dra krez.
he go-PST to the mountain to work
"He went to the mountain to work."
```

### 6.5 Participles as adjectives

The past form after a noun works like an English past participle, and the
progressive works like an *-ing* participle:

```dz
ta az drashad
the axe forge-PST
"the forged axe"
```

```dz
ta dawi gloken
the dwarf drink-PROG
"the drinking dwarf"
```

### 6.6 Passive

`zu` + past form. The agent is introduced with `rof` "from/by":

```dz
Ta az zad drashad rof ta dawi.
the axe be-PST forge-PST by the dwarf
"The axe was forged by the dwarf."
```

### 6.7 Negation

`nai` goes directly before the **first** verbal element: the verb itself, a
modal, or the `an` / `sar` particle. There is no *do*-support.

```dz
Ta drashki nai kend dra ta elgin.
the forge-AGT NEG speak to the elf-PL
"The smith does not speak to the elves."
```

```dz
Or nai an truk.
I NEG FUT go
"I will not go."
```

### 6.8 Imperative and "let's"

The imperative is the plain verb with no subject. *Let's* is the `ut` + plain verb.
Negative imperatives use `nai`:

```dz
Truk! Nai truk! Ut truk!
go NEG go we go
"Go! Don't go! Let's go!"
```

A **formal imperative** keeps its subject, `uzar` + plain verb. It's a polite
request, like *please* or *would you*. The translator produces it from *please* +
imperative when the speaker addresses someone owed `uzar` (§4.1); the *please* is
absorbed into `uzar`:

```dz
Ora rik, uzar vun bin uzara khaz.
I-POSS king you.FML come in your.FML hall
"My king, please come into your hall."
```

---

## 7. Adjectives and adverbs

### 7.1 Position

- **Attributive** adjectives follow the noun (§3.1).
- **Predicate** adjectives follow `zu`.
- **Negating an adjective:** `nai` before it: `ta az nai krang` "the not-strong
  axe". Common opposites get their own words in the lexicon.
- **Intensifier:** `grak` "very" goes before the adjective or adverb:
  `grak krang` "very strong".

### 7.2 Comparison

- **Comparative:** `-ar`, and "than" is `rof`.
- **Superlative:** `ta` + the comparative, as in Romance (*el más grande*).

```dz
Ta karak zu gorzar rof ta khaz.
the mountain be big-CMP than the hall
"The mountain is bigger than the hall."
```

```dz
Zid karak zu ta gorzar.
this mountain be the big-CMP
"This mountain is the biggest."
```

English *more X* and *most X* use the same forms as *X-er* and *X-est*.

### 7.3 Adverbs

Manner adverbs are adjective + `-ul`: `krangul` "strongly", `dhalul` "in the old
way". Adverbs keep the position they had in the English sentence. The `-ul`
adverb normally ends the verb phrase:

```dz
Ek drashad ta az krangul.
he forge-PST the axe strong-ADV
"He forged the axe strongly."
```

---

## 8. Clauses

### 8.1 Basic order and objects

The order is **S V O**. An indirect object always comes *after* the direct object,
with `dra`. English *gave him the axe* becomes "gave the axe to him":

```dz
Um saldad ta az dra ek.
they give-PST the axe to he
"They gave him the axe."
```

### 8.2 Yes/no questions

Put `wan` in front of an ordinary statement. There is no inversion and no *do*.

```dz
Wan uz thiz ta gleth?
Q you see the gold
"Do you see the gold?"
```

Answers are `ai` "yes" and `na` "no".

### 8.3 Question-word questions

The `wor-` word goes first, then ordinary statement order. There is **no** `wan`
in these questions.

```dz
Woraz uz truken?
which-PLACE you go-PROG
"Where are you going?"
```

```dz
Worki drashad ta az?
which-AGT forge-PST the axe
"Who forged the axe?"
```

```dz
Wor az uz narg?
which axe you want
"Which axe do you want?"
```

**The one ordering rule to remember:** when the question word is what `zu` links to (*what is ...*,
*where is ...*, *who was ...*), `zu`/`zad` comes right after the question word,
just as in English:

```dz
Woraz zu ta az?
which-PLACE be the axe
"Where is the axe?"
```

### 8.4 Relative clauses: `zo`

A relative clause is `zo` + a clause with a gap, placed after the noun and its
adjectives. The same `zo` is used for people and things (*who, which, that*):

```dz
ta dawi zo drashad ta az
the dwarf REL forge-PST the axe
"the dwarf who forged the axe"
```

```dz
ta az zo ta dawi drashad
the axe REL the dwarf forge-PST
"the axe that the dwarf forged"
```

**Prepositions are never stranded or fronted.** Keep the preposition in place
and fill the gap with a pronoun:

```dz
ta dawi zo or kendad zol ek
the dwarf REL I speak-PST with he
"the dwarf I spoke with"
```

**Place and time relatives** use `woraz` and `worur`:
`ta khaz woraz ut glok` "the hall where we drink".

### 8.5 Complement clauses

"That"-clauses also use `zo`, and it is **never omitted**, even where English
drops *that*:

```dz
Or zork zo ek zu krang.
I know that he be strong
"I know (that) he is strong."
```

### 8.6 Adverbial clauses

These conjunctions introduce a full clause:

| Conjunction | Meaning |
|---|---|
| `os` | because |
| `mur` | if, whether |
| `worur` | when, while |
| `tand` | until |
| `gez` | before (also a preposition) |
| `rul` | after (also a preposition) |

The clause can come before or after the main clause, as in English:

```dz
Mur uz truk, or an truk.
if you go I FUT go
"If you go, I will go."
```

```dz
Ut skrafad tand ta grobin vunad.
we fight-PST until the goblin-PL come-PST
"We fought until the goblins came."
```

### 8.7 Coordination

`og` "and", `vel` "or" and `ba` "but" join words, phrases and clauses:

```dz
Kurm og zath, bral og iza.
stone and iron ale and song
"Stone and iron, ale and song."
```

---

## 9. Numbers

Base 10.

| | |
|---|---|
| 1–10 | `un`, `tuf`, `thra`, `kag`, `vam`, `sib`, `mok`, `gir`, `nund`, `zer` |
| 100 | `kunk` |
| 1000 | `thrul` |

- **Multiplying** joins with a hyphen, and **adding** is a sequence of separate
  words, biggest first: `tuf-zer` 20, `tuf-zer thra` 23, `thra-kunk` 300,
  `thrul tuf-kunk thra-zer kag` 1234. Bare `kunk` and `thrul` mean one hundred
  and one thousand.
- **Numerals go before the noun**, and the noun is plural: `thra azi` "three axes".
- **Ordinals** add `-ik` to the last word and act as adjectives after the noun:
  `ta khaz tufik` "the second hall", `unik` "first".
- **Digits pass through** unchanged: `3 azi`.

```dz
Ta rik harg tuf-zer thra azi.
the king have two-ten three axe-PL
"The king has twenty-three axes."
```

---

## 10. Writing conventions

- **Capitalization:** capitalize the first word of a sentence and proper nouns.
  Everything else is lowercase, including `or` "I".
- **Punctuation** and quotation marks follow the English source exactly.
- **Hyphens** appear only in compound numerals (and in glosses).
- **Lexicalized compounds** are written as one word.

---

## 11. English → Dammaz: translator summary

| English | Dammaz | § |
|---|---|---|
| *the / a, an / one* | `ta` / `un` / `un` | 3.2 |
| adjective + noun | noun + adjective | 3.1 |
| *X's Y*, *Y of X* | `Y a X` | 3.4 |
| *puppy, kitten, mommy…* | base + `-it` (`slin → slinit`) | 3.7 |
| noun-noun compound *stone gate* | `dwan a kurm` (no article) | 3.5 |
| plural *-s* | `-i` / `-n`, always marked | 3.3 |
| *he / she / it* | `ek` | 4 |
| *his / her / its* | `eka` | 4 |
| *himself* | `eka keb` | 4 |
| *there is/was X*, *it is dark* | `Zu/Zad X`, `Zu skom` | 6.3 |
| present *goes*, *go* | `truk` | 6.1 |
| *is going* | `truken` | 6.1 |
| *went, was going, has/had gone* | `trukad` | 6.1 |
| *will/shall go, is going to go* | `an truk` | 6.1 |
| *would / might / may go* | `sar truk` | 6.1 |
| *can go / could go (past ability)* | `throk truk` / `throkad truk` | 6.4 |
| *must go, has to go* / *should go* | `dret truk` / `sar dret truk` | 6.4 |
| *want to go* | `narg truk` | 6.4 |
| *(in order) to go* | `dra truk` | 6.4 |
| *is forged / was forged by X* | `zu drashad` / `zad drashad rof X` | 6.6 |
| *do/does/did not V* | `nai V` / `nai V-ad` | 6.7 |
| *don't V!* / *let's V* | `nai V!` / `ut V!` | 6.8 |
| *you* to a king/elder, *sir*, *my lord*… | `uzar`, possessive `uzara`; *please V* = `uzar V` | 4.1 |
| *very X* | `grak X` | 7.1 |
| *X-er than Y*, *more X than Y* | `X-ar rof Y` | 7.2 |
| *the X-est* | `ta X-ar` | 7.2 |
| *X-ly* | `X-ul` | 7.3 |
| *gave him the axe* | `sald ta az dra ek` | 8.1 |
| *Do you V?* | `Wan uz V?` | 8.2 |
| *What/who/where... do you V?* | `Worak/worki/woraz uz V?` | 8.3 |
| *Where is X?* | `Woraz zu X?` | 8.3 |
| *who / which / that* (relative) | `zo` | 8.4 |
| *the dwarf I spoke with* | `ta dawi zo or kendad zol ek` | 8.4 |
| *I know (that) S* | `Or zork zo S` | 8.5 |
| *not ... anything* / *nothing* | `nai ... salak` / `narak` | 5 |
| number words / digits | Dammaz numerals / unchanged | 9 |

### What Dammaz does not distinguish

These English distinctions are deliberately dropped, so a round trip back to
English can't recover them:

- *he / she / it*
- *I / me* (and all other case pairs)
- *went / was going / has gone / had gone*
- *could* as past ability vs. as a hypothetical (the translator always renders it
  as past ability, `throkad`)
- *a* vs. *one*
- *singular they* vs. plural *they*
- emphatic *do*

Dammaz also marks something English doesn't: **formality**. English *you* is
translated as:

- `uzar` when the addressee is owed respect (§4.1)
- otherwise `af` when the source is plainly plural (*you all*, *you guys*, *you two*,
  *you both*); *all* and *guys* are absorbed into `af`
- otherwise `uz`

### Translator conventions

These choices are made by `dammaz.translate` where English leaves a gap. Each one
is deterministic, so the same English always gives the same Dammaz.

| English | Dammaz | Why |
|---|---|---|
| *let me V* | `or an V` | An offer ("I will V"). *let's V* = `ut V` (§6.8). |
| *let* X *V* (allow) | `zhaf X V` | `zhaf` "let, allow" is a grammar verb. |
| Bare auxiliary: *Yes, I can.* / *I did.* / *She will.* | `throk` / *do*-`ad` / `an` *do* | Dammaz repeats a verb: the modal verb, or the lexicon's word for *do*. |
| *as* + clause (*as they walked*) | `worur` | Temporal *as* = *while*. *as* + noun (*as a gift*) = `lak`. |
| Dummy *it* | dropped | Only before *be* + a weather/time word: *dark, cold, hot, sunny, rainy, windy, late, early, night, day, morning, time…* |
| Formal address | `uzar` | Inside quotes that contain a respect cue (*king, queen, lord, lady, sir, madam, majesty, highness, elder, master, grandfather, grandmother*), or a whole unquoted sentence with a cue and *you/your/please*. |
| *please* + imperative in formal address | `uzar V` | The *please* is absorbed (§6.8). Elsewhere *please* is an ordinary word. |
| Kinship words used as names (*Dad said*, *Mummy!*) | translated, capitalized (`Nong kvizad`) | Real names (*Lily*, *Tom*) pass through untouched. |
| *first, second… tenth* | numeral + `-ik` | `unik`, `tufik`… (§9). |
| *once upon a time*, *a lot of*, *next to*… | phrase table | `lexicon/phrases.yaml`. |
| A word not in the lexicon | **loanword** | English spelling re-spelled in the Dammaz alphabet + a class ending: noun `-uz`, verb `-ash`, adjective `-rak` (`banana → bananuz`, `juggle → zhuglash`). This follows the Zharralid precedent (*victraz*). Loans are counted, and the corpus filter caps them. |

---

## 12. Decisions made in this draft (override any of them)

| # | Decision | Default taken | Alternative |
|---|---|---|---|
| D1 | Formal vs. familiar *you* | **Decided 2026-09-27:** formal `uzar` for one or many (§4.1) | — |
| D2 | Number base | **10** | Base 12, which is very dwarvish, but the translator would have to convert every English number |
| D3 | Perfect (*has gone*) | Merged into the past | A perfect particle (Khazalid `ad`: `ad truk`) |
| D4 | Past progressive (*was going*) | Merged into the past | Allow `-en` + `-ad` stacking (`trukenad`) |
| D5 | Question words | The `wor-` series, with `wan` kept only as the yes/no marker. The regular series with `wan-` would have made "who" `wanki` | — |
| D6 | Copula in *where is X?* | `zu` follows the question word (English-like) | Strict statement order: `Woraz ta az zu?` |
| D7 | Past of `zu` | `zad` (regular elision) | — |
