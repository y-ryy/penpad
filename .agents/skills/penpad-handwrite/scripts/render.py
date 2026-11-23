#!/usr/bin/env python3
"""Render a penpad Markdown file into a pure-vector handwritten PDF (+ optional PNG previews)."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time


SKILL_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
REPO_ROOT = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if os.path.isdir(SRC_DIR) and SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# If invoked with system python outside .venv, re-exec transparently with repo .venv if available.
_VENV_PY = os.path.join(REPO_ROOT, ".venv", "bin", "python")
try:
    import penpad  # noqa: F401
except ImportError:
    if os.path.exists(_VENV_PY) and os.path.abspath(sys.executable) != os.path.abspath(_VENV_PY):
        os.execv(_VENV_PY, [_VENV_PY] + sys.argv)
    raise

from penpad import PAPERS, cjk_style, render_markdown  # noqa: E402
from penpad.styles import DENSITIES  # noqa: E402

STROKE_OFFSET_TIERS = {
    "off": dict(cjk_component_shift=0.0, cjk_component_rot=0.0, cjk_component_scale=0.0, cjk_elastic=0.0),
    "default": dict(cjk_component_shift=0.022, cjk_component_rot=2.2, cjk_component_scale=0.045, cjk_elastic=0.024),
    "strong": dict(cjk_component_shift=0.036, cjk_component_rot=3.5, cjk_component_scale=0.070, cjk_elastic=0.038),
}

PRESETS = {
    "hw-black": dict(pure_cjk=True, monochrome="black"),
    "notes-color": dict(pure_cjk=True, monochrome=None),
    "mix-black": dict(latin_from_cjk=True, monochrome="black"),
    "mix-color": dict(latin_from_cjk=True, monochrome=None),
}


def _load_config() -> dict:
    cfg_path = os.path.join(SKILL_DIR, "config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _resolve_font(path_str: str | None) -> str | None:
    if not path_str:
        return None
    if os.path.exists(path_str):
        return os.path.abspath(path_str)
    for base in (REPO_ROOT, SKILL_DIR):
        cand = os.path.join(base, path_str)
        if os.path.exists(cand):
            return os.path.abspath(cand)
    return path_str


def _configure_warnings() -> None:
    """Surface penpad WARNING logs (unsupported LaTeX, wide-line overflow) to stderr."""
    logger = logging.getLogger("penpad")
    logger.setLevel(logging.WARNING)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("WARNING [penpad]: %(message)s"))
        logger.addHandler(h)
    logger.propagate = False


def _clean_stale_previews(png_base: str) -> None:
    """Remove stale <stem>.png and <stem>-NN.png from an earlier render with a different page count."""
    parent = os.path.dirname(os.path.abspath(png_base))
    if not os.path.isdir(parent):
        return
    stem = os.path.splitext(os.path.basename(png_base))[0]
    pat = re.compile(r"^" + re.escape(stem) + r"(?:-\d+)?\.png$", re.IGNORECASE)
    for name in os.listdir(parent):
        if pat.match(name):
            try:
                os.remove(os.path.join(parent, name))
            except OSError:
                pass


def main(argv=None) -> int:
    _configure_warnings()
    cfg = _load_config()
    ap = argparse.ArgumentParser(description="Render Markdown + LaTeX notes to handwritten vector PDF/PNG.")
    ap.add_argument("input", help="input Markdown file (or - for stdin)")
    ap.add_argument("-o", "--output", help="output .pdf, .svg or .png (default: <input>.pdf)")
    ap.add_argument("--preset", default=cfg.get("preset", "hw-black"), choices=sorted(PRESETS))
    ap.add_argument("--paper", default=cfg.get("paper", "goodnotes"), choices=sorted(PAPERS))
    ap.add_argument("--density", default=cfg.get("density", "compact"), choices=DENSITIES)
    ap.add_argument("--stroke-offset", default=cfg.get("stroke_offset", "default"),
                    choices=sorted(STROKE_OFFSET_TIERS))
    ap.add_argument("--cjk-font", default=os.environ.get("PENPAD_CJK_FONT") or cfg.get("cjk_font"))
    ap.add_argument("--seed", type=int, default=int(cfg.get("seed", 88)))
    ap.add_argument("--min-orphan-lines", type=int, default=int(cfg.get("min_orphan_lines", 3)))
    ap.add_argument("--footer", help="optional page footer text")
    ap.add_argument("--dpi", type=int, default=int(cfg.get("dpi", 160)))
    ap.add_argument("--preview", action="store_true", help="also write PNG page previews next to the PDF")
    ap.add_argument("--preview-dir", help="optional directory for --preview PNGs (default: same folder as PDF)")
    ap.add_argument("--raster", action="store_true", help="rasterize PDF instead of pure vector paths")
    args = ap.parse_args(argv)

    t0 = time.time()
    if args.input == "-":
        src = sys.stdin.read()
        default_out = "notes.pdf"
    else:
        with open(args.input, encoding="utf-8") as f:
            src = f.read()
        default_out = os.path.splitext(args.input)[0] + ".pdf"

    out_path = args.output or default_out
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    font_path = _resolve_font(args.cjk_font)
    if not font_path or not os.path.exists(font_path):
        print(f"penpad-handwrite: CJK font not found: {args.cjk_font}", file=sys.stderr)
        return 1

    preset_kw = dict(PRESETS[args.preset])
    stroke_kw = dict(STROKE_OFFSET_TIERS[args.stroke_offset])
    style = cjk_style(
        font_path,
        density=args.density,
        min_orphan_lines=args.min_orphan_lines,
        **preset_kw,
        **stroke_kw,
    )

    nb = render_markdown(src, paper=args.paper, style=style, seed=args.seed, footer=args.footer)
    if out_path.lower().endswith(".png"):
        _clean_stale_previews(out_path)
    written = nb.save(out_path, dpi=args.dpi, vector_pdf=not args.raster)
    previews = []
    if args.preview and out_path.lower().endswith(".pdf"):
        stem = os.path.splitext(os.path.basename(out_path))[0]
        if args.preview_dir:
            os.makedirs(args.preview_dir, exist_ok=True)
            png_base = os.path.join(args.preview_dir, stem + ".png")
        else:
            png_base = os.path.splitext(out_path)[0] + ".png"
        _clean_stale_previews(png_base)
        previews = nb.save(png_base, dpi=args.dpi)

    size_kb = os.path.getsize(written[0]) // 1024 if written and os.path.exists(written[0]) else 0
    print(f"PDF: {', '.join(written)} ({len(nb.pages)} pages, {size_kb} KB, {time.time() - t0:.2f}s)")
    if previews:
        print("PNG: " + ", ".join(previews))
    return 0


if __name__ == "__main__":
    sys.exit(main())
