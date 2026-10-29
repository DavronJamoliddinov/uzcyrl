"""Uzbek Latin ↔ Cyrillic transliteration.

Rules:
- Latin follows the 1995 orthography (oʻ, gʻ use U+02BB, the tutuq/apostrophe uses U+02BC). Input is normalized
  first (`normalize_uz`), so o', o‘, o` and similar variants work too.
- Cyrillic follows the 1956 orthography rules (the last officially approved rules for Cyrillic): Russian loanwords keep
  their Russian spelling — компьютер, цирк, сентябрь, объект. Latin script lost ь, ц and ъ, so they cannot be restored by
  rules alone; the loanword table (`data/loanwords.tsv`) works on stems and also matches words with Uzbek suffixes:
  kompyuterlarda → компьютерларда.
- A stem-final ь is dropped before an Uzbek suffix (январдан, автомобиллар) — `DROP_SOFT_SIGN_BEFORE_SUFFIX`.
- Foreign words in Latin script (German, English, brands, Roman numerals, codes) are left unchanged: `to_cyrillic(text,
  keep=...)` decides per word; a word with letters that do not exist in the Uzbek alphabet (ä, ß, w, c without h) is
  always kept.
- The reverse direction (`to_latin`) uses the official rules and the same table, so that
  `to_latin(to_cyrillic(x)) == x` holds for everything except loanwords with several Latin spellings.
"""
from __future__ import annotations

import csv
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .normalize import OKINA, TUTUQ, normalize_uz

LOANWORDS_FILE = Path(__file__).parent / "data" / "loanwords.tsv"
DROP_SOFT_SIGN_BEFORE_SUFFIX = True

_LATIN_VOWELS = set("aeiou")  # oʻ is checked separately
_LETTERS = {
    "a": "а", "b": "б", "d": "д", "f": "ф", "g": "г", "h": "ҳ", "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м",
    "n": "н", "o": "о", "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в", "x": "х", "y": "й",
    "z": "з",
}
_Y_VOWEL = {"a": "я", "o": "ё", "u": "ю", "e": "е"}
_UZ_LATIN_LETTERS = set(_LETTERS) | {"e", "c", OKINA, TUTUQ}  # c only inside "ch"

# A word: letters, digits, the oʻ/gʻ mark and the tutuq (hyphens and other characters split words).
_TOKEN_RE = re.compile(rf"[0-9A-Za-zÀ-ÖØ-öø-ÿĀ-ſ][0-9A-Za-zÀ-ÖØ-öø-ÿĀ-ſ{OKINA}{TUTUQ}]*")
_ROMAN_RE = re.compile(r"^(?:[IVXLCDM]{2,}|[IVX])$")

# Uzbek suffixes after a loanword stem: plural, possessive, case, derivational and verbal suffixes.
_SUFFIXES = sorted(
    """lar ning ni ga ka qa da ta dan tan dagi dagina gacha cha lik li siz chi chilik dek day dagidek ki
    im ing i si m ng miz imiz ngiz ingiz lari laring larim larimiz laringiz
    mi ku gina kina dir dirlar u yu oq yoq man san miz siz
    lash lashtir lashtirish lashtirilgan lashgan lashuv tir ish ib gan adi di moq yapti
    ga-da""".split(),
    key=len,
    reverse=True,
)
_SUFFIX_CHAIN_RE = re.compile(rf"^(?:{'|'.join(map(re.escape, _SUFFIXES))})*$")


def _is_vowel(prev: str) -> bool:
    return prev in _LATIN_VOWELS or prev == f"o{OKINA}"


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    source: str  # the whole text (for context-aware `keep` callbacks)


def tokens(text: str) -> Iterator[Token]:
    for m in _TOKEN_RE.finditer(text):
        yield Token(m.group(), m.start(), m.end(), text)


def is_uzbek_spelling(word: str) -> bool:
    """True if the word uses only letters of the Uzbek Latin alphabet (c only inside ch)."""
    w = word.lower()
    if any(ch.isdigit() for ch in w):
        return False
    if any(ch not in _UZ_LATIN_LETTERS for ch in w):
        return False
    return "c" not in w.replace("ch", "")


