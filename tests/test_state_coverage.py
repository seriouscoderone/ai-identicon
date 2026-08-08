"""Coverage guards over the per-state tables.

Adding an AvatarState member alone leaves the rest of the suite green while the
state is broken at runtime: nothing in src/ iterates AvatarState, so every table
restates the list by hand and an omission stays invisible until a KeyError in
production. These assertions turn each table's completeness into a test failure.

Qt-free by construction — the renderer invariant (added in a later task) reads
widget.py as TEXT rather than importing it, so this module runs in CI's Qt-less
job like everything else here.
"""

from __future__ import annotations

import pytest

from ai_identicon.controller import EVENT_STATES
from ai_identicon.genome import Genome
from ai_identicon.model import STATE_TARGETS, TRANSIENT, AvatarModel, AvatarState

DT = 1 / 60
SETTLE = 1.0  # seconds; shorter than the briefest transient (SUCCESS, 1.2s)


def _settled(state):
    """A model parked in `state` long enough for every channel to converge.

    SETTLE is deliberately under the shortest TRANSIENT duration so transient
    states have not yet auto-returned to idle when we assert on them.
    """
    m = AvatarModel(Genome.from_seed("coverage"))
    m.set_state(state)
    for _ in range(int(SETTLE / DT)):
        m.advance(DT)
    return m


def _assert_converged(m, row, label):
    for key, target in row.items():
        cur = m.cur[key]
        if isinstance(cur, list):  # tint is a 3-vector, 0..255 per channel
            for i in range(3):
                assert abs(cur[i] - target[i]) < 6.0, f"{label}.{key}[{i}]"
        else:
            assert abs(cur - target) < 0.05, f"{label}.{key}"


def test_every_state_has_a_targets_row():
    assert set(STATE_TARGETS) == set(AvatarState)


def test_targets_rows_share_one_key_set():
    reference = frozenset(STATE_TARGETS[AvatarState.IDLE])
    for state, row in STATE_TARGETS.items():
        assert frozenset(row) == reference, (
            f"{state.name} row differs by {frozenset(row) ^ reference}")


def test_every_state_is_reachable_by_event():
    assert set(EVENT_STATES.values()) == set(AvatarState)


def test_transients_are_exactly_these_three():
    # Literal, not derived. A derived transient/holding pair cannot catch a
    # MISCLASSIFICATION: moving a state between the two derived sets keeps both
    # passing. Intent has to be spelled out.
    assert set(TRANSIENT) == {AvatarState.NOTIFY, AvatarState.SUCCESS,
                              AvatarState.ERROR}


@pytest.mark.parametrize("state", list(AvatarState), ids=lambda s: s.value)
def test_state_can_be_entered_and_converges(state):
    _assert_converged(_settled(state), STATE_TARGETS[state], state.name)


@pytest.mark.parametrize("state", list(AvatarState), ids=lambda s: s.value)
def test_every_channel_eases_home_after_leaving(state):
    # catches "the waveform never turns off after leaving streaming"
    m = _settled(state)
    m.set_state(AvatarState.IDLE)
    for _ in range(int(3.0 / DT)):
        m.advance(DT)
    _assert_converged(m, STATE_TARGETS[AvatarState.IDLE], f"{state.name}->idle")
