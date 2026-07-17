"""Avatar static portraits — line-art and filled-color SVG exporters.

These render the avatar's canonical FRONT pose (physics-settled, so it's the
pose it actually holds facing the user) as standalone SVG strings for use as
profile pictures / identicons. Pure text output — no Qt, no rasterizer — so
this whole module is testable headless; callers rasterize the SVG themselves
if they need a bitmap.

Three variants:
  line "black"  — dark strokes on transparent bg, for light UIs
  line "white"  — light strokes on transparent bg, for dark UIs
  "color"       — filled, shaded facets (a still "photo" of the live avatar)

Line-art does true hidden-line removal (only visible front edges, occluded
segments clipped) and a size-aware stroke/line-hierarchy so it reads at 40px.
Color is opaque back-to-front with back faces culled, so there are never
interior wireframe lines.
"""

from __future__ import annotations

import math
from pathlib import Path

from .genome import Genome
from .geometry import (
    build_cluster,
    derive_appearance,
    lerp_rgb,
    material_base,
    norm3,
    physics_step,
    rotate,
    shade,
)

_SETTLE_STEPS = 500


def _settled(genome: Genome, vol_min: float, vol_max: float, cluster):
    if cluster is None:
        cluster = build_cluster(genome, vol_min, vol_max)
        for _ in range(_SETTLE_STEPS):  # the pose it holds facing the user
            physics_step(cluster, 0.016)
    return cluster


