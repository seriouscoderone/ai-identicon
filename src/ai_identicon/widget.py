"""Avatar live renderer — a Qt widget driven by an AvatarModel.

This is the only rendering layer that needs Qt. It owns a QTimer that advances
the (headless) model each frame and paints the result: the shard cluster
(flat-shaded facets, no wireframe), the state halo and notify rings, the
thinking treatments (breakup/glow/shimmer/orbiter), and the listening/speaking
ring. It also hosts the static portrait "preview" (via portrait.py) and plays
the model's one-shot sound cues through an optional SoundBank.

Integration surface: set_state(), set_amplitude(), set_spectrum(),
set_genome(), set_preview(). All behavior lives in the model; this file is
pixels. (Glassy transparency is intrinsic to crystal/glass materials — not a
toggle.)
"""

from __future__ import annotations

import math

from PySide6.QtCore import QByteArray, QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from . import geometry, portrait
from .genome import Genome, MATERIALS
from .model import AvatarModel, AvatarState

# "glassy" (literal per-shard transparency) only reads as a material property
# on the see-through materials; stone and metal stay opaque even when toggled.
_GLASSY_MATERIALS = frozenset({"crystal", "glass"})

try:
    from PySide6.QtSvg import QSvgRenderer

    HAVE_SVG = True
except ImportError:  # portrait preview degrades gracefully
    HAVE_SVG = False

_lerp_rgb = geometry.lerp_rgb


