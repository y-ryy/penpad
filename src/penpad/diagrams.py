"""Hand-drawn vector diagrams and tables from compact Markdown blocks.

Supported constructs:
- Markdown tables (``| col1 | col2 |`` with ``|---|---|`` separator)
- ```` ```seq ````: sequence diagrams (``Client -> Server: SYN=1, ACK=0``)
- ```` ```graph ````: circled-node directed graphs (``a, b -> c -> e [nih]``)
- ```` ```wave ````: digital logic waveforms (``00101101`` or ``DATA: 00101101``)
"""

from __future__ import annotations

import math
import re

from . import fonts
from .latex import escape_text
from .layout import Row, measure_markup, parse


def _write_centered(nb, cx: float, cy: float, text: str, size: float, color: str = "black") -> None:
    """Write text optically centered horizontally and vertically at (cx, cy)."""
    if len(text) == 1:
        f = nb.hand._pick_font(text, 0)
        b = fonts.glyph_bounds(f, text) if f else None
        if b:
            sc = nb.hand._glyph_scale(text, f, size)
            mid_y = -0.5 * (b[1] + b[3]) * sc
        else:
            mid_y = -0.32 * size
    else:
        mid_y = -0.32 * size
    nb.write(cx, cy - mid_y, escape_text(text), size=size, color=color, anchor="middle")


# ------------------------------------------------------------------ Markdown Table
def parse_table_lines(lines: list[str]) -> list[list[str]]:
    """Parse Markdown pipe-table lines (skipping the |---|---| separator row)."""
    rows: list[list[str]] = []
    for idx, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("|"):
            s = s[1:]
        if s.endswith("|"):
            s = s[:-1]
        cells = [c.strip() for c in s.split("|")]
        if idx == 1 and all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells if c):
            continue
        rows.append(cells)
    if not rows:
        return []
    ncols = max(len(r) for r in rows)
    return [r + [""] * (ncols - len(r)) for r in rows]


def render_table(nb, rows: list[list[str]], inline_fn, color: str = "black") -> None:
    """Render a parsed table as a hand-drawn, non-splitting Notebook figure."""
    if not rows:
        return
    ncols = len(rows[0])
    max_w = nb.W - 2 * nb.M
    sz_hdr = nb.size * 0.88
    sz_body = nb.size * 0.90

    # Estimate natural column widths from cell markup
    col_nat = [60.0] * ncols
    markup_rows: list[list[str]] = []
    for r_idx, row in enumerate(rows):
        sz = sz_hdr if r_idx == 0 else sz_body
        m_row = []
        for c_idx, cell in enumerate(row):
            mk = inline_fn(cell)
            m_row.append(mk)
            w = measure_markup(nb.hand, mk, sz) + 28.0
            if w > col_nat[c_idx]:
                col_nat[c_idx] = w
        markup_rows.append(m_row)

    total_nat = sum(col_nat)
    # Use a balanced width (at least 72% of page width if reasonably wide, capped at 96%)
    target_w = min(max_w * 0.96, max(total_nat, min(max_w * 0.82, total_nat * 1.18)))
    scale_w = target_w / max(total_nat, 1.0)
    col_ws = [w * scale_w for w in col_nat]
    total_w = sum(col_ws)
    row_h = max(26.5, min(31.6, nb.G * 0.90))
    total_h = row_h * len(markup_rows)

    def _draw(nb_ref, x0, y0):
        tx0 = x0 + max(0.0, (max_w - total_w) * 0.5)
        for r_idx in range(len(markup_rows) + 1):
            y = y0 + r_idx * row_h
            lw = 1.85 if r_idx in (0, 1, len(markup_rows)) else 1.15
            nb_ref.line(tx0, y, tx0 + total_w, y, color=color, width=lw, roughness=0.45, bow=0.2)

        cx = tx0
        for c_idx, cw in enumerate(col_ws):
            if c_idx > 0:
                nb_ref.line(cx, y0, cx, y0 + total_h, color=color, width=1.15, roughness=0.4, bow=0.15)
            cx += cw

        for r_idx, m_row in enumerate(markup_rows):
            base_y = y0 + (r_idx + 1) * row_h - row_h * 0.24
            cx = tx0
            base_sz = sz_hdr if r_idx == 0 else sz_body
            for mk, cw in zip(m_row, col_ws):
                if mk:
                    room = max(20.0, cw - 12.0)
                    col_hex = nb_ref._ink(color)
                    it = nb_ref._fit(lambda t, _mk=mk, _c=col_hex: Row(parse(nb_ref.hand, _mk, t, _c)),
                                     base_sz, room, mk)
                    nb_ref.place(it, cx + (cw - it.w) * 0.5, base_y)
                cx += cw

    nb.figure(total_h + 6, _draw)


