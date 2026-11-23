"""Tests for native CJK typography, font mixing, Kinsoku wrapping, optical kerning and CLI/MCP."""

import os
import re

import pytest

from penpad import Hand, Notebook, STYLES, cjk_style, fonts, latex_to_markup, render_markdown
from penpad.cjk import CJK_CLOSE_PUNCT, CJK_OPEN_PUNCT, has_cjk, is_cjk
from penpad.cli import main
from penpad.layout import coalesce_line_tokens, tokenize_line
from penpad.styles import INKS, get_style

RAW_CJK_FONT = os.path.join(os.path.dirname(__file__), "..", "out", "未知手写体_1.ttf")
HAS_CJK_FONT = os.path.exists(RAW_CJK_FONT)


def test_cjk_classification():
    assert is_cjk("中") and is_cjk("繁") and is_cjk("，") and is_cjk("（") and is_cjk("①")
    assert not is_cjk("a") and not is_cjk("Z") and not is_cjk("5") and not is_cjk("α")
    assert has_cjk("hello世界")
    assert not has_cjk("hello world 123 α+β")


def test_latex_command_stops_before_cjk():
    assert latex_to_markup(r"\alpha质量") == "α质量"
    assert latex_to_markup(r"\nabla场 + \pi倍") == "∇场 + π倍"
    assert latex_to_markup(r"\text{机械能} = \frac{1}{2}mv^2") == r"机械能 = \f{1}{2}mv^{2}"


def test_tokenize_line_kinsoku_and_cjk_latin_spacing():
    toks = tokenize_line("质量m在弹簧上，方程为（见图1）。")
    strs = [t for t, _ in toks]
    # No token may start with closing punctuation (避头)
    for t in strs:
        assert t[0] not in CJK_CLOSE_PUNCT, "closing punct at token start: %r" % t
    # No token may end with standalone opening punctuation (避尾)
    for t in strs:
        assert t[-1] not in CJK_OPEN_PUNCT, "opening punct stranded at token end: %r" % t
    # Adjacent CJK ideographs have zero gap; CJK <-> Latin gets subtle cjk_latin gap
    by_tok = dict(toks)
    assert by_tok["量"] == "none"
    assert by_tok["m"] == "cjk_latin"
    assert by_tok["在"] == "cjk_latin"
    assert any(t.startswith("（") and len(t) >= 2 for t in strs)
    assert any(t.endswith("，") and len(t) >= 2 for t in strs)


def test_tokenize_line_explicit_space_after_fullwidth_punct_stays_compact():
    toks = tokenize_line("能量守恒， 机械能不变。")
    seps = {t: sep for t, sep in toks}
    assert seps["机"] == "cjk_punct_space"


def test_coalesce_merges_cjk_runs_and_same_line_highlights():
    toks = [("\\h{物}", "none"), ("\\h{理}", "none"), ("\\h{意}", "none"), ("\\h{义：}", "none")]
    merged = coalesce_line_tokens(toks)
    assert merged == [("\\h{物理意义：}", "none")]

    plain = [("阻", "none"), ("尼", "none"), ("力", "none"), ("F", "cjk_latin"), ("为", "cjk_latin")]
    assert coalesce_line_tokens(plain) == [("阻尼力", "none"), ("F", "cjk_latin"), ("为", "cjk_latin")]


def test_monochrome_does_not_mutate_global_inks():
    orig = dict(INKS)
    nb = Notebook(style="cjk", monochrome="black", seed=1)
    nb.title("Title")
    nb.heading("Heading")
    nb.text("Body")
    nb.math("x = 1", box=True)
    assert INKS == orig
    ink_colors = {c for c, _ in nb.page["inked"]}
    assert ink_colors == {INKS["black"]}


def test_lone_ascii_between_cjk_still_gets_isolated_font():
    style = get_style("cursive")
    hand = Hand(style, 1)
    assert hand.font_for("弹簧C的", 2) == "Handlee"
    assert hand.font_for("参数b为", 2) == "Handlee"


def test_bullet_renders_hand_drawn_dot_not_raw_dash():
    from penpad.layout import Symbol
    hand = Hand(get_style("cjk"), 5)
    draws = ["".join(s for _, s in Symbol(hand, "•", 24, "#1e1b1b").parts) for _ in range(4)]
    assert len(set(draws)) == 4
    assert all('stroke="' not in d and 'fill="#1e1b1b"' in d for d in draws)


def test_circled_numerals_render_hand_drawn_across_all_20():
    from penpad.layout import CIRCLED_DIGITS, Symbol
    hand = Hand(get_style("cjk"), 9)
    for ch in CIRCLED_DIGITS:
        sym = Symbol(hand, ch, 24, "#1e1b1b")
        svg = "".join(s for _, s in sym.parts)
        assert sym.w > 20 and 'fill="#1e1b1b"' in svg and 'stroke="' not in svg
    # Same circled numeral varies organically across instances
    d1 = "".join(s for _, s in Symbol(hand, "①", 24, "#1e1b1b").parts)
    d2 = "".join(s for _, s in Symbol(hand, "①", 24, "#1e1b1b").parts)
    assert d1 != d2


