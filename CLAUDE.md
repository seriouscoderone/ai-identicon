# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python -m venv .venv && .venv/bin/pip install -e ".[test]"     # core + pytest (Qt-free, what CI does)
.venv/bin/pip install -e ".[qt,test]"                          # + PySide6 for widget/audio/clipboard/gallery

pytest -q                                    # full suite (~0.4s)
pytest tests/test_model.py -q                # one file
pytest tests/test_model.py::test_starts_idle -q
pytest -k "brand or material" -q

python examples/gallery.py                   # interactive Qt gallery (seed box, state buttons, genome sliders)
python scripts/render_readme_loops.py        # regenerate docs/hero.webp + docs/faces/*.webp (needs qt + pillow)
```

**Verify which package you are testing before trusting a run.** `pytest` from the repo root imports
the *installed* `ai_identicon`, not `./src`; a stale sibling virtualenv has produced false greens.

```bash
python -c "import ai_identicon; print(ai_identicon.__file__, ai_identicon.__version__)"
PYTHONPATH=$PWD/src python -m pytest -q      # run against the working tree without installing
```

CI (`.github/workflows/ci.yml`) is pytest only, on Python 3.10–3.13, **without** the Qt extra — the
suite must stay green Qt-free. No linter or formatter is configured. Some test docstrings still
name a stale `tests/unit/avatar` path; the real command is `pytest -q`.

## Architecture

A layered stack; each layer is usable alone and only the top layer knows about Qt.

```
genome.py      identity   — (seed, algo_version, brand, overrides) → all appearance/behavior fields
geometry.py    math       — shard meshes, cluster layout, micro-physics, shading inputs
model.py       behavior   — headless state machine; advance(dt), read the pose
portrait.py    static     — SVG strings (line-art + filled color)        pure Python
controller.py  adapter    — assistant-lifecycle event names → AvatarState
widget.py      live       — QWidget renderer                             ) Qt extra:
audio.py       sound      — synthesized cues + live-mic spectrum         ) PySide6 imports
clipboard.py   paste      — rasterize to PNG for the system clipboard    ) live ONLY here
```

**The Qt boundary is load-bearing.** `genome`/`geometry`/`model`/`portrait`/`controller` must never
import PySide6 — that is what keeps the package dependency-free and the suite headless. Qt tests
guard with `pytest.importorskip("PySide6")` and `QT_QPA_PLATFORM=offscreen`.

**The widget owns pixels, never behavior.** Anything time-driven (transitions, tumble, gaze,
blink/saccade scheduling, transient auto-return, physics) belongs in `AvatarModel`; `widget.py`
calls `advance(dt)` and paints. Behavior added to the widget is untestable in CI.

**One source of truth for appearance.** `geometry.derive_appearance()` / `material_base()` /
`hsv_to_rgb()` are shared verbatim by the live widget and the color portrait, so the two can't
drift. Duplicating shading math in either is a bug in waiting.

### The determinism contract

This is the project's central constraint: **a seed's avatar must render identically forever under a
given `ALGO_VERSION`.**

- `genome._derive_v1` is **frozen — never edit it**. A changed generator ships as `_derive_v2`
  registered in `_DERIVERS`, with `ALGO_VERSION` bumped; v1 stays renderable and its golden file
  stays pinned.
- `Genome.to_dict()` is the whole portable identity: `{seed, algo_version, brand, overrides}`.
  Every other field is re-derivable, so nothing else may become load-bearing state.
- `Brand` is a **post-derivation remap** (snap the drawn hue/material into the allowed set), never a
  change to the draw sequence — an unbranded genome must stay byte-identical.
- `OVERRIDE_FIELDS` gates what users may pin. `seed`/`algo_version`/`mesh_seed`/`shards` are
  identity structure, not knobs.
- `_derive_v1` always derives 5 shards regardless of `shapes`, so moving the Shapes slider doesn't
  reshuffle the RNG stream.

`tests/golden_v1.json` locks this in two tiers:

1. **Derived genome fields + shard seeds** — frozen by `ALGO_VERSION`. If these drift, the change is
   wrong (or needs a new algo version + `golden_v2.json`).
2. **Rendered-SVG hashes** — track the geometry/shading pipeline, which is still being refined
   pre-1.0. A *deliberate* rendering change re-pins them, with a package minor bump and a CHANGELOG
   line saying so; the genome fields must be unchanged in the same commit.

Re-pinning is manual (no generator script). This reproduces the committed file exactly:

```python
# PYTHONPATH=. python - <<'EOF'   (run from the repo root)
import hashlib, json, sys; sys.path.insert(0, "src")
from ai_identicon.genome import Genome, ALGO_VERSION
from ai_identicon import portrait
from tests.test_golden_v1 import FIELDS, _rnd, GOLDEN
h = lambda s: hashlib.sha256(s.encode()).hexdigest()[:16]
out = {"algo_version": ALGO_VERSION, "seeds": {}}
for seed in GOLDEN["seeds"]:
    g = Genome.from_seed(seed)
    out["seeds"][seed] = {
        "fields": {f: _rnd(getattr(g, f)) for f in FIELDS},
        "shard_seeds": [sh["mesh_seed"] for sh in g.shards],
        "svg": {"color": h(portrait.color_svg(g)),
                "black": h(portrait.line_art_svg(g, "black")),
                "black40": h(portrait.line_art_svg(g, "black", px=40))}}
