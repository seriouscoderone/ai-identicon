#!/usr/bin/env python
"""Render the README's gallery screenshot (docs/gallery.png).

The original was captured by hand, which is why it went stale the moment the
gallery grew a control. This renders the same window programmatically so it
can be refreshed whenever the UI changes.

Deliberately NOT run under QT_QPA_PLATFORM=offscreen, unlike the other render
scripts here: the offscreen backend substitutes fonts (it has no "Sans Serif"),
so labels and buttons would not look like what a user actually sees. That means
this briefly flashes a real window on screen while it grabs — the cost of the
shot being honest.

It captures the widget's own content, so there is no window title bar or drop
shadow. If you want the macOS chrome, take the screenshot by hand instead.

Needs the Qt extra:  pip install -e ".[qt]"
Run from the repo root:  python scripts/render_gallery_shot.py
"""

from __future__ import annotations

import os
import sys
import time

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ai_identicon.gallery import Demo          # noqa: E402
from ai_identicon.model import AvatarState     # noqa: E402

SEED = "bmev5p5akc"
WINDOW = (980, 660)    # a floor; the genome panel makes the real window taller
ORB_PX = 480           # fill the left column — the 360 default leaves it empty
SETTLE_SECONDS = 2.0   # let the cluster settle and the orb reach a good pose


def main() -> int:
    app = QApplication(sys.argv[:1])
    demo = Demo(SEED)
    demo.resize(*WINDOW)
    demo.size_slider.setValue(ORB_PX)
    demo.show()
    # the seed box takes focus on open and its caret blinks into the shot
    demo.seed_edit.clearFocus()

    # The orb animates off its own QTimer, so pump the event loop in real time
    # rather than stepping the model by hand — this shot should be the app as
    # it actually runs, not a synthetic frame.
    demo._go(AvatarState.IDLE)
    end = time.monotonic() + SETTLE_SECONDS
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)

    out = os.path.join(os.path.dirname(__file__), "..", "docs", "gallery.png")
    shot = demo.grab()
    shot.save(out, "PNG")
    print(f"  {os.path.relpath(out)}  {shot.width()}x{shot.height()}  "
          f"{os.path.getsize(out) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