def test_density_presets_control_vertical_compactness():
    md = "# Title\n\n## Sec\nLine one.\n\nLine two.\n\n## Sec 2\nLine three.\n"
    y_compact = render_markdown(md, style="cjk", density="compact", seed=1).cursor
    y_normal = render_markdown(md, style="cjk", density="normal", seed=1).cursor
    y_spacious = render_markdown(md, style="cjk", density="spacious", seed=1).cursor
    assert y_compact < y_normal < y_spacious
    with pytest.raises(ValueError):
        get_style("cjk", density="ultra")


@pytest.mark.skipif(not HAS_CJK_FONT, reason="local CJK test font not present")
def test_smooth_baseline_oscillates_continuously_across_tokens():
    style = cjk_style(RAW_CJK_FONT, latin_from_cjk=True)
    hand = Hand(style, 88)
    # Write a mixed line across multiple tokens (CJK -> ASCII -> CJK)
    for tok in ("防止已失效的旧连接报文段干扰新连接：经过", "2*MSL", "时间，避免在相同", "IP", "和端口上建立新连接"):
        hand.write(0, 0, tok, "#1e1b1b", 22)
    dys = hand._dy_history
    assert len(dys) >= 35
    # Bounded (no runaway downward drift or collision)
    assert max(abs(d) for d in dys) <= 2.5
    # Smooth continuity across every adjacent pair including token boundaries (no cliff jumps)
    diffs = [abs(b - a) for a, b in zip(dys, dys[1:])]
    assert max(diffs) < 1.8
    # Oscillates above and below baseline multiple times (上→中→下→中→上)
    crossings = sum(1 for a, b in zip(dys, dys[1:]) if (a < 0 <= b) or (a > 0 >= b))
    assert crossings >= 3


@pytest.mark.skipif(not HAS_CJK_FONT, reason="local CJK test font not present")
def test_cjk_hole_bound_components_and_stroke_offset():
    name = fonts.ensure_font(RAW_CJK_FONT)
    # '中' has 1 outer + 1 inner hole -> must group into 1 component so hole never drifts
    comps_zhong, _, _ = fonts.glyph_components(name, "中")
    assert len(comps_zhong) == 1
    # '接' has 2 outers + 5 inner holes -> must group into 2 components (扌 and 妾)
    comps_jie, _, _ = fonts.glyph_components(name, "接")
    assert len(comps_jie) == 2
    # '三' has 3 independent strokes -> 3 components
    comps_san, _, _ = fonts.glyph_components(name, "三")
    assert len(comps_san) == 3

    # Repeated CJK characters (both multi-component '接' and single-contour '的') vary geometrically
    hand = Hand(cjk_style(RAW_CJK_FONT, latin_from_cjk=True), 42)
    for ch in ("的", "接", "三", "中"):
        svgs = [hand.write(0, 0, ch, "#1e1b1b", 24)[0] for _ in range(5)]
        assert len(set(svgs)) == 5, "expected %r to vary across instances" % ch


@pytest.mark.skipif(not HAS_CJK_FONT, reason="local CJK test font not present")
def test_orphan_protection_moves_whole_6_line_block_when_only_2_lines_fit():
    style = cjk_style(RAW_CJK_FONT, pure_cjk=True, density="compact", min_orphan_lines=3)
    nb = Notebook(paper="goodnotes", style=style, seed=1)
    # Fill page 1 so only ~2.2 grid rows remain before bottom
    nb.text("先占满上半页内容。")
    nb.cursor = nb._bottom() - nb.G * 2.2
    before_inked = len(nb.page["inked"])
    # Now add a 6-line paragraph: since only ~2 lines fit (< min_orphan_lines=3),
    # ALL 6 lines must move cleanly to page 2 without leaving 1-2 lines on page 1.
    six_line_para = "这是一个六行左右的完整题目解答段落用来测试孤行保护规则，" * 8
    nb.text(six_line_para)
    assert len(nb.pages) == 2
    assert len(nb.pages[0]["inked"]) == before_inked, "page 1 should receive zero orphan lines"
    assert nb.pages[1]["inked"]