# ------------------------------------------------------------------ Sequence Diagram (```seq)
_SEQ_ARROW_RE = re.compile(r"^\s*(.+?)\s*(-->|->)\s*(.+?)\s*(?::\s*(.*))?$")


def render_sequence(nb, src: str, inline_fn=None, color: str = "black") -> None:
    """Render a hand-drawn sequence diagram from ``A -> B: label`` lines."""
    participants: list[str] = []
    messages: list[tuple[str, str, bool, str]] = []
    for raw in src.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("#") or ln.startswith("//"):
            continue
        if ln.lower().startswith("participants:"):
            for p in ln.split(":", 1)[1].split(","):
                p = p.strip()
                if p and p not in participants:
                    participants.append(p)
            continue
        m = _SEQ_ARROW_RE.match(ln)
        if not m:
            continue
        a, arrow, b, label = m.group(1).strip(), m.group(2), m.group(3).strip(), (m.group(4) or "").strip()
        for p in (a, b):
            if p not in participants:
                participants.append(p)
        messages.append((a, b, arrow == "-->", label))

    if len(participants) < 2 or not messages:
        return

    max_w = nb.W - 2 * nb.M
    n_p = len(participants)
    pad_x = max(70.0, min(145.0, max_w * (0.18 if n_p == 2 else 0.10)))
    step_x = (max_w - 2 * pad_x) / max(1, n_p - 1)
    step_y = 52.0
    slant_y = 18.0
    total_h = 38.0 + len(messages) * step_y + 18.0

    def _draw(nb_ref, x0, y0):
        xs = {p: x0 + pad_x + idx * step_x for idx, p in enumerate(participants)}
        y_top = y0 + 26.0
        y_bot = y0 + total_h - 6.0
        for p, px in xs.items():
            nb_ref.write(px, y0 + 16.0, escape_text(p), size=nb_ref.size * 0.95, color=color, anchor="middle")
            nb_ref.line(px, y_top, px, y_bot, color=color, width=1.8, roughness=0.5, bow=0.2)

        lbl_sz = nb_ref.size * 0.85
        for idx, (a, b, dashed, label) in enumerate(messages):
            ya = y_top + 24.0 + idx * step_y
            yb = ya + slant_y
            xa, xb = xs[a], xs[b]
            sgn = 1.0 if xb >= xa else -1.0
            sx, ex = xa + 4.0 * sgn, xb - 4.0 * sgn
            if dashed:
                nb_ref.line(sx, ya, ex, yb, color=color, width=1.5, dashed=True, roughness=0.45, bow=0.2)
                ang = math.atan2(yb - ya, ex - sx)
                for ds in (-0.45, 0.45):
                    nb_ref.line(ex, yb, ex - 10 * math.cos(ang + ds), yb - 10 * math.sin(ang + ds),
                                color=color, width=1.5, roughness=0.45, bow=0.2)
            else:
                nb_ref.arrow(sx, ya, ex, yb, color=color, width=1.6, head=10)
            if label:
                mk = inline_fn(label) if inline_fn else escape_text(label)
                xm = 0.5 * (sx + ex)
                # Right-to-left arrows slope down from the right; lift label slightly higher so
                # the right tail of long labels never grazes the arrow shaft.
                ym = ya - 3.5 if xb < xa else ya + 0.5
                room = max(60.0, abs(ex - sx) - 18.0)
                col_hex = nb_ref._ink(color)
                it = nb_ref._fit(lambda t, _mk=mk, _c=col_hex: Row(parse(nb_ref.hand, _mk, t, _c)),
                                 lbl_sz, room, mk)
                nb_ref.place(it, xm - it.w * 0.5, ym)

    nb.figure(total_h, _draw)


