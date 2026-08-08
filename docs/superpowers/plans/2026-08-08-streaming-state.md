# Streaming State + State-Table Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `STREAMING` as the 8th `AvatarState` — drawn as one fast orbiting comet — and make every per-state table's completeness a test failure instead of a silent runtime `KeyError`.

**Architecture:** `widget.py` currently branches on state identity twice. Those branches are replaced by smoothed scalar channels in `STATE_TARGETS` (`ripple_mix` / `wave_mix` / `comet_mix`, replacing `trace_mix`), leaving the renderer with zero knowledge of which state it is in. Coverage assertions land *first*, so they demonstrably catch the half-wired state that the later tasks then create and fill in.

**Tech Stack:** Python ≥3.10, pure-stdlib core, PySide6 (optional `qt` extra) for the live widget, pytest.

**Spec:** `docs/superpowers/specs/2026-08-08-streaming-state-design.md`
**Issue:** [#1](https://github.com/seriouscoderone/ai-identicon/issues/1)

**Mapping to the spec's two phases** — the spec describes sequencing as two
phases; this plan splits them into seven commits for reviewability. Spec
"Commit 1" (coverage + refactor, no new state) = Tasks 1–3. Spec "Commit 2"
(the state) = Tasks 4–7. The phase boundary is the only ordering that matters:
no task from 4–7 may land before Task 3 is green.

## Global Constraints

- **Python ≥3.10.** No new runtime dependencies. The core (`genome`, `geometry`, `model`, `portrait`, `controller`) must stay dependency-free.
- **Only `widget.py`, `audio.py`, `clipboard.py` may import PySide6.** Never import it in `model.py` or any core module.
- **The test suite must pass Qt-free** — CI installs `.[test]` only. Any test needing Qt starts with `pytest.importorskip("PySide6")` and sets `QT_QPA_PLATFORM=offscreen`, following `tests/test_clipboard.py`.
- **`ALGO_VERSION` stays `1`. `tests/golden_v1.json` must stay byte-identical.** `portrait.py` is not touched by any task here. The CHANGELOG must **not** claim "golden SVG hashes re-pinned".
- **Version `0.8.0`** goes in **two** files that move together: `pyproject.toml` and `src/ai_identicon/__init__.py`.
- **Run tests with the repo venv:** `.venv/bin/python -m pytest -q`. Before trusting any run, confirm which package is loaded: `.venv/bin/python -c "import ai_identicon; print(ai_identicon.__file__, ai_identicon.__version__)"` — it must print a path under `<repo>/src/`. A stale sibling virtualenv has produced false greens on this repo before.
- **`genome.thinking` is an index into `THINKING_STYLES`, frozen by `ALGO_VERSION` — it is NOT `AvatarState.THINKING`.** They share a word and nothing else. Never touch the former.
- Commits stay **local**; do not push unless the user asks.

---

### Task 1: Coverage guards over the per-state tables

Nothing in `src/` iterates `AvatarState`, so every table restates the state list by hand. These assertions make an omission a test failure. They pass against today's seven states — the point is that Task 4 will make them fail the instant a state is half-wired, so this task ends by *proving* each guard bites.

**Files:**
- Create: `tests/test_state_coverage.py`

**Interfaces:**
- Consumes: `STATE_TARGETS`, `TRANSIENT`, `AvatarState`, `AvatarModel` from `ai_identicon.model`; `EVENT_STATES` from `ai_identicon.controller`.
- Produces: the guard suite that Tasks 3–5 are validated against. No importable symbols.

- [ ] **Step 1: Write the guard tests**

Create `tests/test_state_coverage.py`:

```python
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
```

- [ ] **Step 2: Run the guards — they must pass against today's seven states**

Run: `.venv/bin/python -m pytest tests/test_state_coverage.py -q`
Expected: PASS (18 tests — 4 flat + 7 + 7 parametrized).

- [ ] **Step 3: Prove the key-set guard bites**

Mutate a row in memory, then run only that guard. This is the corrupt-observe-restore check; without it the guards are unfalsifiable decoration.

```bash
.venv/bin/python -c "
import sys, pytest
from ai_identicon.model import STATE_TARGETS, AvatarState
del STATE_TARGETS[AvatarState.ERROR]['trace_mix']
sys.exit(pytest.main(['tests/test_state_coverage.py::test_targets_rows_share_one_key_set','-q']))"
```

Expected: FAIL, message naming `ERROR` and `trace_mix`. (After Task 3 this key is `ripple_mix` — use whichever key the row actually has.)

- [ ] **Step 4: Prove the reachability guard bites**

`ERROR` is reachable via two names, so remove both:

```bash
.venv/bin/python -c "
import sys, pytest
from ai_identicon.controller import EVENT_STATES
del EVENT_STATES['error'], EVENT_STATES['failed']
sys.exit(pytest.main(['tests/test_state_coverage.py::test_every_state_is_reachable_by_event','-q']))"
```

Expected: FAIL. No source was edited in Steps 3–4, so nothing needs reverting.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 86 passed (68 existing + 18 new).

- [ ] **Step 6: Commit**

```bash
git add tests/test_state_coverage.py
git commit -m "test: guard every per-state table against missing states

Nothing in src/ iterates AvatarState, so STATE_TARGETS, EVENT_STATES and
TRANSIENT each restate the state list by hand and an omission is invisible
until a runtime KeyError. These assertions make completeness a test failure.

TRANSIENT is asserted literally on purpose: a derived transient/holding pair
cannot catch a misclassification, since moving a state between the two derived
sets leaves both passing."
```

---

### Task 2: Render-equivalence harness

Task 3 refactors the renderer and claims the picture does not change. That claim needs a measurement, not an assertion. This script hashes rendered frames per state; run it before and after and diff.

**Files:**
- Create: `scripts/state_render_hashes.py`

**Interfaces:**
- Consumes: `PresenceWidget`, `Genome`, `AvatarState`.
- Produces: `state_hash(seed: str, state: AvatarState) -> str` (16-hex-char digest) and a CLI printing one line per `(seed, state)` pair. Task 3 Step 2 and Step 7 consume its stdout. Reused later by issue #2's before/after review.

- [ ] **Step 1: Write the harness**

Create `scripts/state_render_hashes.py`:

```python
#!/usr/bin/env python
"""Print a stable render hash per avatar state — the equivalence harness.

A refactor meant to leave the picture alone (splitting a scalar, renaming a
channel) is verified by running this before and after and diffing the output.
The model is driven with a fixed timestep and sampled at fixed times, and the
blink schedule — the one seeded-random element in a frame — is frozen, so the
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
HOLDING_SAMPLES = (0.75, 1.5, 3.0)   # seconds after entering a holding state
TRANSIENT_FRACS = (0.2, 0.5, 0.85)   # fractions of a transient's own duration
SIZE = 240
DT = 1 / 60


def state_hash(seed: str, state: AvatarState) -> str:
    w = PresenceWidget(Genome.from_seed(seed))
    w._timer.stop()               # drive the clock by hand, not by wall time
    w.setFixedSize(SIZE, SIZE)
    w.model.next_blink = 1e9      # blinks are RNG-scheduled; freeze them out
    w.set_state(state)
    # Transient states auto-return to idle partway through a fixed window, so
    # sample them at fractions of their OWN duration — otherwise notify and
    # success mostly hash idle-settling frames instead of their real look.
    samples = ([TRANSIENT[state] * f for f in TRANSIENT_FRACS]
               if state in TRANSIENT else HOLDING_SAMPLES)
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
```

- [ ] **Step 2: Run it and confirm it is deterministic**

```bash
.venv/bin/python scripts/state_render_hashes.py > /tmp/h1.txt
.venv/bin/python scripts/state_render_hashes.py > /tmp/h2.txt
diff /tmp/h1.txt /tmp/h2.txt && echo "DETERMINISTIC"
```

Expected: 14 lines (2 seeds × 7 states), `DETERMINISTIC` printed, no diff. If the two runs differ, stop — an unfrozen random source is leaking into rendering and the Task 3 equivalence check would be meaningless.

- [ ] **Step 3: Commit**

```bash
git add scripts/state_render_hashes.py
git commit -m "test: add a per-state render-equivalence harness

Hashes rendered frames per state with a hand-driven clock and the blink
schedule frozen, so a refactor that claims not to change the picture can be
measured instead of asserted. Also the before/after tool for issue #2."
```

---

### Task 3: Split `trace_mix` into `ripple_mix` + `wave_mix`

Removes both state-identity branches from the renderer. Behaviour-preserving in steady state; transitions gain easing where they used to pop.

**Files:**
- Modify: `src/ai_identicon/model.py:44-52` (`STATE_TARGETS`)
- Modify: `src/ai_identicon/widget.py:319` and `:421-438`
- Modify: `tests/test_state_coverage.py` (append the renderer invariant)

**Interfaces:**
- Consumes: the guard suite from Task 1; `scripts/state_render_hashes.py` from Task 2.
- Produces: `STATE_TARGETS` rows keyed with `ripple_mix` and `wave_mix` in place of `trace_mix`; Task 5 adds `comet_mix` alongside them. `_draw_speaking_wave` and `_draw_trace_activity` keep their existing signatures — only the value passed as their `trace` argument changes.

- [ ] **Step 1: Write the failing invariant test**

Append to `tests/test_state_coverage.py` (and add `import re` plus `from pathlib import Path` and `import ai_identicon` to the imports at the top):

```python
WIDGET_SRC = Path(ai_identicon.__file__).parent / "widget.py"


def test_renderer_is_scalar_driven():
    """The renderer must never ask WHICH state it is in — only how much of each
    mark to draw. Reads widget.py as text so this runs without PySide6."""
    hits = [ln for ln in WIDGET_SRC.read_text().splitlines()
            if re.search(r"\.state\s*(?:==|!=|\bin\b)", ln)]
    assert not hits, "state-identity branch in the renderer:\n" + "\n".join(hits)
```

- [ ] **Step 2: Run it to verify it fails, and capture the baseline**

```bash
.venv/bin/python -m pytest tests/test_state_coverage.py::test_renderer_is_scalar_driven -q
.venv/bin/python scripts/state_render_hashes.py > /tmp/before.txt
```

Expected: FAIL, listing the two `m.state == AvatarState.SPEAKING` lines. `/tmp/before.txt` holds 14 hashes.

- [ ] **Step 3: Replace `trace_mix` in `STATE_TARGETS`**

In `src/ai_identicon/model.py`, update the comment block above `STATE_TARGETS` — change the `think_mix/trace_mix  gate the thinking effect / the listening-speaking ring` line to:

```python
#   think_mix      gate the thinking effect
#   ripple_mix/wave_mix  the ring instruments: listening's circle + inward
#                  ripples, and speaking's waveform. Each mark has its own
#                  channel so the renderer never branches on state identity.
```

Then replace the seven rows, swapping each `trace_mix=X` for `ripple_mix` / `wave_mix`:

```python
STATE_TARGETS = {
    AvatarState.IDLE: dict(tint=(255, 255, 255), tint_mix=0.0, scale=1.00, glow=1.00, core_dim=1.00, spin=1.0, think_mix=0.0, ripple_mix=0.0, wave_mix=0.0, face_mix=0.0, gaze_yaw=0.0, gaze_pitch=0.0),
    AvatarState.LISTENING: dict(tint=(120, 210, 255), tint_mix=0.10, scale=1.10, glow=1.30, core_dim=1.06, spin=0.7, think_mix=0.0, ripple_mix=1.0, wave_mix=0.0, face_mix=1.0, gaze_yaw=0.0, gaze_pitch=0.0),
    AvatarState.THINKING: dict(tint=(150, 120, 250), tint_mix=0.40, scale=0.94, glow=0.90, core_dim=0.78, spin=1.0, think_mix=1.0, ripple_mix=0.0, wave_mix=0.0, face_mix=1.0, gaze_yaw=0.35, gaze_pitch=0.22),
    AvatarState.SPEAKING: dict(tint=(255, 255, 255), tint_mix=0.0, scale=1.02, glow=1.15, core_dim=1.04, spin=1.3, think_mix=0.0, ripple_mix=0.0, wave_mix=1.0, face_mix=1.0, gaze_yaw=0.0, gaze_pitch=0.0),
    AvatarState.NOTIFY: dict(tint=(255, 190, 90), tint_mix=0.85, scale=1.16, glow=1.50, core_dim=1.10, spin=2.0, think_mix=0.0, ripple_mix=0.0, wave_mix=0.0, face_mix=0.0, gaze_yaw=0.0, gaze_pitch=0.0),
    AvatarState.SUCCESS: dict(tint=(90, 220, 160), tint_mix=0.85, scale=1.08, glow=1.40, core_dim=1.05, spin=1.5, think_mix=0.0, ripple_mix=0.0, wave_mix=0.0, face_mix=0.0, gaze_yaw=0.0, gaze_pitch=0.0),
    AvatarState.ERROR: dict(tint=(250, 110, 85), tint_mix=0.85, scale=0.95, glow=0.75, core_dim=0.95, spin=0.05, think_mix=0.0, ripple_mix=0.0, wave_mix=0.0, face_mix=0.0, gaze_yaw=0.0, gaze_pitch=0.0),
}
```

- [ ] **Step 4: Make the renderer read the scalars**

In `src/ai_identicon/widget.py`, replace line 319:

```python
        env = m.speech_env() * m.cur["wave_mix"]
```

Then replace the ring block (currently lines 421-438, from `trace = m.cur["trace_mix"]` through the `p.setPen(Qt.NoPen)` that closes it):

```python
        # Each ring mark has its own smoothed channel, so the renderer never
        # asks which state it is in — and marks cross-fade instead of popping.
        ripple, wave = m.cur["ripple_mix"], m.cur["wave_mix"]
        if max(ripple, wave) > 0.02 and hull_pts:
            target_r = max(math.hypot(qx - cx, qy - cy) for qx, qy in hull_pts) + r * 0.30
            if self._ring_r <= 1.0:
                self._ring_r = target_r
            self._ring_r += (target_r - self._ring_r) * 0.06  # calm, no jitter
            ring = self._ring_r

            if wave > 0.02:
                self._draw_speaking_wave(p, cx, cy, ring, r, disp, wave, env, k_t, k_e, g)
            if ripple > 0.02:
                base_pen = QPen(QColor(*disp, int(45 * ripple)))
                base_pen.setWidthF(1.2)
                p.setPen(base_pen)
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(cx, cy), ring, ring)
                self._draw_trace_activity(p, cx, cy, ring, disp, ripple, k_t)
            p.setPen(Qt.NoPen)
```

- [ ] **Step 5: Run the invariant test and the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS, 87 passed. If `test_targets_rows_share_one_key_set` fails, a row was missed in Step 3.

- [ ] **Step 6: Verify no leftover references to the old key**

```bash
grep -rn "trace_mix" src/ tests/ examples/ scripts/ || echo "CLEAN"
```

Expected: `CLEAN`. (`_draw_trace_activity` keeps its name — it draws the trace/ripple activity — and its `trace` parameter name is fine; only the `trace_mix` *channel* is gone.)

- [ ] **Step 7: Verify the picture did not change**

```bash
.venv/bin/python scripts/state_render_hashes.py > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt && echo "STEADY-STATE IDENTICAL"
```

Expected: no diff. The samples at 0.75s/1.5s/3.0s are all past the ~0.5s easing, so steady-state frames must match exactly. **If a hash differs, stop and diagnose** — the likeliest cause is a mistyped row value in Step 3, not the easing.

- [ ] **Step 8: Confirm the determinism contract is untouched**

```bash
.venv/bin/python -m pytest tests/test_golden_v1.py -q && git diff --stat tests/golden_v1.json
```

Expected: PASS and no diff for `golden_v1.json`.

- [ ] **Step 9: Commit**

```bash
git add src/ai_identicon/model.py src/ai_identicon/widget.py tests/test_state_coverage.py
git commit -m "refactor: make the renderer scalar-driven

trace_mix gated the whole ring block and a state-identity test then picked the
instrument. It splits into one channel per mark — ripple_mix (listening's
circle and inward ripples) and wave_mix (speaking's waveform) — so widget.py
holds zero state-identity branches and per-state visual config lives only in
STATE_TARGETS. Locked by test_renderer_is_scalar_driven.

Steady-state renders verified identical per state via
scripts/state_render_hashes.py. Transitions now ease rather than pop: env is
multiplied by wave_mix instead of snapping to zero on exit, and env also feeds
the glow radius and facet brightness."
```

---

### Task 4: Add the `STREAMING` state

The state exists, is reachable, and re-tints the body — but draws no ring mark yet. Task 5 gives it the comet. This task starts by watching the Task 1 guards go red, which is the whole reason they were written first.

**Files:**
- Modify: `src/ai_identicon/model.py:26-33` (enum), `:44-52` (`STATE_TARGETS`)
- Modify: `src/ai_identicon/controller.py:1-11` (docstring), `:20-38` (`EVENT_STATES`), `:75-96` (shortcuts)
- Modify: `tests/test_controller.py:19`
- Modify: `examples/gallery.py:30-37` (`_CAPTION`)

**Interfaces:**
- Consumes: guards from Task 1; `ripple_mix`/`wave_mix` from Task 3.
- Produces: `AvatarState.STREAMING`; `EVENT_STATES["streaming"|"typing"|"tokens"] -> AvatarState.STREAMING`; `AvatarController.streaming() -> AvatarState`. Task 5 adds `comet_mix=1.0` to this state's row.

- [ ] **Step 1: Add ONLY the enum member, and watch the guards fail**

In `src/ai_identicon/model.py`, add to `AvatarState`:

```python
    STREAMING = "streaming"
```

- [ ] **Step 2: Run the guards to see the half-wired state caught**

Run: `.venv/bin/python -m pytest tests/test_state_coverage.py -q`

Expected: FAIL — `test_every_state_has_a_targets_row` (no row), `test_every_state_is_reachable_by_event` (unreachable), and both parametrized `streaming` cases (`KeyError` on `STATE_TARGETS[STREAMING]`). This is the exact failure mode that was invisible before Task 1: confirm you see it, then continue.

- [ ] **Step 3: Add the `STATE_TARGETS` row**

In `src/ai_identicon/model.py`, insert after the `SPEAKING` row:

```python
    # text tokens landing — the output channel of a text-first assistant.
    # Deliberately NOT speaking's waveform (see the comet in widget.py): tint
    # sits next to listening's so text-arrival and sound-arrival read as one
    # "arriving" family, while tint_mix separates it from speaking, which holds
    # identity colour at 0.0. No blink and no sound cue, both by omission:
    # the blink whitelist is (IDLE, LISTENING) and cues are set by explicit
    # branches in set_state — a chirp on every response would grate.
    AvatarState.STREAMING: dict(tint=(150, 200, 255), tint_mix=0.32, scale=1.00, glow=1.05, core_dim=1.02, spin=1.10, think_mix=0.0, ripple_mix=0.0, wave_mix=0.0, face_mix=1.0, gaze_yaw=0.0, gaze_pitch=0.0),
```

- [ ] **Step 4: Re-point the event mapping and add the shortcut**

In `src/ai_identicon/controller.py`, replace these two existing consecutive lines in `EVENT_STATES` —

```python
    "speaking": AvatarState.SPEAKING,
    "streaming": AvatarState.SPEAKING,
```

— with these six (do not leave the originals in place, or `"speaking"` ends up defined twice):

```python
    "speaking": AvatarState.SPEAKING,
    "tts": AvatarState.SPEAKING,
    "voice": AvatarState.SPEAKING,
    "streaming": AvatarState.STREAMING,
    "typing": AvatarState.STREAMING,
    "tokens": AvatarState.STREAMING,
```

Add the shortcut after `speaking()`:

```python
    def streaming(self):
        return self.event("streaming")
```

And extend the module docstring's first paragraph so the split is documented where a reader looks first — after the sentence ending `"...translates them into AvatarModel calls."`, add:

```
Note the two output states: "speaking" is voice (a waveform), "streaming" is
text tokens landing (an orbiting comet). "streaming" mapped to SPEAKING before
0.8.0; callers emitting it for TTS audio should now emit "speaking" (or the
"tts"/"voice" synonyms).
```

- [ ] **Step 5: Flip the stale controller assertion**

In `tests/test_controller.py:19`, change:

```python
    assert c.event("streaming") == AvatarState.STREAMING
```

and add below the `test_synonyms_share_states` body:

```python
    assert EVENT_STATES["typing"] == EVENT_STATES["tokens"] == AvatarState.STREAMING
    assert EVENT_STATES["tts"] == EVENT_STATES["voice"] == AvatarState.SPEAKING
```

- [ ] **Step 6: Add the gallery caption**

`examples/gallery.py:69` iterates `AvatarState`, so the button already exists and `_CAPTION[st]` would `KeyError` on click. In `_CAPTION`, after the `SPEAKING` entry:

```python
    AvatarState.STREAMING: "streaming — text arriving; a bright point laps its edge, fast",
```

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 89 passed (two more parametrized cases for the new state).

- [ ] **Step 8: Verify the gallery does not crash on the new button**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "
import sys; sys.path.insert(0,'examples'); sys.argv=['x']
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from gallery import Demo
from ai_identicon.model import AvatarState
d = Demo(); d.show()
d._go(AvatarState.STREAMING); d.orb.grab()
print('caption:', d.caption.text())"
```

Expected: prints the streaming caption, no traceback.

- [ ] **Step 9: Commit**

```bash
git add src/ai_identicon/model.py src/ai_identicon/controller.py tests/test_controller.py examples/gallery.py
git commit -m "feat: add the STREAMING avatar state

speaking covers voice; nothing covered text tokens landing, which is the
primary output channel for a text-first assistant. STREAMING is the 8th state:
cool blue, undimmed, face-locked, no blink and no sound cue.

BEHAVIOUR CHANGE: the published event name \"streaming\" now maps to
AvatarState.STREAMING instead of SPEAKING. Callers emitting it for TTS audio
should emit \"speaking\" (or the new \"tts\"/\"voice\" synonyms). \"typing\" and
\"tokens\" are added as streaming synonyms.

The state draws no ring mark yet — the comet lands next."
```

---

### Task 5: The comet

One glowing dot lapping the ring radius, with a subtle tail. The circle itself is not drawn — the dot travels an invisible orbit.

**Files:**
- Modify: `src/ai_identicon/model.py` (`STATE_TARGETS`: add `comet_mix` to all 8 rows)
- Modify: `src/ai_identicon/widget.py` (ring block + new `_draw_stream_comet`)
- Create: `tests/test_widget_marks.py`

**Interfaces:**
- Consumes: `ripple_mix`/`wave_mix` block from Task 3; `AvatarState.STREAMING` from Task 4.
- Produces: `PresenceWidget._draw_stream_comet(self, p, cx, cy, ring, r, disp, comet, k_t) -> None`, called from `paintEvent` when `comet > 0.02`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_widget_marks.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_widget_marks.py -q
.venv/bin/python scripts/state_render_hashes.py > /tmp/before-comet.txt
```

Expected: FAIL on `test_streaming_comet_moves` — nothing is travelling at the ring, so the two samples are identical. (`test_streaming_draws_its_own_mark` may already pass on tint/glow alone; the moving-comet test is the one that matters here.) Capture the baseline in the same step so Step 6 does not depend on a `/tmp` file written by an earlier task.

- [ ] **Step 3: Add the `comet_mix` channel to all eight rows**

In `src/ai_identicon/model.py`, add `comet_mix=0.0` to every row immediately after its `wave_mix`, except `STREAMING`, which gets `comet_mix=1.0`. Extend the comment block:

```python
#   ripple_mix/wave_mix/comet_mix  the three ring instruments: listening's
#                  circle + inward ripples, speaking's waveform, streaming's
#                  orbiting comet. One channel per mark, so the renderer never
#                  branches on state identity.
```

- [ ] **Step 4: Draw it**

In `src/ai_identicon/widget.py`, extend the ring block's gate and add the call:

```python
        ripple, wave, comet = (m.cur[k] for k in ("ripple_mix", "wave_mix", "comet_mix"))
        if max(ripple, wave, comet) > 0.02 and hull_pts:
```

and after the `ripple` block, before `p.setPen(Qt.NoPen)`:

```python
            if comet > 0.02:
                self._draw_stream_comet(p, cx, cy, ring, r, disp, comet, k_t)
```

Add the method after `_draw_trace_activity`:

```python
    def _draw_stream_comet(self, p, cx, cy, ring, r, disp, comet, k_t):
        """Streaming: one bright dot lapping the (undrawn) ring — text arriving,
        fast. Deliberately not the speaking waveform: text is not voice.

        The orbit is a FLAT circle at ring radius, which the `orbiter` thinking
        style (tilted ellipse, closer in, a third the speed, many sparkles) never
        uses — so the two marks stay legible as different instruments.

        Sized in r-units throughout — the trail spans a fixed arc in radians, the
        widths and head radius are fractions of r — so unlike the rest of this
        file the mark keeps its proportions at any embed size (see issue #2).
        """
        m = self.model
        spark = _lerp_rgb(disp, (255, 255, 255), 0.55)
        head = m.t * math.tau * 0.75 * k_t   # ~0.75 rev/s, scaled by tempo

        def at(tau):
            return QPointF(cx + ring * math.cos(tau), cy + ring * math.sin(tau))

        n_trail = 16
        prev = at(head)
        for k in range(1, n_trail):
            q = at(head - k * 0.045)
            fade = 1.0 - k / n_trail
            pen = QPen(QColor(*spark, int(150 * fade ** 1.7 * comet)))
            pen.setWidthF(max(0.6, r * 0.055 * fade))
            p.setPen(pen)
            p.drawLine(prev, q)
            prev = q
        p.setPen(Qt.NoPen)

        hd = at(head)
        core_r = max(1.5, r * 0.13)
        core = QRadialGradient(hd, core_r)
        core.setColorAt(0.0, QColor(255, 255, 255, int(235 * comet)))
        core.setColorAt(0.45, QColor(*spark, int(160 * comet)))
        core.setColorAt(1.0, QColor(*spark, 0))
        p.setBrush(core)
        p.drawEllipse(hd, core_r, core_r)
        p.setBrush(Qt.NoBrush)
```

- [ ] **Step 5: Run the tests**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS, 94 passed (89 + 5 new: two flat plus three parametrized sizes; the widget-marks module is skipped in CI, which has no PySide6).

- [ ] **Step 6: Confirm the other states still render identically**

```bash
.venv/bin/python scripts/state_render_hashes.py > /tmp/after-comet.txt
diff <(grep -v streaming /tmp/before-comet.txt) <(grep -v streaming /tmp/after-comet.txt) && echo "OTHER STATES UNCHANGED"
```

Expected: no diff. Adding a dormant `comet_mix=0.0` channel must not alter any other state.

- [ ] **Step 7: Judge it on screen — the one step that cannot be automated**

```bash
.venv/bin/python examples/gallery.py
```

Check, in order:
1. Click **streaming**. The dot should read as brisk, not frantic — roughly one lap per 1–1.8s at mid tempo.
2. Drag **Size** to 40px, then 480px. The comet should hold its proportions at both (this is the mark's whole design claim).
3. Set **Thinking** to `orbiter`, then toggle thinking → streaming. The two marks must read as different instruments, not the same sparkle twice.
4. Toggle speaking → streaming → listening. Marks should cross-fade, not pop.

If the speed is wrong, `0.75` in `head` is the number to change; record whatever you land on in the commit message.

- [ ] **Step 8: Commit**

```bash
git add src/ai_identicon/model.py src/ai_identicon/widget.py tests/test_widget_marks.py
git commit -m "feat: draw streaming as one fast orbiting comet

A single glowing dot with a subtle tail laps the ring radius; the ring circle
itself is not drawn. Text output gets its own instrument rather than borrowing
speech's waveform.

Kept legible against the orbiter thinking style (20% of seeds) by reserving the
flat circular orbit at ring radius to streaming — the orbiter uses a tilted
ellipse, closer in, at a third the speed, with many sparkles.

Sized in r-units throughout, so it is the first mark in widget.py that holds its
proportions at any embed size (cf. issue #2)."
```

---

### Task 6: State stills generator

Seven `docs/states/*.png` are hand-captured with no generator. An 8th is needed, and the next state would have the same problem.

**Files:**
- Create: `scripts/render_state_stills.py`
- Modify: `docs/states/*.png` (all 8 regenerated)

**Interfaces:**
- Consumes: `AvatarState.STREAMING` (Task 4), the comet (Task 5).
- Produces: `docs/states/<state>.png` for all 8 states, at the size the README's table expects.

- [ ] **Step 1: Write the generator**

Create `scripts/render_state_stills.py`:

```python
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
    AvatarState.ERROR: 0.22,
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
    QApplication(sys.argv[:1])
    out = os.path.join(os.path.dirname(__file__), "..", "docs", "states")
    os.makedirs(out, exist_ok=True)
    for state in AvatarState:
        path = os.path.join(out, f"{state.value}.png")
        print(f"  {state.value:10} {render(state, path) // 1024:>4} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python scripts/render_state_stills.py`
Expected: 8 lines, one per state, each a non-trivial size (>5 KB).

- [ ] **Step 3: Eyeball all eight**

Open `docs/states/`. Each still must be recognisably its state: `notify`/`success` caught mid-flare, `error` amber and off-centre from the flinch, `streaming` showing the comet clearly. If a transient looks like plain idle, its `SAMPLE_AT` value is too late — adjust and re-run.

- [ ] **Step 4: Commit**

```bash
git add scripts/render_state_stills.py docs/states
git commit -m "docs: generate the state stills instead of hand-capturing them

Seven stills were captured by hand with no generator, so an 8th state meant
repeating the chore and the set drifted in framing. This renders all eight
offscreen from one seed, mirroring render_readme_loops.py, sampling transients
mid-flare and holding states once settled.

All eight are regenerated, so the README's state row changes visibly even where
the state itself did not."
```

---

### Task 7: Docs, version, changelog

**Files:**
- Modify: `README.md:36-38`, `:43-61`
- Modify: `docs/demo-video-script.md:64-76`
- Modify: `CHANGELOG.md` (new entry at top, under the header block)
- Modify: `pyproject.toml:7`
- Modify: `src/ai_identicon/__init__.py:39`

**Interfaces:**
- Consumes: everything above.
- Produces: no code symbols. Ships 0.8.0.

- [ ] **Step 1: Update the README's state-model bullet**

Replace the parenthesised list on `README.md:36-38`:

```markdown
- **Alive, but calm.** A headless state model (`idle / listening / thinking /
  speaking / streaming / notify / success / error`) with gaze choreography,
  breathing, blinks, and shard micro-physics. Present without being noisy; never
  interrupts.
```

- [ ] **Step 2: Update the states section and relayout the table**

On `README.md:45-46` change `all seven states:` to `all eight states:`. Then replace the table (lines 48-61) — eight states fill exactly two rows of four, so the transient note moves out of its 8th cell to a caption beneath:

```markdown
<table>
  <tr>
    <td align="center"><img src="docs/states/idle.png" width="190"><br><b>idle</b><br><sub>at rest, breathing; the odd blink</sub></td>
    <td align="center"><img src="docs/states/listening.png" width="190"><br><b>listening</b><br><sub>turns to face you; ripples drift inward</sub></td>
    <td align="center"><img src="docs/states/thinking.png" width="190"><br><b>thinking</b><br><sub>comes apart to turn it over, gaze down‑right</sub></td>
    <td align="center"><img src="docs/states/speaking.png" width="190"><br><b>speaking</b><br><sub>voice drawn as a waveform around it</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="docs/states/streaming.png" width="190"><br><b>streaming</b><br><sub>text arriving; a bright point laps its edge</sub></td>
    <td align="center"><img src="docs/states/notify.png" width="190"><br><b>notify</b><br><sub>a chirp and an excited spin; self‑returns</sub></td>
    <td align="center"><img src="docs/states/success.png" width="190"><br><b>success</b><br><sub>a warm pulse and spin‑up; self‑returns</sub></td>
    <td align="center"><img src="docs/states/error.png" width="190"><br><b>error</b><br><sub>seized: rotation frozen, amber, one flinch</sub></td>
  </tr>
</table>

<sub><b>speaking</b> is voice, <b>streaming</b> is text tokens landing — the two
output channels. notify / success / error are transient: they play out and
settle back to idle on their own.</sub>
```

- [ ] **Step 3: Renumber the demo script**

In `docs/demo-video-script.md`, insert streaming after the speaking item and renumber the tail — items 5, 6, 7 become 6, 7, 8:

```markdown
5. **streaming** — *[VO]* "And when it's writing to you rather than talking, a
   bright point laps its edge — text arriving, fast."
6. **notify** — *[VO]* "A notification is a quick chirp and an excited little
   spin…" *(it returns to idle on its own)*
7. **success** — *[VO]* "…success, a warm pulse…"
8. **error** — *[VO]* "…and an error makes it seize up and flush amber."
```

- [ ] **Step 4: Add the CHANGELOG entry**

In `CHANGELOG.md`, directly above the `## [0.7.0]` heading:

```markdown
## [0.8.0] — 2026-08-08

- **⚠️ `"streaming"` now means text, not voice.** The published lifecycle event
  `"streaming"` mapped to `SPEAKING`; it now maps to the new
  `AvatarState.STREAMING`. Callers emitting it for TTS audio should emit
  `"speaking"` — or the new `"tts"` / `"voice"` synonyms. `"typing"` and
  `"tokens"` are added as streaming synonyms.
- **New state: `streaming`** — text tokens landing, the primary output channel
  of a text-first assistant. Drawn as a single glowing comet lapping the orb at
  speed, deliberately not speech's waveform. No blink and no sound cue: it is a
  working state, and a chirp on every response would grate.
- **The renderer is now scalar-driven.** `trace_mix` split into `ripple_mix` /
  `wave_mix` / `comet_mix` — one channel per ring mark — so `widget.py` holds no
  state-identity branches and per-state visual config lives only in
  `STATE_TARGETS`. Marks now cross-fade between states instead of popping.
- **Coverage guards** over `STATE_TARGETS`, `EVENT_STATES` and `TRANSIENT`:
  adding a state without wiring it is now a test failure rather than a runtime
  `KeyError`.
- **State stills are generated**, not hand-captured
  (`scripts/render_state_stills.py`); all eight are regenerated.

Genome derivation and `ALGO_VERSION 1` are unchanged, and the golden SVG hashes
are untouched — no existing seed's avatar moves.
```

- [ ] **Step 5: Bump the version in both places**

`pyproject.toml:7`:

```toml
version = "0.8.0"
```

`src/ai_identicon/__init__.py:39`:

```python
__version__ = "0.8.0"
```

- [ ] **Step 6: Verify the two versions agree and nothing is stale**

```bash
.venv/bin/python -c "
import re, pathlib, ai_identicon
pyproject = re.search(r'version = \"([^\"]+)\"', pathlib.Path('pyproject.toml').read_text()).group(1)
assert pyproject == ai_identicon.__version__ == '0.8.0', (pyproject, ai_identicon.__version__)
print('version 0.8.0 in both places')"
grep -rn "seven states\|all seven" README.md docs/ && echo "STALE COPY ABOVE" || echo "no stale state counts"
```

Expected: the version line prints, and `no stale state counts`.

- [ ] **Step 7: Full verification**

```bash
.venv/bin/python -m pytest -q
git diff --stat tests/golden_v1.json
```

Expected: PASS, 94 passed. No diff on `golden_v1.json`.

- [ ] **Step 8: Commit**

```bash
git add README.md docs/demo-video-script.md CHANGELOG.md pyproject.toml src/ai_identicon/__init__.py
git commit -m "docs: document the streaming state; release 0.8.0

README state table relaid out for eight states (the transient note moves from
its 8th cell to a caption), demo script renumbered, CHANGELOG entry leading with
the \"streaming\" event re-point since that is a behaviour change to a published
mapping.

ALGO_VERSION stays 1 and the golden SVG hashes are untouched."
```

---

## Done criteria

- `.venv/bin/python -m pytest -q` green (94 passed locally; the Qt-dependent `test_widget_marks.py` and `test_clipboard.py` skip in CI).
- `tests/golden_v1.json` byte-identical; `ALGO_VERSION` still `1`.
- `grep -rn "\.state\s*\(==\|!=\)" src/ai_identicon/widget.py` finds nothing.
- The comet judged on screen at 40px and 480px, and against an `orbiter`-thinking seed.
- Issue #1 closable; issue #2 (absolute-pixel stroke weights) untouched and still open.
