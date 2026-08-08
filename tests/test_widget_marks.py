"""The live renderer's per-state ring marks (Qt — skipped in the Qt-free CI job).

These are smoke-and-difference checks, not pixel goldens: they prove each state
actually draws its own mark and that the comet survives small embed sizes. The
real judgement is visual, via the gallery's Size slider.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ai_identicon.genome import Genome  # noqa: E402
from ai_identicon.model import AvatarState  # noqa: E402
from ai_identicon.widget import PresenceWidget  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _frame(state, size=240, secs=1.0, seed="bmev5p5akc"):
    _app()
    w = PresenceWidget(Genome.from_seed(seed))
    w._timer.stop()
    w.setFixedSize(size, size)
    w.model.next_blink = 1e9
    w.set_state(state)
    for _ in range(int(secs * 60)):
        w.model.advance(1 / 60)
    img = w.grab().toImage()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def test_streaming_draws_its_own_mark():
    streaming = _frame(AvatarState.STREAMING)
    assert streaming != _frame(AvatarState.IDLE)
    assert streaming != _frame(AvatarState.LISTENING)
    assert streaming != _frame(AvatarState.SPEAKING)


def test_streaming_comet_moves():
    # a comet that does not travel is a dot; two samples a third of a lap apart
    # must differ
    assert _frame(AvatarState.STREAMING, secs=1.0) != _frame(AvatarState.STREAMING, secs=1.4)


@pytest.mark.parametrize("size", [40, 120, 480])
def test_streaming_comet_draws_at_every_embed_size(size):
    # the comet is authored in r-units, so at EVERY embed size it must put light
    # on screen that idle does not — a render that merely completes is not enough
    assert _frame(AvatarState.STREAMING, size=size) != _frame(AvatarState.IDLE, size=size)
