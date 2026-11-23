# penpad Extended Markdown Syntax Reference

One construct per line (except fenced blocks and tables):

## Structure & Text

| Syntax | Rendered Result |
|---|---|
| `# Title` | Document/section title (blue in color presets, black in `hw-black`) |
| `## 6.8` / `### 小节` | Heading (automatically moves whole question to next page if < `min_orphan_lines` fit) |
| Plain Chinese/English text | Automatic CJK Kinsoku line wrap + CJK-Latin micro-spacing + optical fullwidth punctuation |
| `① ② ③ ... ⑳` | Hand-circled numeral in the writer's own digit font (with hanging indent at line start) |
| `1、`, `（1）`, `1.`, `(a)` | Numbered list with hanging indent |
| `- item` / `* item` | Hand-drawn organic ink dot (`•`) with aligned hanging indent |
| `> note` | Side note (purple in color presets) |
| `| derivation step` | Intermediate algebra/scratchpad block with vertical left bar (graphite) |
| `==highlighted text==` | Seamless vector yellow highlighter behind ink (wraps cleanly across CJK lines) |
| `{red} line` | Force ink color for one line (`black`, `navy`, `blue`, `red`, `purple`, `green`, `graphite`, `gray`, `#hex`) |
| `---` | Manual page break |
| Blank line | Controlled vertical spacing (scaled by `density`) |

Notes:
- Underscores in plain text (e.g. `TIME_WAIT`, `LAST_ACK`) are automatically escaped and rendered literally.
- Do **not** use `**bold**`, `*italic*`, `` `code` ``, or generic fenced code blocks (e.g. ```` ```python ```` / ```` ```text ````); penpad only recognizes `seq`, `graph`, `wave`, and `svg` fences and renders other markers literally.
- Short intro lines (≤ 80 chars) placed immediately before a table or diagram block automatically keep-with-next so they are never stranded alone at the bottom of a page.

## LaTeX Math

- Inline: `$m\ddot{x} + c\dot{x} + kx = 0$`
- Display equation: `$$ \eta = \frac{L}{L + 58} $$`
- Boxed final result: `$$! H(\omega) = \frac{1/k}{1 - (\omega/\omega_n)^2 + 2i\zeta(\omega/\omega_n)} $$`
- Supported subset: `\frac`, `\int_a^b`, `\oint`, `\sum`, `\sqrt`, `\sqrt[n]`, `\vec`, `\hat`, `\dot`, `\ddot`, `\bar`, `\tilde`, `\left( \right)`, `\text{...}`, Greek letters, `\partial`, `\nabla`, `\cdot`, `\times`, `\div`, `\pm`, `\leq`, `\geq`, `\ll`, `\gg`, `\neq`, `\approx`, `\to`, `\Rightarrow`, `\therefore`, `\because`, `\angle`, `\triangle`, `\infty`, `sin`/`cos`/`log`/`min`/`max`...

## Native Markdown Tables (Hand-Drawn, Non-Splitting)

```markdown
| ACK | 拥塞窗口（字节） | 慢启动阈值（字节） |
|---|---|---|
| 初始 | 1000 | 4000 |
| 1 | 2000 | 4000 |
| 7 丢失 | 1000 | 2696 |
```

Cells support inline `$LaTeX$` and auto-size columns proportionally.

## Hand-Drawn Diagram Code Blocks

### Sequence Diagram (```` ```seq ````)

````markdown
```seq
Client -> Server: SYN=1, ACK=0, seq=x
Server -> Client: SYN=1, ACK=1, seq=y, ack=x+1
Client -> Server: SYN=0, ACK=1, seq=x+1, ack=y+1
```
````

Use `->` for solid arrows, `-->` for dashed arrows. Optional first line: `participants: A, B, C`. Best kept to ≤ 4 participants so arrow labels have ample horizontal room.

### Circled-Node Directed Graph (```` ```graph ````)

````markdown
```graph
a, b -> c -> e [nih]
d -> e [nih]
```
````

Each node gets a compact hand-drawn circle (`r = 20`) with an optically centered label; `[label]` or `: label` annotates the arrows. Layout is a left-to-right layered DAG: use concise 1–2 character node codes (e.g. `S1`, `A`, `e`), ideally ≤ 6–7 horizontal layers and 1–4 nodes per layer.

### Digital Waveform (```` ```wave ````)

````markdown
```wave
00101101
```
````

Multi-signal labeled mode is also supported:

````markdown
```wave
CLK: 01010101
DATA: 00101101
```
````

### Custom Vector SVG (```` ```svg ````)

Any valid `<svg viewBox="...">...</svg>` embeds directly as pure vector paths in the PDF.