open("tests/golden_v1.json", "w").write(json.dumps(out, indent=2, sort_keys=True) + "\n")
EOF
```

Watch the name collision: `genome.thinking` is an **index into `THINKING_STYLES`**, frozen by
`ALGO_VERSION`; `AvatarState.THINKING` is a runtime state and is *not* covered by the golden file.
They share a word and nothing else.

### Geometry invariants (why the constants exist)

The avatar is a "broken whole" — 1–5 shards of one fractured solid, with the genome's *totals*
partitioned across them. Several guards exist because their absence produced specific visual
failures; the code comments record the failure each one prevents. Don't relax them casually:

- **HEFT** — ≥8 vertices and ≥8 faces per shard, plus an axis-thickness floor (42% of the widest).
  Fewer vertices yields a low-volume octahedron that can never pass the plumpness bar.
- **Plumpness** — `make_shard` retries with tamer parameters until true volume ≥22% of the bounding
  sphere; retries switch to a jittered Fibonacci lattice that can't land near-planar. Attempt 0 stays
  free-random so existing seeds keep their look.
- **PRESENCE** — total true mesh volume clamped into a band (widening with shard count) so no avatar
  reads as "less than".
- **`_MAX_SHARD_DIST` / `_SPREAD_CAP`** — keep a fragmented cluster a frame-filling group instead of
  sparse debris with a lone far outlier.
- Vertex perturbation is **radial only**, keeping meshes star-shaped so painter's-algorithm depth
  sorting stays correct.
- `portrait.py` deliberately does **not** cull back faces (all faces painted back-to-front); culling
  dropped near-edge-on faces on flat shards and left holes.

### Model / rendering details worth knowing

- `STATE_TARGETS` holds a per-state row of scalars; everything is exponentially smoothed toward the
  current row, so any state transitions to any other with no special-casing. The rows must stay
  key-identical — a missing key is a silent runtime `KeyError`/wrong visual, not a test failure.
- `TRANSIENT` states (notify/success/error) self-return to idle; conversational states hold.
- Personality is two multipliers derived from the genome — `k_e` (express: gesture amplitude) and
  `k_t` (tempo: the master clock) — applied to every gesture rather than tuned per effect.
- Portraits render the **canonical front pose**: `ax=genome.tilt, ay=0`, after 500 settle steps of
  the same `physics_step` the live widget uses, so the still matches the live face when it locks.
- `breath_override` / `blink_override` on the model exist solely so `scripts/render_readme_loops.py`
  can build seamless loops (whole breath cycles + one full blink per revolution).
- `nothing in src/ iterates AvatarState` — every table (`STATE_TARGETS`, `EVENT_STATES`, gallery
  captions, audio `RECIPES`) restates the state list by hand, so adding a state means updating each
  one; `audio.play()` no-ops silently on a missing cue.

## Releasing

Version lives in **two** places that must move together: `pyproject.toml` and
`src/ai_identicon/__init__.py.__version__`. Add a CHANGELOG entry stating whether the change is
rendering-only (golden SVG hashes re-pinned, `ALGO_VERSION` untouched) or a genome change (new
`ALGO_VERSION`). Docs assets: `docs/hero.webp` and `docs/faces/*.webp` come from
`scripts/render_readme_loops.py`; `docs/states/*.png` are hand-captured with no generator.
