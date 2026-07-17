"""Tests for the headless avatar behavior model (pure, no Qt).

Covers state transitions, transient auto-return, sound cues, determinism of
the seeded schedule, target smoothing, gaze/face-lock, and that fragmentation
reaches the resting pose through the model (not just raw geometry).

Run: .venv/bin/python -m pytest tests/unit/avatar -q --import-mode=importlib
"""

from __future__ import annotations

import math

from ai_identicon.genome import Genome
from ai_identicon.model import AvatarModel, AvatarState, TRANSIENT


def _model(seed="bmev5p5akc", **ov):
    g = Genome.from_seed(seed)
    if ov:
        g = g.with_overrides(**ov)
    return AvatarModel(g)


def _run(m, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt)):
        m.advance(dt)


# ------------------------------------------------------------- state machine

def test_starts_idle():
    assert _model().state == AvatarState.IDLE


def test_set_state_switches_and_resets_clock():
    m = _model()
    _run(m, 1.0)
    m.set_state(AvatarState.THINKING)
    assert m.state == AvatarState.THINKING
    assert m.state_t == 0.0


def test_transients_return_to_idle():
    for st in (AvatarState.NOTIFY, AvatarState.SUCCESS, AvatarState.ERROR):
        m = _model()
        m.set_state(st)
        _run(m, TRANSIENT[st] + 0.3)
        assert m.state == AvatarState.IDLE, st


def test_conversational_states_hold():
    for st in (AvatarState.LISTENING, AvatarState.THINKING, AvatarState.SPEAKING):
        m = _model()
        m.set_state(st)
        _run(m, 5.0)
        assert m.state == st, st


def test_sound_cue_emitted_once():
    m = _model()
    m.set_state(AvatarState.NOTIFY)
    assert m.take_cue() == "notify"
    assert m.take_cue() is None  # drained


# -------------------------------------------------------------- determinism

def test_same_genome_advances_identically():
    a, b = _model("agent-alpha"), _model("agent-alpha")
    for _ in range(600):
        a.advance(1 / 60)
        b.advance(1 / 60)
    assert a.ay == b.ay
    assert a.next_blink == b.next_blink
    assert a.ax == b.ax
    assert [round(s["pos"][0], 9) for s in a.cluster] == [round(s["pos"][0], 9) for s in b.cluster]


# -------------------------------------------------------------- smoothing

def test_cur_smooths_toward_target():
    m = _model()
    m.set_state(AvatarState.NOTIFY)  # tint_mix target 0.85
    m.advance(1 / 60)
    first = m.cur["tint_mix"]
    _run(m, 0.5)
    assert 0.0 < first < m.cur["tint_mix"] <= 0.86


def test_amplitude_overrides_simulated_env():
    m = _model()
    m.set_amplitude(0.42)
    assert m.speech_env() == 0.42
    m.set_amplitude(None)
    assert 0.0 <= m.speech_env() <= 1.0


# ------------------------------------------------------------- gaze / pose

def test_listening_faces_front():
    m = _model()
    m.set_state(AvatarState.LISTENING)
    _run(m, 4.0)
    # yaw eases to the front (0); allow a small residual
    wrapped = (m.ay + math.pi) % math.tau - math.pi
    assert abs(wrapped) < 0.15


def test_thinking_gazes_down_right():
    m = _model()
    m.set_state(AvatarState.THINKING)
    _run(m, 4.0)
    assert m.cur["gaze_pitch"] > 0.15   # pitched down
    assert m.cur["gaze_yaw"] > 0.15     # turned right


# ---------------------------------------------------------- fragmentation

def _spread(m):
    _run(m, 8.0)
    return math.sqrt(sum(sum(q * q for q in s["pos"]) for s in m.cluster) / len(m.cluster))


def test_fragmentation_spreads_cluster_through_model():
    low = _spread(_model("8f2p7ke747", shapes=3, frag=0.1))
    high = _spread(_model("8f2p7ke747", shapes=3, frag=0.9))
    assert high > low * 1.3
