import pytest

import uzcyrl
from uzcyrl import _core, normalize_uz, to_cyrillic, to_latin, word_to_cyrillic
from uzcyrl.__main__ import main


@pytest.mark.parametrize(
    ("latin", "cyrillic"),
    [
        ("Oʻzbekiston", "Ўзбекистон"),
        ("shahar", "шаҳар"),
        ("Shahar", "Шаҳар"),
        ("SHAHAR", "ШАҲАР"),
        ("choy", "чой"),
        ("gʻisht", "ғишт"),
        ("maʼno", "маъно"),
        ("taʼlim", "таълим"),
        # э at the start of a word and after a vowel, е elsewhere
        ("eshik", "эшик"),
        ("Ertaga", "Эртага"),
        ("kecha", "кеча"),
        ("poema", "поэма"),
        ("aeroport", "аэропорт"),
        # y + vowel → я/ё/ю/е
        ("yer", "ер"),
        ("qayerda", "қаерда"),
        ("yoz", "ёз"),
        ("yulduz", "юлдуз"),
        ("yangi", "янги"),
        ("tayyor", "тайёр"),
        ("ayol", "аёл"),
        ("yil", "йил"),
        ("qoʻyaman", "қўяман"),
        ("dunyo", "дунё"),
        # the tutuq separates s and h
        ("Isʼhoq", "Исҳоқ"),
        # ts in a native Uzbek word is т+с (not ц)
        ("ketsa", "кетса"),
        ("oʻtsa", "ўтса"),
        ("xursand", "хурсанд"),
        ("bogʻcha", "боғча"),
    ],
)
def test_rules(latin, cyrillic):
    assert word_to_cyrillic(latin) == cyrillic


@pytest.mark.parametrize(
    ("latin", "cyrillic"),
    [
        ("sentabr", "сентябрь"),
        ("Sentabr", "Сентябрь"),
        ("sentabrda", "сентябрда"),  # a stem-final ь is dropped before a suffix
        ("yanvardan", "январдан"),
        ("filmlar", "фильмлар"),  # ь inside the stem is kept
        ("avtomobilga", "автомобилга"),
        ("sirk", "цирк"),
        ("sirkka", "циркка"),
        ("konsertda", "концертда"),
        ("obyekt", "объект"),
        ("politsiyaga", "полицияга"),
    ],
)
def test_loanwords_with_suffixes(latin, cyrillic):
    assert word_to_cyrillic(latin) == cyrillic


def test_loanword_stem_needs_a_real_suffix():
    # The stem "rol" (роль) does not change "rolik": "ik" is not an Uzbek suffix.
    assert word_to_cyrillic("rolik") == "ролик"


@pytest.mark.parametrize("word", ["DeutschUz", "Müller", "Café", "A1", "B2", "XX", "iPhone", "WhatsApp", "ich"])
def test_foreign_and_codes_stay_latin_when_marked(word):
    keep_marked = word == "ich"  # a German word spelled with Uzbek letters — kept only by the caller's decision
    result = to_cyrillic(word, keep=lambda t: keep_marked)
    assert result == word


def test_text_keeps_marked_german_words_and_punctuation():
    text = "Bu soʻz der Tisch — «stol». 2-dars, A1 darajasi."
    german = {"der", "Tisch"}
    assert to_cyrillic(text, keep=lambda t: t.text in german) == "Бу сўз der Tisch — «стол». 2-дарс, A1 даражаси."


@pytest.mark.parametrize(
    "word",
    ["Oʻzbekiston", "shahar", "maʼno", "eshik", "kecha", "poema", "yer", "qayerda", "tayyor", "Isʼhoq", "ketsa",
     "sentabr", "sentabrda", "filmlar", "avtomobilga", "sirk", "obyekt", "politsiyaga", "litsey", "SHAHAR", "yoz"],
)
def test_round_trip(word):
    assert to_latin(word_to_cyrillic(word)) == word


def test_latin_from_cyrillic_official_rules():
    assert to_latin("Ер юзида етти ўғил") == "Yer yuzida yetti oʻgʻil"
    assert to_latin("кетди, поэма, маъно") == "ketdi, poema, maʼno"
    assert to_latin("1 январдан, цирк, лицей") == "1 yanvardan, sirk, litsey"


