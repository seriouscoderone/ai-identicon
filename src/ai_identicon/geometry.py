"""Avatar geometry layer — pure math for shard meshes, cluster layout,
micro-physics, and per-facet shading inputs.

No Qt, no I/O: every function here takes plain numbers/dicts and returns
plain numbers/dicts, so the whole geometry+identity stack is unit-testable
headless and shared verbatim by the live widget and the SVG portrait.

The avatar is a "broken whole": 1-5 shards of one fractured solid. The
genome's totals (face budget, roughness) are PARTITIONED across shards, then
two constraints keep it believable — HEFT (min 8 faces/shard, no flat panes)
and PRESENCE (true mesh volume clamped into a band) — and a spring+collision
micro-physics keeps shards touching without interpenetrating.
"""

from __future__ import annotations

import math
import random

from .genome import Genome, MATERIALS, MATERIAL_PARAMS


# ----------------------------------------------------------------- color math

def hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """HSV → RGB matching QColor.fromHsv: h in [0,360), s and v in [0,255].

    Kept pure (no QColor) so this layer needs no Qt; verified to match Qt's
    integer output for the palette's hue/sat/val range.
    """
    sf = s / 255.0
    vf = v / 255.0
    c = vf * sf
    hp = (h % 360) / 60.0
    x = c * (1.0 - abs(hp % 2.0 - 1.0))
    if hp < 1:
        r, g, b = c, x, 0.0
    elif hp < 2:
        r, g, b = x, c, 0.0
    elif hp < 3:
        r, g, b = 0.0, c, x
    elif hp < 4:
        r, g, b = 0.0, x, c
    elif hp < 5:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    m = vf - c
    return (round((r + m) * 255), round((g + m) * 255), round((b + m) * 255))


def lerp_rgb(a, b, t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shade(rgb, val: float) -> tuple[int, int, int]:
    """Brightness 0..1 darkens; >1 blows out toward white (bloom, blink)."""
    if val <= 1.0:
        return tuple(int(c * val) for c in rgb)
    over = min(1.0, (val - 1.0) / 0.6)
    return tuple(int(c + (255 - c) * over) for c in rgb)


def material_base(rgb, sat: float, frost: float) -> tuple[float, float, float]:
    """Apply a material's saturation (lerp toward the color's own luminance,
    i.e. grey) then a frost lightening. This is the rest-state material tell:
    matte-grey stone/metal vs vivid crystal/glass, independent of any
    specular hotspot. Shared by the live widget and the color portrait."""
    lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    desat = tuple(lum + (rgb[i] - lum) * sat for i in range(3))
    return lerp_rgb(desat, (240, 244, 255), frost)


# ----------------------------------------------------------------- 3D helpers

def norm3(x: float, y: float, z: float) -> tuple[float, float, float]:
    d = math.sqrt(x * x + y * y + z * z) or 1.0
    return (x / d, y / d, z / d)


def rotate(v, ax: float, ay: float) -> tuple[float, float, float]:
    """Ry(ay) then Rx(ax) — enough axes for a natural-looking tumble."""
    x, y, z = v
    cy_, sy_ = math.cos(ay), math.sin(ay)
    x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_
    cx_, sx_ = math.cos(ax), math.sin(ax)
    y, z = y * cx_ - z * sx_, y * sx_ + z * cx_
    return x, y, z


def convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """2D convex hull (monotonic chain) — used to clip a shard's glow to its
    own projected silhouette."""
    pts = sorted(set((round(x, 1), round(y, 1)) for x, y in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list = []
    for pt in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], pt) <= 0:
            lower.pop()
        lower.append(pt)
    upper: list = []
    for pt in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], pt) <= 0:
            upper.pop()
        upper.append(pt)
    return lower[:-1] + upper[:-1]


# ----------------------------------------------------------------------- mesh

