# Presets & Parameter Guide

## Built-in Skill Presets (`scripts/render.py --preset`)

| Preset | Font Strategy | Ink | Best For |
|---|---|---|---|
| `hw-black` *(default)* | Pure `未知手写体_1.ttf` for Chinese + Latin + digits, `Virgil` only for Greek math | Goodnotes monochrome black (`#1e1b1b`); `==highlight==` still draws yellow highlighter if used | Homework, worked problem sets, clean exam-style notes |
| `notes-color` | Same unified font strategy | Multi-color (blue titles, purple headings/notes, red boxes, yellow highlights) | Tablet study notes & summaries |
| `mix-black` | `未知手写体_1.ttf` + `Bad Script` uppercase (`0.70×`) & `p/w/b/l` | Monochrome black (`#1e1b1b`) | Extra separation between ambiguous Latin math variables |
| `mix-color` | Same mixed font strategy | Multi-color | Colorful math/physics notes with heavy Latin symbols |

## Layout Density (`--density`)

- `compact` *(default in config.json)*: Tight notebook spacing, maximizes content per page while staying crisp.
- `normal`: Standard penpad spacing.
- `spacious`: Extra line and section breathing room for airy study sheets.

## Stroke / Component Offset (`--stroke-offset`)

Hole-bound connected-component offset + 2D smooth bilinear elastic warp (never tears inner holes):

- `off`: Whole-glyph variation only.
- `default` *(recommended)*: Subtle natural variation (`shift=0.022`, `rot=2.2°`, `scale=4.5%`, `elastic=0.024`).
- `strong`: More expressive freehand variation (`shift=0.036`, `rot=3.5°`, `scale=7.0%`, `elastic=0.038`).

## Orphan Pagination Rule (`--min-orphan-lines`)

Default `3`: if a heading/problem or multi-line paragraph would leave only 1–2 lines at the bottom of the current page before splitting, the entire block moves cleanly to the top of the next page.

## Font Resolution Precedence

`scripts/render.py` resolves the CJK handwriting font in order:

1. `--cjk-font /path/to/font.ttf` CLI flag
2. `PENPAD_CJK_FONT` environment variable
3. `cjk_font` in [config.json](../config.json) (relative paths are resolved against the penpad repo root or skill directory)
