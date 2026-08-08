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

import ast
from pathlib import Path

import pytest

import ai_identicon
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


WIDGET_SRC = Path(ai_identicon.__file__).parent / "widget.py"


def _refs_state_member(node: ast.AST) -> bool:
    """True if `node` is (or literally contains) an `AvatarState.MEMBER` name.

    A regex over operator spellings ("==", "is", ...) has to enumerate every
    way a comparison can be written and still misses reversed operands or a
    locally-aliased variable (`state = m.state; if state == AvatarState.X`).
    Keying on "does this expression mention an AvatarState member at all" is
    operand-order- and alias-proof by construction: it doesn't matter what the
    *other* side of the comparison is spelled as.
    """
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
            and node.value.id == "AvatarState":
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):  # `m.state in (A, B)`
        return any(_refs_state_member(elt) for elt in node.elts)
    if isinstance(node, ast.MatchValue):  # `case AvatarState.X:`
        return _refs_state_member(node.value)
    if isinstance(node, ast.MatchOr):  # `case AvatarState.X | AvatarState.Y:`
        return any(_refs_state_member(p) for p in node.patterns)
    return False


def test_renderer_is_scalar_driven():
    """The renderer must never ask WHICH state it is in — only how much of each
    mark to draw. Parses widget.py as an AST (never imports it, so this runs
    without PySide6) and flags any comparison or match/case pattern that
    mentions an AvatarState member — catching `==`, `!=`, `is`, `is not`,
    `in`, reversed operand order, and aliasing, not just one spelling."""
    tree = ast.parse(WIDGET_SRC.read_text())
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            operands = (node.left, *node.comparators)
            if any(_refs_state_member(o) for o in operands):
                hits.append(ast.unparse(node))
        elif isinstance(node, ast.match_case):
            if _refs_state_member(node.pattern):
                hits.append(f"case {ast.unparse(node.pattern)}:")
    assert not hits, "state-identity branch(es) in the renderer:\n" + "\n".join(hits)
