"""Handwriting styles (pen + letterforms) and ink colors.

A style is a plain dict, so any key can be overridden per call:
``Notebook(style="cursive", jitter=0.9, slant=6)``.
"""

from __future__ import annotations

from . import fonts

# Goodnotes pen colors measured on exported pages.
INKS = {
    "black": "#1e1b1b",
    "navy": "#1a2b4c",
    "blue": "#53aaff",
    "red": "#f33f3f",
    "purple": "#6f44a3",
    "green": "#2f9e44",
    "graphite": "#4a5568",
    "gray": "#adb5bd",
}

HIGHLIGHT_COLOR = "#ffeb64"

UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

CURSIVE = {
    # -- strokes drawn by penpad (lines, arrows, fraction bars) --
    "roughness": 0.9,         # how much a ruled line wobbles
    "bow": 0.6,               # how much a line arcs in the middle
    "stroke_width": 1.7,      # default line width, px on a 900 px wide page
    "pen_width": 0.07,        # drawn symbols (→ ∇ √ ...), fraction of the letter size
    # -- letterforms --
    "font": "Cedarville",     # main handwriting font
    "alternates": [],         # other fonts the hand borrows a letter from now and then
    "alternate_rate": 0.25,   # chance of borrowing, per letter
    "match_x_height": True,   # borrowed lowercase letters take the main font's x-height
    # Letters that are ambiguous in the main font are written with another one.
    # In Cedarville p looks like ρ, w like ω, b like ℓ, l like e, and the capitals are
    # too ornate (Z reads as 3, H as #).
    # Its comma also reads as a subscript 7.
    # Greek comes from Virgil (clear α ζ ω), except ρ, which reads as p there.
    "pinned": dict({c: "Bad Script" for c in UPPER + "pwbl,;"}, ρ="Mynerve"),
    "isolated_font": "Bad Script",   # single letters in formulas (s, t, x) in print style
    "isolated": {"b": "Handlee", "C": "Handlee"},   # lone b reads as 6, lone C as (
    "greek_font": "Virgil",
    "crossed_seven": False,
    # -- variation model (see hand.py) --
    "allographs": 4,          # distinct shapes the hand keeps for each letter
    "digit_allographs": 3,
    "glyph_noise": 0.012,     # outline deformation, fraction of the em
    "digit_noise": 3.6,       # digits deform more than letters in this font
    "instance_noise": 0.35,   # share of the deformation redrawn on every use
    "jitter": 0.7,            # rotation, slant, size and baseline wobble
    "looseness": 0.6,         # baseline drift, word tilt
    "slant": 0.0,             # mean slant in degrees (positive leans right)
    "fatigue": 0.0,           # extra jitter towards the end of long documents
    "pressure": 0.6,          # pen weight parameter
    "margin_jitter": 2.5,     # subtle organic left-margin drift across lines (px)
    "baseline_jitter": 0.04,  # subtle vertical baseline offset as fraction of ruling pitch
    "correction_rate": 0.0,   # opt-in occasional false-start + strikethrough on prose words
    "tone_variation": 0.0,    # Goodnotes ink is flat
    "retrace": 0.0,           # chance of going over a letter twice
    # -- font mixing & CJK typography (neutral by default for Latin styles) --
    "cjk_font": None,         # dedicated CJK handwriting font (name or .ttf/.otf/.woff2 path)
    "cjk_scale": 1.0,         # CJK scale multiplier (float or "auto" to align visual height)
    "cjk_target_height": 0.90,  # target CJK ink height in em when cjk_scale="auto"
    "latin_scale": 1.0,       # scale multiplier for Latin letters/digits (e.g. 1.15 with a CJK main font)
    "caps_font": None,        # optional dedicated font for uppercase A-Z (e.g. "Bad Script")
    "caps_scale": 1.0,        # scale multiplier for uppercase A-Z (float or "auto")
    "font_scales": {},        # optional per-font scale overrides {font_name: scale}
    "cjk_max_rotation": 3.5,  # tighter rotation clamp (deg) for square CJK glyphs
    "cjk_max_skew": 4.5,      # tighter skew clamp (deg) so glyph tops never collide
    "cjk_max_scale": 0.08,    # tighter size variation clamp for CJK glyphs
    "cjk_glyph_noise": None,  # outline deformation for CJK (None = glyph_noise * 0.55)
    "cjk_stroke_shift": 0.12, # legacy fallback contour shift factor
    "cjk_component_shift": 0.022,  # hole-bound per-component (radical/stroke) offset, fraction of em
    "cjk_component_rot": 2.2,      # per-component rotation around its own centroid (degrees)
    "cjk_component_scale": 0.045,  # per-component independent X/Y micro-scale (fraction)
    "cjk_elastic": 0.024,          # smooth 2D bilinear elastic warp amplitude (fraction of em)
    "cjk_pressure": None,     # pathops stroke dilation for CJK (None = min(pressure, 0.25))
    "cjk_punct_squeeze": True,  # optical kerning for over-padded fullwidth CJK punctuation
    "cjk_tracking": 0.0,      # extra CJK horizontal tracking in em
    "size_scale": 1.0,        # overall multiplier applied to paper.text_size
    "density": "normal",      # layout density: "compact", "normal" or "spacious"
    "min_orphan_lines": 0,    # move whole question/paragraph to next page if fewer lines fit (e.g. 3)
    "smooth_baseline": False, # continuous cross-token oscillating baseline wave (auto-on for CJK)
    "line_spacing": 0.0,      # extra vertical spacing between lines in ruling pitches
    "monochrome": None,       # optional single ink override (e.g. "black" or "#1e1b1b")
    "monochrome_footer": False,  # if True, monochrome also overrides the gray page footer
    # -- ink --
    "ink_softness": 0.3,      # edge blur radius at 225 dpi
    "ink_gain": 1.3,
    # -- render --
    "supersample": 2.0,
}