def always_keep(word: str) -> bool:
    """A word that stays Latin in any text: a letter outside the Uzbek alphabet, a digit, a Roman numeral, mixed case."""
    if not is_uzbek_spelling(word):
        return True
    if _ROMAN_RE.match(word):
        return True
    letters = word.replace(OKINA, "").replace(TUTUQ, "")
    lower_tail = letters[1:]
    # Uzbek abbreviation: sh/ch count as one letter (AQSh → АҚШ), not mixed case. A lone Y in a short abbreviation is
    # ambiguous (YI — Yevropa Ittifoqi, ЕИ in Cyrillic) and stays Latin.
    if _is_abbreviation(letters):
        return len(letters) <= 2 and bool(re.search(r"Y(?![oaueOAUE])", letters))
    # iPhone, DeutschUz — mixed case (other than a capital first letter or all caps) is a brand name.
    return bool(lower_tail) and not (letters.isupper() or lower_tail.islower())


_ABBR_SUFFIX_RE = re.compile(rf"^((?:Sh|Ch|Y[oaue]|[A-Z]){{2,}})([{OKINA}{TUTUQ}]?[a-z]+)$")
# Reliable suffixes glued to a foreign word without an apostrophe (Präteritumda, Jobcenterga). One-letter i/m/u and
# ta/ka, which look like German word endings, are not used.
_STRONG_SUFFIX_RE = re.compile(
    r"^(?:lar|larni|larning|larda|lardan|larga|ning|ni|ga|da|dan|dagi|dagidek|gacha|dek|dir|lik|ligi|lari)+$")


def split_foreign_suffix(word: str, *, glued: bool = True) -> tuple[str, str] | None:
    """A stem that stays Latin + an Uzbek suffix: YouTubeʼda → (YouTube, ʼda), WGda → (WG, da),
    AQShdagi → (AQSh, dagi); with `glued` also without an apostrophe: Präteritumda → (Präteritum, da). None if there is
    no suffix."""
    m = _ABBR_SUFFIX_RE.match(word)
    if m and _SUFFIX_CHAIN_RE.match(m.group(2).lstrip(OKINA + TUTUQ)):
        return m.group(1), m.group(2)
    for i in range(len(word) - 1, 0, -1):
        if word[i] in (OKINA, TUTUQ) and _SUFFIX_CHAIN_RE.match(word[i + 1:].lower()) and word[i + 1:]:
            return word[:i], word[i:]
    if glued:
        # shortest stem: Präsens|dagidek (not Präsensdagi|dek); …i|ni is ambiguous (possessive + accusative: podcastini)
        for cut in range(4, len(word) - 1):
            stem, suffix = word[:cut], word[cut:]
            if suffix.islower() and _STRONG_SUFFIX_RE.match(suffix) and always_keep(stem):
                return None if stem.endswith("i") and suffix.startswith("n") else (stem, suffix)
    return None


def kept_word(word: str, *, uzbek_abbreviations: bool = True, glued: bool = True) -> str:
    """A word that stays Latin: its suffix follows the target script (YouTubeʼда, WGда, Präteritumда), while an Uzbek
    abbreviation is converted (AQShdagi → АҚШдаги). `uzbek_abbreviations=False` keeps the stem Latin (marked as
    foreign); `glued=False` splits only suffixes after an apostrophe or an abbreviation."""
    split = split_foreign_suffix(word, glued=glued)
    if not split:
        return word
    stem, suffix = split
    stem_out = word_to_cyrillic(stem) if uzbek_abbreviations and not always_keep(stem) else stem
    return stem_out + suffix_to_cyrillic(suffix, prev=stem[-1].lower())


# --- Loanword table -----------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def loan_rows() -> tuple[tuple[str, str, bool], ...]:
    """(Latin stem, Cyrillic stem, is the main spelling). One Cyrillic word can have several Latin spellings
    (sentabr / sentyabr); `main` picks the one used by `to_latin`."""
    if not LOANWORDS_FILE.exists():
        return ()
    with LOANWORDS_FILE.open(encoding="utf-8", newline="") as f:
        return tuple(
            (row["latin"].strip().lower(), row["cyrillic"].strip().lower(), row.get("main", "1") != "0")
            for row in csv.DictReader(f, delimiter="\t")
        )


@lru_cache(maxsize=1)
def loanwords() -> dict[str, str]:
    """Latin stem (lower case) → Cyrillic stem. Empty if the table is missing (rules only)."""
    return {latin: cyr for latin, cyr, _ in loan_rows()}


@lru_cache(maxsize=1)
def _loanwords_by_cyrillic() -> dict[str, str]:
    """Cyrillic stem → main Latin spelling; stems ending in ь also without it (январ+дан)."""
    result: dict[str, str] = {}
    for latin, cyr, _ in sorted(loan_rows(), key=lambda r: not r[2]):
        result.setdefault(cyr, latin)
        if cyr.endswith("ь"):
            result.setdefault(cyr[:-1], latin)
    return result