# ------------------------------------------------------------------ Directed Graph (```graph)
def render_graph(nb, src: str, color: str = "black", edge_color: str = "navy", label_color: str = "red") -> None:
    """Render a hand-drawn circled-node directed graph.

    Supports chained/multi-source syntax such as:
        a, b -> c -> e [nih]
        d -> e [nih]
    or ``a -> c: label``.
    """
    nodes_order: list[str] = []
    edges: list[tuple[str, str, str]] = []

    def add_node(name: str):
        if name not in nodes_order:
            nodes_order.append(name)

    for raw in src.splitlines():
        for stmt in raw.split(";"):
            ln = stmt.strip()
            if not ln or ln.startswith("#") or ln.startswith("//"):
                continue
            label = ""
            m_br = re.search(r"\[([^\]]+)\]\s*$", ln)
            if m_br:
                label = m_br.group(1).strip()
                ln = ln[:m_br.start()].strip()
            elif ":" in ln:
                left, right = ln.rsplit(":", 1)
                if "->" in left:
                    ln, label = left.strip(), right.strip()
            parts = [p.strip() for p in re.split(r"-->|->", ln) if p.strip()]
            if len(parts) < 2:
                for p in parts:
                    for n in p.split(","):
                        if n.strip():
                            add_node(n.strip())
                continue
            groups = [[n.strip() for n in p.split(",") if n.strip()] for p in parts]
            for g in groups:
                for n in g:
                    add_node(n)
            for g1, g2 in zip(groups, groups[1:]):
                for u in g1:
                    for v in g2:
                        edges.append((u, v, label))

    if not nodes_order:
        return

    # Longest-path layer assignment (handles DAGs cleanly; cycle-safe via relaxation cap)
    rank = {n: 0 for n in nodes_order}
    for _ in range(len(nodes_order)):
        changed = False
        for u, v, _ in edges:
            if rank[v] < rank[u] + 1:
                rank[v] = rank[u] + 1
                changed = True
        if not changed:
            break

    max_rank = max(rank.values()) if rank else 0
    layers: list[list[str]] = [[] for _ in range(max_rank + 1)]
    for n in nodes_order:
        layers[rank[n]].append(n)

    max_layer_sz = max(len(ly) for ly in layers)
    r = 20.0
    max_w = nb.W - 2 * nb.M
    row_gap = 104.0
    total_h = max(120.0, max_layer_sz * row_gap + 24.0)

    def _draw(nb_ref, x0, y0):
        pad_x = 85.0
        col_step = (max_w - 2 * pad_x) / max(1, max_rank) if max_rank > 0 else 0.0
        pos: dict[str, tuple[float, float]] = {}
        for li, ly in enumerate(layers):
            cx = x0 + (max_w * 0.5 if max_rank == 0 else pad_x + li * col_step)
            span_y = (len(ly) - 1) * row_gap
            y_start = y0 + (total_h - span_y) * 0.5
            for idx, name in enumerate(ly):
                pos[name] = (cx, y_start + idx * row_gap)

        for name, (cx, cy) in pos.items():
            nb_ref.circle(cx, cy, r, color=color, width=2.0)
            if len(name) == 1:
                sz = nb_ref.size * (1.35 if name in "bdhklft" else 1.72)
            else:
                sz = nb_ref.size * max(0.65, min(1.0, 2.0 / len(name)))
            _write_centered(nb_ref, cx, cy, name, size=sz, color=color)

        for idx, (u, v, lbl) in enumerate(edges):
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            dx, dy = x2 - x1, y2 - y1
            L = math.hypot(dx, dy)
            if L < 1e-3:
                continue
            ux, uy = dx / L, dy / L
            pad = r + 5.0
            sx, sy = x1 + ux * pad, y1 + uy * pad
            ex, ey = x2 - ux * pad, y2 - uy * pad
            nb_ref.arrow(sx, sy, ex, ey, color=edge_color, head=11)
            if lbl:
                # Place upper-sloping or top edges above, downward-rising bottom edges below
                side = -1 if y1 > y2 + 10 else 1
                nx, ny = uy * side, -ux * side
                mx = 0.5 * (sx + ex) + nx * 19.0
                my = 0.5 * (sy + ey) + ny * 19.0
                nb_ref.write(mx, my + 6.0, escape_text(lbl), size=nb_ref.size * 0.92,
                             color=label_color, anchor="middle")

    nb.figure(total_h, _draw)


