---
name: penpad-handwrite
description: >-
  Generate realistic Chinese/English/LaTeX handwritten notebook pages (pure-vector PDF and PNG
  previews) from problem images, PDFs, or text via penpad. Use when the user wants AI to draft
  structured Markdown solutions/study notes (with math, tables, sequence/graph/waveform diagrams),
  review the Markdown draft first, and then render realistic handwritten pages for Goodnotes,
  Notability, reMarkable, or printing.
---

# penpad-handwrite Skill

Turn problems or study material into realistic handwritten vector PDF pages through a **two-stage human-in-the-loop workflow**: AI drafts clean Markdown → user reviews/edits → `penpad` renders handwritten pages → agent visually verifies every page.

## Output & Workspace Hygiene Rules

- **Deliverables belong in the workspace**: always save the Markdown draft (`.md`), rendered handwritten PDF (`.pdf`), and page preview PNGs inside the current workspace (prefer the directory containing the user's source problems, or a tidy topic subfolder such as `./<topic>/`). Never place final deliverables in `/tmp/` unless the user explicitly asks for `/tmp/`.
- **Stay in the user's workspace directory**: resolve the script paths from this `SKILL.md`'s directory and invoke them by absolute path (e.g., `python3 <skill_dir>/scripts/render.py ./<topic>/draft.md -o ./<topic>/output.pdf --preview`). **Never `cd` into the skill directory**, or relative workspace paths will write to the wrong place.
- **Keep temporary scripts and intermediate files out of the workspace**:
  - Always use the bundled `scripts/render.py` and `scripts/extract_pdf.py` rather than creating one-off Python rendering/probing scripts inside the workspace.
  - Put any temporary inspection files (extracted PDF page images, cropped zoom-in QA images, quick probes) under `/tmp/penpad_work/`, and **delete `/tmp/penpad_work/` once final verification passes** so neither the workspace nor `/tmp` accumulates clutter.

## Workflow

### Stage 1: Read Source & Draft Markdown (Pause for User Review)

1. **Inspect inputs**:
   - **Images (`.png`/`.jpg`)**: read directly with vision.
   - **PDFs (especially Chinese PDFs with garbled CID text or scanned exercises)**: locate and rasterize relevant pages into `/tmp/penpad_work/` first using [extract_pdf.py](./scripts/extract_pdf.py) (from your workspace CWD, using the absolute path to the script):
     ```bash
     python3 <skill_dir>/scripts/extract_pdf.py <input.pdf> --find "6.8,6.14,6.25,6.27" --out /tmp/penpad_work/pdf_pages
     ```
     Then inspect the exported PNG pages directly. (If `--find` returns 0 matches on a scanned PDF, retry with `--pages 1-5`.)
2. **Write a clean Markdown draft** inside the workspace (e.g., `./<topic>/draft.md`) following [syntax.md](./references/syntax.md):
   - **Default to pure black ink**: do not add `{red}` / colored line tags unless the user explicitly requests multi-color notes.
   - Use `## 题号` / `### 小节` for headings; **never** use unsupported Markdown syntax (`**bold**`, `*italic*`, `` `code` ``, generic ```` ``` ```` code blocks, or unescaped `$`) — penpad renders them literally.
   - Use `$...$` for inline math, `$$ ... $$` for display equations, `$$! ... $$` for boxed conclusions.
   - Use `① ② ③` for sub-steps (rendered as hand-circled writer digits up to `⑳`), `- ` for hand-drawn bullet dots. In `compact` mode, **do not insert blank lines** between consecutive `①②③` or `- ` items inside the same problem; only add blank lines between problems or around diagrams/tables.
   - Use native Markdown pipe tables (`| 列1 | 列2 |`) for tables — never write Python coordinate scripts unless a bespoke figure is needed.
   - Use fenced diagram blocks (```` ```seq ````, ```` ```graph ````, ```` ```wave ````) for sequence diagrams, circled-node graphs, and digital waveforms.
3. **Pause and present the draft** to the user for review (unless the user explicitly asked to render directly without review).

### Stage 2: Render Handwritten Pages & Visual Self-Check

1. **Render PDF + PNG previews** using [render.py](./scripts/render.py) from your workspace CWD (see [presets.md](./references/presets.md) for presets and overrides):
   ```bash
   python3 <skill_dir>/scripts/render.py <draft.md> -o <output.pdf> --preview
   ```
   - **Color rule**: always use pure black ink by default (`--preset hw-black`, already set in [config.json](./config.json)). Only switch to `notes-color` / `mix-color` when the user explicitly asks for colored notes.
   Useful flags:
   - `--preset hw-black|notes-color|mix-black|mix-color` (default from [config.json](./config.json): `hw-black`)
   - `--density compact|normal|spacious`
   - `--paper goodnotes|a4-grid|a4-lines|a4-dots|a4-blank|letter-lines|letter-grid|remarkable`
   - `--seed 88` (change seed if any localized glyph collision appears)
   - `--stroke-offset off|default|strong`
   - `--cjk-font /path/to/font.ttf`
   - `--footer "课程笔记"`
   - `--preview-dir /tmp/penpad_work/previews` (optional: keep preview PNGs out of workspace if only `.md` + `.pdf` should remain)
2. **Visually inspect every generated preview PNG** before reporting done. Check:
   - **No orphan splits**: a multi-line problem/paragraph must not leave only 1–2 lines at the bottom of a page (enforced automatically via `min_orphan_lines=3`; add `---` only if manual page grouping is cleaner).
   - **No raw syntax leaks**: no literal `$`, unrendered LaTeX commands, or unintended subscripts on identifiers like `TIME_WAIT`.
   - **Clean diagrams & tables**: arrows do not poke inside circles, labels do not overlap lines, tables stay intact on one page.
   - **Smooth baseline & legibility**: continuous gentle wave (`上→中→中→下→下→中→中→上`), no cliff jumps between Chinese and English tokens, no broken inner holes.
3. If any issue appears, fix the Markdown or adjust `--seed` / `--density`, re-render, and re-check.
4. Before reporting done, remove temporary inspection files under `/tmp/penpad_work/` so only clean workspace deliverables remain.

## References

- Markdown & diagram DSL reference: [references/syntax.md](./references/syntax.md)
- Presets, fonts, and parameter tuning: [references/presets.md](./references/presets.md)
- Default local configuration: [config.json](./config.json)