PRINT = dict(
    CURSIVE,
    roughness=1.9, bow=1.1, stroke_width=2.6, pen_width=0.085,
    font="Handlee", alternates=[],
    # Caveat b looks like 6, cursive w like ω, Handlee p like ρ and u like υ
    pinned={"b": "Virgil", "w": "Bad Script", "W": "Walter Turncoat", "p": "Gochi Hand", "u": "Gochi Hand",
            "ρ": "Mynerve"},
    isolated_font=None, isolated={},
    glyph_noise=0.020, digit_noise=1.0, jitter=0.9, looseness=0.7,
    pressure=0.45, tone_variation=0.18, retrace=0.13, ink_softness=0.6, ink_gain=1.7,
)

CASUAL = dict(
    PRINT,
    roughness=1.2, stroke_width=2.0, pen_width=0.075,
    font="Caveat", alternates=[],
    pinned={"b": "Virgil", "w": "Bad Script", "ρ": "Mynerve"},
    glyph_noise=0.016, jitter=0.8, looseness=0.6, slant=3.0,
    pressure=0.35, tone_variation=0.0, retrace=0.0, ink_softness=0.35, ink_gain=1.4,
)

# Mixed CJK + Latin/Math handwriting style: pairs any CJK font (via cjk_font=...)
# with balanced Bad Script uppercase/ambiguous letters, clean math symbols, tight
# anti-overlap clamps and optical fullwidth punctuation kerning.
CJK = dict(
    CURSIVE,
    font="Handlee",
    caps_font="Bad Script",
    caps_scale=0.70,
    pinned=dict({c: "Bad Script" for c in "pwbl,;"}, ρ="Mynerve"),
    isolated_font=None,
    isolated={"b": "Handlee", "C": "Handlee"},
    digit_noise=1.0,
    jitter=0.65,
    looseness=0.55,
    pressure=0.28,
    cjk_scale="auto",
    cjk_target_height=0.90,
    cjk_max_rotation=3.5,
    cjk_max_skew=4.5,
    cjk_max_scale=0.08,
    cjk_stroke_shift=0.12,
    cjk_pressure=0.18,
    cjk_punct_squeeze=True,
    size_scale=0.94,
    smooth_baseline=True,
    min_orphan_lines=3,
    line_spacing=0.0,
)

