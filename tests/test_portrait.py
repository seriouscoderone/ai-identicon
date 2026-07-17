"""Tests for the static SVG portrait exporters (pure, no Qt).

Structural assertions plus a material-differentiation spec: the four
materials must produce visibly different color portraits at rest (the fix for
the 'materials all look the same' regression).

Run: .venv/bin/python -m pytest tests/unit/avatar -q --import-mode=importlib
"""

from __future__ import annotations

import re

from ai_identicon.genome import Genome, MATERIALS
from ai_identicon import portrait


def _fills(svg: str) -> list[tuple[int, int, int]]:
    out = []
    for hexcol in re.findall(r'fill="#([0-9a-f]{6})"', svg):
        out.append((int(hexcol[0:2], 16), int(hexcol[2:4], 16), int(hexcol[4:6], 16)))
    return out


def _mean_fill(svg: str) -> tuple[float, float, float]:
    fills = _fills(svg)
    n = len(fills)
    return tuple(sum(f[i] for f in fills) / n for i in range(3))


# ------------------------------------------------------------------ structure

def test_line_art_is_stroke_only_transparent():
    svg = portrait.line_art_svg(Genome.from_seed("bmev5p5akc"), "black")
    assert "<line" in svg and "<polygon" not in svg
    assert 'fill="none"' in svg  # no filled background — transparent


def test_black_and_white_share_geometry_differ_only_in_stroke():
    g = Genome.from_seed("bmev5p5akc")
    black = portrait.line_art_svg(g, "black")
    white = portrait.line_art_svg(g, "white")
    # identical line coordinates, only the stroke color differs
    coords = lambda s: re.findall(r'x1="[^"]+" y1="[^"]+" x2="[^"]+" y2="[^"]+"', s)
    assert coords(black) == coords(white)
    assert "#15181c" in black and "#e8eef4" in white


def test_color_portrait_is_opaque_filled():
    svg = portrait.color_svg(Genome.from_seed("bmev5p5akc"))
    assert "<polygon" in svg
    assert "fill-opacity" not in svg  # opaque — no see-through interior lines
    assert len(_fills(svg)) > 4


def test_small_size_thickens_stroke_and_thins_lines():
    g = Genome.from_seed("bmev5p5akc")
    big = portrait.line_art_svg(g, "black", px=512)
    small = portrait.line_art_svg(g, "black", px=40)
    sw = lambda s: float(re.search(r'stroke-width="([\d.]+)"', s).group(1))
    assert sw(small) > sw(big)  # thicker stroke at small display size
    # small drops some interior edges to whisper weight (a 2nd stroke group)
    assert small.count("<g ") >= big.count("<g ")


# --------------------------------------------------------- determinism / io

def test_color_portrait_deterministic():
    g = Genome.from_seed("agent-alpha")
    assert portrait.color_svg(g) == portrait.color_svg(g)


def test_export_writes_all_variants(tmp_path):
    g = Genome.from_seed("bmev5p5akc")
    for variant in ("black", "white", "color"):
        p = portrait.export_svg(g, tmp_path / f"{variant}.svg", variant=variant)
        assert p.exists() and p.read_text().startswith("<svg")


# --------------------------------------------------- material differentiation

def test_materials_produce_visibly_different_portraits():
    """The four materials must read as different substances at rest, not just
    at a specular hotspot. Mean fill color must be pairwise distinguishable."""
    seed = "bmev5p5akc"
    means = {}
    for m in MATERIALS:
        g = Genome.from_seed(seed).with_overrides(material=MATERIALS.index(m))
        means[m] = _mean_fill(portrait.color_svg(g))

    def dist(a, b):
        return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5

    mats = list(MATERIALS)
    for i in range(len(mats)):
        for j in range(i + 1, len(mats)):
            d = dist(means[mats[i]], means[mats[j]])
            assert d > 10.0, f"{mats[i]} vs {mats[j]} too similar (mean dist {d:.1f})"
