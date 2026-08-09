#!/usr/bin/env python
"""Render the README's gallery screenshot (docs/gallery.png).

The original was captured by hand, which is why it went stale the moment the
gallery grew a control. This renders the same window programmatically so it
can be refreshed whenever the UI changes.

Deliberately NOT run under QT_QPA_PLATFORM=offscreen, unlike the other render
scripts here: the offscreen backend substitutes fonts (it has no "Sans Serif"),
so labels and buttons would not look like what a user actually sees. That means
this briefly shows a real window on screen while it captures — the cost of the
shot being honest.

On macOS it tries to capture the real window through `screencapture`, so the
shot can keep the title bar and drop shadow that make it read as a running app
rather than a mockup. That needs Screen Recording permission for whatever runs
this, and macOS does not prompt for command-line tools — the terminal or IDE
has to be added by hand under System Settings > Privacy & Security > Screen
Recording, then restarted. Without it the capture is refused outright ("could
not create image from window") and this falls back to a chrome-less
`QWidget.grab()`, saying so rather than failing quietly.

Needs the Qt extra:  pip install -e ".[qt]"
Run from the repo root:  python scripts/render_gallery_shot.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from PIL import Image
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ai_identicon.gallery import Demo          # noqa: E402
from ai_identicon.model import AvatarState     # noqa: E402

SEED = "bmev5p5akc"
WINDOW = (980, 660)    # a floor; the genome panel makes the real window taller
ORB_PX = 480           # fill the left column — the 360 default leaves it empty
SETTLE_SECONDS = 2.0   # let the cluster settle and the orb reach a good pose

# NB: zoom is deliberately left at the widget's own default. An earlier version
# of this script set 1.30 to fill the frame, which made the README shot flatter
# the app — nobody running it would see that. The default itself was raised
# instead, to the largest value measured not to clip any ordinary avatar's
# listening ring.


def _window_id(title: str) -> int | None:
    """The CGWindowID of our own on-screen window, or None."""
    try:
        import Quartz
    except ImportError:
        return None
    mine = os.getpid()
    for w in Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID):
        if w.get("kCGWindowOwnerPID") == mine and w.get("kCGWindowName") == title:
            return w["kCGWindowNumber"]
    return None


def _capture_with_chrome(win_id: int, out: str) -> str | None:
    """screencapture the window itself. Returns None on success, else why not.

    Denial here is a permission problem, not a bug: macOS refuses window
    content to anything lacking Screen Recording, and it does not prompt for
    command-line tools — the terminal (or IDE) running this has to be added by
    hand under System Settings > Privacy & Security > Screen Recording, and
    then restarted.
    """
    p = subprocess.run(["screencapture", "-x", f"-l{win_id}", out],
                       capture_output=True)
    if p.returncode != 0:
        return (p.stderr.decode().strip() or f"screencapture exited {p.returncode}")
    if not os.path.exists(out):
        return "screencapture wrote nothing"
    return None


def main() -> int:
    app = QApplication(sys.argv[:1])
    demo = Demo(SEED)
    demo.resize(*WINDOW)
    demo.size_slider.setValue(ORB_PX)
    demo.show()
    demo.raise_()
    demo.activateWindow()
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

    win_id = _window_id(demo.windowTitle()) if sys.platform == "darwin" else None
    why = "not macOS" if win_id is None else _capture_with_chrome(win_id, out)
    if why is None:
        how = "real window via screencapture (title bar + shadow)"
    else:
        how = "chrome-less QWidget.grab()"
        demo.grab().save(out, "PNG")
        print(f"  note: window capture unavailable — {why}\n"
              "        (grant Screen Recording to the terminal running this,"
              " then restart it)")

    with Image.open(out) as im:
        dims = im.size
    print(f"  {os.path.relpath(out)}  {dims[0]}x{dims[1]}  "
          f"{os.path.getsize(out) // 1024} KB  — {how}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
