#!/usr/bin/env python
"""Print a stable render hash per avatar state — the equivalence harness.

A refactor meant to leave the picture alone (splitting a scalar, renaming a
channel) is verified by running this before and after and diffing the output.
The model is driven with a fixed timestep and sampled at fixed times. The
blink schedule is frozen (`next_blink = 1e9`); saccades are already
deterministic — seeded from `genome.mesh_seed` — and stay stable here because
freezing blinks stops anything else from consuming that RNG stream. So the
hashes depend only on the rendering code.

Needs the Qt extra:  pip install -e ".[qt]"
Run:                 python scripts/state_render_hashes.py
"""

from __future__ import annotations

import hashlib
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ai_identicon.genome import Genome              # noqa: E402
from ai_identicon.model import AvatarState, TRANSIENT  # noqa: E402
from ai_identicon.widget import PresenceWidget      # noqa: E402

SEEDS = ("bmev5p5akc", "James")   # two materials, two personalities
HOLDING_SAMPLES = (0.75, 1.5, 3.0)  # seconds after entering the state
TRANSIENT_FRACS = (0.2, 0.5, 0.85)  # fractions of state duration for transients
SIZE = 240
DT = 1 / 60


def state_hash(seed: str, state: AvatarState) -> str:
    w = PresenceWidget(Genome.from_seed(seed))
    w._timer.stop()               # drive the clock by hand, not by wall time
    w.setFixedSize(SIZE, SIZE)
    w.model.next_blink = 1e9      # blinks are RNG-scheduled; freeze them out
    w.set_state(state)
    # For transient states, sample at fractions of their duration; for holding
    # states, use fixed absolute times. This ensures all samples land while the
    # state's specific visual effects (bloom, ripple_mix/wave_mix/comet_mix)
    # are active.
    if state in TRANSIENT:
        samples = [TRANSIENT[state] * frac for frac in TRANSIENT_FRACS]
    else:
        samples = HOLDING_SAMPLES
    digest = hashlib.sha256()
    t = 0.0
    for sample in samples:
        while t < sample - 1e-9:
            w.model.advance(DT)
            t += DT
        img = w.grab().toImage()
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QBuffer.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        digest.update(bytes(ba))
    return digest.hexdigest()[:16]


def main() -> int:
    QApplication(sys.argv[:1])
    for seed in SEEDS:
        for state in AvatarState:
            print(f"{seed:12} {state.value:10} {state_hash(seed, state)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
