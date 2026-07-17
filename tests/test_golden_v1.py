"""Golden-file lock on ALGO_VERSION 1 — the determinism contract.

`golden_v1.json` pins the derived genome fields, shard seeds, and rendered-SVG
hashes for a set of seeds. If any change to the v1 generator or the geometry/
shading pipeline alters what an existing seed produces, these tests fail —
which is the whole point: a published identicon must render the same avatar
for the same seed, forever, under a given ALGO_VERSION.

If you INTEND to change generation, do NOT edit v1: add `_derive_v2`, bump
ALGO_VERSION, and write a golden_v2.json. v1 and its golden stay frozen.

Run: .venv/bin/python -m pytest tests/unit/avatar -q --import-mode=importlib
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ai_identicon.genome import Genome, ALGO_VERSION
from ai_identicon import portrait

GOLDEN = json.loads((Path(__file__).parent / "golden_v1.json").read_text())
FIELDS = ["mesh_seed", "faces", "shapes", "frag", "roughness", "translucency",
          "hue", "n_colors", "material", "shine", "elong", "tilt", "edge_hue",
          "express", "tempo", "sharp", "thinking", "voice"]


def _rnd(v):
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, (list, tuple)):
        return [round(x, 6) for x in v]
    return v


def test_algo_version_matches_golden():
    assert ALGO_VERSION == GOLDEN["algo_version"], (
        "ALGO_VERSION changed — if intentional, add a new golden file; the v1 "
        "golden must stay pinned to v1.")


@pytest.mark.parametrize("seed", sorted(GOLDEN["seeds"]))
def test_derived_genome_is_frozen(seed):
    g = Genome.from_seed(seed)
    want = GOLDEN["seeds"][seed]
    got = {f: _rnd(getattr(g, f)) for f in FIELDS}
    assert got == want["fields"], f"v1 derivation drifted for seed {seed!r}"
    assert [sh["mesh_seed"] for sh in g.shards] == want["shard_seeds"]


@pytest.mark.parametrize("seed", sorted(GOLDEN["seeds"]))
def test_rendered_svgs_are_frozen(seed):
    g = Genome.from_seed(seed)
    want = GOLDEN["seeds"][seed]["svg"]

    def h(svg):
        return hashlib.sha256(svg.encode()).hexdigest()[:16]

    assert h(portrait.color_svg(g)) == want["color"], f"color portrait drifted: {seed!r}"
    assert h(portrait.line_art_svg(g, "black")) == want["black"], f"line-art drifted: {seed!r}"
    assert h(portrait.line_art_svg(g, "black", px=40)) == want["black40"], f"40px drifted: {seed!r}"