@pytest.mark.skipif(not HAS_CJK_FONT, reason="local CJK test font not present")
def test_markdown_native_table_and_diagram_blocks(tmp_path):
    md = """## 综合图示与表格测试

| ACK | 拥塞窗口 | 慢启动阈值 |
|---|---|---|
| 初始 | 1000 | 4000 |
| 1 | 2000 | 4000 |

```seq
Client -> Server: SYN=1, seq=x
Server -> Client: SYN=1, ACK=1
```

```graph
a, b -> c -> e [nih]
d -> e [nih]
```

```wave
00101101
```
"""
    nb = render_markdown(md, paper="goodnotes", style=cjk_style(RAW_CJK_FONT, pure_cjk=True), seed=12)
    assert any(p["strokes"] for p in nb.pages)
    assert any(p["inked"] for p in nb.pages)
    pdf = tmp_path / "diag.pdf"
    nb.save(str(pdf))
    assert pdf.exists() and b"/Subtype /Image" not in pdf.read_bytes()


@pytest.mark.skipif(not HAS_CJK_FONT, reason="local CJK test font not present")
def test_cjk_font_mixing_auto_scale_and_clamps():
    style = cjk_style(RAW_CJK_FONT, latin_from_cjk=True)
    hand = Hand(style, 88)
    # Mixed font routing: CJK -> raw CJK font, A -> Bad Script, p -> Bad Script, ρ -> Mynerve
    assert hand._pick_font("中", 0) == style["cjk_font"]
    assert hand._pick_font("A", 0) == "Bad Script"
    assert hand._pick_font("p", 0) == "Bad Script"
    assert hand._pick_font("ρ", 0) == "Mynerve"
    # Auto CJK scale lifts raw font (~0.75 em) close to target (~0.90 em)
    sc = hand._resolve_cjk_scale(style["cjk_font"])
    assert 1.10 <= sc <= 1.35

    # CJK rotation/skew/scale stay within tighter anti-overlap clamps even under high jitter
    high = Hand(cjk_style(RAW_CJK_FONT, jitter=3.0, looseness=3.0), 7)
    high.write(0, 0, "阻尼简谐振动能量守恒" * 8, "#1e1b1b", 24)
    assert high._history
    for rot, skew, grow in high._history:
        assert abs(rot) <= style["cjk_max_rotation"] + 1e-6
        assert abs(skew) <= style["cjk_max_skew"] + 1e-6
        assert abs(grow) <= style["cjk_max_scale"] + 1e-6


@pytest.mark.skipif(not HAS_CJK_FONT, reason="local CJK test font not present")
def test_optical_punctuation_kerning_reduces_fullwidth_void():
    st_on = cjk_style(RAW_CJK_FONT, cjk_punct_squeeze=True)
    st_off = cjk_style(RAW_CJK_FONT, cjk_punct_squeeze=False)
    w_on = Hand(st_on, 1).measure("上，下。（左）", 24)
    w_off = Hand(st_off, 1).measure("上，下。（左）", 24)
    assert w_on < w_off * 0.80


@pytest.mark.skipif(not HAS_CJK_FONT, reason="local CJK test font not present")
def test_long_cjk_paragraph_wraps_without_spaces_or_warnings(caplog, tmp_path):
    long_para = (
        "考虑一个质量为$m$的质点连接在劲度系数为$k$的理想弹簧上并在粘性介质中做一维阻尼简谐振动，"
        "当阻尼系数$c$较小时系统处于欠阻尼状态（即$\\zeta < 1$），"
        "==物理意义：阻尼力每周期消耗机械能导致振幅按指数包络持续衰减==，"
        "且阻尼角频率$\\omega_d = \\omega_n\\sqrt{1-\\zeta^2}$略低于固有频率。"
    )
    md = "# 阻尼振动笔记\n" + long_para + "\n1、欠阻尼\n（2）临界阻尼\n① 能量检验\n"
    nb = render_markdown(md, paper="goodnotes", style=cjk_style(RAW_CJK_FONT, latin_from_cjk=True), seed=88)
    assert not caplog.records
    # Ensure text wrapped across multiple lines and every glyph leaves ink
    pdf = tmp_path / "cjk.pdf"
    nb.save(str(pdf))
    assert pdf.exists() and b"/Subtype /Image" not in pdf.read_bytes()
    img = nb.render_page(0, dpi=72).convert("RGB")
    assert min(lo for lo, _ in img.getextrema()) < 80


@pytest.mark.skipif(not HAS_CJK_FONT, reason="local CJK test font not present")
def test_cli_cjk_font_and_monochrome_flags(tmp_path, capsys):
    src = tmp_path / "cn.md"
    src.write_text("# 力学\n动能 $E = \\frac{1}{2}mv^2$，动量 $p = mv$。\n", encoding="utf-8")
    out_pdf = tmp_path / "cn.pdf"
    rc = main([
        "render", str(src), "-o", str(out_pdf),
        "--style", "cjk", "--cjk-font", RAW_CJK_FONT, "--monochrome",
    ])
    assert rc == 0
    assert out_pdf.exists()
    assert capsys.readouterr().err == ""
