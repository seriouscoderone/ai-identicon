#!/usr/bin/env python
"""Render the README's animated idle loops (hero + the sixteen faces).

Each loop is a seamless single 360° revolution in which breathing completes a
whole number of cycles and one blink plays out fully — so it loops perfectly —
and the avatar's *personality* shows: tempo sets the playback speed, expressive-
ness sets breathing depth (and thus the glow pulse), and the seed picks the
spin direction. That variety is the point: without it every orb feels the same.

Needs the Qt extra plus Pillow:  pip install -e .[qt] pillow
Run from the repo root:          python scripts/render_readme_loops.py
"""

from __future__ import annotations

import io
import math
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray
from PySide6.QtWidgets import QApplication
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ai_identicon.genome import Genome                # noqa: E402
from ai_identicon.widget import PresenceWidget        # noqa: E402
from ai_identicon.model import AvatarState            # noqa: E402

NAMES = ["James", "Mary", "Michael", "Jennifer", "William", "Elizabeth", "David",
         "Sarah", "John", "Jessica", "Robert", "Emily", "Joseph", "Emma", "Daniel", "Olivia"]
BREATHS_PER_REV = 4        # whole cycles per revolution → seamless
BASE_FPS = 10              # smooth enough for such a slow rotation
YAW_RATE = 0.23            # live idle yaw: dθ/dt = YAW_RATE * k_t  (rad/s)


def render_loop(seed: str, path: str, size: int, zoom: float, quality: int = 86):
    """One seamless revolution at the LIVE idle speed. Time-based: a full turn
    takes 2π/(YAW_RATE·k_t) seconds (≈27s at mid tempo, faster/slower by the
    avatar's tempo), sampled at BASE_FPS with a short dense burst so the blink
    stays quick even though the rotation is slow. Breathing = aura pulse."""
    w = PresenceWidget(Genome.from_seed(seed))
    w._timer.stop()
    w.setFixedSize(size, size)
    w.zoom = zoom
    g = w.genome
    w.set_state(AvatarState.IDLE)
    w.model.next_blink = 1e9
    for _ in range(45):            # settle cluster + smoothing, then freeze
        w.model.advance(1 / 30)
    w.model.ax_tumble = 0.0

    direction = 1.0 if (g.mesh_seed % 2 == 0) else -1.0   # per-seed spin sense
    a_breath = 0.025 + 0.06 * g.express                   # expressive → aura depth
    T = 2 * math.pi / (YAW_RATE * w.model.k_t)            # sec/rev; tempo → speed
    t_blink = T * 0.5

    # frame timeline: a base grid, plus a dense ~0.24s burst around the blink
    times = {round(i / BASE_FPS, 4) for i in range(int(T * BASE_FPS))}
    times |= {round(t_blink + j * 0.03, 4) for j in range(-4, 5)}
    times = sorted(t for t in times if 0.0 <= t < T)

    imgs, durs = [], []
    for idx, t in enumerate(times):
        nxt = times[idx + 1] if idx + 1 < len(times) else T
        durs.append(max(20, round((nxt - t) * 1000)))
        phi = t / T
        w.model.t = 0.0                                   # kill ambient sway/bob
        w.model.ay = direction * 2 * math.pi * phi        # one full revolution
        w.model.breath_override = 1.0 + a_breath * math.sin(2 * math.pi * BREATHS_PER_REV * phi)
        w.model.blink_override = 1.0 - 0.5 * math.exp(-((t - t_blink) / 0.06) ** 2)  # ~0.15s blink
        q = w.grab().toImage()
        ba = QByteArray(); buf = QBuffer(ba); buf.open(QBuffer.WriteOnly)
        q.save(buf, "PNG"); buf.close()
        imgs.append(Image.open(io.BytesIO(bytes(ba))).convert("RGB"))

    imgs[0].save(path, save_all=True, append_images=imgs[1:],
                 duration=durs, loop=0, quality=quality, method=6)
    return len(imgs), round(T, 1), os.path.getsize(path)


def main():
    QApplication(sys.argv[:1])
    root = os.path.join(os.path.dirname(__file__), "..", "docs")
    n, T, sz = render_loop("bmev5p5akc", os.path.join(root, "hero.webp"), 380, zoom=1.22)
    print(f"hero: {n} frames, {T}s/rev, {sz // 1024} KB")
    total = 0
    for name in NAMES:
        n, T, sz = render_loop(name, os.path.join(root, "faces", f"{name}.webp"), 220, zoom=1.35)
        total += sz
        print(f"  {name:10} {n}f  {T}s/rev  {sz // 1024}KB")
    print(f"16 faces: {total // 1024} KB total (avg {total // 1024 // 16} KB)")


if __name__ == "__main__":
    main()
