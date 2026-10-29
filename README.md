# uzcyrl

Uzbek Latin ↔ Cyrillic transliteration that gets Russian loanwords right.

```python
>>> from uzcyrl import to_cyrillic, to_latin
>>> to_cyrillic("Kompyuterlarda sentabrdan boshlab yangi dastur ishlaydi.")
'Компьютерларда сентябрдан бошлаб янги дастур ишлайди.'
>>> to_cyrillic("Politsiya informatsiyani tekshirdi.")
'Полиция информацияни текширди.'
>>> to_latin("Ўзбекистон Республикаси")
'Oʻzbekiston Respublikasi'

```

A letter-by-letter converter writes *компютерларда*, *сентабрдан*, *политсия*, *сирк*. Latin script lost the letters
ь, ц and ъ, so they cannot be restored by rules alone. `uzcyrl` combines the official rules with a table of 728
loanword stems that also matches words with Uzbek suffixes (*sentabrdan* → *сентябрдан*, *sirkka* → *циркка*).

Zero dependencies, Python 3.9+, MIT license.

## Install

```bash
pip install git+https://github.com/DavronJamoliddinov/uzcyrl
```

A PyPI release is coming soon.

## What it handles

| Rule | Example |
|---|---|
| Russian loanwords keep their spelling (1956 orthography) | kompyuter → компьютер, sirk → цирк, obyekt → объект |
| Loanword stem + Uzbek suffixes; stem-final ь is dropped before a suffix | sentabrda → сентябрда, filmlar → фильмлар |
| ts: ц only in loanword patterns, т+с in native words | informatsiya → информация, ketsa → кетса |
| э at the start of a word and after a vowel, е elsewhere | eshik → эшик, poema → поэма, kecha → кеча |
| y + vowel | yer → ер, tayyor → тайёр, yoʻl → йўл |
| oʻ, gʻ, tutuq | Oʻzbekiston → Ўзбекистон, maʼno → маъно, Isʼhoq → Исҳоқ |
| Uzbek abbreviations in capitals (sh/ch/yo count as one letter) | AQShdagi → АҚШдаги, FHDYo → ФҲДЁ |
| Foreign words stay Latin, their Uzbek suffix follows the script | YouTubeʼda → YouTubeʼда, Präteritumda → Präteritumда |
| IPA in square brackets is never converted | [ʃøːn] |
| Apostrophe variants are normalized first | o'zbek, o‘zbek, o\`zbek → oʻzbek |

Words with letters that do not exist in the Uzbek alphabet (ä, ß, w, c without h), digits, Roman numerals and mixed
case brand names (iPhone, WhatsApp) always stay Latin.

## Keeping foreign words in Latin

A foreign word spelled only with Uzbek letters (German *der*, *Tisch*, English *man*) cannot be detected reliably. Pass
a `keep` callback that decides per token:

```python
>>> german = {"der", "Tisch"}
>>> to_cyrillic("der Tisch soʻzi «stol» degani", keep=lambda t: t.text in german)
'der Tisch сўзи «стол» дегани'

```

The callback receives a `Token` with `text`, `start`, `end` and the whole `source` text, so it can use context.

## Command line

```bash
$ uzcyrl "O'zbekiston sentabrda"
Ўзбекистон сентябрда
$ uzcyrl --latin "Ўзбекистон сентябрда"
Oʻzbekiston sentabrda
$ uzcyrl < latin.txt > cyrillic.txt
```

## API

- `to_cyrillic(text, keep=None, *, normalize=True)` — Latin → Cyrillic.
- `to_latin(text)` — Cyrillic → Latin (1995 orthography, oʻ/gʻ with U+02BB, tutuq with U+02BC).
- `normalize_uz(text)` — standard apostrophes: oʻ, gʻ (U+02BB) and tutuq (U+02BC).
- `word_to_cyrillic(word)` — one normalized Uzbek word, without the foreign-word check.
- `loanwords()` — the loanword table as a `dict` (Latin stem → Cyrillic stem).

`to_latin(to_cyrillic(x)) == x` holds for all words except loanwords with several Latin spellings (*sentabr* /
*sentyabr* both become *сентябрь*, which converts back to the main spelling).

## Loanword table

[`src/uzcyrl/data/loanwords.tsv`](src/uzcyrl/data/loanwords.tsv): `latin`, `cyrillic`, `source`, `main`. 468 entries
come from [UzTransliterator](https://github.com/elmurod1202/UzTransliterator) (MIT), normalized and checked; 260 were
added for the DeutschUz project. `main = 0` marks an alternative Latin spelling. Missing words and corrections are
welcome as pull requests.

## Background

`uzcyrl` was written for [DeutschUz](https://deutschuz.com), a German–Uzbek dictionary and learning app with full
Latin and Cyrillic support. It converts the app's interface, 65,000 dictionary entries and lesson texts.

## Oʻzbekcha

Oʻzbek lotin ↔ kirill oʻgirgich. Ruscha oʻzlashmalarni toʻgʻri yozadi (компьютер, сентябрь, цирк, объект), oʻzbekcha
qoʻshimchalar bilan ham (сентябрда, циркка), nemischa va inglizcha soʻzlarni lotinda qoldiradi. Kirill — 1956 yilgi
imlo qoidalari, lotin — 1995 yilgi alifbo. Xato yoki yetishmayotgan soʻz topsangiz, issue yoki pull request oching.

## License

MIT — see [LICENSE](LICENSE). Third-party data: [LICENSES/UzTransliterator-MIT.txt](LICENSES/UzTransliterator-MIT.txt).
