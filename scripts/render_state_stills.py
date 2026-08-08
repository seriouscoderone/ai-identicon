#!/usr/bin/env python
"""Render the README's per-state stills — one PNG per AvatarState.

The seven originals were hand-captured, which made an 8th state a manual chore
and left the set inconsistent. This renders all of them offscreen from one seed
at one moment per state, mirroring scripts/render_readme_loops.py.

Each state is sampled at the moment it reads most clearly: transients early,
while the flare is still up; holding states once settled.

Needs the Qt extra:  pip install -e ".[qt]"
Run from the repo root:  python scripts/render_state_stills.py
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ai_identicon.genome import Genome              # noqa: E402
from ai_identicon.model import AvatarState          # noqa: E402
from ai_identicon.widget import PresenceWidget      # noqa: E402

SEED = "bmev5p5akc"
SIZE = 380
ZOOM = 1.22
DT = 1 / 60

# seconds after entering the state — transients are caught mid-flare, holding
# states after they settle
SAMPLE_AT = {
    AvatarState.IDLE: 2.0,
    AvatarState.LISTENING: 2.0,
    AvatarState.THINKING: 2.5,
    AvatarState.SPEAKING: 2.0,
    AvatarState.STREAMING: 1.2,
    AvatarState.NOTIFY: 0.30,
    AvatarState.SUCCESS: 0.28,
    AvatarState.ERROR: 0.10,
}


def render(state: AvatarState, path: str) -> int:
    w = PresenceWidget(Genome.from_seed(SEED))
    w._timer.stop()
    w.setFixedSize(SIZE, SIZE)
    w.zoom = ZOOM
    w.model.next_blink = 1e9      # never blink in a still
    w.set_state(state)
    t = 0.0
    while t < SAMPLE_AT[state]:
        w.model.advance(DT)
        t += DT
    w.grab().save(path, "PNG")
    return os.path.getsize(path)


def main() -> int:
    missing = set(AvatarState) - set(SAMPLE_AT)
    assert not missing, f"no SAMPLE_AT for {sorted(s.name for s in missing)}"
    QApplication(sys.argv[:1])
    out = os.path.join(os.path.dirname(__file__), "..", "docs", "states")
    os.makedirs(out, exist_ok=True)
    for state in AvatarState:
        path = os.path.join(out, f"{state.value}.png")
        print(f"  {state.value:10} {render(state, path) // 1024:>4} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
