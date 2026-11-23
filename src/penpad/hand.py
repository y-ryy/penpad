"""The writer model: how one person's letters vary while staying recognizable.

Three layers of variation, from slow to fast:

1. **Writer state**: slant, rotation, size and baseline follow mean-reverting
   (Ornstein-Uhlenbeck) processes, so neighbouring letters lean and float
   together the way a real hand does, instead of every letter jittering on its own.
2. **Allographs**: each character has a small fixed repertoire of shapes
   (``allographs``) derived from the seed. The same writer always draws an "a" in
   one of, say, four ways and never repeats the same shape twice in a row.
3. **Instance noise**: every use redraws a fraction (``instance_noise``) of the
   outline deformation, so no two letters are pixel-identical.

Glyph transforms are baked directly into page-space path coordinates (pure fill,
no per-letter transform matrices or fill+stroke operators), preserving exact
letterforms while keeping the PDF stream clean. Everything is deterministic for
a given seed.
"""

from __future__ import annotations

import math
import random
import zlib

from fontTools.pens.svgPathPen import SVGPathPen

try:
    import pathops as _pathops
except ImportError:  # pragma: no cover
    _pathops = None

from . import fonts
from .cjk import is_cjk, is_cjk_punct, punct_kerning_targets

DIGITS = frozenset("0123456789")
SPACES = {" ": 0.52, "\u2009": 0.17, "\u2005": 0.25, "\u2003": 1.0}   # widths in letter sizes
GREEK = range(0x0370, 0x0400)

# legibility limits, applied after all variation
MAX_ROTATION = 9.0    # degrees
MAX_SKEW = 14.0       # degrees around the writer's slant
MAX_SCALE = 0.18      # relative size change


def _stable_seed(*parts) -> int:
    return zlib.crc32("|".join(map(str, parts)).encode())


class _OU:
    """Discrete Ornstein-Uhlenbeck process with stationary deviation ``sigma``."""

    def __init__(self, rng, rho):
        self.rng, self.rho, self.x = rng, rho, 0.0

    def step(self, sigma):
        self.x = self.rho * self.x + math.sqrt(1 - self.rho ** 2) * self.rng.gauss(0, sigma)
        return self.x


def hand_line(x1, y1, x2, y2, r, roughness, bow):
    """SVG path of one pen pass between two points, with wobble and a slight arc."""
    length2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
    length = math.sqrt(length2)
    off = 2.0 * roughness
    if off * off * 100 > length2:
        off = length / 10.0
    div = 0.2 + r.random() * 0.2
    mx = bow * 2.0 * (y2 - y1) / 200.0
    my = bow * 2.0 * (x1 - x2) / 200.0

    def d():
        return r.uniform(-off, off)

    return "M%.2f %.2f C%.2f %.2f %.2f %.2f %.2f %.2f" % (
        x1 + d(), y1 + d(),
        mx + x1 + (x2 - x1) * div + d(), my + y1 + (y2 - y1) * div + d(),
        mx + x1 + 2 * (x2 - x1) * div + d(), my + y1 + 2 * (y2 - y1) * div + d(),
        x2 + d(), y2 + d(),
    )


def _mat_mul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _letter_matrix(tx, ty, rot_deg, skew_deg, sx, sy):
    rad = math.radians(rot_deg)
    cs, sn = math.cos(rad), math.sin(rad)
    tk = math.tan(math.radians(skew_deg))
    return (cs * sx, sn * sx, (cs * tk - sn) * sy, (sn * tk + cs) * sy, tx, ty)


def _rotate_around(deg, cx, cy):
    rad = math.radians(deg)
    cs, sn = math.cos(rad), math.sin(rad)
    return (cs, sn, -sn, cs, cx - cs * cx + sn * cy, cy - sn * cx - cs * cy)


def _xform_pt(m, pt):
    a, b, c, d, e, f = m
    x, y = pt
    return (a * x + c * y + e, b * x + d * y + f)