def hull3d(pts: list[list[float]]) -> list[tuple[int, int, int]]:
    """Incremental convex hull of points in general position on a sphere.

    Every point lands on the hull, and n points give exactly 2n-4 triangular
    faces — which is what turns "number of faces" into a real slider.
    """

    def normal(f):
        a, b, c = pts[f[0]], pts[f[1]], pts[f[2]]
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        return [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]

    ctr = [sum(p[i] for p in pts[:4]) / 4 for i in range(3)]
    faces = []
    for f in [(0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)]:
        n = normal(f)
        a = pts[f[0]]
        if sum(n[i] * (a[i] - ctr[i]) for i in range(3)) < 0:
            f = (f[0], f[2], f[1])
        faces.append(f)

    for pi in range(4, len(pts)):
        p = pts[pi]
        visible = []
        for f in faces:
            n = normal(f)
            a = pts[f[0]]
            if sum(n[i] * (p[i] - a[i]) for i in range(3)) > 1e-12:
                visible.append(f)
        if not visible:
            continue
        vis = set(visible)
        edges = {}
        for f in visible:
            for e in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
                edges[e] = f
        horizon = [e for e in edges if (e[1], e[0]) not in edges]
        faces = [f for f in faces if f not in vis]
        # (u, v) was a directed edge of an outward face, so (u, v, p) is outward
        faces.extend((u, v, pi) for u, v in horizon)
    return faces


def make_shard(face_count: int, roughness: float, elong: tuple[float, float, float],
               seed: int) -> dict:
    """One irregular rock, guaranteed plump.

    Regenerates with tamer parameters until the shard's TRUE volume is at
    least 22% of its bounding sphere — flat, blade-like shards never ship
    (they read as sharp and hostile, and they lie about having substance).
    """
    rough = roughness
    el = list(elong)
    mesh = None
    for attempt in range(6):
        rng = random.Random(seed + attempt * 7919)
        # attempt 0 = free random points (preserves existing seeds' looks);
        # retries switch to a well-spread distribution that cannot land all
        # its points near one plane — the flat-shard failure mode
        mesh = _build_shard_once(face_count, rough, tuple(el), rng, spread=attempt > 0)
        if mesh["plump"] >= 0.22:
            return mesh
        rough *= 0.7
        el = [q + (0.29 - q) * 0.4 for q in el]  # ease toward neutral stretch
    return mesh


def _build_shard_once(face_count: int, roughness: float,
                      elong: tuple[float, float, float], rng: random.Random,
                      spread: bool = False) -> dict:
    """Hull of random sphere points, roughed up radially.

    Radial-only perturbation keeps the mesh star-shaped around the origin,
    which keeps painter's-algorithm depth sorting safe. roughness may exceed
    1.0 (fragment jitter) — the range is deliberately extreme at the top.
    """
    n_pts = max(4, (face_count + 4) // 2)
    verts = []
    if spread:  # jittered fibonacci lattice: organic but never planar
        golden = math.pi * (3.0 - math.sqrt(5.0))
        jit = 0.55 / math.sqrt(n_pts)
        for i in range(n_pts):
            y = 1.0 - 2.0 * (i + 0.5) / n_pts
            rr = math.sqrt(max(0.0, 1.0 - y * y))
            th = golden * i
            x = rr * math.cos(th) + rng.gauss(0, jit)
            yy = y + rng.gauss(0, jit)
            z = rr * math.sin(th) + rng.gauss(0, jit)
            d = math.sqrt(x * x + yy * yy + z * z) or 1.0
            verts.append([x / d, yy / d, z / d])
    else:
        for _ in range(n_pts):
            x, y, z = rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)
            d = math.sqrt(x * x + y * y + z * z) or 1.0
            verts.append([x / d, y / d, z / d])
    faces = hull3d(verts)

    lo = max(0.45, 1.0 - 0.06 - 0.40 * roughness)  # floor guards against slivers
    hi = 1.0 + 0.07 + 0.55 * roughness
    sx, sy, sz = (0.75 + 0.85 * e for e in elong)
    for v in verts:
        bump = rng.uniform(lo, hi)
        v[0] *= bump * sx
        v[1] *= bump * sy
        v[2] *= bump * sz

    # the HEFT (not-gimpy) constraint: no shard may be a near-flat pane —
    # any axis thinner than 42% of the widest gets scaled back up
    mins = [min(v[k] for v in verts) for k in range(3)]
    maxs = [max(v[k] for v in verts) for k in range(3)]
    exts = [maxs[k] - mins[k] for k in range(3)]
    big = max(exts) or 1.0
    for k in range(3):
        if exts[k] < 0.42 * big:
            f = (0.42 * big) / (exts[k] or 1e-6)
            for v in verts:
                v[k] *= f

    cents, var = [], []
    vol6 = 0.0  # divergence theorem: exact volume from outward-wound faces
    for a, b, c in faces:
        va, vb, vc = verts[a], verts[b], verts[c]
        cents.append(tuple((va[k] + vb[k] + vc[k]) / 3 for k in range(3)))
        var.append(rng.uniform(-1.0, 1.0))  # static per-facet value jitter
        vol6 += (va[0] * (vb[1] * vc[2] - vb[2] * vc[1])
                 - va[1] * (vb[0] * vc[2] - vb[2] * vc[0])
                 + va[2] * (vb[0] * vc[1] - vb[1] * vc[0]))
    volume = abs(vol6) / 6.0
    ys = [c[1] for c in cents]
    norms = [math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) for v in verts]
    rad = max(norms)
    sphere = (4.0 / 3.0) * math.pi
    return dict(verts=verts, faces=faces, cents=cents, var=var,
                spec_prev=[0.0] * len(faces),  # temporally eased glints
                rad=rad, rad_avg=sum(norms) / len(norms),
                vol_norm=volume / sphere,           # in unit-sphere volumes
                plump=volume / (sphere * rad ** 3),  # 1.0 = sphere, ~0 = blade
                ylo=min(ys), yhi=max(ys))