def clear_caches() -> None:
    loan_rows.cache_clear()
    loanwords.cache_clear()
    _loanwords_by_cyrillic.cache_clear()


def _split_loanword(word: str) -> tuple[str, str] | None:
    """(stem, suffixes) — the longest matching stem, if the rest is a chain of Uzbek suffixes."""
    table = loanwords()
    if not table:
        return None
    for cut in range(len(word), 1, -1):
        stem = word[:cut]
        if stem in table and _SUFFIX_CHAIN_RE.match(word[cut:]):
            return stem, word[cut:]
    return None


# --- Latin → Cyrillic ---------------------------------------------------------------------------------------------

_TS_LOAN_RE = re.compile(r"i(?:ya|yo|ye|[aeou])")  # ts + i + vowel does not occur in native Uzbek words


def _rules(word: str, prev: str = "") -> str:
    """A lower-case Uzbek word (or suffixes) → Cyrillic; `prev` is the preceding Latin letter (for the e/э rule)."""
    out: list[str] = []
    i, n = 0, len(word)
    while i < n:
        ch = word[i]
        nxt = word[i + 1] if i + 1 < n else ""
        if nxt == OKINA and ch in "og":
            out.append("ў" if ch == "o" else "ғ")
            prev, i = f"{ch}{OKINA}", i + 2
            continue
        if ch == "s" and nxt == "h":
            out.append("ш")
        elif ch == "c" and nxt == "h":
            out.append("ч")
        elif ch == "s" and nxt == TUTUQ and i + 2 < n and word[i + 2] == "h":
            out.append("сҳ")  # Isʼhoq → Исҳоқ: here the tutuq only separates s and h
            prev, i = "h", i + 3
            continue
        elif ch == "t" and nxt == "s" and (_TS_LOAN_RE.match(word, i + 2) or (i == 0 and not prev)):
            # Russian loanword: informatsiya → информация, ratsion → рацион, patsiyent → пациент, tsement → цемент.
            # An Uzbek verb + suffix (ketsa, aytsin) stays тс.
            out.append("ц")
        elif ch == "y" and nxt in _Y_VOWEL and not (nxt == "o" and i + 2 < n and word[i + 2] == OKINA):
            out.append(_Y_VOWEL[nxt])  # yoʻl → йўл: "oʻ" is a separate letter and does not merge with y
        elif ch == "e":
            # э at the start of a word and after a vowel (эшик, поэма), е elsewhere (кетди).
            out.append("э" if not prev or _is_vowel(prev) else "е")
            prev, i = "e", i + 1
            continue
        elif ch == TUTUQ:
            out.append("ъ")
            prev, i = ch, i + 1
            continue
        else:
            out.append(_LETTERS.get(ch, ch))
            prev, i = ch, i + 1
            continue
        prev, i = nxt, i + 2
    return "".join(out)


_DIGRAPH_TAIL_RE = re.compile(r"(?<=[A-Z])(?:Sh|Ch)|(?<=[A-Z])Y[oaue]|^Y[oaue](?=[A-Z])")


def _is_abbreviation(letters: str) -> bool:
    """An all-caps word or abbreviation; sh/ch/yo… count as one letter (AQSh, FHDYo, MDH)."""
    return len(letters) > 1 and _DIGRAPH_TAIL_RE.sub(lambda m: m.group()[0], letters).isupper()


def _apply_case(original: str, converted: str) -> str:
    letters = original.replace(OKINA, "").replace(TUTUQ, "")
    if _is_abbreviation(letters):
        return converted.upper()
    if letters[:1].isupper():
        return converted[:1].upper() + converted[1:]
    return converted


def word_to_cyrillic(word: str) -> str:
    """One Uzbek word (no foreign-word check). Expects normalized input — see `normalize_uz`."""
    lower = word.lower()
    split = _split_loanword(lower)
    if split:
        stem, rest = split
        cyr_stem = loanwords()[stem]
        if rest and DROP_SOFT_SIGN_BEFORE_SUFFIX and cyr_stem.endswith("ь"):
            cyr_stem = cyr_stem[:-1]
        converted = cyr_stem + _rules(rest, prev=stem[-1])
    else:
        converted = _rules(lower)
    return _apply_case(word, converted)


