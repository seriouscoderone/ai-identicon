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
BREATHS_PER_REV = 4
FRAMES = 96


def render_loop(seed: str, path: str, size: int, zoom: float, quality: int = 85):
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
    a_breath = 0.025 + 0.06 * g.express                   # expressive → depth
    # tempo → playback speed: higher tempo, shorter frame duration (spins/breathes faster)
    frame_ms = max(30, min(80, round(52.0 / w.model.k_t)))

    imgs = []
    for k in range(FRAMES):
        phi = k / FRAMES
        w.model.t = 0.0                                   # kill ambient sway/bob
        w.model.ay = direction * 2 * math.pi * phi        # one full revolution
        w.model.breath_override = 1.0 + a_breath * math.sin(2 * math.pi * BREATHS_PER_REV * phi)
        w.model.blink_override = 1.0 - 0.5 * math.exp(-((phi - 0.5) / 0.035) ** 2)
        q = w.grab().toImage()
        ba = QByteArray(); buf = QBuffer(ba); buf.open(QBuffer.WriteOnly)
        q.save(buf, "PNG"); buf.close()
        imgs.append(Image.open(io.BytesIO(bytes(ba))).convert("RGB"))

    imgs[0].save(path, save_all=True, append_images=imgs[1:],
                 duration=frame_ms, loop=0, quality=quality, method=6)
    return frame_ms, os.path.getsize(path)


def main():
    QApplication(sys.argv[:1])
    root = os.path.join(os.path.dirname(__file__), "..", "docs")
    ms, sz = render_loop("bmev5p5akc", os.path.join(root, "hero.webp"), 380, zoom=1.22)
    print(f"hero: {ms}ms/frame, {sz // 1024} KB")
    total = 0
    for name in NAMES:
        ms, sz = render_loop(name, os.path.join(root, "faces", f"{name}.webp"), 220, zoom=1.35)
        total += sz
        print(f"  {name:10} {ms}ms/frame")
    print(f"16 faces: {total // 1024} KB total (avg {total // 1024 // 16} KB)")


if __name__ == "__main__":
    main()
