"""CJK character classification, Kinsoku line-break rules and optical punctuation metrics."""

from __future__ import annotations

# Opening punctuation: prohibited at end of line (sticks to the following glyph/word).
CJK_OPEN_PUNCT = frozenset("（【《〈「『〔〖“‘")

# Closing / pause punctuation: prohibited at start of line (sticks to the preceding glyph/word).
CJK_CLOSE_PUNCT = frozenset("，。、；：！？）】》〉」』〕〗”’·…—～")

# ASCII punctuation that should not start a new line after a CJK character.
ASCII_NO_START = frozenset(",.;:!?)]}")

# Non-CJK-block symbols commonly written in Chinese notes (circled digits, dashes, quotes, ellipsis).
CJK_CONTEXT_SYMBOLS = frozenset(
    "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
    "“”‘’—…·"
)

# Optical kerning targets (target_lsb_em, target_rsb_em) for over-padded fullwidth CJK punctuation.
# Only applied when a font's measured sidebearings exceed the target, so tight fonts are untouched.
PUNCT_PAUSE = frozenset("，。、；：！？")
PUNCT_CLOSE = frozenset("）】》〉」』〕〗”’")
PUNCT_OPEN = frozenset("（【《〈「『〔〖“‘")


def is_cjk_ideograph(ch: str) -> bool:
    """True for CJK ideographs, Kana, Hangul, Bopomofo and circled numerals."""
    if not ch:
        return False
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF       # CJK Unified Ideographs
        or 0x3400 <= cp <= 0x4DBF    # CJK Extension A
        or 0x3040 <= cp <= 0x31FF    # Hiragana, Katakana, Bopomofo, Hangul Compat
        or 0x2E80 <= cp <= 0x2FDF    # CJK Radicals / Kangxi
        or 0xF900 <= cp <= 0xFAFF    # CJK Compatibility Ideographs
        or 0xAC00 <= cp <= 0xD7AF    # Hangul Syllables
        or 0x2460 <= cp <= 0x2473    # Circled digits ①..⑳
        or 0x20000 <= cp <= 0x2FA1F  # CJK Extensions B..F & Compat
    )


def is_cjk_punct(ch: str) -> bool:
    """True for CJK and fullwidth punctuation marks."""
    if not ch:
        return False
    if ch in CJK_OPEN_PUNCT or ch in CJK_CLOSE_PUNCT:
        return True
    cp = ord(ch)
    return (
        0x3000 <= cp <= 0x303F       # CJK Symbols and Punctuation
        or 0xFE10 <= cp <= 0xFE6F    # Vertical / CJK Compat / Small Form Variants
        or 0xFF01 <= cp <= 0xFF60    # Fullwidth ASCII & Punctuation
        or 0xFFE0 <= cp <= 0xFFEF    # Fullwidth Symbols
    )


def is_cjk(ch: str) -> bool:
    """True for any character belonging to CJK prose (ideographs, fullwidth punctuation, CJK symbols)."""
    if not ch:
        return False
    return is_cjk_ideograph(ch) or is_cjk_punct(ch) or ch in CJK_CONTEXT_SYMBOLS


def has_cjk(s: str) -> bool:
    """Fast check for whether a string contains any CJK character."""
    return any(is_cjk(ch) for ch in s)


def punct_kerning_targets(ch: str) -> tuple[float, float] | None:
    """Desired (lsb_em, rsb_em) for fullwidth CJK punctuation, or None if not squeezed."""
    if ch in PUNCT_PAUSE:
        return (0.08, 0.22)
    if ch in PUNCT_CLOSE:
        return (0.06, 0.16)
    if ch in PUNCT_OPEN:
        return (0.16, 0.06)
    return None