def line_art_svg(genome: Genome, line: str = "black", size: int = 512,
                 px: int | None = None, vol_min: float = 0.65, vol_max: float = 1.2,
                 cluster: list | None = None) -> str:
    """Pure line-art portrait — only the visible front lines, hidden segments
    clipped. `px` = intended display size: smaller sizes get proportionally
    thicker strokes and drop near-coplanar interior edges to whisper weight,
    so the mark reads as a shape (not mud) down to ~40px."""
    px = px or size
    if px >= 128:
        crease_deg = 0.0  # every visible edge is a primary line
    elif px >= 64:
        crease_deg = 18.0
    elif px >= 40:
        crease_deg = 32.0
    else:
        crease_deg = 45.0
    stroke_units = max(size / 256.0, size * 1.3 / px)

    cluster = _settled(genome, vol_min, vol_max, cluster)
    ax, ay = genome.tilt, 0.0  # canonical front pose

    shards = []
    for sh in cluster:
        off = rotate(sh["pos"], ax, ay)
        rot = [rotate(v, ax + sh["dax"], ay + sh["day"]) for v in sh["mesh"]["verts"]]
        world = [(off[0] + v[0] * sh["size"],
                  off[1] + v[1] * sh["size"],
                  off[2] + v[2] * sh["size"]) for v in rot]
        front, normals = [], []
        for ia, ib, ic in sh["mesh"]["faces"]:
            a, b, c = world[ia], world[ib], world[ic]
            ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
            vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
            nx3 = uy * vz - uz * vy
            ny3 = uz * vx - ux * vz
            nz3 = ux * vy - uy * vx
            mx = (a[0] + b[0] + c[0]) / 3 - off[0]
            my = (a[1] + b[1] + c[1]) / 3 - off[1]
            mz = (a[2] + b[2] + c[2]) / 3 - off[2]
            if nx3 * mx + ny3 * my + nz3 * mz < 0:  # outward normal
                nx3, ny3, nz3 = -nx3, -ny3, -nz3
            ln = math.sqrt(nx3 * nx3 + ny3 * ny3 + nz3 * nz3) or 1.0
            normals.append((nx3 / ln, ny3 / ln, nz3 / ln))
            front.append(nz3 > 0.0)
        edge_faces: dict[tuple[int, int], list[int]] = {}
        for fi, (ia, ib, ic) in enumerate(sh["mesh"]["faces"]):
            for e in ((ia, ib), (ib, ic), (ic, ia)):
                edge_faces.setdefault((min(e), max(e)), []).append(fi)
        thr_cos = math.cos(math.radians(crease_deg)) if crease_deg > 0 else None
        # every edge is a candidate — the hidden-line pass decides visibility.
        # Silhouettes are primary; near-coplanar front-front edges are whispers.
        visible = []
        for e, fs in edge_faces.items():
            primary = True
            if thr_cos is not None and len(fs) == 2 and front[fs[0]] and front[fs[1]]:
                n1, n2 = normals[fs[0]], normals[fs[1]]
                if n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2] > thr_cos:
                    primary = False
            visible.append((e, primary, tuple(fs)))
        pts2 = [(w[0], -w[1]) for w in world]
        shards.append(dict(world=world, edges=visible, front=front, pts2=pts2))

    # occluder set: every front-facing triangle, with 2D barycentric data for
    # exact per-sample depth tests (real hidden-line removal)
    occluders = []
    for si, sh in enumerate(shards):
        for fi, (ia, ib, ic) in enumerate(cluster[si]["mesh"]["faces"]):
            if not sh["front"][fi]:
                continue
            a2, b2, c2 = sh["pts2"][ia], sh["pts2"][ib], sh["pts2"][ic]
            den = (b2[1] - c2[1]) * (a2[0] - c2[0]) + (c2[0] - b2[0]) * (a2[1] - c2[1])
            if abs(den) < 1e-9:
                continue
            occluders.append(dict(
                shard=si, fid=fi, a=a2, b=b2, c=c2, den=den,
                za=sh["world"][ia][2], zb=sh["world"][ib][2], zc=sh["world"][ic][2],
                xmin=min(a2[0], b2[0], c2[0]), xmax=max(a2[0], b2[0], c2[0]),
                ymin=min(a2[1], b2[1], c2[1]), ymax=max(a2[1], b2[1], c2[1]),
            ))

    def occluded(qx, qy, z, shard, adj) -> bool:
        for tri in occluders:
            if qx < tri["xmin"] or qx > tri["xmax"] or qy < tri["ymin"] or qy > tri["ymax"]:
                continue
            if tri["shard"] == shard and tri["fid"] in adj:
                continue  # the faces this edge belongs to can't hide it
            a2, b2, c2 = tri["a"], tri["b"], tri["c"]
            w1 = ((b2[1] - c2[1]) * (qx - c2[0]) + (c2[0] - b2[0]) * (qy - c2[1])) / tri["den"]
            w2 = ((c2[1] - a2[1]) * (qx - c2[0]) + (a2[0] - c2[0]) * (qy - c2[1])) / tri["den"]
            w3 = 1.0 - w1 - w2
            if w1 < 0.02 or w2 < 0.02 or w3 < 0.02:  # strictly interior only
                continue
            if w1 * tri["za"] + w2 * tri["zb"] + w3 * tri["zc"] > z + 1e-3:
                return True
        return False

    runs = []
    steps = 24
    for si, sh in enumerate(shards):
        for (ia, ib), primary, adj in sh["edges"]:
            a3, b3 = sh["world"][ia], sh["world"][ib]
            current: list[tuple[float, float]] = []
            for k in range(steps + 1):
                f = k / steps
                z = a3[2] + (b3[2] - a3[2]) * f
                qx = a3[0] + (b3[0] - a3[0]) * f
                qy = -(a3[1] + (b3[1] - a3[1]) * f)
                if occluded(qx, qy, z, si, adj):
                    if len(current) >= 2:
                        runs.append((current[0], current[-1], primary))
                    current = []
                else:
                    current.append((qx, qy))
            if len(current) >= 2:
                runs.append((current[0], current[-1], primary))

    xs = [q[0] for sh in shards for q in sh["pts2"]]
    ys = [q[1] for sh in shards for q in sh["pts2"]]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    scale = size * 0.86 / span
    ox = size / 2 - (min(xs) + max(xs)) / 2 * scale
    oy = size / 2 - (min(ys) + max(ys)) / 2 * scale

    stroke = "#15181c" if line == "black" else "#e8eef4"

    def line_el(a, b) -> str:
        return (f'  <line x1="{a[0] * scale + ox:.1f}" y1="{a[1] * scale + oy:.1f}"'
                f' x2="{b[0] * scale + ox:.1f}" y2="{b[1] * scale + oy:.1f}"/>')

    prim = [line_el(a, b) for a, b, primary in runs if primary]
    sec = [line_el(a, b) for a, b, primary in runs if not primary]
    body = (
        f'<g fill="none" stroke="{stroke}" stroke-width="{stroke_units:.2f}"'
        f' stroke-linecap="round" stroke-linejoin="round">\n'
        + "\n".join(prim) + "\n</g>\n"
    )
    if sec:  # whisper lines: same drawing, at a fraction of the weight
        body += (
            f'<g fill="none" stroke="{stroke}" stroke-width="{stroke_units * 0.45:.2f}"'
            f' stroke-opacity="0.55" stroke-linecap="round" stroke-linejoin="round">\n'
            + "\n".join(sec) + "\n</g>\n"
        )
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">\n{body}</svg>\n'