def _bar_path(p0, p1, half_w):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return ""
    nx, ny = -dy / L * half_w, dx / L * half_w
    return "M%.1f %.1fL%.1f %.1fL%.1f %.1fL%.1f %.1fZ" % (
        p0[0] + nx, p0[1] + ny,
        p1[0] + nx, p1[1] + ny,
        p1[0] - nx, p1[1] - ny,
        p0[0] - nx, p0[1] - ny,
    )


class Hand:
    """One writer. Keep a single Hand per page so the letters stay coherent."""

    def __init__(self, style: dict, seed: int = 1):
        self.style = style
        self.seed = seed
        self.rng = random.Random(seed)
        self._slant = _OU(self.rng, 0.9)
        self._rot = _OU(self.rng, 0.85)
        self._size = _OU(self.rng, 0.92)
        self._drift = _OU(self.rng, 0.93)
        self._smooth_drift = _OU(self.rng, 0.72)
        self._wave_phase = self.rng.uniform(0, 6.28)
        self._tilt = _OU(self.rng, 0.6)
        self._last = {}
        self.glyphs = 0
        self._history = []      # (rot, skew, grow) per glyph for diagnostics/tests
        self._dy_history = []   # vertical baseline offset (px) per glyph for continuity tests

    # ------------------------------------------------------------ font choice
    def font_for(self, s: str, i: int) -> str | None:
        """Font pinned for s[i], or None to pick between the main font and alternates."""
        e, ch = self.style, s[i]
        cjk_font = e.get("cjk_font")
        if is_cjk(ch) and cjk_font and fonts.has(cjk_font, ch):
            return cjk_font
        prev_ascii = i > 0 and s[i - 1].isascii() and s[i - 1].isalpha()
        next_ascii = i + 1 < len(s) and s[i + 1].isascii() and s[i + 1].isalpha()
        lone = ch.isascii() and ch.isalpha() and not prev_ascii and not next_ascii
        if lone:
            iso = e.get("isolated", {})
            if ch in iso:
                return iso[ch]
            if e.get("isolated_font"):
                return e["isolated_font"]
        if ch.isascii() and ch.isupper() and e.get("caps_font") and fonts.has(e["caps_font"], ch):
            return e["caps_font"]
        if ch in e.get("pinned", {}):
            return e["pinned"][ch]
        if ord(ch) in GREEK and fonts.has(e.get("greek_font"), ch):
            return e["greek_font"]
        return None

    def _pick_font(self, s, i):
        e, ch = self.style, s[i]
        cjk_font = e.get("cjk_font")
        extra = (cjk_font,) if cjk_font else ()
        if ch in DIGITS:
            f = e["font"]
        else:
            f = self.font_for(s, i)
            if f is None:
                f = e["font"]
                pool = [a for a in e["alternates"] if fonts.has(a, ch)]
                if pool and fonts.has(f, ch) and self.rng.random() < e.get("alternate_rate", 0.25):
                    f = self.rng.choice(pool)
        return fonts.resolve(f, ch, extra_fallbacks=extra)

    def _resolve_cjk_scale(self, font: str) -> float:
        cs = self.style.get("cjk_scale", 1.0)
        if cs == "auto":
            target = float(self.style.get("cjk_target_height", 0.90))
            h = fonts.cjk_height(font)
            return max(0.85, min(1.45, target / h))
        return float(cs)

    def cjk_visual_scale(self) -> float:
        """Effective height ratio of CJK characters relative to nominal size."""
        e = self.style
        f = e.get("cjk_font") or e["font"]
        if not f or f not in fonts.FONTS:
            return 1.0
        return self._resolve_cjk_scale(f) * fonts.cjk_height(f)

    def _glyph_scale(self, ch: str, font: str, size: float) -> float:
        e = self.style
        upem = fonts.units_per_em(font)
        scale = size / upem
        cjk = is_cjk(ch)
        if cjk:
            scale *= self._resolve_cjk_scale(font)
        else:
            latin_scale = float(e.get("latin_scale", 1.0))
            if ch.isascii() and ch.isupper():
                cs = e.get("caps_scale", 1.0)
                if cs == "auto":
                    scale *= max(0.55, min(1.25, 0.68 / fonts.cap_height(font)))
                elif float(cs) != 1.0:
                    scale *= float(cs)
                elif latin_scale != 1.0 and font == e["font"]:
                    scale *= latin_scale
            elif ch.isascii() and (ch.isalpha() or ch in DIGITS):
                if latin_scale != 1.0 and font == e["font"]:
                    scale *= latin_scale
                if font != e["font"] and e.get("match_x_height", True) and ch.islower():
                    ref_x = fonts.x_height(e["font"]) * latin_scale
                    k = ref_x / fonts.x_height(font)
                    scale *= max(0.75, min(1.35, k))
            elif font != e["font"] and e.get("match_x_height", True) and ch.islower():
                k = fonts.x_height(e["font"]) / fonts.x_height(font)
                scale *= max(0.75, min(1.35, k))
        fscales = e.get("font_scales")
        if fscales and font in fscales:
            scale *= float(fscales[font])
        return scale

    def _punct_adjust(self, ch: str, font: str, upem: int, adv: float) -> tuple[float, float]:
        """Optical sidebearing trim for over-padded fullwidth CJK punctuation.

        Returns (shift_x_fu, effective_adv_fu) in font units.
        """
        if not self.style.get("cjk_punct_squeeze", True) or not is_cjk_punct(ch):
            return 0.0, adv
        targets = punct_kerning_targets(ch)
        if targets is None:
            return 0.0, adv
        b = fonts.glyph_bounds(font, ch)
        if b is None:
            return 0.0, adv
        xmin, _, xmax, _, raw_adv, _ = b
        gw = max(0.0, xmax - xmin)
        lsb = xmin
        rsb = raw_adv - xmax
        t_lsb = targets[0] * upem
        t_rsb = targets[1] * upem
        shift_x = -(lsb - t_lsb) if lsb > t_lsb else 0.0
        eff_lsb = min(lsb, t_lsb) if lsb > 0 else lsb
        eff_rsb = min(rsb, t_rsb) if rsb > 0 else rsb
        eff_adv = max(gw + 0.12 * upem, gw + eff_lsb + eff_rsb)
        return shift_x, min(adv, eff_adv)

    def measure(self, s: str, size: float = 18) -> float:
        """Fast deterministic horizontal width estimate (no RNG state mutation or pathops)."""
        e = self.style
        u = size / 24.0
        jit = e["jitter"]
        total = 0.0
        for i, ch in enumerate(s):
            if ch in SPACES:
                total += size * SPACES[ch]
                continue
            font = self._pick_font(s, i)
            if font is None:
                total += size * 0.52
                continue
            rec = fonts.outline(font, ch)
            upem = fonts.units_per_em(font)
            adv = rec[1] if rec is not None else upem * 0.5
            _, adv = self._punct_adjust(ch, font, upem, adv)
            scale = self._glyph_scale(ch, font, size)
            w = (adv or upem * 0.5) * scale
            if is_cjk(ch):
                total += w + e.get("cjk_tracking", 0.0) * size + 0.20 * jit * u
            else:
                total += w + 0.35 * jit * u
        return total

    # ------------------------------------------------------------ glyph shape
    def _variant(self, font, ch):
        """Pick one of the writer's allographs for ch, never the same one twice in a row."""
        k = self.style["digit_allographs" if ch in DIGITS else "allographs"]
        k = max(1, int(k))
        last = self._last.get((font, ch))
        v = self.rng.randrange(k)
        if k > 1 and v == last:
            v = (v + 1 + self.rng.randrange(k - 1)) % k
        self._last[(font, ch)] = v
        return random.Random(_stable_seed(self.seed, font, ch, v))

    def _deform_ops(self, font, ch, vr, noise, cjk: bool = False):
        """Return deformed glyph drawing ops and advance width in font units.

        For CJK glyphs, applies two structure-preserving layers:
        1. Hole-bound connected-component transforms (micro translation, rotation around
           component centroid, and independent X/Y scale), keeping inner holes locked to
           their parent stroke so walls never tear or collapse.
        2. A smooth 2D bilinear elastic warp field across the glyph box, giving single-contour
           cursive characters (like ``的`` or ``十``) organic stroke-level variation too.
        """
        if cjk:
            comp_rec = fonts.glyph_components(font, ch)
            if comp_rec is None:
                return None, 0
            components, adv, (gxmin, gymin, gxmax, gymax) = comp_rec
            if not components:
                return (), adv
            upem = fonts.units_per_em(font)
            e, r = self.style, self.rng
            share = float(e["instance_noise"])
            comp_shift = float(e.get("cjk_component_shift", 0.022)) * upem
            comp_rot = float(e.get("cjk_component_rot", 2.2))
            comp_scale = float(e.get("cjk_component_scale", 0.045))
            elastic = float(e.get("cjk_elastic", 0.024)) * upem

            # Layer 2: smooth 2D bilinear elastic warp field (zero-mean 4 corner anchors)
            def _anchor():
                return (
                    vr.gauss(0.0, elastic * 0.65) + r.gauss(0.0, elastic * 0.35 * share),
                    vr.gauss(0.0, elastic * 0.65) + r.gauss(0.0, elastic * 0.35 * share),
                )

            if elastic > 1e-4:
                c00, c10, c01, c11 = _anchor(), _anchor(), _anchor(), _anchor()
                mx = 0.25 * (c00[0] + c10[0] + c01[0] + c11[0])
                my = 0.25 * (c00[1] + c10[1] + c01[1] + c11[1])
                cap = elastic * 1.4
                corners = tuple(
                    (max(-cap, min(cap, cx - mx)), max(-cap, min(cap, cy - my)))
                    for cx, cy in (c00, c10, c01, c11)
                )
            else:
                corners = ((0.0, 0.0),) * 4

            gw = max(gxmax - gxmin, 0.25 * upem)
            gh = max(gymax - gymin, 0.25 * upem)

            # Layer 1: per-component transforms (zero-mean translation so glyph stays centered)
            n_comp = len(components)
            c_xforms = []
            if n_comp >= 2 and (comp_shift > 1e-4 or comp_rot > 1e-4 or comp_scale > 1e-4):
                dxs, dys = [], []
                for _ in range(n_comp):
                    dx = vr.gauss(0.0, comp_shift * 0.70) + r.gauss(0.0, comp_shift * 0.35 * share)
                    dy = vr.gauss(0.0, comp_shift * 0.70) + r.gauss(0.0, comp_shift * 0.35 * share)
                    dxs.append(max(-comp_shift, min(comp_shift, dx)))
                    dys.append(max(-comp_shift, min(comp_shift, dy)))
                mdx = sum(dxs) / n_comp
                mdy = sum(dys) / n_comp
                for k in range(n_comp):
                    ang = vr.gauss(0.0, comp_rot * 0.65) + r.gauss(0.0, comp_rot * 0.35 * share)
                    ang = math.radians(max(-comp_rot, min(comp_rot, ang)))
                    sx = 1.0 + max(-comp_scale, min(comp_scale,
                                   vr.gauss(0.0, comp_scale * 0.65) + r.gauss(0.0, comp_scale * 0.35 * share)))
                    sy = 1.0 + max(-comp_scale, min(comp_scale,
                                   vr.gauss(0.0, comp_scale * 0.65) + r.gauss(0.0, comp_scale * 0.35 * share)))
                    c_xforms.append((dxs[k] - mdx, dys[k] - mdy, math.cos(ang), math.sin(ang), sx, sy))
            else:
                c_xforms = [(0.0, 0.0, 1.0, 0.0, 1.0, 1.0)] * n_comp

            fine = upem * noise * 0.08 * (0.5 + share)
            c00, c10, c01, c11 = corners
            deformed = []
            for (c_ops, (cx, cy), _), (dx, dy, cs, sn, sx, sy) in zip(components, c_xforms):
                def _xform_cjk(pt, _cx=cx, _cy=cy, _dx=dx, _dy=dy, _cs=cs, _sn=sn, _sx=sx, _sy=sy):
                    # 1. Per-component local scale + rotation around centroid + offset
                    lx = (pt[0] - _cx) * _sx
                    ly = (pt[1] - _cy) * _sy
                    x = _cx + lx * _cs - ly * _sn + _dx
                    y = _cy + lx * _sn + ly * _cs + _dy
                    # 2. Smooth 2D bilinear elastic warp field
                    if elastic > 1e-4:
                        s = max(0.0, min(1.0, (x - gxmin) / gw))
                        t = max(0.0, min(1.0, (y - gymin) / gh))
                        ms, mt = 1.0 - s, 1.0 - t
                        wx = ms * mt * c00[0] + s * mt * c10[0] + ms * t * c01[0] + s * t * c11[0]
                        wy = ms * mt * c00[1] + s * mt * c10[1] + ms * t * c01[1] + s * t * c11[1]
                        x += wx
                        y += wy
                    if fine > 1e-4:
                        x += r.gauss(0.0, fine)
                        y += r.gauss(0.0, fine)
                    return (x, y)

                for op, args in c_ops:
                    deformed.append((op, tuple(None if a is None else _xform_cjk(a) for a in args)))
            return deformed, adv

        rec = fonts.outline(font, ch)
        if rec is None:
            return None, 0
        ops, adv = rec
        upem = fonts.units_per_em(font)
        share = self.style["instance_noise"]
        r = self.rng
        a1 = upem * noise * vr.uniform(0.6, 1.4)
        a2 = upem * noise * vr.uniform(0.6, 1.4)
        w1, w2 = vr.uniform(1.2, 2.6), vr.uniform(1.2, 2.6)
        f1, f2 = vr.uniform(0, 6.28), vr.uniform(0, 6.28)
        f1 += r.gauss(0, 0.6 * share)
        f2 += r.gauss(0, 0.6 * share)
        fine = upem * noise * 0.12 * (0.5 + share)
        shift = [0.0, 0.0]

        def p(pt):
            x, y = pt
            return (x + a1 * math.sin(w1 * y / upem + f1) + shift[0] + r.gauss(0, fine),
                    y + a2 * math.sin(w2 * x / upem + f2) + shift[1] + r.gauss(0, fine))

        deformed = []
        for op, args in ops:
            if op == "moveTo" or (op == "qCurveTo" and args and args[-1] is None):
                for j in (0, 1):
                    shift[j] = vr.gauss(0, upem * noise * 0.45) + r.gauss(0, upem * noise * 0.2 * share)
            deformed.append((op, tuple(None if a is None else p(a) for a in args)))
        return deformed, adv

    @staticmethod
    def _render_ops(ops, mat, stroke_px: float = 0.0) -> str:
        """Bake affine transform into glyph ops and convert fill+stroke pressure into one pure-fill path."""
        if _pathops is not None and stroke_px > 1e-3:
            try:
                fill_p = _pathops.Path()
                pen = fill_p.getPen()
                for op, args in ops:
                    getattr(pen, op)(*[None if a is None else _xform_pt(mat, a) for a in args])
                stroke_p = _pathops.Path(fill_p)
                stroke_p.stroke(
                    stroke_px,
                    _pathops.LineCap.ROUND_CAP,
                    _pathops.LineJoin.ROUND_JOIN,
                    4.0,
                )
                stroke_p.convertConicsToQuads()
                merged = _pathops.Path()
                _pathops.union([fill_p, stroke_p], merged.getPen())
                merged.convertConicsToQuads()
                svg_pen = SVGPathPen(None, ntos=lambda v: "%.1f" % v)
                merged.draw(svg_pen)
                d = svg_pen.getCommands()
                if d:
                    return d
            except Exception:
                pass
        pen = SVGPathPen(None, ntos=lambda v: "%.1f" % v)
        for op, args in ops:
            getattr(pen, op)(*[None if a is None else _xform_pt(mat, a) for a in args])
        return pen.getCommands()

    # ------------------------------------------------------------ writing
    def write(self, x, y, s, color, size=18, anchor="start"):
        """SVG of the handwritten string with baseline at y, and the pen advance."""
        e, r = self.style, self.rng
        fat = 1 + e.get("fatigue", 0) * min(1.0, self.glyphs / 3000)
        jit, loose = e["jitter"] * fat, e["looseness"]
        u = size / 24.0   # variation amplitudes were tuned at 24 px letters

        glyphs = []
        for i, ch in enumerate(s):
            if ch in SPACES:
                glyphs.append((ch, None, size * SPACES[ch], 1.0, None, None, False, 0.0))
                continue
            font = self._pick_font(s, i)
            if font is None:
                glyphs.append((ch, None, size * 0.5, 1.0, None, None, False, 0.0))
                continue
            cjk = is_cjk(ch)
            vr = self._variant(font, ch)
            if cjk:
                cjk_noise = e.get("cjk_glyph_noise")
                noise = float(cjk_noise) if cjk_noise is not None else e["glyph_noise"] * 0.55
            else:
                noise = e["glyph_noise"] * (e["digit_noise"] if ch in DIGITS else 1.0)
            ops, adv = self._deform_ops(font, ch, vr, noise, cjk=cjk)
            upem = fonts.units_per_em(font)
            shift_x_fu, eff_adv = self._punct_adjust(ch, font, upem, adv or upem * 0.5)
            scale = self._glyph_scale(ch, font, size)
            glyphs.append((ch, ops, eff_adv * scale, scale, vr, font, cjk, shift_x_fu))

        total = sum(g[2] for g in glyphs) + 0.45 * jit * u * len(glyphs)
        cx = x - total / 2 if anchor == "middle" else (x - total if anchor == "end" else x)
        start = cx
        use_smooth = bool(e.get("smooth_baseline")) or bool(e.get("cjk_font")) or any(g[6] for g in glyphs)
        if use_smooth:
            # Avoid rigid lever-arm rotation across long coalesced CJK runs; baseline sway is
            # driven by the continuous cross-token oscillating wave below (上→中→中→下→下→中→中→上).
            phase = 0.0
            tilt_mat = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        else:
            phase = r.uniform(0, 6.28)
            tilt = self._tilt.step(1.0 * loose)
            tilt_mat = _rotate_around(tilt, x, y)

        out = []
        word_parts = []
        word_color = None
        word_retraces = []

        def flush_word():
            nonlocal word_parts, word_color, word_retraces
            if word_parts:
                out.append('<path d="%s" fill="%s"/>' % ("".join(word_parts), word_color))
            for rt_d, rt_c in word_retraces:
                out.append('<path d="%s" fill="%s" opacity="0.75"/>' % (rt_d, rt_c))
            word_parts = []
            word_color = None
            word_retraces = []

        cjk_max_rot = min(MAX_ROTATION, float(e.get("cjk_max_rotation", 3.5)))
        cjk_max_skew = min(MAX_SKEW, float(e.get("cjk_max_skew", 4.5)))
        cjk_max_scale = min(MAX_SCALE, float(e.get("cjk_max_scale", 0.08)))
        cjk_tracking = float(e.get("cjk_tracking", 0.0))

        for i, (ch, ops, w, scale, vr, font, cjk, shift_x_fu) in enumerate(glyphs):
            if not ops:
                flush_word()
                cx += (w if ch in SPACES else max(w, size * 0.52)) + r.uniform(0.0, 1.6) * jit * u
                continue
            self.glyphs += 1
            if cjk:
                rot = vr.uniform(-1.8, 1.8) * jit + self._rot.step(1.4 * jit) + r.uniform(-1.0, 1.0) * jit
                skew = (e["slant"] * 0.45 + vr.uniform(-1.5, 1.5) * jit + self._slant.step(1.8 * jit)
                        + r.uniform(-1.0, 1.0) * jit)
                grow = vr.uniform(-0.03, 0.03) * jit + self._size.step(0.04 * jit) + r.uniform(-0.02, 0.02) * jit
                rot = max(-cjk_max_rot, min(cjk_max_rot, rot))
                skew = max(e["slant"] * 0.45 - cjk_max_skew, min(e["slant"] * 0.45 + cjk_max_skew, skew))
                grow = max(-cjk_max_scale, min(cjk_max_scale, grow))
            else:
                rot = vr.uniform(-2.5, 2.5) * jit + self._rot.step(2.2 * jit) + r.uniform(-1.5, 1.5) * jit
                skew = (e["slant"] + vr.uniform(-2.5, 2.5) * jit + self._slant.step(3.2 * jit)
                        + r.uniform(-2.0, 2.0) * jit)
                grow = vr.uniform(-0.05, 0.05) * jit + self._size.step(0.07 * jit) + r.uniform(-0.03, 0.03) * jit
                rot = max(-MAX_ROTATION, min(MAX_ROTATION, rot))
                skew = max(e["slant"] - MAX_SKEW, min(e["slant"] + MAX_SKEW, skew))
                grow = max(-MAX_SCALE, min(MAX_SCALE, grow))
            self._history.append((rot, skew, grow))

            if use_smooth:
                # Continuous oscillating wave across tokens: smooth 上→中→中→下→下→中→中→上
                step_rad = (0.44 if cjk else 0.28) * (0.85 + 0.30 * r.random())
                self._wave_phase += step_rad
                wave = 1.55 * loose * math.sin(self._wave_phase)
                mdrift = self._smooth_drift.step(0.45 * loose)
                micro = r.uniform(-0.32, 0.32) * jit
                max_dy = 2.4 * max(0.45, loose) * u
                dy = max(-max_dy, min(max_dy, (wave + mdrift + micro) * u))
            else:
                dy = (self._drift.step(2.4 * loose) + math.sin(phase + i * 0.8) * jit
                      + r.uniform(-1.0, 1.0) * jit) * u
            self._dy_history.append(dy)
            sx = scale * (1 + grow)
            sy = scale * (1 + grow + vr.uniform(-0.03 if cjk else -0.05, 0.03 if cjk else 0.05))
            c = _tone(color, r, e["tone_variation"] * loose) if e["tone_variation"] else color
            if cjk:
                cjk_p = e.get("cjk_pressure")
                press = float(cjk_p) if cjk_p is not None else min(float(e["pressure"]), 0.25)
                sw_px = r.uniform(0.70, 1.05) * press * max(0.75, u)
            else:
                # Keep pen weight consistent across the page (compensate thinner borrowed fonts like Bad Script)
                thin_boost = 0.45 if font == "Bad Script" and e["font"] != "Bad Script" else 0.0
                sw_px = (r.uniform(0.65, 1.05) + thin_boost) * e["pressure"] * max(0.75, u)
            gx = cx + shift_x_fu * sx
            mat = _mat_mul(tilt_mat, _letter_matrix(gx, y + dy, rot, skew, sx, -sy))
            d = self._render_ops(ops, mat, sw_px)

            if word_color is not None and c != word_color:
                flush_word()
            word_color = c
            if d:
                word_parts.append(d)

            if ch == "7" and e.get("crossed_seven"):
                em = size / scale
                adv = w / sx
                p0 = _xform_pt(mat, (adv * 0.10, em * 0.315))
                p1 = _xform_pt(mat, (adv * 0.88, em * 0.29))
                bar = _bar_path(p0, p1, max(0.35, em * 0.022 * sx))
                if bar:
                    word_parts.append(bar)

            if e["retrace"] and ch not in DIGITS and not cjk and r.random() < e["retrace"] * loose:
                mat2 = _mat_mul(
                    tilt_mat,
                    _letter_matrix(
                        gx + r.uniform(-0.8, 0.8),
                        y + dy + r.uniform(-0.8, 0.8),
                        rot + r.uniform(-2, 2),
                        skew,
                        sx,
                        -sy,
                    ),
                )
                rt_d = self._render_ops(ops, mat2)
                if rt_d:
                    word_retraces.append((rt_d, c))

            if cjk:
                cx += w * (1 + grow * 0.35) + cjk_tracking * size + r.uniform(-0.3, 0.7) * jit * u
            else:
                cx += w * (1 + grow * 0.5) + r.uniform(-0.5, 1.2) * jit * u

        flush_word()
        return "<g>%s</g>" % "".join(out), cx - start


def _tone(color, r, k):
    color = color.lstrip("#")
    rgb = [int(color[i:i + 2], 16) for i in (0, 2, 4)]
    f = 1 + r.uniform(-k, k)
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * f))) for c in rgb)
