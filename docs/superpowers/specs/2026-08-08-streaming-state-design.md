# `streaming` state + state-table coverage — design

**Date:** 2026-08-08
**Issue:** [#1](https://github.com/seriouscoderone/ai-identicon/issues/1)
**Target version:** 0.8.0
**Status:** approved, ready for implementation planning

## Problem

`speaking` covers voice output. Nothing covers **text tokens landing** — the primary
output channel for a text-first assistant UI, where the agent writes prose and working
logs rather than talking. This adds `STREAMING` as the 8th `AvatarState`.

Separately, the state tables are unguarded: adding an enum member alone leaves the
whole suite green while the state is broken at runtime. Nothing in `src/` iterates
`AvatarState`, so every table restates the list by hand and an omission is invisible.

## Non-goals

- No change to `ALGO_VERSION`, genome derivation, or `tests/golden_v1.json`. `portrait.py`
  is untouched, so the golden SVG hashes must stay **byte-identical** — a checkable
  invariant, not merely an intention.
- No fix for absolute-pixel stroke weights (see [Out of scope](#out-of-scope)).
- No audio input or token-rate feed. Streaming animates from `m.t` alone.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Scope | Coverage tests + renderer refactor **first**, then the state | The assertions must be able to prove they'd catch a half-wired state; also gives a clean bisect point |
| `EVENT_STATES["streaming"]` | **Re-point** to `STREAMING` | The name matches the thing. Pre-1.0 is the cheap moment to take the break rather than carry the wart |
| Blink during streaming | **No** | Working state, not a resting one; its always-moving comet already carries liveness |
| Sound cue | **No** | A text-first agent enters streaming on *every* response; a chirp each time would grate |
| The mark | **One orbiting comet**, not a waveform | Text is not speech and should not borrow speech's instrument |
| 8th state still | **Generator script** | `scripts/render_readme_loops.py` is an exact precedent; makes the 9th state free |

## Architecture — a scalar-driven renderer

`widget.py` has exactly two `AvatarState.SPEAKING` identity tests (`:319`, `:429`; its
other occurrences are the import and two type annotations). A scalars-only `STREAMING`
would fall into the `else` at `:429` and render *listening's* inward ripples with `env`
hard-zeroed by `:319` — wrong visual, no error.

`trace_mix` splits into **three instrument channels**, one per ring mark:

| channel | draws | `1.0` in |
|---|---|---|
| `ripple_mix` | base circle + inward ripples | listening |
| `wave_mix` | audio waveform | speaking |
| `comet_mix` | the streaming comet | streaming |

```python
# widget.py:319
env = m.speech_env() * m.cur["wave_mix"]

# widget.py:429
ripple, wave, comet = (m.cur[k] for k in ("ripple_mix", "wave_mix", "comet_mix"))
if max(ripple, wave, comet) > 0.02 and hull_pts:
    <ring radius smoothing — unchanged>
    if wave   > 0.02: self._draw_speaking_wave(..., wave)      # reused verbatim
    if ripple > 0.02: <base circle, alpha x ripple> + self._draw_trace_activity(..., ripple)
    if comet  > 0.02: self._draw_stream_comet(..., comet)
```

`trace_mix` is **removed**, not kept alongside — no redundant key. `_draw_speaking_wave`
and `_draw_trace_activity` keep their signatures; the `trace` argument is simply fed
`wave` / `ripple` respectively.

Result: **zero** state-identity branches in the renderer. Per-state visual config lives
in exactly one table (`STATE_TARGETS`), matching how every other channel already works.

### Steady-state equivalence, not byte equivalence

`env` now decays smoothly on exit instead of snapping to zero, and `env` also feeds
`glow_r` (`2.4 + 0.5*env`) and `bright` (`1.0 + 0.10*env`). So **transitions ease where
they used to pop** — the intended improvement. The refactor commit's claim is therefore
"steady-state renders unchanged", verified per state with offscreen render hashes.

## The streaming mark

One glowing dot with a subtle tail, lapping the ring radius. The circle itself is **not
drawn** — the dot travels an invisible orbit at that radius.

Parameter sketch (the full body belongs in the implementation plan) — the head is a
radial-gradient core, the tail a decaying-alpha polyline behind it, following the proven
technique in `_paint_orbiter`:

```python
def _draw_stream_comet(self, p, cx, cy, ring, r, disp, comet, k_t):
    """Streaming: one bright dot lapping the (undrawn) ring — text arriving, fast.
    Sized in r-units throughout, so it scales at any embed size."""
    head    = m.t * math.tau * 0.75 * k_t     # ~0.75 rev/s, tempo-scaled
    trail   = 16 samples spaced 0.045 rad     # arc in radians -> scales with radius
    width   = max(0.6, r * 0.055 * fade)      # r-units, not fixed px
    core_r  = max(1.5, r * 0.13)
```

Drawn under the existing `CompositionMode_Plus`, so it reads as additive light.

**Lap time** at 0.75 rev/s x `k_t`: **0.98–1.83 s** for derived seeds
(`k_t` 0.73–1.36), 0.92–2.42 s across the full override slider. Tune on screen before
landing; the base rate is the one number most likely to move.

### Distinctness from the `orbiter` thinking style

`_paint_orbiter` (`widget.py:495`) already draws an orbiting sparkle with a ribbon trail,
and **20% of seeds** get `thinking = orbiter` (400/2000 sampled). Since `thinking →
streaming` is the most common transition in a text-first UI, the two marks must not read
as one instrument:

| | streaming comet | orbiter thinking sparkle |
|---|---|---|
| path | flat circle, no tilt | tilted ellipse (`rx 1.75r x ry 0.70r`, tilt 0.45) |
| radius | ring radius (hull + `0.30r`), ~2.0–2.5r | ~1.75r |
| speed | ~0.75 rev/s | 1.4 rad/s ~ 0.22 rev/s |
| count | exactly one | one per shard **plus** one cluster-wide |
| extras | trail only | twinkles + rotating rays |
| body | undimmed (`core_dim 1.02`), cool blue, face-locked | dimmed (`0.78`), violet, fragmenting |

The flat circular orbit at ring radius is reserved to streaming; the orbiter never uses
it. For the 20% case the thinking sparkle fades out as the comet fades in, reading as a
hand-off.

### `STATE_TARGETS` row

```python
AvatarState.STREAMING: dict(
    tint=(150, 200, 255), tint_mix=0.32, scale=1.00, glow=1.05, core_dim=1.02,
    spin=1.10, think_mix=0.0, ripple_mix=0.0, wave_mix=0.0, comet_mix=1.0,
    face_mix=1.0, gaze_yaw=0.0, gaze_pitch=0.0),
```

`tint` is deliberately adjacent to listening's `(120,210,255)` so text-arrival and
sound-arrival read as one "arriving" family, apart from thinking's violet and the warm
transients. `tint_mix=0.32` is the primary distinguisher from speaking, which holds
identity colour at `0.0`. All seven existing rows gain `ripple_mix` / `wave_mix` /
`comet_mix` and lose `trace_mix`; only listening, speaking and streaming are non-zero.

**No code is needed for the blink and sound decisions** — the blink whitelist is
`(IDLE, LISTENING)` and cues are set by explicit branches in `set_state`, so `STREAMING`
is excluded by omission. Both get an explicit comment so the omission reads as intent.

## Controller

```python
"streaming": AvatarState.STREAMING,   # RE-POINTED (was SPEAKING)
"typing":    AvatarState.STREAMING,
"tokens":    AvatarState.STREAMING,
```

Plus a `streaming()` convenience shortcut. The module docstring at `controller.py:5`
documents the old meaning and goes stale — update it. `tests/test_controller.py:19`
asserts the old mapping and must flip.

Callers emitting `"streaming"` for TTS audio should switch to `"speaking"`. This is a
behaviour change to a published mapping and gets its own CHANGELOG lead-in.

## Tests

New Qt-free `tests/test_state_coverage.py`:

1. `set(STATE_TARGETS) == set(AvatarState)` — no state without a row
2. Every row has an **identical key set** — catches a channel missing from one row
3. `set(EVENT_STATES.values()) == set(AvatarState)` — no unreachable state
4. `TRANSIENT == {NOTIFY, SUCCESS, ERROR}` **literally** — a derived transient/holding
   pair cannot catch misclassification, since moving `STREAMING` between the two derived
   sets keeps both passing. Intent needs a literal assertion.
5. Parametrized over `list(AvatarState)`: set → advance 2 s → no exception and `cur`
   converges toward the row; then return to idle and assert every channel eases home
   (the "waveform never turns off after leaving streaming" class)
6. Renderer invariant: read `widget.py` **as text** (no import, so it runs Qt-free in CI)
   and assert no `\.state\s*(==|!=|\bin\b)`

№6 is a source-grep test and the most likely to age badly; it is included deliberately
but is the first thing to drop if it becomes precious.

## Docs and assets

- **New** `scripts/render_state_stills.py` — renders all 8 states offscreen, mirroring
  `scripts/render_readme_loops.py`. Regenerates every `docs/states/*.png`, so the README's
  state row changes visibly even where the state did not: a one-time churn buying
  permanent consistency and a free 9th state.
- **README** — prose list; the state `<table>` relayouts (8 states fill exactly 2 rows of
  4, so the transient note moves from its 8th cell to a caption beneath); "all seven
  states" becomes eight.
- **`examples/gallery.py`** — `_CAPTION[AvatarState.STREAMING]`. Mandatory: `gallery.py:69`
  iterates `AvatarState`, so the button auto-appears and `_CAPTION[st]` would `KeyError`
  on click.
- **`docs/demo-video-script.md`** — numbered 1–7 walkthrough; an insertion renumbers the tail.
- **CHANGELOG** — 0.8.0, with its own lead-in naming the event re-point. Must **not** claim
  "golden SVG hashes re-pinned".
- **Version** — `pyproject.toml` and `src/ai_identicon/__init__.py` move together.

## Sequencing

**Commit 1 — coverage + refactor, no new state.** Split `trace_mix` into the three
channels, promote both identity branches to scalar reads, add all six assertions (each
passes against the current seven states). All existing tests stay green; steady-state
render hashes unchanged per state.

**Commit 2 — the state.** `STREAMING` enum member, `STATE_TARGETS` row,
`_draw_stream_comet`, controller re-point, gallery caption, stills generator, docs,
version, CHANGELOG. The tests from commit 1 now actively guard the addition.

## Verification

- `pytest -q` green at both commits (Qt-free, matching CI)
- `golden_v1.json` byte-identical; `ALGO_VERSION` still 1
- Per-state offscreen render hashes unchanged in steady state across commit 1
- Comet visually checked at 40px / 120px / 360px via the gallery Size slider, and against
  an `orbiter`-thinking seed for instrument collision

## Out of scope

The gallery Size slider surfaced that **the animations only half-scale**: geometry keys
off `r = min(w,h) * 0.13 * zoom` and scales correctly, but ten constants are absolute
pixels — ring stroke `1.2` (`:433`), ripple `1.3` (`:491`), wave `1.1` (`:478`), notify
rings `1.5–4.0` (`:345`), idle bob `2.0` (`:307`), error shake `7.0` (`:312`), orbiter
core `6.0` / rays `4.5` (`:551`, `:558`), facet seam `0.8` (`:248`). Small embeds get too
much ink, large embeds too little; the error shake is a sixth of a 40px frame.

Filed separately as issue #2. It would shift every rendered pixel, so it needs its own
before/after review rather than riding along inside the streaming work. `_draw_stream_comet`
is authored in `r`-units from the start so it does not add to that debt.

## Trap worth restating

`genome.thinking` is an *index into `THINKING_STYLES`*, present in `golden_v1.json` and
frozen by `ALGO_VERSION`. It is **not** `AvatarState.THINKING`. They share a word and
nothing else; touching the former **is** an `ALGO_VERSION` break.