DENSITIES = ("compact", "normal", "spacious")
STYLES = {"cursive": CURSIVE, "print": PRINT, "casual": CASUAL, "cjk": CJK}


def _resolve_style_fonts(d: dict) -> dict:
    """Allow passing .ttf/.otf/.woff2 file paths directly in style font slots."""
    density = d.get("density", "normal")
    if density not in DENSITIES:
        raise ValueError("unknown density %r, choose from %s" % (density, ", ".join(DENSITIES)))
    for key in ("font", "cjk_font", "caps_font", "greek_font", "isolated_font"):
        if d.get(key):
            d[key] = fonts.ensure_font(d[key])
    if d.get("alternates"):
        d["alternates"] = [fonts.ensure_font(a) for a in d["alternates"]]
    if d.get("pinned"):
        d["pinned"] = {k: fonts.ensure_font(v) for k, v in d["pinned"].items()}
    if d.get("isolated"):
        d["isolated"] = {k: fonts.ensure_font(v) for k, v in d["isolated"].items()}
    if d.get("font_scales"):
        d["font_scales"] = {fonts.ensure_font(k): v for k, v in d["font_scales"].items()}
    if d.get("monochrome") is True:
        d["monochrome"] = "black"
    return d


def cjk_style(cjk_font: str, *, latin_from_cjk: bool = False, pure_cjk: bool = False,
              monochrome: str | bool | None = None, base: str = "cjk", **overrides) -> dict:
    """Build a ready-to-use CJK + Latin/Math mixed handwriting style from any raw CJK font file.

    - ``latin_from_cjk=False`` (default): uses the base style's English handwriting font for
      Latin/math while routing Chinese/fullwidth punctuation to ``cjk_font`` with auto-aligned size.
    - ``latin_from_cjk=True``: uses ``cjk_font`` as the main font (including its lowercase/digits,
      scaled up to match) while borrowing ``Bad Script`` for uppercase A-Z (scaled 0.70) and
      ambiguous letters ``p w b l , ;``.
    - ``pure_cjk=True``: uses ``cjk_font`` uniformly for Chinese, uppercase, lowercase and digits
      (scaled 1.15 for Latin) while keeping only ``Virgil`` for Greek letters so math stays crisp.
    """
    cjk_name = fonts.ensure_font(cjk_font)
    opts = dict(cjk_font=cjk_name)
    if pure_cjk:
        opts.update(
            font=cjk_name,
            latin_scale=1.15,
            caps_font=None,
            caps_scale=1.15,
            pinned={},
            isolated_font=None,
            isolated={},
            greek_font="Virgil",
            size_scale=0.92,
        )
    elif latin_from_cjk:
        opts.update(
            font=cjk_name,
            latin_scale=1.15,
            caps_font="Bad Script",
            caps_scale=0.70,
            pinned=dict({c: "Bad Script" for c in "pwbl,;"}, ρ="Mynerve"),
            isolated_font=None,
            isolated={"b": "Handlee", "C": "Handlee"},
            size_scale=0.92,
        )
    if monochrome is not None:
        opts["monochrome"] = "black" if monochrome is True else (monochrome or None)
    opts.update(overrides)
    return get_style(base, **opts)


def get_style(style=None, **overrides) -> dict:
    """Resolve a preset name or dict and apply overrides."""
    if style is None:
        base = CURSIVE
    elif isinstance(style, str):
        if style not in STYLES:
            raise ValueError("unknown style %r, choose from %s" % (style, ", ".join(STYLES)))
        base = STYLES[style]
    else:
        base = style
    return _resolve_style_fonts(dict(base, **overrides))


def ink(color) -> str:
    """Ink name ('blue') or any hex color ('#123456')."""
    if color is None:
        return INKS["black"]
    if color in INKS:
        return INKS[color]
    if isinstance(color, str) and color.startswith("#") and len(color) in (4, 7):
        return color
    raise ValueError("unknown ink %r: use %s or a #hex color" % (color, ", ".join(INKS)))