def color_svg(genome: Genome, size: int = 512, px: int | None = None,
              vol_min: float = 0.65, vol_max: float = 1.2,
              cluster: list | None = None) -> str:
    """Filled, shaded color portrait — a still of the live avatar facing you.
    Opaque, back faces culled (never any interior lines); material reads via
    saturation/lightness/rim/specular, not a wireframe."""
    px = px or size
    stroke_units = max(size / 320.0, size * 0.9 / px)
    palette, edge_rgb, mat = derive_appearance(genome)
    cluster = _settled(genome, vol_min, vol_max, cluster)

    ax, ay = genome.tilt, 0.0
    lx, ly, lz = -0.42, 0.53, 0.74          # key light: upper-left, to viewer
    hx, hy, hz = norm3(lx, ly, lz + 1.0)    # Blinn half-vector for glints
    n_pal = len(palette)
    sat, val_bias = mat["sat"], mat["val_bias"]

    faces_out = []  # (world_depth, [(x, y) * 3], fill_rgb)
    allpts = []
    for sh in cluster:
        mesh = sh["mesh"]
        off = rotate(sh["pos"], ax, ay)
        rot = [rotate(v, ax + sh["dax"], ay + sh["day"]) for v in mesh["verts"]]
        world = [(off[0] + v[0] * sh["size"], off[1] + v[1] * sh["size"],
                  off[2] + v[2] * sh["size"]) for v in rot]
        allpts.extend((w[0], -w[1]) for w in world)
        ylo, yhi = mesh["ylo"], mesh["yhi"]
        yspan = (yhi - ylo) or 1.0
        white_cap = 0.55 + 0.35 * min(1.0, max(0.0, (len(mesh["faces"]) - 8) / 20.0))
        czs = [(world[a][2] + world[b][2] + world[c][2]) / 3 for a, b, c in mesh["faces"]]
        zmin = min(czs)
        zspan = (max(czs) - zmin) or 1.0
        for fi, (ia, ib, ic) in enumerate(mesh["faces"]):
            a, b, c = world[ia], world[ib], world[ic]
            ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
            vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            mx = (a[0] + b[0] + c[0]) / 3 - off[0]
            my = (a[1] + b[1] + c[1]) / 3 - off[1]
            mz = (a[2] + b[2] + c[2]) / 3 - off[2]
            if nx * mx + ny * my + nz * mz < 0:  # outward normal
                nx, ny, nz = -nx, -ny, -nz
            if nz <= 0.0:  # back-facing: hidden behind the front hull
                continue
            nlen = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nx, ny, nz = nx / nlen, ny / nlen, nz / nlen
            lit = max(0.0, nx * lx + ny * ly + nz * lz)
            val = (0.30 + 0.85 * lit) * val_bias                # material lightness
            val *= 1.0 + mesh["var"][fi] * mat["jit"]           # material grain
            val *= 0.80 + 0.20 * ((czs[fi] - zmin) / zspan)     # cheap AO
            band = min(n_pal - 1, max(0, int((mesh["cents"][fi][1] - ylo) / yspan * n_pal)))
            rim = min(1.0, mat["rim"] * (1.0 - max(0.0, nz)) ** 2)
            spec = max(0.0, nx * hx + ny * hy + nz * hz) ** mat["pow"]
            white_mix = min(white_cap, mat["spec"] * 1.3 * spec)
            base = material_base(palette[band], sat, 0.22 * genome.translucency)
            col = shade(base, val)
            col = lerp_rgb(col, (235, 240, 255), rim)
            col = lerp_rgb(col, (255, 255, 255), white_mix)
            faces_out.append((czs[fi],
                              [(world[i][0], -world[i][1]) for i in (ia, ib, ic)],
                              col))
    faces_out.sort(key=lambda t: t[0])  # far first

    xs = [q[0] for q in allpts]
    ys = [q[1] for q in allpts]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    scale = size * 0.86 / span
    ox = size / 2 - (min(xs) + max(xs)) / 2 * scale
    oy = size / 2 - (min(ys) + max(ys)) / 2 * scale

    polys = []
    for _depth, pts, col in faces_out:
        ptstr = " ".join(f"{q[0] * scale + ox:.1f},{q[1] * scale + oy:.1f}" for q in pts)
        fill = "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in col)
        # stroke in the face's OWN color: closes the anti-alias seam between
        # triangles with no visible outline — facets read via shading
        polys.append(f'  <polygon points="{ptstr}" fill="{fill}" stroke="{fill}"'
                     f' stroke-width="{stroke_units:.2f}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">\n'
        f'<g stroke-linejoin="round">\n'
        + "\n".join(polys) + "\n</g>\n</svg>\n"
    )


def export_svg(genome: Genome, out_path: Path, variant: str = "black",
               size: int = 512, px: int | None = None,
               vol_min: float = 0.65, vol_max: float = 1.2) -> Path:
    """Write a portrait to disk: line-art ("black"/"white") or "color"."""
    if variant == "color":
        svg = color_svg(genome, size, px, vol_min, vol_max)
    else:
        svg = line_art_svg(genome, variant, size, px, vol_min, vol_max)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg)
    return out_path
