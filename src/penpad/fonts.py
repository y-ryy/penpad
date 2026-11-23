"""Font registry: bundled handwriting fonts, user fonts and cached glyph outlines."""

from __future__ import annotations

import os
from functools import lru_cache

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# name -> file inside FONT_DIR (or an absolute path for user fonts)
FONTS = {
    "Cedarville": "Cedarville-Cursive.ttf",
    "Bad Script": "BadScript-Regular.ttf",
    "Handlee": "Handlee-Regular.ttf",
    "Caveat": "Caveat.ttf",
    "Gochi Hand": "GochiHand-Regular.ttf",
    "Walter Turncoat": "WalterTurncoat-Regular.ttf",
    "Virgil": "Virgil.woff2",
    "Mynerve": "Mynerve-Regular.ttf",
}

# Tried in order when the chosen font lacks a character. Mynerve covers Greek and
# most math symbols, so output never depends on fonts installed on the machine.
FALLBACKS = ("Virgil", "Mynerve")
_USER_FALLBACKS: list[str] = []


def _clear_caches() -> None:
    _load.cache_clear()
    outline.cache_clear()
    glyph_components.cache_clear()
    glyph_bounds.cache_clear()
    x_height.cache_clear()
    cap_height.cache_clear()
    cjk_height.cache_clear()