# -------------------------------------------------------------------- cluster

def build_cluster(genome: Genome, vol_min: float, vol_max: float) -> list[dict]:
    """Partition the genome totals into a shard cluster (shared by the live
    widget and the SVG portrait exporter)."""
    n = max(1, min(5, genome.shapes))
    raw = genome.shards[:n]
    tot = sum(s["wg"] for s in raw) or 1.0
    weights = [(1.0 - genome.frag) / n + genome.frag * s["wg"] / tot for s in raw]
    wsum = sum(weights)
    weights = [w / wsum for w in weights]

    cluster = []
    for s, w in zip(raw, weights):
        face_share = max(8, 2 * round(genome.faces * w / 2))  # heft: min faces
        rough = min(1.2, max(0.05, genome.roughness * (1.0 + genome.frag * s["rj"])))
        mesh = make_shard(face_share, rough, genome.elong, s["mesh_seed"])
        # Fragmentation home distance. Low frag keeps homes well inside the
        # collision contact floor, so shards settle into a compact cracked
        # whole; high frag pushes homes far past contact, so they scatter as
        # a debris field. The gain is tuned so the range clearly exceeds the
        # contact distance (a smaller range gets swallowed by collisions).
        dist = 0.0 if n == 1 else (0.15 + 2.0 * genome.frag ** 1.3) * s["draw"]
        size = (w ** (1.0 / 3.0)) * 1.05 / (n ** 0.28)
        prng = random.Random(s["mesh_seed"] ^ 0x5EED)
        cluster.append(dict(
            mesh=mesh, size=size, dist=dist,
            wph=[prng.uniform(0.0, math.tau) for _ in range(3)],
            pos=[s["dir"][k] * dist for k in range(3)],
            vel=[0.0, 0.0, 0.0], drift=0.0, **s))

    # PRESENCE (volume) constraint: TRUE total mesh volume (in unit-sphere
    # volumes, exact under elongation/roughness) clamped into the band —
    # so no avatar reads as "less than", however stretched its genome is.
    # The band grows modestly with shard count so more shards read as more
    # substance (else the clamp just shrinks each shard and 3/4/5 converge).
    grow = 1.0 + 0.12 * (n - 1)
    lo, hi = vol_min * grow, vol_max * grow
    vol = sum((sh["size"] ** 3) * sh["mesh"]["vol_norm"] for sh in cluster)
    f = 1.0
    if vol < lo:
        f = (lo / vol) ** (1.0 / 3.0)
    elif vol > hi:
        f = (hi / vol) ** (1.0 / 3.0)
    if f != 1.0:
        for sh in cluster:
            sh["size"] *= f
            sh["dist"] *= f
            sh["pos"] = [q * f for q in sh["pos"]]
    return cluster