def suffix_to_cyrillic(suffix: str, prev: str) -> str:
    """An Uzbek suffix after a stem that stays Latin (Akkusativ|da → Akkusativда). An apostrophe after a foreign word
    (Mensaʼda, Ausbildungʻni) is kept as is — it is a separator, not a tutuq (ъ): Mensaʼда."""
    if not suffix:
        return suffix
    lead = len(suffix) - len(suffix.lstrip(OKINA + TUTUQ))
    return suffix[:lead] + _apply_case(suffix[lead:], _rules(suffix[lead:].lower(), prev=prev))


# Pronunciation (IPA) in square brackets: [ʒeˈniː], [ˈtsuːˌzeːən] — never converted.
_IPA_RE = re.compile(r"\[[^\]\n]*[ˈˌːʃʒəɐʊɪɛɔœøʏçŋχʁ̯][^\]\n]*\]")


def protected_ranges(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _IPA_RE.finditer(text)]


KeepFn = Callable[[Token], bool]


def to_cyrillic(text: str, keep: KeepFn | None = None, *, normalize: bool = True) -> str:
    """Converts Uzbek Latin text to Cyrillic; words for which `keep(token)` returns True (German words, names, …) stay
    Latin. With `normalize` (default) apostrophe variants are normalized first: o'zbek → oʻzbek."""
    if normalize:
        text = normalize_uz(text)
    out: list[str] = []
    last = 0
    protected = protected_ranges(text)
    for tok in tokens(text):
        out.append(text[last:tok.start])
        if any(s <= tok.start < e for s, e in protected):
            out.append(tok.text)
        elif always_keep(tok.text):
            out.append(kept_word(tok.text))
        elif keep is not None and keep(tok):
            out.append(kept_word(tok.text, uzbek_abbreviations=False, glued=False))
        else:
            out.append(word_to_cyrillic(tok.text))
        last = tok.end
    out.append(text[last:])
    return "".join(out)


# --- Cyrillic → Latin ---------------------------------------------------------------------------------------------

_CYR_VOWELS = set("аеёиоуэюяў")
_CYR_LETTERS = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l",
    "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ч": "ch",
    "ш": "sh", "щ": "sh", "ы": "i", "э": "e", "ё": "yo", "ю": "yu", "я": "ya", "ў": f"o{OKINA}", "қ": "q",
    "ғ": f"g{OKINA}", "ҳ": "h", "ь": "",
}
_CYR_TOKEN_RE = re.compile(r"[А-Яа-яЁёЎўҚқҒғҲҳ]+")


def _cyr_rules(word: str, prev: str = "") -> str:
    out: list[str] = []
    for i, ch in enumerate(word):
        before = word[i - 1] if i else prev
        if ch == "е":
            out.append("ye" if not before or before in _CYR_VOWELS or before in "ъь" else "e")
        elif ch == "ц":
            out.append("ts" if before and before in _CYR_VOWELS else "s")
        elif ch == "ъ":
            # Tutuq (маъно → maʼno, меъёр → meʼyor); Russian words with the hard sign (объект → obyekt) come from the table.
            out.append(TUTUQ)
        elif ch == "с" and i + 1 < len(word) and word[i + 1] == "ҳ":
            out.append(f"s{TUTUQ}")  # Исҳоқ → Isʼhoq
        else:
            out.append(_CYR_LETTERS.get(ch, ch))
    return "".join(out)


def _cyr_word_to_latin(word: str) -> str:
    lower = word.lower()
    table = _loanwords_by_cyrillic()
    converted = None
    for cut in range(len(lower), 1, -1):
        stem = lower[:cut]
        if stem in table:
            rest = lower[cut:]
            latin_rest = _cyr_rules(rest, prev=stem[-1])
            if _SUFFIX_CHAIN_RE.match(latin_rest):
                converted = table[stem] + latin_rest
                break
    if converted is None:
        converted = _cyr_rules(lower)
    letters = word
    if len(letters) > 1 and letters.isupper():
        return converted.upper().replace(OKINA.upper(), OKINA)
    if letters[:1].isupper():
        return converted[:1].upper() + converted[1:]
    return converted


def to_latin(text: str) -> str:
    """Converts Uzbek Cyrillic text to Latin (1995 orthography); Latin-script words are left unchanged."""
    out: list[str] = []
    last = 0
    for m in _CYR_TOKEN_RE.finditer(text):
        out.append(text[last:m.start()])
        out.append(_cyr_word_to_latin(m.group()))
        last = m.end()
    out.append(text[last:])
    return "".join(out)
