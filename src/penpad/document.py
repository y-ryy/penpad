"""Markdown-with-LaTeX notes -> Notebook.

Supported, one construct per line:

    # Title                      accent color (blue)
    ## Heading                   purple
    Plain text with $inline$ LaTeX math.
    $$ \\frac{a}{b} = c $$        equation on its own line
    $$! E = mc^2 $$              boxed result
    - bullet / * bullet          hanging indent
    1. item / (a) item / a) item hanging indent, label kept
    > note                       written in purple
    | algebraic step             intermediate derivation in graphite with a left bar
    ==highlighted text==         translucent vector highlighter behind the ink
    ```svg ... ```               pure vector SVG diagram embedded in the Diagrams layer
    {red} any line               ink for that line (black, navy, blue, red, purple, green, graphite, gray)
    ---                          new page
    blank line                   one empty ruling line
"""

from __future__ import annotations

import re

from .cjk import CJK_CLOSE_PUNCT, CJK_OPEN_PUNCT, has_cjk, is_cjk
from .diagrams import parse_table_lines, render_graph, render_sequence, render_table, render_waveform
from .latex import escape_text, latex_to_markup
from .notebook import Notebook
from .styles import INKS

_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$")

_COLOR = re.compile(r"^\{(%s|#[0-9a-fA-F]{3,6})\}\s*" % "|".join(INKS))
_ITEM = re.compile(
    r"^(\d+[.)]\s+|\([a-z0-9]+\)\s+|[a-z][.)]\s+"
    r"|\d+、\s*|（[a-z0-9一二三四五六七八九十]+）\s*|[\u2460-\u2473]\s*)(.*)$"
)
_DISPLAY = re.compile(r"^\$\$(!?)\s*(.*?)\s*\$\$$")
_HIGHLIGHT = re.compile(r"==(.+?)==")


def _inline_plain(s: str) -> str:
    """Escape literal text, translate $...$ spans from LaTeX."""
    out, pos = [], 0
    for m in re.finditer(r"(?<!\\)\$(.+?)(?<!\\)\$", s):
        out.append(escape_text(s[pos:m.start()].replace("\\$", "$")))
        out.append(latex_to_markup(m.group(1)))
        pos = m.end()
    out.append(escape_text(s[pos:].replace("\\$", "$")))
    return "".join(out)


def _split_tokens_preserving_math(s: str) -> list[tuple[str, str]]:
    """Split highlighted text into breakable tokens while preserving $...$ spans.

    Returns ``(token, sep_before)`` pairs where ``sep_before`` is ``" "`` or ``""``.
    Pure Latin text splits only on spaces; CJK text also splits between ideographs
    respecting Kinsoku punctuation so long Chinese highlights wrap cleanly.
    """
    if not has_cjk(s):
        tokens, cur, in_math, i = [], [], False, 0
        while i < len(s):
            ch = s[i]
            if ch == "\\" and i + 1 < len(s):
                cur.append(s[i:i + 2])
                i += 2
                continue
            if ch == "$":
                in_math = not in_math
                cur.append(ch)
                i += 1
                continue
            if ch == " " and not in_math:
                if cur:
                    tokens.append(("".join(cur), " " if tokens else ""))
                    cur = []
                i += 1
                continue
            cur.append(ch)
            i += 1
        if cur:
            tokens.append(("".join(cur), " " if tokens else ""))
        return tokens

    tokens: list[tuple[str, str]] = []
    cur: list[str] = []
    in_math = False
    pending_space = False
    pending_open = ""
    i = 0

    def flush_cur():
        nonlocal pending_space, pending_open
        if cur:
            tok = pending_open + "".join(cur)
            sep = " " if (pending_space and tokens) else ""
            tokens.append((tok, sep))
            cur.clear()
            pending_space = False
            pending_open = ""

    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            cur.append(s[i:i + 2])
            i += 2
            continue
        if ch == "$":
            in_math = not in_math
            cur.append(ch)
            i += 1
            continue
        if in_math:
            cur.append(ch)
            i += 1
            continue
        if ch == " ":
            flush_cur()
            pending_space = True
            i += 1
            continue
        if ch in CJK_OPEN_PUNCT:
            flush_cur()
            pending_open += ch
            i += 1
            continue
        if ch in CJK_CLOSE_PUNCT:
            if cur:
                cur.append(ch)
                flush_cur()
            elif tokens and not pending_space and not pending_open:
                prev_tok, prev_sep = tokens[-1]
                tokens[-1] = (prev_tok + ch, prev_sep)
            else:
                cur.append(ch)
                flush_cur()
            i += 1
            continue
        if is_cjk(ch):
            flush_cur()
            tok = pending_open + ch
            sep = " " if (pending_space and tokens) else ""
            pending_open = ""
            pending_space = False
            tokens.append((tok, sep))
            i += 1
            continue
        cur.append(ch)
        i += 1
    flush_cur()
    if pending_open:
        if tokens and not pending_space:
            prev_tok, prev_sep = tokens[-1]
            tokens[-1] = (prev_tok + pending_open, prev_sep)
        else:
            tokens.append((pending_open, " " if (pending_space and tokens) else ""))
    return tokens