def test_missing_loanword_table_falls_back_to_rules(monkeypatch, tmp_path):
    monkeypatch.setattr(_core, "LOANWORDS_FILE", tmp_path / "none.tsv")
    uzcyrl.clear_caches()
    try:
        assert word_to_cyrillic("sirk") == "сирк"
    finally:
        monkeypatch.undo()
        uzcyrl.clear_caches()


@pytest.mark.parametrize(
    ("latin", "cyrillic"),
    [
        ("AQSh dollarida", "АҚШ долларида"),  # sh is one letter in an abbreviation
        ("AQShdagi saylov", "АҚШдаги сайлов"),
        ("FHDYo", "ФҲДЁ"),
        ("SSSRda", "СССРда"),
        ("OITSga chalingan", "ОИТСга чалинган"),
        ("YHXB", "ЙҲХБ"),
        ("YIdan chiqdi", "YIдан чиқди"),  # YI (Yevropa Ittifoqi) = ЕИ — ambiguous, stays Latin
    ],
)
def test_uzbek_abbreviations_are_converted_in_upper_case(latin, cyrillic):
    assert to_cyrillic(latin) == cyrillic


@pytest.mark.parametrize(
    ("latin", "cyrillic"),
    [
        ("YouTubeʼda oching", "YouTubeʼда очинг"),  # a foreign stem stays Latin, the suffix follows the script
        ("WGda yashayman", "WGда яшайман"),
        ("WGʻni topdim", "WGʻни топдим"),
        ("die CDs", "die CDs"),  # German plural -s is not an Uzbek suffix
    ],
)
def test_suffix_after_a_foreign_word_follows_the_script(latin, cyrillic):
    assert to_cyrillic(latin, keep=lambda t: t.text in {"die"}) == cyrillic


@pytest.mark.parametrize(
    ("latin", "cyrillic"),
    [
        ("informatsiyani", "информацияни"),  # ts + i + vowel — Russian loanword (ц)
        ("ratsion", "рацион"),
        ("sotsiolog", "социолог"),
        ("tsement", "цемент"),  # word-initial ts
        ("ketsa", "кетса"),  # verb + conditional suffix — тс
        ("aytsin", "айтсин"),
    ],
)
def test_ts_is_tse_only_in_russian_loanword_patterns(latin, cyrillic):
    assert word_to_cyrillic(latin) == cyrillic


def test_ipa_in_square_brackets_is_never_converted():
    assert to_cyrillic("talaffuzi [ʃøːn]") == "талаффузи [ʃøːn]"


# --- Apostrophe normalization ---------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("o'zbek", "oʻzbek"),
        ("O‘zbekiston", "Oʻzbekiston"),
        ("g`isht", "gʻisht"),
        ("ma'no", "maʼno"),
        ("ta’lim", "taʼlim"),
        ("«stol» 'kitob'", "«stol» 'kitob'"),  # quotes next to spaces are not letters
    ],
)
def test_normalize_uz(raw, normalized):
    assert normalize_uz(raw) == normalized


def test_to_cyrillic_accepts_plain_apostrophes():
    assert to_cyrillic("O'zbekiston, ma'no, g'isht") == "Ўзбекистон, маъно, ғишт"


def test_normalization_can_be_turned_off():
    assert to_cyrillic("o'z", normalize=False) == "о'з"


# --- Loanword table and command line -------------------------------------------------------------------------------

def test_loanword_table_ships_with_the_package():
    table = uzcyrl.loanwords()
    assert len(table) > 700
    assert table["kompyuter"] == "компьютер"


def test_cli_converts_arguments(capsys):
    assert main(["O'zbekiston", "sentabrda"]) == 0
    assert capsys.readouterr().out.strip() == "Ўзбекистон сентябрда"


def test_cli_converts_back_to_latin(capsys):
    assert main(["--latin", "Ўзбекистон сентябрда"]) == 0
    assert capsys.readouterr().out.strip() == "Oʻzbekiston sentabrda"
