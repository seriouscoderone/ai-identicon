"""Clipboard rasterization test (Qt — skipped where PySide6 isn't installed,
e.g. the Qt-free CI job)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from ai_identicon.genome import Genome  # noqa: E402
from ai_identicon import clipboard  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_render_png_is_nonblank_and_sized():
    _app()
    img = clipboard.render_png(Genome.from_seed("alice"), size=128, variant="color")
    assert not img.isNull()
    assert img.width() == 128 and img.height() == 128
    # the avatar leaves opaque pixels on the transparent field
    opaque = sum(1 for y in range(0, 128, 6) for x in range(0, 128, 6)
                 if img.pixelColor(x, y).alpha() > 10)
    assert opaque > 0


def test_render_png_background_fills():
    _app()
    img = clipboard.render_png(Genome.from_seed("alice"), size=64, background="#101418")
    # a solid background => every pixel opaque
    assert img.pixelColor(2, 2).alpha() == 255