def inline(s: str) -> str:
    """Escape literal text, translate $...$ LaTeX spans and ==...== vector highlights."""
    if "==" not in s:
        return _inline_plain(s)
    out, pos = [], 0
    for m in _HIGHLIGHT.finditer(s):
        out.append(_inline_plain(s[pos:m.start()]))
        words_hl = _split_tokens_preserving_math(m.group(1))
        out.append("".join("%s\\h{%s}" % (sep, _inline_plain(tok)) for tok, sep in words_hl))
        pos = m.end()
    out.append(_inline_plain(s[pos:]))
    return "".join(out)


def render_markdown(source: str, notebook: Notebook | None = None, **kw) -> Notebook:
    nb = notebook or Notebook(**kw)
    hang = 1.6 * nb.size
    blank = 0
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        i += 1
        # fenced pure-vector SVG / hand-drawn diagram blocks
        low_fence = raw.strip().lower()
        if low_fence.startswith(("```svg", "```seq", "```graph", "```wave")):
            kind = low_fence[3:].strip().split()[0]
            block_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            body = "\n".join(block_lines)
            if kind == "svg":
                nb.svg_figure(body)
            elif kind == "seq":
                render_sequence(nb, body, inline_fn=inline)
            elif kind == "graph":
                render_graph(nb, body)
            elif kind == "wave":
                render_waveform(nb, body)
            blank = 0
            continue
        # multi-line display math: $$ on its own line
        if raw.strip() in ("$$", "$$!"):
            boxed = raw.strip() == "$$!"
            body = []
            while i < len(lines) and lines[i].strip() != "$$":
                body.append(lines[i].strip())
                i += 1
            i += 1
            raw = "$$%s %s $$" % ("!" if boxed else "", " ".join(body))
        line = raw.strip()
        if not line:
            blank += 1
            if blank == 1 and nb.cursor > nb.G * 2.5:
                nb.space(1)
            continue
        blank = 0
        color = "black"
        m = _COLOR.match(line)
        if m:
            color, line = m.group(1), line[m.end():]
        if line.startswith("<!--"):
            continue
        if line in ("---", "***", "___"):
            nb.page_break()
            continue
        if line.startswith("### "):
            nb.heading(inline(line[4:]), color=None if color == "black" else color)
            continue
        if line.startswith("## "):
            nb.heading(inline(line[3:]), color=None if color == "black" else color)
            continue
        if line.startswith("# "):
            nb.title(inline(line[2:]), color=None if color == "black" else color)
            continue
        # Markdown pipe table: header row with '|' followed by |---|---| separator
        if "|" in line and i < len(lines) and _TABLE_SEP.match(lines[i].strip()):
            tbl_lines = [line]
            while i < len(lines) and "|" in lines[i].strip():
                tbl_lines.append(lines[i].strip())
                i += 1
            render_table(nb, parse_table_lines(tbl_lines), inline_fn=inline, color=color)
            continue
        # contiguous algebraic step / scratchpad block: | ...
        if line.startswith("| "):
            step_lines = [inline(line[2:].strip())]
            while i < len(lines) and lines[i].strip().startswith("| "):
                step_lines.append(inline(lines[i].strip()[2:].strip()))
                i += 1
            nb.steps(step_lines, color="graphite" if color == "black" else color)
            continue
        m = _DISPLAY.match(line)
        if m:
            nb.eq(latex_to_markup(m.group(2)), box=bool(m.group(1)), color=color)
            continue
        if line.startswith("> "):
            nb.text(inline(line[2:]), color="purple" if color == "black" else color)
            continue
        if line[:2] in ("- ", "* "):
            nb.text(inline("• " + line[2:]), hanging=0.78 * nb.size, color=color)
            continue
        m = _ITEM.match(line)
        if m:
            marker = m.group(1).rstrip()
            sep = "" if marker[-1] in "、）" else " "
            nb.text(inline(marker + sep + m.group(2)), hanging=hang, color=color)
            continue
        # Keep short figure/table intro lines attached to the immediately following diagram/table
        if len(line) <= 80 and int(nb.style.get("min_orphan_lines", 0)) > 0:
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                nxt = lines[j].strip()
                nxt_low = nxt.lower()
                is_next_fig = nxt_low.startswith(("```seq", "```graph", "```wave", "```svg"))
                is_next_tbl = ("|" in nxt and j + 1 < len(lines) and bool(_TABLE_SEP.match(lines[j + 1].strip())))
                if is_next_fig or is_next_tbl:
                    # Estimate minimum height for intro (2 rows) + upcoming diagram/table (~6-8 rows)
                    nb.ensure_lines(9.0 if is_next_fig else 7.0)
        nb.text(inline(line), color=color)
    return nb
