"""Uzbek Latin apostrophe normalization: oʻ/gʻ use U+02BB (ʻ), the tutuq uses U+02BC (ʼ)."""
from __future__ import annotations

import re
import unicodedata

OKINA = "ʻ"  # U+02BB — oʻ, gʻ
TUTUQ = "ʼ"  # U+02BC — maʼno, taʼlim
_APOSTROPHES = "'‘’`´ʻʼʹ′"  # ' ‘ ’ ` ´ ʻ ʼ ʹ ′

_OKINA_RE = re.compile(rf"([oOgG])[{_APOSTROPHES}]")
_TUTUQ_RE = re.compile(rf"(?<=\w)(?<![oOgG])[{_APOSTROPHES}](?=\w)")


def normalize_uz(text: str) -> str:
    """Replaces apostrophe variants in Uzbek Latin text with the standard characters: o'zbek → oʻzbek, ma'no → maʼno."""
    text = unicodedata.normalize("NFC", text)
    text = _OKINA_RE.sub(lambda m: m.group(1) + OKINA, text)
    return _TUTUQ_RE.sub(TUTUQ, text)