class PresenceWidget(QWidget):
    """Live avatar widget. Construct with a Genome (or an AvatarModel) and an
    optional SoundBank; drive with set_state()/set_amplitude()."""

    def __init__(self, genome_or_model, parent: QWidget | None = None, sounds=None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self.model = (genome_or_model if isinstance(genome_or_model, AvatarModel)
                      else AvatarModel(genome_or_model))
        self._sounds = sounds
        self.zoom = 1.0           # orb size within the frame (1.0 = default)
        self._ring_r = 0.0        # smoothed listening/speaking circle radius
        self._preview: str | None = None
        self._preview_renderers: list = []
        self._preview_quad = 0.0

        self._clock = QElapsedTimer()
        self._clock.start()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    # ------------------------------------------------------------------- API

    def set_state(self, state: AvatarState) -> None:
        self.model.set_state(state)

    def set_amplitude(self, value) -> None:
        self.model.set_amplitude(value)

    def set_spectrum(self, bands) -> None:
        self.model.set_spectrum(bands)

    def set_genome(self, genome: Genome) -> None:
        self.model.set_genome(genome)
        if self._preview:
            self.set_preview(self._preview)
        self.update()

    def copy_to_clipboard(self, variant: str = "color", size: int = 512,
                          background: str | None = None) -> None:
        """Copy this avatar to the system clipboard as a pasteable PNG."""
        from .clipboard import copy_to_clipboard
        copy_to_clipboard(self.model.genome, size=size, variant=variant,
                          background=background,
                          vol_min=self.model.vol_min, vol_max=self.model.vol_max)

    @property
    def genome(self) -> Genome:
        return self.model.genome

    @property
    def state(self) -> AvatarState:
        return self.model.state

    @property
    def preview_mode(self) -> str | None:
        return self._preview

    # ------------------------------------------------------------ animation

    def _tick(self) -> None:
        dt = min(0.05, self._clock.restart() / 1000.0)
        self.model.advance(dt)
        if self._sounds is not None:
            cue = self.model.take_cue()
            if cue:
                self._sounds.play(cue)
        self.update()

    # --------------------------------------------------------------- preview

    def set_preview(self, mode: str | None) -> None:
        """Show static portraits instead of the live avatar — four sizes in
        four quadrants (smallest = the standard ~40px avatar). "white"/"black"
        line-art or "color". None returns to the animated avatar."""
        if mode is None or not HAVE_SVG:
            self._preview = None
            self._preview_renderers = []
            self.update()
            return
        m = self.model
        quad = min(self.width(), self.height()) / 2.0
        self._preview_quad = quad
        big = max(200, int(quad * 0.86))
        vmax = max(m.vol_min, m.vol_max)
        cl = geometry.build_cluster(m.genome, m.vol_min, vmax)
        for _ in range(500):  # settle once, render four times
            geometry.physics_step(cl, 0.016)
        self._preview_renderers = []
        for px in (40, 96, 160, big):
            if mode == "color":
                svg = portrait.color_svg(m.genome, 512, px, m.vol_min, vmax, cluster=cl)
            else:
                svg = portrait.line_art_svg(m.genome, mode, 512, px, m.vol_min, vmax, cluster=cl)
            self._preview_renderers.append((px, QSvgRenderer(QByteArray(svg.encode()))))
        self._preview = mode
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._preview and self._preview_quad > 0:
            quad = min(self.width(), self.height()) / 2.0
            if abs(quad - self._preview_quad) / self._preview_quad > 0.2:
                self.set_preview(self._preview)  # re-tune to the new size

    # ------------------------------------------------------------- painting

    def _draw_solid(self, p, mesh, ax, ay, cx, cy, scale_px, bright,
                    tint_mix, tint, explode, shimmer, hull_out):
        m = self.model
        g = m.genome
        mat = m.mat
        palette = m.palette
        n_pal = len(palette)
        ylo, yhi = mesh["ylo"], mesh["yhi"]
        yspan = (yhi - ylo) or 1.0
        alpha = 255  # opaque: back faces culled, so nothing shows through
        # frost is the opaque stand-in for translucency; glassy mode does real
        # transparency instead, so skip it there (else glass whitens twice)
        # frost is the opaque stand-in for translucency; the see-through
        # materials get real transparency instead, so skip frost there
        frost = 0.0 if MATERIALS[g.material] in _GLASSY_MATERIALS else 0.22 * g.translucency
        white_cap = 0.55 + 0.35 * min(1.0, max(0.0, (len(mesh["faces"]) - 8) / 20.0))

        rotated = [geometry.rotate(v, ax, ay) for v in mesh["verts"]]
        proj2d = [(cx + x * scale_px, cy - y * scale_px) for x, y, _z in rotated]
        hull_out.extend(proj2d)

        cents_rot = [geometry.rotate(list(c), ax, ay) for c in mesh["cents"]]
        offs = []
        for fi in range(len(mesh["faces"])):
            if explode > 0.001:
                c = cents_rot[fi]
                nl = math.sqrt(sum(q * q for q in c)) or 1.0
                k = explode * (1.0 + 0.3 * math.sin(m.t * 1.6 + fi * 1.1))
                offs.append((c[0] / nl * k, c[1] / nl * k, c[2] / nl * k))
            else:
                offs.append((0.0, 0.0, 0.0))
        order = sorted(range(len(mesh["faces"])), key=lambda fi: cents_rot[fi][2] + offs[fi][2])
        zs = [c[2] for c in cents_rot]
        zmin = min(zs)
        zspan = (max(zs) - zmin) or 1.0

        lx, ly, lz = -0.42, 0.53, 0.74  # key light: upper-left, toward viewer
        hx, hy, hz = geometry.norm3(lx, ly, lz + 1.0)  # Blinn half-vector
        glx, gly = geometry.norm3(lx, -ly, 0.0)[:2]    # screen-space light dir

        for fi in order:
            ia, ib, ic = mesh["faces"][fi]
            ox, oy, oz = offs[fi]
            a = (rotated[ia][0] + ox, rotated[ia][1] + oy, rotated[ia][2] + oz)
            b = (rotated[ib][0] + ox, rotated[ib][1] + oy, rotated[ib][2] + oz)
            c = (rotated[ic][0] + ox, rotated[ic][1] + oy, rotated[ic][2] + oz)
            ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
            vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            mx, my, mz = cents_rot[fi]
            if nx * mx + ny * my + nz * mz < 0:
                nx, ny, nz = -nx, -ny, -nz
            nlen = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nx, ny, nz = nx / nlen, ny / nlen, nz / nlen
            # no back-face culling: all faces painted back-to-front (order
            # above), so a convex shard fills its silhouette with no holes —
            # culling could drop a near-edge-on face on a flat shard.

            lit = max(0.0, nx * lx + ny * ly + nz * lz)
            val = (0.30 + 0.85 * lit) * bright * mat["val_bias"]
            if shimmer > 0.001:
                cy_obj = mesh["cents"][fi][1]
                val *= 1.0 + 0.35 * shimmer * math.sin(m.t * 2.8 + fi * 0.9 + cy_obj * 2.0)
            val *= 1.0 + mesh["var"][fi] * mat["jit"]          # material grain
            val *= 0.80 + 0.20 * ((cents_rot[fi][2] - zmin) / zspan)  # cheap AO

            band = min(n_pal - 1, max(0, int((mesh["cents"][fi][1] - ylo) / yspan * n_pal)))
            base = geometry.material_base(palette[band], mat["sat"], frost)
            base = _lerp_rgb(base, tint, tint_mix)
            rim = min(1.0, mat["rim"] * (1.0 - max(0.0, nz)) ** 2)
            spec = max(0.0, nx * hx + ny * hy + nz * hz) ** mat["pow"]
            s = mesh["spec_prev"][fi] + (spec - mesh["spec_prev"][fi]) * 0.25
            mesh["spec_prev"][fi] = s  # glints swell and fade instead of popping
            white_mix = min(white_cap, mat["spec"] * 1.3 * s)

            grad = mat["grad"]
            top = _lerp_rgb(geometry.shade(base, val * (1.0 + 0.35 * grad)), (235, 240, 255), rim)
            bot = _lerp_rgb(geometry.shade(base, val * (1.0 - 0.35 * grad)), (235, 240, 255), rim)
            top = _lerp_rgb(top, (255, 255, 255), white_mix)
            bot = _lerp_rgb(bot, (255, 255, 255), white_mix * 0.35)

            pa = QPointF(cx + a[0] * scale_px, cy - a[1] * scale_px)
            pb = QPointF(cx + b[0] * scale_px, cy - b[1] * scale_px)
            pc = QPointF(cx + c[0] * scale_px, cy - c[1] * scale_px)
            ctr_x = (pa.x() + pb.x() + pc.x()) / 3
            ctr_y = (pa.y() + pb.y() + pc.y()) / 3
            rad2 = max(math.hypot(q.x() - ctr_x, q.y() - ctr_y) for q in (pa, pb, pc))
            mid = _lerp_rgb(top, bot, 0.5)
            seam = QPen(QColor(*mid, alpha))  # hairline in own color: no outline
            seam.setWidthF(0.8)
            p.setPen(seam)
            if grad > 0.05 and rad2 > 1.5:
                lg = QLinearGradient(QPointF(ctr_x + glx * rad2, ctr_y + gly * rad2),
                                     QPointF(ctr_x - glx * rad2, ctr_y - gly * rad2))
                lg.setColorAt(0.0, QColor(*top, alpha))
                lg.setColorAt(1.0, QColor(*bot, alpha))
                p.setBrush(lg)
            else:
                p.setBrush(QColor(*mid, alpha))
            p.drawPolygon(QPolygonF([pa, pb, pc]))
        p.setPen(Qt.NoPen)
        return proj2d

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(13, 17, 22))
        m = self.model

        if self._preview:  # static portraits, four sizes in four quadrants
            pw, ph = self.width(), self.height()
            quads = [QRectF(0, 0, pw / 2, ph / 2), QRectF(pw / 2, 0, pw / 2, ph / 2),
                     QRectF(0, ph / 2, pw / 2, ph / 2), QRectF(pw / 2, ph / 2, pw / 2, ph / 2)]
            p.setPen(Qt.NoPen)
            for (px, renderer), quad in zip(self._preview_renderers, quads):
                side = min(float(px), quad.width() * 0.84, quad.height() * 0.84)
                target = QRectF(quad.center().x() - side / 2,
                                quad.center().y() - side / 2, side, side)
                if self._preview == "black":
                    disp = m.palette[0]
                    p.setCompositionMode(QPainter.CompositionMode_Plus)
                    halo = QRadialGradient(target.center(), side * 0.64)
                    halo.setColorAt(0.0, QColor(*disp, 205))
                    halo.setColorAt(0.55, QColor(*disp, 120))
                    halo.setColorAt(1.0, QColor(*disp, 0))
                    p.setBrush(halo)
                    p.drawEllipse(target.center(), side * 0.64, side * 0.64)
                    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
                renderer.render(p, target)
                p.setPen(QColor(138, 151, 165, 210))
                p.drawText(QRectF(quad.x(), target.bottom() + 3, quad.width(), 16),
                           Qt.AlignHCenter, f"{px} px")
                p.setPen(Qt.NoPen)
            return

        g = m.genome
        k_e, k_t = m.k_e, m.k_t
        w, h = self.width(), self.height()
        base_r = min(w, h) * 0.13 * self.zoom
        # the shards hold their size (state scale only) — "breathing" is the
        # AURA gently expanding/contracting, applied to the glow below, not a
        # scaling of the solid (a scaling shape reads as zooming, not breath)
        r = base_r * m.cur["scale"]
        pulse = m.breath()   # ~1 ± small; drives the glow halo

        think = m.cur["think_mix"]
        fm = m.cur["face_mix"]
        cx = w / 2.0
        cy = h / 2.0 + 2.0 * math.sin(m.t * 0.7) * (1.0 - 0.7 * fm)
        if think > 0.05:
            cx += think * r * 0.06 * math.sin(m.t * 0.53 + m.drift_seed)
            cy += think * r * 0.04 * math.sin(m.t * 0.71 + m.drift_seed * 2)
        if m.shake_t < 0.6:
            cx += 7.0 * math.exp(-m.shake_t * 7.0) * math.sin(m.shake_t * 42.0)

        tint = tuple(int(q) for q in m.cur["tint"])
        tint_mix = m.cur["tint_mix"]
        disp = _lerp_rgb(m.palette[0], tint, tint_mix)
        blink = m.blink()
        bloom = m.bloom()
        env = m.speech_env() if m.state == AvatarState.SPEAKING else 0.0

        p.setPen(Qt.NoPen)
        p.setCompositionMode(QPainter.CompositionMode_Plus)

        # breathing lives here: the halo radius (and, softly, its brightness)
        # pulse with `pulse`, amplified so the aura's breath is visible while
        # the crystal stays a fixed solid
        glow_r = min(r * (2.4 + 0.5 * env) * m.cur["glow"] * bloom * (1.0 + 2.2 * (pulse - 1.0)),
                     min(w, h) * 0.62)
        halo = QRadialGradient(QPointF(cx, cy), glow_r)
        # the aura is NOT dimmed by the blink — a blink dims the body, the
        # glow holds steady (reads better, and keeps the soft dark gradient
        # stable frame-to-frame so lossy encoders don't block it)
        halo_alpha = min(115, int(70 * m.cur["glow"] * bloom * (1.0 + 1.3 * (pulse - 1.0))))
        halo.setColorAt(0.0, QColor(*disp, halo_alpha))
        halo.setColorAt(1.0, QColor(*disp, 0))
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        for birth in m.rings:
            prog = (m.t - birth) / 1.2
            if not 0.0 <= prog <= 1.0:
                continue
            ring_r = r * (1.1 + 2.3 * prog)
            pen = QPen(QColor(*disp, int(150 * (1.0 - prog) ** 1.5)))
            pen.setWidthF(1.5 + 2.5 * (1.0 - prog))
            p.setBrush(Qt.NoBrush)
            p.setPen(pen)
            p.drawEllipse(QPointF(cx, cy), ring_r, ring_r)
            p.setPen(Qt.NoPen)

        # ---- the shard cluster, back to front
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        bright = m.cur["core_dim"] * blink * min(bloom, 1.4) * (1.0 + 0.10 * env)
        breakup_pulse = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(m.t * 1.15 * k_t)) ** 1.8
        explode = 0.26 * think * breakup_pulse * k_e if m.thinking_style == "breakup" else 0.0
        shimmer = think * k_e if m.thinking_style == "shimmer" else 0.0
        ax = m.ax

        hull_pts: list[tuple[float, float]] = []
        placed = []
        for sh in m.cluster:
            off = geometry.rotate(sh["pos"], ax, m.ay)
            placed.append((off[2], cx + off[0] * r, cy - off[1] * r, sh))
        ordered = sorted(placed, key=lambda e: e[0])
        # glassy transparency is an intrinsic property of the see-through
        # materials (crystal/glass), scaled by the genome's translucency — not
        # a user toggle. Stone/metal are always opaque.
        glassy = MATERIALS[g.material] in _GLASSY_MATERIALS
        shard_op = (1.0 - 0.55 * g.translucency) if glassy else 1.0
        for si, (oz, sx, sy, sh) in enumerate(ordered):
            depth = si / (len(ordered) - 1) if len(ordered) > 1 else 1.0
            args = (sh["mesh"], ax + sh["dax"], m.ay + sh["day"] + sh["drift"],
                    sx, sy, r * sh["size"], bright * (0.84 + 0.16 * depth),
                    tint_mix, tint, explode, shimmer, hull_pts)
            if shard_op < 0.99:  # glassy: per-shard translucent composite
                layer = QImage(self.size(), QImage.Format_ARGB32)
                layer.fill(QColor(0, 0, 0, 0))
                lp = QPainter(layer)
                lp.setRenderHint(QPainter.Antialiasing)
                sh["proj"] = self._draw_solid(lp, *args)
                lp.end()
                p.setOpacity(shard_op)
                p.drawImage(0, 0, layer)
                p.setOpacity(1.0)
            else:
                sh["proj"] = self._draw_solid(p, *args)

        p.setCompositionMode(QPainter.CompositionMode_Plus)

        # thinking "glow": light building inside each shard, clipped to its
        # own projected silhouette so it never leaks out
        if think > 0.02 and m.thinking_style == "glow":
            glow_rgb = _lerp_rgb(disp, (255, 255, 255), 0.40)
            for si, (oz, sx, sy, sh) in enumerate(placed):
                proj = sh.get("proj")
                if not proj or len(proj) < 3:
                    continue
                shell = geometry.convex_hull(proj)
                if len(shell) < 3:
                    continue
                path = QPainterPath()
                path.moveTo(*shell[0])
                for q in shell[1:]:
                    path.lineTo(*q)
                path.closeSubpath()
                grad_r = max(math.hypot(qx - sx, qy - sy) for qx, qy in shell) or 1.0
                pulse = (0.5 + 0.5 * math.sin(m.t * 3.6 * k_t + si * 0.7)) ** 1.5
                inner = QRadialGradient(QPointF(sx, sy), grad_r)
                inner.setColorAt(0.0, QColor(*glow_rgb, int(175 * k_e * think * pulse)))
                inner.setColorAt(0.75, QColor(*glow_rgb, int(60 * k_e * think * pulse)))
                inner.setColorAt(1.0, QColor(*glow_rgb, 0))
                p.save()
                p.setClipPath(path)
                p.setBrush(inner)
                p.drawEllipse(QPointF(sx, sy), grad_r, grad_r)
                p.restore()
            p.setBrush(Qt.NoBrush)

        # ---- the ring: a clean circle enclosing the cluster; listening shows
        # inward ripples, speaking shows a circular audio waveform
        trace = m.cur["trace_mix"]
        if trace > 0.02 and hull_pts:
            target_r = max(math.hypot(qx - cx, qy - cy) for qx, qy in hull_pts) + r * 0.30
            if self._ring_r <= 1.0:
                self._ring_r = target_r
            self._ring_r += (target_r - self._ring_r) * 0.06  # calm, no jitter
            ring = self._ring_r

            if m.state == AvatarState.SPEAKING:
                self._draw_speaking_wave(p, cx, cy, ring, r, disp, trace, env, k_t, k_e, g)
            else:
                base_pen = QPen(QColor(*disp, int(45 * trace)))
                base_pen.setWidthF(1.2)
                p.setPen(base_pen)
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(cx, cy), ring, ring)
                self._draw_trace_activity(p, cx, cy, ring, disp, trace, k_t)
            p.setPen(Qt.NoPen)

        self._paint_orbiter(p, cx, cy, r, disp, think, k_t, g, placed)

    def _draw_speaking_wave(self, p, cx, cy, ring, r, disp, trace, env, k_t, k_e, g):
        m = self.model
        n_wave = 220
        envs = []
        if m.spectrum:
            nb = len(m.spectrum)
            for i in range(n_wave):
                pos = i * nb / n_wave
                lo = int(pos) % nb
                frac = pos - int(pos)
                envs.append(m.spectrum[lo] * (1 - frac) + m.spectrum[(lo + 1) % nb] * frac)
        else:
            for i in range(n_wave):
                b = m.bins[i * len(m.bins) // n_wave]
                osc = abs(math.sin(m.t * b["rate"] * k_t + b["phase"]))
                gate = (0.5 + 0.5 * math.sin(m.t * b["rate"] * 0.31 + b["phase"] * 2.3)) ** 2
                envs.append(env * b["gain"] * (0.25 + 0.75 * osc) * gate)
        loud = m.amplitude if m.amplitude is not None else env
        step = int(m.t * 30.0)
        grit_amt = 0.35 + 0.85 * g.sharp
        pts = []
        for i in range(n_wave):
            th = math.tau * i / n_wave
            carrier = math.sin(22.0 * th + m.t * 12.0 * k_t)
            grit = math.sin(i * 12.9898 + step * 78.233) * 43758.5453
            carrier += ((grit - math.floor(grit)) * 2.0 - 1.0) * grit_amt
            rr = ring + r * 0.34 * k_e * envs[i] * carrier
            if m.voice_style == "glitch":
                block = math.sin((i // 8) * 91.7 + step * 57.31) * 24634.63
                block -= math.floor(block)
                if block > 0.88:
                    rr += r * 0.14 * (block - 0.88) / 0.12 * (0.3 + loud) * (0.5 + g.sharp)
                elif block < 0.07:
                    rr = ring
            pts.append(QPointF(cx + rr * math.cos(th), cy + rr * math.sin(th)))
        pen = QPen(QColor(*disp, int((45 + 130 * min(1.0, loud * 1.3)) * trace)))
        pen.setWidthF(1.1 + 0.6 * loud)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(pts + [pts[0]])

    def _draw_trace_activity(self, p, cx, cy, ring, disp, trace, k_t):
        """Listening: gentle rings drifting INWARD — arriving sound, subtle."""
        m = self.model
        p.setBrush(Qt.NoBrush)
        for j in range(2):
            prog = (m.t * 0.35 * k_t + j / 2.0) % 1.0
            rr = ring * (1.18 - 0.20 * prog)
            pen = QPen(QColor(*disp, int(55 * math.sin(math.pi * prog) * trace)))
            pen.setWidthF(1.3)
            p.setPen(pen)
            p.drawEllipse(QPointF(cx, cy), rr, rr)

    def _paint_orbiter(self, p, cx, cy, r, disp, think, k_t, g, placed):
        """Thinking "orbiter": a sparkle around every shard plus one around the
        whole cluster — ribbon trail + shed twinkles."""
        m = self.model
        if think <= 0.02 or m.thinking_style != "orbiter":
            return
        k_e = m.k_e
        spark_rgb = _lerp_rgb(disp, (255, 255, 255), 0.55)

        orbits = []
        for oz, sx, sy, sh in placed:
            rad = r * sh["size"] * sh["mesh"]["rad"]
            orbits.append(dict(cx=sx, cy=sy, rx=rad * 1.45, ry=rad * 0.55,
                               tilt=sh["dax"] * 0.35, phase=sh["day"],
                               speed=2.0 * (1.0 + sh["selfr"])))
        orbits.append(dict(cx=cx, cy=cy, rx=r * 1.75, ry=r * 0.70,
                           tilt=0.45, phase=1.7, speed=1.4))

        for ob in orbits:
            tc, ts = math.cos(ob["tilt"]), math.sin(ob["tilt"])

            def orbit_pos(tau, ob=ob, tc=tc, ts=ts):
                ox = math.cos(tau) * ob["rx"]
                oy = math.sin(tau) * ob["ry"]
                return ob["cx"] + ox * tc - oy * ts, ob["cy"] + ox * ts + oy * tc

            head_tau = m.t * ob["speed"] * k_t + ob["phase"]
            scale = min(1.0, ob["rx"] / (r * 1.2))

            prev = None
            n_trail = 18
            for k in range(n_trail):
                q = orbit_pos(head_tau - k * 0.055)
                if prev is not None:
                    fade = 1.0 - k / n_trail
                    pen = QPen(QColor(*spark_rgb, int(140 * fade ** 1.6 * think)))
                    pen.setWidthF((0.4 + 2.2 * fade) * scale)
                    p.setPen(pen)
                    p.drawLine(QPointF(*prev), QPointF(*q))
                prev = q
            p.setPen(Qt.NoPen)

            for j in range(3):
                qx, qy = orbit_pos(head_tau - 0.25 - j * 0.22)
                tw = abs(math.sin(m.t * 9.0 + j * 2.4 + ob["phase"])) * (1.0 - j / 3.5)
                if tw < 0.15:
                    continue
                sz = (0.8 + 2.2 * tw) * scale
                pen = QPen(QColor(*spark_rgb, int(180 * tw * think)))
                pen.setWidthF(1.0)
                p.setPen(pen)
                p.drawLine(QPointF(qx - sz, qy), QPointF(qx + sz, qy))
                p.drawLine(QPointF(qx, qy - sz), QPointF(qx, qy + sz))
            p.setPen(Qt.NoPen)

            hxp, hyp = orbit_pos(head_tau)
            core_r = 6.0 * (0.6 + 0.4 * scale)
            core = QRadialGradient(QPointF(hxp, hyp), core_r)
            core.setColorAt(0.0, QColor(255, 255, 255, int(225 * think)))
            core.setColorAt(0.4, QColor(*spark_rgb, int(150 * think)))
            core.setColorAt(1.0, QColor(*spark_rgb, 0))
            p.setBrush(core)
            p.drawEllipse(QPointF(hxp, hyp), core_r, core_r)
            ray = ((4.5 + 2.0 * math.sin(m.t * 7.0 + ob["phase"]))
                   * (0.8 + 0.5 * k_e) * (0.6 + 0.4 * scale))
            rot = m.t * 3.0 + ob["phase"]
            pen = QPen(QColor(255, 255, 255, int(190 * think)))
            pen.setWidthF(1.1)
            p.setPen(pen)
            for base_ang in (rot, rot + math.pi / 2):
                dxr, dyr = math.cos(base_ang) * ray, math.sin(base_ang) * ray
                p.drawLine(QPointF(hxp - dxr, hyp - dyr), QPointF(hxp + dxr, hyp + dyr))
            p.setPen(Qt.NoPen)
