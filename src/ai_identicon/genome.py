"""Avatar identity layer — deterministic genome derived from a seed.

An avatar is a generative, abstract faceted "presence" for an embedded agent.
Its whole appearance and behavior are grown from a seed string; in production
the seed is the agent's AID prefix, making the avatar a visual fingerprint of
the identifier (an identity *affordance*, never a security control — a
look-alike is grindable, so the verifiable identifier must always remain the
source of truth).

Two engineering decisions are baked in here:

* **Frozen versioning.** Each derivation algorithm is a numbered, immutable
  function (`_derive_v1`, ...). An avatar records the `algo_version` it was
  born under and is re-derived with that same function forever, so improving
  the generator later never silently changes an existing agent's face. This
  mirrors the SAID re-pinning discipline used elsewhere in the repo.

* **Deterministic base + sparse customization overlay.** The stored form is
  `(seed, algo_version, brand, overrides)`. `from_seed` derives every field
  deterministically, applies an optional brand constraint, then lays the
  user's explicit `overrides` on top. Anything the user hasn't pinned keeps
  tracking the seed.

This module is pure Python — no Qt, no rendering — so it is trivially
testable and reusable by the live widget and the static SVG portrait alike.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field, replace

ALGO_VERSION = 1

THINKING_STYLES = ("breakup", "glow", "shimmer", "orbiter")  # personality trait
VOICE_STYLES = ("raw", "glitch")  # speaking-waveform character, personality trait

# Material is categorical (per UX consult): the treatments aren't monotonic
# along one axis — metal has broad low-power glints, glass tiny high-power
# ones, stone is matte — so a preset picker + a continuous Shine fine-tune.
#   pow   specular exponent        spec  specular strength
#   rim   fresnel rim brightening  grad  per-facet gradient strength
#   jit   per-facet value jitter   transl  seeded translucency bias
#   sat   color saturation (rest-state tell)  val_bias  overall lightness
# sat/val_bias differentiate materials WITHOUT relying on the specular
# hotspot (which is angle-dependent and often absent): matte-dark stone,
# bright crystal, desaturated metal, light frosted glass — legible at rest.
MATERIALS = ("stone", "crystal", "metal", "glass")
MATERIAL_PARAMS = {
    "stone": dict(pow=4.0, spec=0.15, rim=0.15, grad=0.40, jit=0.12, transl=0.05, sat=0.68, val_bias=0.86),
    "crystal": dict(pow=60.0, spec=0.70, rim=0.70, grad=0.40, jit=0.05, transl=0.50, sat=1.00, val_bias=1.06),
    "metal": dict(pow=14.0, spec=0.90, rim=0.30, grad=0.70, jit=0.05, transl=0.00, sat=0.48, val_bias=0.98),
    "glass": dict(pow=80.0, spec=0.50, rim=0.85, grad=0.20, jit=0.00, transl=0.75, sat=0.90, val_bias=1.12),
}

# Curated, perceptually spaced hue buckets (the jazzicon lesson): users only
# reliably discriminate ~10-12 hues, so seeds draw from these instead of a
# continuous wheel — two agents' colors are either the same or clearly not.
HUE_BUCKETS = (355, 25, 45, 75, 110, 145, 170, 195, 215, 250, 285, 320)

# Fields a user may pin via overrides (the exposed, safe-to-customize knobs).
# mesh_seed / shards / seed / algo_version are identity structure, not knobs.
OVERRIDE_FIELDS = frozenset({
    "faces", "shapes", "frag", "roughness", "translucency", "hue", "n_colors",
    "material", "shine", "elong", "tilt", "edge_hue", "express", "tempo",
    "sharp", "thinking", "voice",
})


@dataclass(frozen=True)
class Brand:
    """Optional palette/material constraint applied on top of derivation.

    `hues` / `materials` = allowed sets (None = unconstrained). Applied as a
    post-derivation remap so an unconstrained genome is byte-identical to the
    raw seed derivation; a brand only snaps the already-drawn choices into its
    allowed sets, keeping determinism intact.
    """

    hues: tuple[int, ...] | None = None
    materials: tuple[str, ...] | None = None

    def to_dict(self) -> dict | None:
        if self.hues is None and self.materials is None:
            return None
        return {"hues": list(self.hues) if self.hues else None,
                "materials": list(self.materials) if self.materials else None}

    @classmethod
    def from_dict(cls, d: dict | None) -> "Brand | None":
        if not d:
            return None
        return cls(hues=tuple(d["hues"]) if d.get("hues") else None,
                   materials=tuple(d["materials"]) if d.get("materials") else None)


@dataclass
class Genome:
    """Everything that makes one avatar THIS avatar. Deterministic from seed.

    Fields are the derived-then-overridden appearance/behavior values. The
    persistable identity is only `(seed, algo_version, brand, overrides)` —
    see `to_dict`; the rest is reproducible from those.
    """

    seed: str = "ai-identicon"
    algo_version: int = ALGO_VERSION
    mesh_seed: int = 7
    faces: int = 40           # TOTAL face budget, partitioned across shards
    shapes: int = 1           # shard count
    frag: float = 0.5         # 0 = even split & tight cluster, 1 = wild
    roughness: float = 0.5    # 0..1; shards get jittered shares
    translucency: float = 0.3
    hue: int = 215
    n_colors: int = 1
    material: int = 1         # index into MATERIALS — categorical identity channel
    shine: float = 0.3        # polish fine-tune within the material preset
    elong: tuple = (0.3, 0.3, 0.3)  # per-axis stretch, 0.29 ≈ neutral
    tilt: float = 0.35        # resting stance — a consistent cant is identity
    edge_hue: int = 215       # second hue channel (rim / line-art strokes)
    express: float = 0.5      # personality: amplitude of every gesture
    tempo: float = 0.5        # personality: frequency of every gesture
    sharp: float = 0.5        # personality: voice grit / trace crispness
    thinking: int = 0         # personality: index into THINKING_STYLES
    voice: int = 0            # personality: index into VOICE_STYLES
    shards: list = field(default_factory=list)
    brand: Brand | None = None
    overrides: dict = field(default_factory=dict)

    # ------------------------------------------------------------ derivation

    @classmethod
    def from_seed(cls, seed: str, *, brand: Brand | None = None,
                  overrides: dict | None = None,
                  algo_version: int = ALGO_VERSION) -> "Genome":
        try:
            derive = _DERIVERS[algo_version]
        except KeyError:
            raise ValueError(f"unknown genome algo_version {algo_version}") from None
        g = derive(cls, seed)
        g.algo_version = algo_version
        if brand is not None:
            _apply_brand(g, brand)
            g.brand = brand
        g.overrides = dict(overrides or {})
        for key, val in g.overrides.items():
            if key in OVERRIDE_FIELDS:
                setattr(g, key, val)
        return g

    def with_overrides(self, **kw) -> "Genome":
        """Return a fresh genome with these fields pinned (merged over any
        existing overrides). Re-derives from the seed, so unpinned fields
        still track the seed and the result round-trips through to_dict."""
        merged = {**self.overrides, **kw}
        return Genome.from_seed(self.seed, brand=self.brand, overrides=merged,
                                algo_version=self.algo_version)

    # --------------------------------------------------------- serialization

    def to_dict(self) -> dict:
        """The persistable identity: seed + version + brand + overrides only.
        Frozen versioning guarantees this re-derives to the same avatar."""
        return {
            "seed": self.seed,
            "algo_version": self.algo_version,
            "brand": self.brand.to_dict() if self.brand else None,
            "overrides": dict(self.overrides),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Genome":
        return cls.from_seed(
            d["seed"],
            brand=Brand.from_dict(d.get("brand")),
            overrides=d.get("overrides") or {},
            algo_version=d.get("algo_version", ALGO_VERSION),
        )

    def copy(self) -> "Genome":
        return replace(self, elong=tuple(self.elong),
                       shards=[dict(s) for s in self.shards],
                       overrides=dict(self.overrides))


# --------------------------------------------------------------- version 1

def _derive_v1(cls, seed: str) -> Genome:
    """Genome derivation algorithm, version 1. FROZEN — never edit in place;
    add `_derive_v2` and register it if the generator changes."""
    digest = hashlib.sha256(seed.encode()).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    g = cls(seed=seed, mesh_seed=int.from_bytes(digest[8:16], "big"))
    g.faces = 4 + 2 * int(58 * rng.random() ** 1.5)  # skew low; max 120
    g.shapes = rng.choices([1, 2, 3, 4, 5], [4, 3, 2, 2, 1])[0]
    g.frag = rng.uniform(0.2, 0.9)
    g.roughness = rng.uniform(0.15, 0.95)
    g.hue = rng.choice(HUE_BUCKETS)
    g.n_colors = rng.choices([1, 2, 3], [3, 4, 3])[0]
    g.material = rng.choices([0, 1, 2, 3], [3, 3, 2, 2])[0]
    base_transl = MATERIAL_PARAMS[MATERIALS[g.material]]["transl"]
    g.translucency = min(0.85, max(0.0, base_transl + rng.uniform(-0.15, 0.20)))
    g.shine = rng.uniform(0.25, 1.0)
    g.elong = tuple(min(1.0, max(0.0, rng.gauss(0.29, 0.22))) for _ in range(3))
    g.tilt = rng.uniform(0.15, 0.75) * rng.choice([-1, 1])
    g.edge_hue = (g.hue + rng.choice([0, 0, 45, -45, 160])) % 360
    g.express = rng.uniform(0.2, 1.0)
    g.tempo = rng.uniform(0.2, 0.9)
    g.sharp = rng.random()
    g.thinking = rng.choices([0, 1, 2, 3], [3, 3, 2, 2])[0]
    g.voice = rng.choices([0, 1], [3, 2])[0]

    def norm(x, y, z):
        d = math.sqrt(x * x + y * y + z * z) or 1.0
        return (x / d, y / d, z / d)

    g.shards = [dict(
        dir=norm(rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)),
        draw=rng.uniform(0.5, 1.0),        # distance factor from center
        wg=rng.gammavariate(1.2, 1.0),     # raw partition weight
        rj=rng.uniform(-0.5, 0.9),         # roughness jitter (scaled by frag)
        dax=rng.uniform(0.0, math.tau),    # orientation phase offsets
        day=rng.uniform(0.0, math.tau),
        selfr=rng.uniform(-0.4, 0.4),      # slow relative drift
        mesh_seed=rng.randrange(1 << 30),
    ) for _ in range(5)]  # always derive 5 so the Shapes slider is stable
    return g


_DERIVERS = {1: _derive_v1}


def _apply_brand(g: Genome, brand: Brand) -> None:
    """Snap already-drawn choices into a brand's allowed sets (post-derivation
    remap, so it never disturbs the deterministic draw sequence)."""
    if brand.hues:
        g.hue = min(brand.hues, key=lambda h: min(abs(g.hue - h), 360 - abs(g.hue - h)))
        g.edge_hue = min(brand.hues, key=lambda h: min(abs(g.edge_hue - h), 360 - abs(g.edge_hue - h)))
    if brand.materials:
        allowed = [MATERIALS.index(m) for m in brand.materials if m in MATERIALS]
        if allowed and g.material not in allowed:
            g.material = allowed[g.material % len(allowed)]
