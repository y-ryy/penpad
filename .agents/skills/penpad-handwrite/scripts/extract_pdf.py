#!/usr/bin/env python3
"""Locate and rasterize PDF pages to PNG so vision-capable agents can read garbled/scanned Chinese PDFs."""

from __future__ import annotations

import argparse
import os
import re
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
REPO_ROOT = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", ".."))
_VENV_PY = os.path.join(REPO_ROOT, ".venv", "bin", "python")
try:
    import pypdfium2 as pdfium
except ImportError:
    if os.path.exists(_VENV_PY) and os.path.abspath(sys.executable) != os.path.abspath(_VENV_PY):
        os.execv(_VENV_PY, [_VENV_PY] + sys.argv)
    raise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Search and rasterize PDF pages to PNG for visual inspection.")
    ap.add_argument("pdf", help="path to source PDF")
    ap.add_argument("--find", help="comma-separated keywords or exercise numbers to locate (e.g. '6.8,6.14,6.25')")
    ap.add_argument("--pages", help="1-based page numbers/ranges (e.g. '1,3-5')")
    ap.add_argument("--context", type=int, default=1, help="extra following pages to include per hit (default: 1)")
    ap.add_argument("--scale", type=float, default=2.0, help="render scale factor (default: 2.0)")
    ap.add_argument("--out", default="/tmp/penpad_work/pdf_pages", help="output directory for PNGs")
    args = ap.parse_args(argv)

    if not os.path.exists(args.pdf):
        print(f"extract_pdf: file not found: {args.pdf}", file=sys.stderr)
        return 1

    doc = pdfium.PdfDocument(args.pdf)
    total = len(doc)
    selected: set[int] = set()

    if args.pages:
        for part in args.pages.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                for p in range(max(1, int(a)), min(total, int(b)) + 1):
                    selected.add(p - 1)
            elif part:
                p = int(part)
                if 1 <= p <= total:
                    selected.add(p - 1)

    if args.find:
        targets = [t.strip() for t in args.find.split(",") if t.strip()]
        for i in range(total):
            txt = doc[i].get_textpage().get_text_bounded()
            hits = [t for t in targets if re.search(r"(?<!\d)" + re.escape(t) + r"(?!\d)", txt)]
            if hits:
                print(f"Match page {i + 1}: {', '.join(hits)}")
                for d in range(args.context + 1):
                    if i + d < total:
                        selected.add(i + d)

    if not selected:
        if args.find or args.pages:
            print(
                f"extract_pdf: 0 matching pages across {total} page(s) in {args.pdf}. "
                f"If this is a scanned or garbled-CID PDF, retry with --pages 1-{min(total, 5)}.",
                file=sys.stderr,
            )
            return 1
        selected = set(range(min(total, 5)))

    os.makedirs(args.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.pdf))[0]
    for idx in sorted(selected):
        out_file = os.path.join(args.out, f"{stem}_p{idx + 1}.png")
        doc[idx].render(scale=args.scale).to_pil().save(out_file)
        print(f"Saved {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
