"""The live renderer's per-state ring marks (Qt — skipped in the Qt-free CI job).

These are smoke-and-difference checks, not pixel goldens: they prove each state
actually draws its own mark and that the comet survives small embed sizes. The
real judgement is visual, via the gallery's Size slider.
"""

from __future__ import annotations

import math
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


def _settled_streaming(seed="bmev5p5akc", size=240, settle_secs=1.0):
    """A STREAMING widget whose ring radius and comet_mix have converged —
    long enough that `w._ring_r` (the ring block's own smoothed radius) is a
    stable orbit to sample, matching test_state_coverage's SETTLE window."""
    _app()
    w = PresenceWidget(Genome.from_seed(seed))
    w._timer.stop()
    w.setFixedSize(size, size)
    w.model.next_blink = 1e9
    w.set_state(AvatarState.STREAMING)
    for _ in range(int(settle_secs * 60)):
        w.model.advance(1 / 60)
    w.grab()  # force a paintEvent so _ring_r is populated before we read it
    return w


# The ambient aura (breath-driven per v0.7.0, plus rasterization/antialiasing
# of the shard silhouette) leaves faint, angle-dependent noise at the ring
# radius even with no comet at all — empirically R+G+B sums of 77-81 on this
# seed/size. The comet's core is near-white at full alpha — empirically 765
# (max possible) at its brightest sample. PEAK_LUM_FLOOR sits an order of
# magnitude above the noise ceiling and comfortably below the real peak, so a
# missing/disabled comet fails on a clear, deterministic "no bright peak"
# assertion instead of on a coincidental angle that noise happened to produce.
PEAK_LUM_FLOOR = 250


def _peak_ring_angle(w):
    """The (angle in radians, brightness) of the brightest pixel on the ring
    circle — where the comet head sits. The ring circle itself is never drawn
    (only the comet is), so a peak clearing PEAK_LUM_FLOOR here IS the comet."""
    img = w.grab().toImage()
    cx, cy, ring = w.width() / 2.0, w.height() / 2.0, w._ring_r
    best_angle, best_lum = 0.0, -1
    for deg in range(360):
        rad = math.radians(deg)
        x = int(round(cx + ring * math.cos(rad)))
        y = int(round(cy + ring * math.sin(rad)))
        if not (0 <= x < img.width() and 0 <= y < img.height()):
            continue
        c = img.pixelColor(x, y)
        lum = c.red() + c.green() + c.blue()
        if lum > best_lum:
            best_lum, best_angle = lum, rad
    return best_angle, best_lum


def test_streaming_comet_moves():
    # A whole-frame diff (the original shape of this test) passes even with
    # no comet at all: face-locked yaw still leaves a ~30% idle bob
    # (widget.py's `cy = h/2 + 2*sin(t*0.7)*(1-0.7*fm)`) and the shard cluster
    # keeps drifting, so any two time-separated STREAMING frames already
    # differ for reasons that have nothing to do with a ring mark. Instead,
    # track the angular position of the brightest point on the (undrawn)
    # ring circle — that peak only exists, and only moves, because of the
    # comet — and require it to have advanced a plausible slice of a lap.
    w = _settled_streaming()
    angle_a, lum_a = _peak_ring_angle(w)
    t_a = w.model.t

    dt = 0.4
    for _ in range(int(dt * 60)):
        w.model.advance(1 / 60)
    angle_b, lum_b = _peak_ring_angle(w)
    t_b = w.model.t

    # a missing/disabled comet leaves only ambient noise on the ring, and its
    # "peak" is not meaningfully brighter than the rest of the circle
    assert lum_a > PEAK_LUM_FLOOR, f"no bright peak on the ring at t={t_a:.2f} (lum={lum_a})"
    assert lum_b > PEAK_LUM_FLOOR, f"no bright peak on the ring at t={t_b:.2f} (lum={lum_b})"

    lap_frac = ((angle_b - angle_a) / math.tau) % 1.0

    # a static dot (or a missing comet, where every ring sample ties on
    # background and the "peak" never moves) folds to ~0 of a lap
    assert lap_frac > 0.05, f"ring peak barely moved: {lap_frac:.3f} of a lap"
    # a peak wrapping almost all the way around reads the same as one that
    # barely moved backwards — bound it well short of a full lap too
    assert lap_frac < 0.95, f"ring peak advance folds to near-zero: {lap_frac:.3f} of a lap"

    # roughly the speed _draw_stream_comet's `head` predicts (0.75 rev/s,
    # scaled by tempo) — a loose band, wide enough to absorb the ~1 degree
    # of quantization in a 360-sample angle scan, but tight enough to catch
    # a speed that is wildly wrong (e.g. off by 2x or more)
    expected = (0.75 * w.model.k_t * (t_b - t_a)) % 1.0
    assert abs(lap_frac - expected) < 0.25, (
        f"comet advanced {lap_frac:.3f} of a lap, expected ~{expected:.3f}")


@pytest.mark.parametrize("size", [40, 120, 480])
def test_streaming_comet_draws_at_every_embed_size(size):
    # the comet is authored in r-units, so at EVERY embed size it must put light
    # on screen that idle does not — a render that merely completes is not enough
    assert _frame(AvatarState.STREAMING, size=size) != _frame(AvatarState.IDLE, size=size)