def register_font(name: str, path: str, *, fallback: bool = False) -> str:
    """Make a .ttf/.otf/.woff2 usable by name in styles (``font``, ``cjk_font``, ``pinned``...)."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    FONTS[name] = os.path.abspath(path)
    if fallback and name not in _USER_FALLBACKS:
        _USER_FALLBACKS.append(name)
    _clear_caches()
    return name


def ensure_font(name_or_path: str | None) -> str | None:
    """Accept either a registered font name or a path to a .ttf/.otf/.woff2 file."""
    if not name_or_path:
        return None
    if name_or_path in FONTS:
        return name_or_path
    if os.path.exists(name_or_path):
        abs_p = os.path.abspath(name_or_path)
        for existing_name, existing_path in FONTS.items():
            if os.path.abspath(os.path.join(FONT_DIR, existing_path)) == abs_p:
                return existing_name
        stem = os.path.splitext(os.path.basename(abs_p))[0]
        name = stem
        n = 2
        while name in FONTS:
            name = "%s#%d" % (stem, n)
            n += 1
        return register_font(name, abs_p)
    return name_or_path


def font_path(name: str) -> str:
    return os.path.join(FONT_DIR, FONTS[name])


@lru_cache(maxsize=None)
def _load(name: str):
    f = TTFont(font_path(name), fontNumber=0, lazy=True)
    return f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm, f["hmtx"]


def has(name: str | None, ch: str) -> bool:
    return bool(name) and name in FONTS and ord(ch) in _load(name)[1]


def units_per_em(name: str) -> int:
    return _load(name)[2]


@lru_cache(maxsize=4096)
def outline(name: str, ch: str):
    """Recorded drawing operations and advance width of a glyph, or None."""
    gset, cmap, _, hmtx = _load(name)
    g = cmap.get(ord(ch))
    if g is None:
        return None
    pen = DecomposingRecordingPen(gset)
    gset[g].draw(pen)
    return tuple(pen.value), hmtx[g][0]


@lru_cache(maxsize=4096)
def glyph_components(name: str, ch: str):
    """Group a glyph's contours into connected stroke components with inner holes bound to their parent.

    Returns ``(components, adv, glyph_bbox)`` or ``None``, where each component is
    ``(ops_tuple, (cx, cy), (xmin, ymin, xmax, ymax))`` containing one outer contour plus
    every opposite-winding hole contour enclosed by it. Transforming each component as a
    rigid unit keeps inner holes locked to their outer stroke (zero tearing or wall collapse).
    """
    rec = outline(name, ch)
    if rec is None:
        return None
    ops, adv = rec
    raw_contours: list[list] = []
    cur: list = []
    for op, args in ops:
        if (op == "moveTo" or (op == "qCurveTo" and args and args[-1] is None)) and cur:
            raw_contours.append(cur)
            cur = []
        cur.append((op, args))
    if cur:
        raw_contours.append(cur)
    if not raw_contours:
        return (), adv, (0.0, 0.0, 0.0, 0.0)

    meta = []
    gxmin = gymin = float("inf")
    gxmax = gymax = float("-inf")
    for c_ops in raw_contours:
        pts = [a for _, args in c_ops for a in args if a is not None]
        if not pts:
            meta.append((c_ops, 0.0, (0.0, 0.0, 0.0, 0.0), (0.0, 0.0)))
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        gxmin, gymin = min(gxmin, xmin), min(gymin, ymin)
        gxmax, gymax = max(gxmax, xmax), max(gymax, ymax)
        n = len(pts)
        area = 0.5 * sum(
            pts[k][0] * pts[(k + 1) % n][1] - pts[(k + 1) % n][0] * pts[k][1]
            for k in range(n)
        )
        meta.append((c_ops, area, (xmin, ymin, xmax, ymax), (0.5 * (xmin + xmax), 0.5 * (ymin + ymax))))

    if gxmin == float("inf"):
        gxmin = gymin = gxmax = gymax = 0.0

    # Determine outer contour winding sign from the largest-area contour (works for both TTF and CFF)
    max_area = max(meta, key=lambda m: abs(m[1]))[1]
    outer_sign = 1 if max_area >= 0 else -1

    outers = []
    holes = []
    for idx, m in enumerate(meta):
        area = m[1]
        if abs(area) < 1e-3 or (1 if area >= 0 else -1) == outer_sign:
            outers.append((idx, m))
        else:
            holes.append((idx, m))

    if not outers:
        outers = list(enumerate(meta))
        holes = []

    buckets: list[list] = [[m[0]] for _, m in outers]
    tol = 4.0
    for _, hm in holes:
        hxmin, hymin, hxmax, hymax = hm[2]
        hcx, hcy = hm[3]
        best = None
        best_area = float("inf")
        for oi, (_, om) in enumerate(outers):
            oxmin, oymin, oxmax, oymax = om[2]
            if hxmin >= oxmin - tol and hxmax <= oxmax + tol and hymin >= oymin - tol and hymax <= oymax + tol:
                oa = (oxmax - oxmin) * (oymax - oymin)
                if oa < best_area:
                    best_area = oa
                    best = oi
        if best is None:
            best = min(
                range(len(outers)),
                key=lambda oi: (outers[oi][1][3][0] - hcx) ** 2 + (outers[oi][1][3][1] - hcy) ** 2,
            )
        buckets[best].append(hm[0])

    components = []
    for oi, (_, om) in enumerate(outers):
        merged_ops = tuple(item for chunk in buckets[oi] for item in chunk)
        components.append((merged_ops, om[3], om[2]))
    return tuple(components), adv, (gxmin, gymin, gxmax, gymax)


@lru_cache(maxsize=4096)
def glyph_bounds(name: str, ch: str):
    """Return (xmin, ymin, xmax, ymax, adv, upem) in font units, or None."""
    gset, cmap, upem, hmtx = _load(name)
    g = cmap.get(ord(ch))
    if g is None:
        return None
    pen = BoundsPen(gset)
    gset[g].draw(pen)
    if not pen.bounds:
        return None
    xmin, ymin, xmax, ymax = pen.bounds
    return xmin, ymin, xmax, ymax, hmtx[g][0], upem


@lru_cache(maxsize=None)
def x_height(name: str) -> float:
    """Height of the lowercase x as a fraction of the em (measured, OS/2 values are unreliable)."""
    gset, cmap, upem, _ = _load(name)
    g = cmap.get(ord("x"))
    if g is None:
        return 0.5
    pen = BoundsPen(gset)
    gset[g].draw(pen)
    if not pen.bounds:
        return 0.5
    return max(0.2, (pen.bounds[3] - max(pen.bounds[1], 0)) / upem)


@lru_cache(maxsize=None)
def cap_height(name: str) -> float:
    """Measured uppercase letter height as a fraction of the em."""
    heights = []
    for ch in ("H", "A", "M", "E"):
        b = glyph_bounds(name, ch)
        if b:
            heights.append((b[3] - max(b[1], 0)) / b[5])
    if not heights:
        return 0.7
    heights.sort()
    return max(0.3, heights[len(heights) // 2])


@lru_cache(maxsize=None)
def cjk_height(name: str) -> float:
    """Measured median visual height of representative CJK ideographs as a fraction of the em."""
    heights = []
    for ch in ("国", "永", "中", "繁", "学", "水", "木"):
        b = glyph_bounds(name, ch)
        if b:
            heights.append((b[3] - b[1]) / b[5])
    if not heights:
        return 0.85
    heights.sort()
    return max(0.35, heights[len(heights) // 2])


def resolve(name: str, ch: str, extra_fallbacks: tuple[str, ...] = ()) -> str | None:
    """First font in (name, *extra_fallbacks, *FALLBACKS, *_USER_FALLBACKS) that has ch."""
    seen = set()
    for f in (name,) + tuple(extra_fallbacks) + FALLBACKS + tuple(_USER_FALLBACKS):
        if f and f not in seen:
            seen.add(f)
            if has(f, ch):
                return f
    return None
