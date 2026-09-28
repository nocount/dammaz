"""English -> Dammaz translation (the normative implementation of grammar.md).

    >>> t = Translator()
    >>> t.translate("The old dwarf forged a strong axe.")
    'Ta dawi dhal drashad un az krang.'

How it works, per sentence of a spaCy parse:

1. **Phrases** (lexicon/phrases.yaml) are matched first and replace their tokens.
2. **Lexical choice**: every token gets a Dammaz word and a list of suffix
   tags: function words by rule (§4-5), content words from the lexicon, with
   adverb and participle folding (dammaz.english), and a loanword fallback
   (dammaz.loan).
3. **Verb groups** (§6): auxiliaries collapse into ``nai`` / ``an`` / ``sar`` +
   a tensed first verb, *do*-support is dropped, and questions get ``wan``.
4. **Linearization**: the dependency tree is written out in English order,
   except that inside noun phrases adjectives, noun compounds and 's-possessors
   move after the noun (§3), inverted subjects move back before the verb
   (§8.2-8.3), and indirect objects move after the direct object with ``dra`` (§8.1).
5. **Surface**: suffixes are attached, capitalization and spacing rebuilt.

Anything not covered is written out as-is and counted in ``Stats`` so the
validator and the corpus filter can see it.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import yaml

from dammaz.english import ly_base, participle_verb
from dammaz.lexicon import LEXICON_DIR, function_words, load_content
from dammaz.loan import loan
from dammaz.morphology import inflect

# --- closed-class tables (grammar.md §4-5, lexicon/function.yaml) -------------

PRONOUNS = {"i": "or", "me": "or", "you": "uz", "he": "ek", "him": "ek", "she": "ek",
            "her": "ek", "it": "ek", "we": "ut", "us": "ut", "they": "um", "them": "um",
            "'s": "ut", "’s": "ut"}                      # let's
POSSESSIVES = {"my": "ora", "mine": "ora", "your": "uza", "yours": "uza", "his": "eka",
               "her": "eka", "hers": "eka", "its": "eka", "our": "uta", "ours": "uta",
               "their": "uma", "theirs": "uma"}
REFLEXIVES = {"myself": "ora", "yourself": "uza", "himself": "eka", "herself": "eka",
              "itself": "eka", "ourselves": "uta", "yourselves": "afa", "themselves": "uma"}
WH = {"what": "worak", "who": "worki", "whom": "worki", "where": "woraz", "when": "worur",
      "why": "woros", "how": "worul", "which": "wor", "whose": "worki"}
NUMBERS = {"one": ["un"], "two": ["tuf"], "three": ["thra"], "four": ["kag"],
           "five": ["vam"], "six": ["sib"], "seven": ["mok"], "eight": ["gir"],
           "nine": ["nund"], "ten": ["zer"], "eleven": ["zer", "un"], "twelve": ["zer", "tuf"],
           "twenty": ["tuf-zer"], "thirty": ["thra-zer"], "forty": ["kag-zer"],
           "fifty": ["vam-zer"], "hundred": ["kunk"], "thousand": ["thrul"]}
ORDINALS = {"first": "un", "second": "tuf", "third": "thra", "fourth": "kag",
            "fifth": "vam", "sixth": "sib", "seventh": "mok", "eighth": "gir",
            "ninth": "nund", "tenth": "zer"}
# function.yaml categories a content-tagged word may fall back to (many/ADJ -> drur)
FALLBACK_CATS = {"quantifier", "determiner", "numeral", "correlative"}
MODALS = {"can", "could", "may", "might", "must", "shall", "should", "will", "would",
          "'ll", "’ll", "'d", "’d", "wo", "ca", "sha"}
DUMMY_IT_PREDICATES = {"dark", "light", "cold", "hot", "warm", "cool", "sunny", "rainy",
                       "windy", "cloudy", "snowy", "foggy", "late", "early", "night",
                       "day", "morning", "evening", "time", "noon", "quiet", "loud"}
# Kinship words and titles used as names ("Dad said", "Mummy!"): translated,
# keeping the capital. Real names (Lily, Tom) pass through untouched.
NAME_WORDS = {"mom", "mommy", "mum", "mummy", "mama", "dad", "daddy", "papa", "grandma",
              "grandpa", "granny", "grandmother", "grandfather", "sir", "mister", "miss",
              "teacher", "doctor", "king", "queen", "baby", "sweetie", "honey"}
FORMAL_CUES = {"sir", "madam", "majesty", "highness", "lord", "lady", "king", "queen",
               "elder", "master", "grandfather", "grandmother"}
QUOTES = {'"', "“", "”", "``", "''", "‘", "’", "'"}
CLOSING_PUNCT = {".", ",", "!", "?", ";", ":", ")", "…", "...", "%"}
OPENING_PUNCT = {"(",}


@dataclass
class Stats:
    tokens: int = 0            # Dammaz word tokens produced
    loans: int = 0
    names: int = 0
    unknown: int = 0           # passed through unchanged (translator gap)
    loan_words: Counter = field(default_factory=Counter)
    unknown_words: Counter = field(default_factory=Counter)

    def add(self, other: "Stats") -> None:
        self.tokens += other.tokens
        self.loans += other.loans
        self.names += other.names
        self.unknown += other.unknown
        self.loan_words.update(other.loan_words)
        self.unknown_words.update(other.unknown_words)

    @property
    def loan_rate(self) -> float:
        return self.loans / self.tokens if self.tokens else 0.0


@dataclass
class Out:
    """What one English token contributes: words to emit at its position."""
    words: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)  # (stem, tags)
    kind: str = "word"         # word | punct | qopen | qclose | name | loan | unknown
    before: list[str] = field(default_factory=list)   # e.g. 'a' for moved possessors
    cap: bool = False          # qopen: capitalize the first word of the quote


class Translator:
    def __init__(self, nlp=None, lexicon_dir: Path | None = None):
        self._nlp = nlp
        self.lexicon_dir = lexicon_dir or LEXICON_DIR

    # -- resources -------------------------------------------------------------
    @cached_property
    def nlp(self):
        if self._nlp is None:
            import spacy
            self._nlp = spacy.load("en_core_web_sm", disable=["ner"])
        return self._nlp

    @cached_property
    def content(self) -> dict[tuple[str, str], str]:
        return {s: e.dz for e in load_content(lexicon_dir=self.lexicon_dir) for s in e.senses}

    @cached_property
    def by_lemma(self) -> dict[str, list[tuple[str, str]]]:
        out: dict[str, list[tuple[str, str]]] = {}
        for (lemma, pos), dz in self.content.items():
            out.setdefault(lemma, []).append((pos, dz))
        return out

    @cached_property
    def function(self) -> dict[str, str]:
        """single English word -> function word (first entry wins)."""
        out: dict[str, str] = {}
        for w in function_words():
            for e in w.en:
                e = e.split(" (")[0].lower()
                if " " not in e:
                    out.setdefault(e, w.dz)
        return out

    @cached_property
    def function_fallback(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for w in function_words():
            if w.cat in FALLBACK_CATS:
                for e in w.en:
                    e = e.split(" (")[0].lower()
                    if " " not in e:
                        out.setdefault(e, w.dz)
        return out

    @cached_property
    def function_verbs(self) -> dict[str, str]:
        out = {}
        for w in function_words():
            if w.cat == "verb" and w.dz not in ("zu", "throk", "dret"):
                for e in w.en:
                    if " " not in e:
                        out.setdefault(e, w.dz)
        return out

    @cached_property
    def corrections(self) -> dict[tuple[str, str], tuple[str, str]]:
        raw = yaml.safe_load((self.lexicon_dir / "targets" / "corrections.yaml")
                             .read_text(encoding="utf-8"))
        return {tuple(k.rsplit("/", 1)): tuple(v.rsplit("/", 1))
                for k, v in (raw.get("alias") or {}).items()}

    @cached_property
    def phrases(self) -> list[tuple[list[str], str]]:
        raw = yaml.safe_load((self.lexicon_dir / "phrases.yaml").read_text(encoding="utf-8"))
        out = []
        for eng, dz in raw["phrases"].items():
            dz = re.sub(r"\{([^}]+)\}", lambda m: self._phrase_word(m.group(1)), dz)
            out.append((eng.split(), dz))
        return sorted(out, key=lambda p: -len(p[0]))

    def _phrase_word(self, spec: str) -> str:
        sense, *tags = spec.split("+")
        lemma, pos = sense.rsplit("/", 1)
        dz = self.content.get((lemma, pos)) or loan(lemma, pos)
        return inflect(dz, *tags)

    # -- public API ------------------------------------------------------------
    def translate(self, text: str) -> str:
        return self.translate_with_stats(text)[0]

    def translate_with_stats(self, text: str) -> tuple[str, Stats]:
        stats = Stats()
        paras = text.split("\n")
        out = []
        for para, doc in zip(paras, self.nlp.pipe(paras)):
            out.append(self._doc(doc, stats) if para.strip() else para)
        return "\n".join(out), stats

    def translate_many(self, texts, batch_size: int = 256, n_process: int = 1):
        """Yield (dammaz, stats) per input text, parsing all paragraphs of all
        texts in one spaCy pipe (much faster than one call per text)."""
        texts = list(texts)
        paras = [(ti, p) for ti, text in enumerate(texts) for p in text.split("\n")]
        docs = self.nlp.pipe((p for _, p in paras), batch_size=batch_size, n_process=n_process)
        results: list[list[str]] = [[] for _ in texts]
        stats = [Stats() for _ in texts]
        for (ti, p), doc in zip(paras, docs):
            results[ti].append(self._doc(doc, stats[ti]) if p.strip() else p)
        for ti in range(len(texts)):
            yield "\n".join(results[ti]), stats[ti]

    # -- per document ------------------------------------------------------------
    def _doc(self, doc, stats: Stats) -> str:
        # words used as names in this paragraph: tagged PROPN, or capitalized
        # mid-sentence. A sentence-initial "Lily" tagged ADJ is then still a name.
        self._doc_names = {t.text for t in doc if t.text[:1].isupper() and (
            t.pos_ == "PROPN" or (not t.is_sent_start and t.i > 0 and not t.nbor(-1).is_punct))}
        sents = []
        for sent in doc.sents:
            sents.append(self._sentence(sent, stats))
        return " ".join(s for s in sents if s)

    def _sentence(self, sent, stats: Stats) -> str:
        outs: dict[int, Out] = {}
        consumed = self._match_phrases(sent, outs)
        formal_spans = self._formal_quote_spans(sent)
        for t in sent:
            if t.i not in outs:
                outs[t.i] = self._lexical(t, formal=any(a <= t.i < b for a, b in formal_spans))
        for t in sent:
            if self._is_predicate(t) and t.i not in consumed:
                self._verb_group(t, outs)
        self._formal_imperatives(sent, outs, formal_spans)
        self._dummy_it(sent, outs)
        self._comparatives(sent, outs)
        order = self._linearize(sent.root, outs)
        order = self._copula_questions(sent, order)
        order = self._insert_wan(sent, order, outs)
        return self._surface(order, outs, sent, stats)

    # -- 1. phrases ----------------------------------------------------------------
    def _match_phrases(self, sent, outs: dict[int, Out]) -> set[int]:
        consumed: set[int] = set()
        toks = list(sent)
        low = [t.lower_ for t in toks]
        i = 0
        while i < len(toks):
            for words, dz in self.phrases:
                if low[i:i + len(words)] == words and not any(
                        toks[j].i in consumed for j in range(i, i + len(words))):
                    outs[toks[i].i] = Out(words=[(w, ()) for w in dz.split()])
                    for j in range(i + 1, i + len(words)):
                        outs[toks[j].i] = Out(words=[])
                    consumed |= {toks[j].i for j in range(i, i + len(words))}
                    i += len(words) - 1
                    break
            i += 1
        return consumed

    def _formal_quote_spans(self, sent) -> list[tuple[int, int]]:
        """Token ranges addressed to someone owed `uzar` (§4.1): quoted speech
        containing a respect cue, or a whole unquoted sentence that has both a
        cue and a second-person word."""
        has_quotes = any(t.text in ('"', "\u201c", "\u201d") for t in sent)
        if not has_quotes:
            low = {t.lower_ for t in sent}
            second = low & {"you", "your", "yours", "yourself", "please"}
            return [(sent.start, sent.end)] if (low & FORMAL_CUES and second) else []
        spans, start = [], None
        for t in sent:
            if t.text in QUOTES and t.tag_ in ("``", "''", "NFP") or t.text in ('"', "“", "”"):
                if start is None:
                    start = t.i
                else:
                    spans.append((start, t.i))
                    start = None
        return [(a, b) for a, b in spans
                if any(sent.doc[k].lower_ in FORMAL_CUES for k in range(a, b))]

    def _formal_imperatives(self, sent, outs: dict[int, Out], spans) -> None:
        """In a formal span, 'please' + imperative = `uzar` + verb (§6.8)."""
        for a, b in spans:
            for k in range(a, b):
                t = sent.doc[k]
                if t.lower_ == "please":
                    outs[t.i] = Out(words=[])
                if (t.pos_ == "VERB" and t.tag_ == "VB" and t.dep_ in ("ROOT", "conj")
                        and not any(c.dep_ in ("nsubj", "aux") for c in t.children)):
                    outs[t.i].before = ["uzar"] + outs[t.i].before

    def _dummy_it(self, sent, outs: dict[int, Out]) -> None:
        """'It is dark' -> 'Zu skom': drop a dummy 'it' before be + weather/time."""
        for t in sent:
            if t.lower_ != "it" or t.dep_ != "nsubj" or t.head.lemma_.lower() != "be":
                continue
            pred = [c for c in t.head.children if c.dep_ in ("acomp", "attr")]
            if pred and pred[0].lemma_.lower() in DUMMY_IT_PREDICATES:
                outs[t.i] = Out(words=[])

    # -- 2. lexical choice -----------------------------------------------------------
    def _lexical(self, t, formal: bool = False) -> Out:
        text, low, lemma, pos, tag, dep = t.text, t.lower_, t.lemma_.lower(), t.pos_, t.tag_, t.dep_
        if tag == "HYPH" and 0 < t.i < len(t.doc) - 1 and t.nbor(-1).pos_ == "NUM" \
                and t.nbor(1).pos_ == "NUM":
            return Out(words=[])               # twenty-three -> tuf-zer thra (§9)
        if tag == "``" or (text in ("\u201c",) and pos == "PUNCT"):
            nxt = t.nbor(1) if t.i + 1 < len(t.doc) else None
            return Out(words=[(text, ())], kind="qopen",
                       cap=bool(nxt is not None and nxt.text[:1].isupper()))
        if tag == "''" or (text in ("\u201d",) and pos == "PUNCT"):
            return Out(words=[(text, ())], kind="qclose")
        if pos == "PUNCT" or t.is_punct:
            return Out(words=[(text, ())], kind="punct")
        if pos == "SPACE":
            return Out(words=[])
        if pos == "PROPN":
            if not text[:1].isupper():                 # lowercase "PROPN": a tagging error
                return self._content(t, pos_override="NOUN")
            if low in NAME_WORDS:
                o = self._content(t, pos_override="NOUN")
                if o.kind == "word":
                    o.words = [(w[:1].upper() + w[1:], tg) for w, tg in o.words]
                    return o
            return Out(words=[(text, ())], kind="name")
        if text.isdigit() or (pos == "NUM" and re.fullmatch(r"[\d.,]+", text)):
            return Out(words=[(text, ())], kind="name")
        if pos == "NUM" and low in NUMBERS:
            return Out(words=[(w, ()) for w in NUMBERS[low]])
        if low in ORDINALS and pos in ("ADJ", "ADV", "NOUN"):
            return Out(words=[(ORDINALS[low], ("ORD",))])          # first -> unik (§9)
        if low in ("one", "ones") and pos in ("NOUN", "PRON"):
            return Out(words=[("un", ("PL",) if low == "ones" else ())])
        # pronouns & possessives
        if low in REFLEXIVES:
            return Out(words=[(REFLEXIVES[low], ()), ("keb", ())])
        if tag == "PRP$" or (low in ("mine", "yours", "hers", "ours", "theirs") and pos == "PRON"):
            dz = POSSESSIVES.get(low, "eka")
            return Out(words=[("uzara" if formal and dz == "uza" else dz, ())])
        if low in ("all", "guys") and t.i > 0 and t.nbor(-1).lower_ == "you":
            return Out(words=[])                 # "you all" -> af
        if tag == "PRP" or (pos == "PRON" and low in PRONOUNS):
            if low in ("you",):
                if formal:
                    return Out(words=[("uzar", ())])
                nxt = t.nbor(1).lower_ if t.i + 1 < len(t.doc) else ""
                return Out(words=[("af" if nxt in ("all", "guys", "two", "both") else "uz", ())])
            return Out(words=[(PRONOUNS.get(low, PRONOUNS.get(lemma, low)), ())])
        # existential there, infinitive to, possessive 's, aux: decided elsewhere
        if tag == "EX":
            return Out(words=[])
        if tag == "POS":
            return Out(words=[])
        if tag == "TO" or (low == "to" and dep == "aux"):
            purpose = t.head.dep_ in ("advcl",) and t.head.head.pos_ in ("VERB", "AUX")
            return Out(words=[("dra", ())] if purpose else [])
        if pos == "AUX" and dep in ("aux", "auxpass"):
            return Out(words=[])            # filled in by _verb_group
        if dep == "neg" or low in ("not", "n't", "n’t"):
            return Out(words=[])            # filled in by _verb_group
        # wh-words / relativizers / 'that'
        if low in ("that", "which", "who", "whom") and (
                dep in ("mark",) or t.head.dep_ == "relcl" and tag in ("WDT", "WP")):
            return Out(words=[("zo", ())])
        if low == "that" and tag == "WDT":
            return Out(words=[("zo", ())])
        if tag in ("WP", "WRB", "WDT", "WP$") and low in WH:
            if low == "which" and dep == "det":
                return Out(words=[("wor", ())])
            if low == "what" and dep == "det":
                return Out(words=[("wor", ())])
            return Out(words=[(WH[low], ())])
        if low == "as" and dep == "mark":
            return Out(words=[("worur", ())])        # "as they walked" = while
        if low == "as" and dep == "advmod" and t.head.pos_ in ("ADJ", "ADV"):
            return Out(words=[])                     # "as big as" -> gorz lak
        if low == "so":
            degree = dep == "advmod" and t.head.pos_ in ("ADJ", "ADV")
            return Out(words=[("grak" if degree else "zukos", ())])
        if low in ("more", "most") and dep == "advmod" and t.head.pos_ in ("ADJ", "ADV"):
            return Out(words=[])            # becomes -ar on the adjective
        if low == "more" and pos in ("ADJ", "DET", "PRON", "ADV"):
            return Out(words=[("drurar", ())])
        if low == "no" and pos == "INTJ":
            return Out(words=[("na", ())])
        if low == "by" and dep == "agent":
            return Out(words=[("rof", ())])
        if low == "there" and pos == "ADV":
            return Out(words=[("zukaz", ())])
        if low == "all" and pos in ("DET", "ADV", "PRON"):
            return Out(words=[("gom", ())])
        if low == "another":
            return Out(words=[("un", ()), ("hil", ())])
        # everything else closed-class: function.yaml
        if pos in ("DET", "ADP", "CCONJ", "SCONJ", "PART", "PRON") or (
                pos in ("ADV", "INTJ") and (low in self.function or lemma in self.function)
                and not self._content_word(lemma, pos)):
            dz = self.function.get(low) or self.function.get(lemma)
            if dz:
                return Out(words=[(dz, ())])
        return self._content(t)

    def _content_word(self, lemma: str, pos: str) -> str | None:
        return self.content.get(self.corrections.get((lemma, pos), (lemma, pos)))

    def _content(self, t, pos_override: str | None = None) -> Out:
        lemma, pos, tag = t.lemma_.lower(), pos_override or t.pos_, t.tag_
        lemma, pos = self.corrections.get((lemma, pos), (lemma, pos))
        tags: tuple[str, ...] = ()
        if pos == "NOUN" and tag in ("NNS",) and t.lower_ != lemma:
            tags = ("PL",)
        if pos == "ADJ" and tag in ("JJR", "JJS"):
            tags = ("CMP",)
        if pos == "ADV" and tag in ("RBR", "RBS"):
            tags = ("CMP",)
        # grammatical verbs (have, want) live in function.yaml
        if pos == "VERB" and (lemma, pos) not in self.content and lemma in self.function_verbs:
            return Out(words=[(self.function_verbs[lemma], tags)])
        # "the drinking dwarf": the small model often tags -ing modifiers as NOUN
        if pos == "NOUN" and t.dep_ in ("compound", "amod") and t.lower_.endswith("ing"):
            verbs = {l for (l, p) in self.content if p == "VERB"}
            if hit := participle_verb(t.lower_, verbs):
                return Out(words=[(self.content[(hit[0], "VERB")], (hit[1],))])
        # direct hit
        if (lemma, pos) in self.content:
            return Out(words=[(self.content[(lemma, pos)], tags)])
        # adverbs -> adjective + ADV (quickly -> quick-ul, run fast -> fast-ul)
        if pos == "ADV":
            for base in [lemma] + ly_base(lemma):
                if (base, "ADJ") in self.content:
                    return Out(words=[(self.content[(base, "ADJ")], tags + ("ADV",))])
        # participle adjectives -> verb + PST / PROG
        if pos == "ADJ":
            verbs = {l for (l, p) in self.content if p == "VERB"}
            if hit := participle_verb(lemma, verbs):
                return Out(words=[(self.content[(hit[0], "VERB")], (hit[1],))])
        # same lemma under another part of speech (zero conversion)
        if lemma in self.by_lemma and pos in ("NOUN", "VERB", "ADJ", "INTJ"):
            order = {"NOUN": ("VERB", "ADJ"), "VERB": ("NOUN", "ADJ"),
                     "ADJ": ("NOUN", "VERB"), "INTJ": ("ADJ", "NOUN", "VERB")}[pos]
            for p in order:
                for bp, dz in self.by_lemma[lemma]:
                    if bp == p:
                        return Out(words=[(dz, tags)])
        # a capitalized word mid-sentence that isn't in the lexicon is a name
        # the tagger missed ("Lily" tagged ADJ)
        prev = t.nbor(-1) if t.i > t.sent.start else None
        if t.text[:1].isupper() and (
                (prev is not None and not prev.is_punct and not t.is_sent_start)
                or t.text in getattr(self, "_doc_names", ())):
            return Out(words=[(t.text, ())], kind="name")
        # closed-class words spaCy tagged as content (many/ADJ, others/NOUN)
        fb = self.function_fallback.get(t.lower_) or self.function_fallback.get(lemma)
        if fb:
            return Out(words=[(fb, tags)])
        if pos in ("NOUN", "VERB", "ADJ", "ADV", "INTJ", "X", "NUM"):
            lp = "ADJ" if pos == "ADV" else pos
            stem = loan(lemma, lp)
            if pos == "ADV":
                tags = tags + ("ADV",)
            return Out(words=[(stem, tags)], kind="loan")
        if t.text.isalpha():                     # closed-class word missing from function.yaml
            return Out(words=[(loan(lemma, "NOUN"), ())], kind="loan")
        return Out(words=[(t.text, ())], kind="unknown")

    # -- 3. verb groups ----------------------------------------------------------------
    @staticmethod
    def _is_predicate(t) -> bool:
        if t.pos_ == "VERB":
            return True
        return t.pos_ == "AUX" and t.dep_ not in ("aux", "auxpass")

    def _verb_group(self, v, outs: dict[int, Out]) -> None:
        if v.lemma_.lower() == "let":
            comp = next((c for c in v.children if c.dep_ in ("ccomp", "xcomp")), None)
            subj = next((g for g in (comp.children if comp is not None else [])
                         if g.dep_ == "nsubj"), None) or next(
                (c for c in v.children if c.dep_ in ("nsubj", "dobj")), None)
            if subj is not None and subj.lower_ in ("'s", "’s", "us"):
                outs[v.i] = Out(words=[])      # "let's go" = "ut truk" (§6.8)
                return
            if subj is not None and subj.lower_ == "me" and comp is not None:
                outs[v.i] = Out(words=[])      # "let me help" = "or an glunk" (an offer)
                outs[comp.i].words.insert(0, ("an", ()))
                return
        auxes = [c for c in v.children if c.dep_ in ("aux", "auxpass") and c.tag_ != "TO"]
        negs = [c for c in v.children if c.dep_ == "neg"]
        lemmas = [a.lemma_.lower() for a in auxes]
        texts = [a.lower_ for a in auxes]
        is_copula = v.lemma_.lower() == "be"
        if v.pos_ == "AUX" and not is_copula:
            self._elliptical_aux(v, negs, outs)
            return

        # "going to V" future: handled on the xcomp verb; this verb disappears
        xcomp = next((c for c in v.children if c.dep_ == "xcomp" and c.tag_ == "VB"
                      and any(g.tag_ == "TO" for g in c.children)), None)
        if v.lemma_.lower() == "go" and v.tag_ == "VBG" and xcomp is not None and "be" in lemmas:
            past = any(a.tag_ == "VBD" for a in auxes)
            first = min(auxes + negs + [v], key=lambda x: x.i)
            chain = (["nai"] if negs else []) + ["sar" if past else "an"]
            for a in auxes + negs + [v]:
                outs[a.i] = Out(words=[])
            outs[first.i] = Out(words=[(w, ()) for w in chain])
            return

        # "have to V" -> dret
        if v.lemma_.lower() == "have" and xcomp is not None and v.pos_ == "VERB":
            outs[v.i] = Out(words=[("dret", ())])

        modal = next((l for l, x in zip(lemmas, texts) if x in MODALS or l in MODALS), None)
        modal_text = next((x for x in texts if x in MODALS), modal or "")
        fut = modal in ("will", "shall") or modal_text in ("'ll", "’ll", "wo", "sha")
        cond = modal in ("would", "might", "may") or modal_text in ("'d", "’d")
        modal_verb, modal_tags = None, ()
        if modal in ("can", "ca") or modal_text == "ca":
            modal_verb = "throk"
        elif modal == "could":
            modal_verb, modal_tags = "throk", ("PST",)
        elif modal == "must":
            modal_verb = "dret"
        elif modal == "should":
            modal_verb, cond = "dret", True

        passive = any(c.dep_ == "auxpass" for c in v.children) or (
            v.tag_ == "VBN" and "be" in lemmas and v.dep_ != "amod")
        perfect = "have" in lemmas and v.tag_ == "VBN"
        progressive = "be" in lemmas and v.tag_ == "VBG"
        tensed_aux = [a for a in auxes if a.lemma_.lower() in ("be", "have", "do")]
        past = (any(a.tag_ == "VBD" for a in tensed_aux)
                or (not auxes and v.tag_ in ("VBD", "VBN")) or perfect)

        particles = (["nai"] if negs else []) + (["an"] if fut else []) + (["sar"] if cond else [])
        chain: list[tuple[str, tuple[str, ...]]] = []
        head = outs[v.i]
        verb_tags: tuple[str, ...]
        if fut or cond:
            verb_tags = ()
        elif v.tag_ == "VBG" and not auxes and v.dep_ in ("amod", "acl", "compound"):
            verb_tags = ("PROG",)              # "the drinking dwarf" (§6.5)
        elif progressive and not past:
            verb_tags = ("PROG",)
        elif past:
            verb_tags = ("PST",)
        else:
            verb_tags = ()
        if modal_verb:
            chain.append((modal_verb, modal_tags if not (fut or cond) else ()))
            verb_tags = ()
        if passive and not is_copula:
            be_tags = () if (fut or cond or modal_verb) else (("PST",) if past else ())
            chain.append(("zu", be_tags))
            verb_tags = ("PST",)

        if is_copula:
            # the copula itself carries the tense ("was" -> zad, "will be" -> an zu)
            cop_tags = () if (fut or cond or modal_verb) else (
                ("PST",) if (v.tag_ == "VBD" or past) else ())
            head = Out(words=[("zu", cop_tags)], before=head.before)
        elif head.words and head.kind in ("word", "loan"):
            stem, tags = head.words[-1]
            tags = tuple(x for x in tags if x not in ("PST", "PROG")) + verb_tags
            head = Out(words=head.words[:-1] + [(stem, tags)], kind=head.kind, before=head.before)
        outs[v.i] = head

        lead = [(w, ()) for w in particles] + chain
        slots = sorted(auxes + negs, key=lambda x: x.i)
        for s in slots:
            outs[s.i] = Out(words=[])
        if not lead:
            return
        before_verb = [s for s in slots if s.i < v.i]
        if before_verb:
            outs[before_verb[0].i] = Out(words=lead)
        else:                                  # "is not happy": nai goes before zu
            outs[v.i] = Out(words=lead + outs[v.i].words, kind=outs[v.i].kind,
                            before=outs[v.i].before)

    def _elliptical_aux(self, v, negs, outs: dict[int, Out]) -> None:
        """A bare auxiliary as the predicate: "Yes, I can." / "I did." / "She will."
        Dammaz repeats a verb: throk (can), dret (must), or the verb 'do'."""
        do = self.content.get(("do", "VERB")) or loan("do", "VERB")
        low, lemma = v.lower_, v.lemma_.lower()
        past = v.tag_ == "VBD"
        table = {
            "can": [("throk", ())], "ca": [("throk", ())], "could": [("throk", ("PST",))],
            "must": [("dret", ())], "should": [("sar", ()), ("dret", ())],
            "will": [("an", ()), (do, ())], "wo": [("an", ()), (do, ())],
            "'ll": [("an", ()), (do, ())], "shall": [("an", ()), (do, ())],
            "would": [("sar", ()), (do, ())], "'d": [("sar", ()), (do, ())],
            "may": [("sar", ()), (do, ())], "might": [("sar", ()), (do, ())],
        }
        words = table.get(low) or table.get(lemma)
        if words is None:                               # do / does / did / have / has / had
            words = [(do, ("PST",) if (past or lemma == "have") else ())]
        if negs:
            words = [("nai", ())] + words
            for n in negs:
                outs[n.i] = Out(words=[])
        outs[v.i] = Out(words=words, before=outs[v.i].before)

    def _comparatives(self, sent, outs: dict[int, Out]) -> None:
        """'more beautiful' / 'most beautiful' -> adjective + CMP (§7.2)."""
        for t in sent:
            if t.lower_ in ("more", "most") and t.dep_ == "advmod" and t.head.pos_ in ("ADJ", "ADV"):
                o = outs[t.head.i]
                if o.words:
                    stem, tags = o.words[-1]
                    if "CMP" not in tags:
                        adv = tuple(x for x in tags if x == "ADV")
                        rest = tuple(x for x in tags if x != "ADV")
                        o.words[-1] = (stem, rest + ("CMP",) + adv) if not adv else (stem, rest + ("CMP",))

    # -- 4. linearization ------------------------------------------------------------
    NOUNISH = ("NOUN", "PROPN")
    MOVE_AFTER_NOUN = ("amod", "compound", "poss", "nmod")

    def _linearize(self, head, outs: dict[int, Out]) -> list[int]:
        lefts, rights = list(head.lefts), list(head.rights)

        if head.pos_ in self.NOUNISH:
            stay, adjs, comps, possr = [], [], [], []
            for c in lefts:
                counting = c.lower_ in self.function_fallback or c.lower_ in ("more", "another")
                if counting and c.dep_ in ("amod", "compound"):
                    stay.append(c)             # many/other/both count: they stay in front (§3.1)
                elif c.dep_ == "amod" or (c.dep_ == "compound" and (
                        c.pos_ == "ADJ" or c.lower_.endswith("ing"))):
                    adjs.append(c)
                elif c.dep_ in ("compound", "nmod") and c.pos_ == "NOUN":
                    comps.append(c)
                elif c.dep_ == "poss" and any(g.tag_ == "POS" for g in c.children):
                    possr.append(c)
                else:
                    stay.append(c)
            seq: list[int] = []
            has_det = any(c.dep_ in ("det", "poss") and c not in possr for c in stay)
            if possr and not has_det:
                seq.append(self._inject(outs, head.i, "ta"))
            for c in stay:
                seq += self._linearize(c, outs)
            seq.append(head.i)
            for c in adjs:
                seq += self._linearize(c, outs)
            for c in comps:
                seq.append(self._inject(outs, c.i, "a"))
                seq += self._linearize(c, outs)
            for c in possr:
                seq.append(self._inject(outs, c.i, "a"))
                seq += self._linearize(c, outs)
            for c in rights:
                if c.dep_ == "relcl":
                    seq += self._relative_clause(head, c, outs)
                else:
                    seq += self._linearize(c, outs)
            return seq

        if self._is_predicate(head):
            # subject back before the verb chain in inverted questions (§8.2-8.3)
            subj = next((c for c in lefts if c.dep_ in ("nsubj", "nsubjpass")), None)
            vslots = [c for c in lefts if c.dep_ in ("aux", "auxpass", "neg")]
            if subj and vslots and vslots[0].i < subj.i:
                first = vslots[0].i
                lefts = ([c for c in lefts if c.i < first] + [subj]
                         + [c for c in lefts if c.i >= first and c is not subj])
            # indirect object after the direct object, with dra (§8.1)
            dative = next((c for c in rights if c.dep_ == "dative"
                           and not any(g.dep_ == "pobj" for g in c.children)), None)
            dobj = next((c for c in rights if c.dep_ == "dobj"), None)
            if dative is not None and dobj is not None and dative.i < dobj.i:
                rights = [c for c in rights if c is not dative]
                rights.insert(rights.index(dobj) + 1, dative)
                outs[dative.i].before = ["dra"] + outs[dative.i].before

        seq = []
        for c in lefts:
            seq += self._linearize(c, outs)
        seq.append(head.i)
        for c in rights:
            if self._needs_complementizer(head, c):
                seq.append(self._inject(outs, c.i, "zo"))       # §8.5
            seq += self._linearize(c, outs)
        return seq

    @staticmethod
    def _needs_complementizer(head, c) -> bool:
        if c.dep_ != "ccomp" or c.i < head.i or head.lemma_.lower() == "let":
            return False
        if any(g.dep_ == "mark" or g.tag_.startswith("W") for g in c.children):
            return False
        doc = head.doc
        between = range(head.i + 1, c.left_edge.i)
        return not any(doc[k].is_punct for k in between) and not doc[c.left_edge.i].is_punct

    def _relative_clause(self, noun, rel, outs: dict[int, Out]) -> list[int]:
        """§8.4: `zo` + clause; a stranded preposition gets a resumptive pronoun."""
        seq: list[int] = []
        has_rel = any(t.lower_ in ("who", "whom", "which", "that", "where", "when", "whose")
                      and t.tag_ in ("WDT", "WP", "WRB", "WP$", "DT", "IN")
                      for t in rel.subtree if t.i < rel.i)
        if not has_rel:
            seq.append(self._inject(outs, rel.i, "zo"))
        for t in rel.subtree:
            if t.dep_ == "prep" and not any(g.dep_ in ("pobj", "pcomp") for g in t.children):
                pron = "um" if noun.tag_ in ("NNS", "NNPS") else "ek"
                outs[t.i].words.append((pron, ()))
        return seq + self._linearize(rel, outs)

    @staticmethod
    def _inject(outs: dict[int, Out], i: int, word: str) -> int:
        """Attach an extra word to be emitted *before* token i; returns i as a
        marker in the order (negative ids are injected words)."""
        key = -(len([k for k in outs if k < 0]) + 1)
        outs[key] = Out(words=[(word, ())])
        return key

    @staticmethod
    def _ends_with_question(tok) -> bool:
        sent = tok.sent
        last = [t for t in sent if not t.is_space]
        return any(t.text == "?" for t in last[-3:])

    # -- copula-first yes/no questions: "Is the axe strong?" -> "(Wan) ta az zu krang?"
    COPULA_FORMS = {"is", "are", "was", "were", "am"}
    NP_TAGS = {"DT", "PRP$", "CD", "JJ", "JJR", "JJS", "NN", "NNS", "NNP", "NNPS", "PRP", "POS"}

    def _copula_questions(self, sent, order: list[int]) -> list[int]:
        """Move a sentence-initial copula after the first noun phrase. Done on
        tags, not the parse: the small parser often misattaches the subject."""
        doc = sent.doc
        for a, b in self._question_segments(sent):
            words = [doc[k] for k in range(a, b) if not doc[k].is_punct]
            if len(words) < 3 or words[0].lower_ not in self.COPULA_FORMS:
                continue
            if words[0].dep_ in ("aux", "auxpass"):
                continue                       # auxiliary: handled by the subject move
            cop = words[0]
            np_end = None
            for t in words[1:]:
                if t.tag_ not in self.NP_TAGS:
                    break
                if t.tag_ in ("NN", "NNS", "NNP", "NNPS", "PRP"):
                    np_end = t
                    if t.tag_ == "PRP" or not (t.i + 1 < b and doc[t.i + 1].tag_.startswith("NN")):
                        break
            if np_end is None or cop.i not in order:
                continue
            np_ids = [k for k in range(cop.i + 1, np_end.i + 1) if k in order]
            if not np_ids:
                continue
            order.remove(cop.i)
            order.insert(max(order.index(k) for k in np_ids) + 1, cop.i)
        return order

    def _question_segments(self, sent) -> list[tuple[int, int]]:
        segments, start = [], sent.start
        for t in sent:
            if t.text in ('"', "“", "”") or (t.tag_ in ("``", "''") and t.text in QUOTES):
                start = t.i + 1
            elif t.text in (".", "!", ";"):
                start = t.i + 1
            elif t.text == "?":
                segments.append((start, t.i))
                start = t.i + 1
        return segments

    # -- yes/no questions (§8.2) -------------------------------------------------------
    def _insert_wan(self, sent, order: list[int], outs: dict[int, Out]) -> list[int]:
        """Add `wan` at the start of each yes/no question segment: a stretch of
        tokens ending in '?' that doesn't start with a wh-word."""
        doc = sent.doc
        pos_in_order = {i: k for k, i in enumerate(order)}
        segments = self._question_segments(sent)
        inserts = []
        segments = [self._skip_vocative(doc, a, b) for a, b in segments]
        for a, b in segments:
            words = [doc[k] for k in range(a, b) if not doc[k].is_punct]
            if not words:
                continue
            first = words[0]
            if first.tag_.startswith("W") or first.lower_ in WH:
                continue
            # the earliest output position among the segment's tokens
            positions = [pos_in_order[k] for k in range(a, b) if k in pos_in_order]
            if positions:
                inserts.append(min(positions))
        for p in sorted(inserts, reverse=True):
            key = self._inject(outs, 0, "wan")
            order.insert(p, key)
        return order

    @staticmethod
    def _skip_vocative(doc, a: int, b: int) -> tuple[int, int]:
        """If the segment opens with a verbless phrase + comma ("My king, ..."),
        the question proper starts after the comma."""
        for k in range(a, b):
            if doc[k].text == ",":
                head = [doc[j] for j in range(a, k)]
                if head and not any(t.pos_ in ("VERB", "AUX") for t in head):
                    return k + 1, b
                break
        return a, b

    # -- 5. surface --------------------------------------------------------------------
    def _surface(self, order: list[int], outs: dict[int, Out], sent, stats: Stats) -> str:
        pieces: list[tuple[str, str, bool]] = []     # (text, kind, cap-flag)
        for i in order:
            o = outs[i]
            for w in o.before:
                pieces.append((w, "word", False))
            for stem, tags in o.words:
                if o.kind in ("punct", "qopen", "qclose", "name", "unknown"):
                    pieces.append((stem, o.kind, o.cap))
                    continue
                try:
                    pieces.append((inflect(stem, *tags) if tags else stem, o.kind, False))
                except ValueError:
                    pieces.append((stem, o.kind, False))
        for text, kind, _ in pieces:
            if kind in ("punct", "qopen", "qclose"):
                continue
            stats.tokens += 1
            if kind == "loan":
                stats.loans += 1
                stats.loan_words[text] += 1
            elif kind == "name":
                stats.names += 1
            elif kind == "unknown":
                stats.unknown += 1
                stats.unknown_words[text] += 1
        # Capitalize the first word if the English sentence starts with a capital
        # (a name counts only for full sentences: "Borin's axe" stays lowercase),
        # and the first word inside a quote whose English starts with a capital.
        words = [t for t in sent if not t.is_punct and not t.is_space]
        first = words[0] if words else None
        full_sentence = any(t.text in (".", "!", "?") for t in sent)
        cap_next = bool(first is not None and first.text[:1].isupper()
                        and (first.pos_ != "PROPN" or full_sentence))
        out: list[tuple[str, str]] = []
        for text, kind, cap in pieces:
            if kind == "qopen":
                cap_next = cap_next or cap
            elif kind not in ("punct", "qclose"):
                if cap_next and kind != "name":
                    text = text[:1].upper() + text[1:]
                cap_next = False
            out.append((text, kind))
        return self._join(out)

    @staticmethod
    def _join(pieces: list[tuple[str, str]]) -> str:
        s, glue_next = "", True
        for text, kind in pieces:
            if kind == "qclose" or (kind == "punct" and text in CLOSING_PUNCT):
                s += text
                glue_next = False
            elif kind == "qopen" or (kind == "punct" and text in OPENING_PUNCT):
                s += ("" if glue_next or not s else " ") + text
                glue_next = True
            else:
                s += ("" if glue_next or not s else " ") + text
                glue_next = False
        return s


_default: Translator | None = None


def translate(text: str) -> str:
    global _default
    if _default is None:
        _default = Translator()
    return _default.translate(text)


def main() -> None:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    text = " ".join(sys.argv[1:]) or sys.stdin.read()
    out, stats = Translator().translate_with_stats(text)
    print(out)
    print(f"[{stats.tokens} words, {stats.loans} loans, {stats.names} names, "
          f"{stats.unknown} unknown]", file=sys.stderr)


if __name__ == "__main__":
    main()