def physics_step(cluster: list[dict], dt: float, sep: float = 1.0,
                 wander_amp: float = 0.0, t: float = 0.0, k_t: float = 1.0) -> None:
    """One step of the shard micro-physics: springs toward home, optional
    wander, mass-weighted collision response, centroid recentering. Shared by
    the live widget and the portrait renderer (which settles with it)."""
    if len(cluster) < 2:
        return
    for sh in cluster:
        for k in range(3):
            home = sh["dir"][k] * sh["dist"] * sep
            wander = wander_amp * math.sin(t * 0.8 * k_t + sh["wph"][k])
            acc = 6.0 * (home - sh["pos"][k]) - 3.0 * sh["vel"][k] + wander
            sh["vel"][k] += acc * dt
            sh["pos"][k] += sh["vel"][k] * dt
    for i in range(len(cluster)):
        for j in range(i + 1, len(cluster)):
            a, b = cluster[i], cluster[j]
            ra = a["size"] * a["mesh"]["rad"]
            rb = b["size"] * b["mesh"]["rad"]
            dx = [a["pos"][k] - b["pos"][k] for k in range(3)]
            d = math.sqrt(sum(q * q for q in dx)) or 1e-6
            need = (ra + rb) * 0.82  # bounding spheres overstate — real touch
            if d < need:
                nrm = [q / d for q in dx]
                ma, mb = a["size"] ** 3, b["size"] ** 3
                corr = need - d  # separate to contact; heavier moves less
                wa = mb / (ma + mb)
                for k in range(3):
                    a["pos"][k] += nrm[k] * corr * wa
                    b["pos"][k] -= nrm[k] * corr * (1.0 - wa)
                vn = sum((a["vel"][k] - b["vel"][k]) * nrm[k] for k in range(3))
                if vn < 0:  # approaching → bounce with some restitution
                    imp = -(1.0 + 0.55) * vn / (1.0 / ma + 1.0 / mb)
                    for k in range(3):
                        a["vel"][k] += imp / ma * nrm[k]
                        b["vel"][k] -= imp / mb * nrm[k]
    # recenter: collisions push outward, so pin the mass-weighted centroid
    total_m = sum(sh["size"] ** 3 for sh in cluster)
    for k in range(3):
        mean = sum(sh["pos"][k] * sh["size"] ** 3 for sh in cluster) / total_m
        for sh in cluster:
            sh["pos"][k] -= mean


# ------------------------------------------------------------- appearance

def derive_appearance(genome: Genome):
    """Palette bands, edge (rim) color, and material params for a genome.

    The single source of truth for an avatar's coloring — shared by the live
    widget and the SVG color portrait so the two can never drift apart.
    """
    rng = random.Random(genome.mesh_seed ^ 0x9E3779B9)
    offsets = [0, rng.choice([35, -35, 150]), rng.choice([-60, 60, 180])]
    palette = [hsv_to_rgb((genome.hue + offsets[i]) % 360, 165, 235)
               for i in range(genome.n_colors)]
    edge_rgb = hsv_to_rgb(genome.edge_hue, 200, 255)
    mat = dict(MATERIAL_PARAMS[MATERIALS[genome.material]])
    polish = 0.4 + 1.2 * genome.shine  # Shine fine-tune within the preset
    mat["spec"] = min(1.0, mat["spec"] * polish)
    mat["rim"] = min(1.0, mat["rim"] * (0.7 + 0.5 * polish))
    return palette, edge_rgb, mat
