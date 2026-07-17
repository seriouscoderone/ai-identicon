"""Tests for the avatar identity + geometry layers (pure, no Qt).

Covers the two engineering guarantees (frozen versioning, deterministic base +
override overlay + brand) and pins the geometry behavior — including three
known coupling bugs as executable specs so fixes are verifiable.

Run: .venv/bin/python -m pytest tests/unit/avatar -q --import-mode=importlib
"""

from __future__ import annotations

import math

import pytest

from ai_identicon.genome import (
    ALGO_VERSION,
    Brand,
    Genome,
    HUE_BUCKETS,
    MATERIALS,
)
from ai_identicon import geometry

SEEDS = ["bmev5p5akc", "8f2p7ke747", "default-agent", "agent-alpha"]


# --------------------------------------------------------------- determinism

@pytest.mark.parametrize("seed", SEEDS)
def test_from_seed_is_deterministic(seed):
    a = Genome.from_seed(seed)
    b = Genome.from_seed(seed)
    assert a.to_dict() == b.to_dict()
    assert a.mesh_seed == b.mesh_seed
    assert a.elong == b.elong
    assert [s["mesh_seed"] for s in a.shards] == [s["mesh_seed"] for s in b.shards]


def test_distinct_seeds_differ():
    genomes = [Genome.from_seed(s) for s in SEEDS]
    # not all identical across the salient identity channels
    assert len({(g.hue, g.material, g.shapes) for g in genomes}) > 1


# ----------------------------------------------------------- frozen versioning

@pytest.mark.parametrize("seed", SEEDS)
def test_version_recorded_and_roundtrips(seed):
    g = Genome.from_seed(seed)
    assert g.algo_version == ALGO_VERSION
    restored = Genome.from_dict(g.to_dict())
    # frozen: re-derivation from (seed, version, overrides) reproduces it
    assert restored.mesh_seed == g.mesh_seed
    assert restored.hue == g.hue
    assert restored.elong == g.elong


def test_unknown_version_rejected():
    with pytest.raises(ValueError):
        Genome.from_seed("x", algo_version=999)


def test_to_dict_is_minimal_identity():
    # only the reproducible identity is persisted, not the derived fields
    d = Genome.from_seed("bmev5p5akc").to_dict()
    assert set(d) == {"seed", "algo_version", "brand", "overrides"}


# ------------------------------------------------------- customization overlay

def test_overrides_pin_field_but_others_track_seed():
    base = Genome.from_seed("bmev5p5akc")
    custom = base.with_overrides(material=MATERIALS.index("metal"), faces=90)
    assert custom.material == MATERIALS.index("metal")
    assert custom.faces == 90
    # an un-pinned field still equals the seed's derived value
    assert custom.hue == base.hue
    assert custom.mesh_seed == base.mesh_seed


def test_overrides_survive_roundtrip():
    g = Genome.from_seed("bmev5p5akc").with_overrides(hue=250, shapes=4)
    restored = Genome.from_dict(g.to_dict())
    assert restored.hue == 250
    assert restored.shapes == 4
    assert restored.overrides == {"hue": 250, "shapes": 4}


# --------------------------------------------------------------------- brand

def test_unconstrained_hue_comes_from_buckets():
    assert Genome.from_seed("bmev5p5akc").hue in HUE_BUCKETS


def test_brand_constrains_hue_and_material():
    brand = Brand(hues=(45, 215), materials=("metal",))
    for seed in SEEDS:
        g = Genome.from_seed(seed, brand=brand)
        assert g.hue in (45, 215)
        assert g.edge_hue in (45, 215)
        assert g.material == MATERIALS.index("metal")
    # brand survives serialization
    g = Genome.from_seed("agent-alpha", brand=brand)
    assert Genome.from_dict(g.to_dict()).hue in (45, 215)


def test_brand_none_is_unconstrained():
    assert Genome.from_seed("agent-alpha", brand=None).to_dict()["brand"] is None


# ------------------------------------------------------------ geometry basics

@pytest.mark.parametrize("seed", SEEDS)
def test_shards_are_never_flat_panes(seed):
    """HEFT invariant: every shard fills its bounding box in all three axes
    (the anti-sliver guard). Guards against the flat 'evil blade' regression."""
    g = Genome.from_seed(seed)
    g = g.with_overrides(shapes=5)
    for sh in geometry.build_cluster(g, 0.65, 1.2):
        verts = sh["mesh"]["verts"]
        exts = [max(v[k] for v in verts) - min(v[k] for v in verts) for k in range(3)]
        assert min(exts) / max(exts) >= 0.40


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_shape_count_builds_that_many_shards(n):
    g = Genome.from_seed("bmev5p5akc").with_overrides(shapes=n)
    assert len(geometry.build_cluster(g, 0.65, 1.2)) == n


def test_more_shards_read_as_more_substance():
    """Fixed: the presence band grows with shard count, so more shards means
    more total volume (was a known bug: the clamp held volume constant, so
    3/4/5 looked alike)."""
    def total_vol(n):
        cl = geometry.build_cluster(
            Genome.from_seed("bmev5p5akc").with_overrides(shapes=n), 0.65, 1.2)
        return sum((s["size"] ** 3) * s["mesh"]["vol_norm"] for s in cl)

    vols = [total_vol(n) for n in (2, 3, 4, 5)]
    assert all(b > a for a, b in zip(vols, vols[1:]))  # strictly increasing
    assert vols[-1] > vols[0] * 1.2


def test_materials_are_visually_distinct():
    """Material params must actually differ (they do); the open question is
    whether the *renderer* surfaces the difference — see the known-issue note."""
    specs = set()
    for m in MATERIALS:
        g = Genome.from_seed("bmev5p5akc").with_overrides(material=MATERIALS.index(m))
        _, _, mat = geometry.derive_appearance(g)
        specs.add((round(mat["pow"]), round(mat["spec"], 2), round(mat["rim"], 2)))
    assert len(specs) == len(MATERIALS)


def _settled_spread(genome) -> float:
    cluster = geometry.build_cluster(genome, 0.65, 1.2)
    for _ in range(500):
        geometry.physics_step(cluster, 0.016)
    return math.sqrt(sum(sum(q * q for q in s["pos"]) for s in cluster) / len(cluster))


def test_fragmentation_meaningfully_changes_spread():
    """Fixed: the frag home-distance range now clearly exceeds the collision
    contact floor, so low frag = compact cracked whole, high frag = scattered
    debris. (Was a known bug: contact resolution swallowed the frag range.)"""
    seed = "8f2p7ke747"
    low = _settled_spread(Genome.from_seed(seed).with_overrides(shapes=3, frag=0.1))
    high = _settled_spread(Genome.from_seed(seed).with_overrides(shapes=3, frag=0.9))
    assert high > low * 1.3