# ------------------------------------------------------------------ Digital Waveform (```wave)
def render_waveform(nb, src: str, color: str = "blue") -> None:
    """Render one or more digital square-wave signals (e.g. ``00101101`` or ``DATA: 00101101``)."""
    tracks: list[tuple[str, str]] = []
    for raw in src.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("#") or ln.startswith("//"):
            continue
        if ":" in ln:
            lbl, bits = ln.split(":", 1)
            bits = re.sub(r"[^01]", "", bits)
            if bits:
                tracks.append((lbl.strip(), bits))
        else:
            bits = re.sub(r"[^01]", "", ln)
            if bits:
                tracks.append(("V", bits))
    if not tracks:
        return

    n = max(len(b) for _, b in tracks)
    max_w = nb.W - 2 * nb.M
    ax_left = 74.0
    bit_w = min(84.0, (max_w - ax_left - 42.0) / max(1, n))
    track_h = 152.0 if len(tracks) == 1 else 146.0
    total_h = track_h * len(tracks) + 46.0

    def _draw(nb_ref, x0, y0):
        ax_x = x0 + ax_left
        end_x = ax_x + n * bit_w + 28.0
        for t_idx, (lbl, bits) in enumerate(tracks):
            ty = y0 + t_idx * track_h
            y_hi = ty + 48.0
            y_lo = ty + (134.0 if len(tracks) == 1 else 108.0)
            ax_y = y_lo + 20.0

            nb_ref.arrow(ax_x, ax_y, end_x, ax_y, color="graphite", width=1.5, head=10)
            nb_ref.arrow(ax_x, ax_y, ax_x, y_hi - 30.0, color="graphite", width=1.5, head=10)
            nb_ref.write(ax_x - 14.0, y_hi - 22.0, escape_text(lbl), size=nb_ref.size * 0.88,
                         color="graphite", anchor="end")
            nb_ref.write(end_x + 8.0, ax_y + 6.0, "t", size=nb_ref.size * 0.90,
                         color="graphite", anchor="start")

            nb_ref.line(ax_x - 7, y_hi, ax_x + 2, y_hi, color="graphite", width=1.4)
            nb_ref.line(ax_x - 7, y_lo, ax_x + 2, y_lo, color="graphite", width=1.4)
            nb_ref.write(ax_x - 15.0, y_hi + 7.0, "1", size=nb_ref.size * 0.90, color="graphite", anchor="end")
            nb_ref.write(ax_x - 15.0, y_lo + 7.0, "0", size=nb_ref.size * 0.90, color="graphite", anchor="end")

            for i in range(len(bits) + 1):
                gx = ax_x + i * bit_w
                if i > 0:
                    nb_ref.line(gx, y_hi - 14, gx, ax_y, color="gray", width=1.0, dashed=True,
                                roughness=0.35, bow=0.1)
                if i < len(bits):
                    cx = gx + bit_w * 0.5
                    nb_ref.write(cx, y_hi - 18.0, bits[i], size=nb_ref.size * 0.95,
                                 color="red" if bits[i] == "1" else "navy", anchor="middle")
                    if t_idx == len(tracks) - 1:
                        nb_ref.write(cx, ax_y + 22.0, "t_%d" % i, size=nb_ref.size * 0.70,
                                     color="gray", anchor="middle")

            prev_y = None
            for i, b in enumerate(bits):
                x1 = ax_x + i * bit_w
                x2 = x1 + bit_w
                y = y_hi if b == "1" else y_lo
                if prev_y is not None and prev_y != y:
                    nb_ref.line(x1, prev_y, x1, y, color=color, width=2.5, roughness=0.5, bow=0.22)
                nb_ref.line(x1, y, x2, y, color=color, width=2.5, roughness=0.5, bow=0.22)
                prev_y = y

    nb.figure(total_h, _draw)
