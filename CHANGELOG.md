# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org). The package version is
independent of `ALGO_VERSION` (the frozen avatar-generation contract): a
package release never changes an existing seed's avatar.

## [0.7.0] — 2026-07-18

- **Breathing is now the aura, not the shape.** The crystal holds its size;
  the glow halo gently expands/contracts (and softly brightens). A scaling
  solid read as zooming — this reads as breath. Live-widget behavior change.
- **Idle loops run at the live speed.** A full revolution now takes the same
  time as the running app (~20–37s depending on the avatar's tempo) instead of
  the previous ~5s; blinks stay quick via a time-based render with a dense
  frame burst, and breathing completes whole cycles per revolution (seamless).

## [0.6.1] — 2026-07-18

- Idle loops now show **personality**: tempo sets each avatar's loop speed,
  expressiveness sets breathing depth, and the seed picks the spin direction —
  so they no longer all feel the same. Breathing and one blink complete whole
  cycles per revolution, so the loop stays seamless.
- The blink dims the orb body but leaves the **aura steady** (reads better, and
  keeps the soft dark gradient stable so lossy encoders don't block it). New
  internal `breath_override` / `blink_override` hooks on the model support
  seamless loop rendering; see `scripts/render_readme_loops.py`.

## [0.6.0] — 2026-07-18

- **`PresenceWidget.zoom`** — a render-scale knob (default 1.0) to size the orb
  within its frame; used to fill the README tiles.
- **Docs:** the README hero and the sixteen faces are now **true 360° spin
  loops** (seamless full revolution) as animated WebP, zoomed in and lighter
  than the earlier ping-pong loops per frame budget.

## [0.5.0] — 2026-07-17

- **Copy to clipboard** (`ai_identicon.clipboard`, Qt extra): rasterize an
  avatar to PNG and put it on the system clipboard to paste into Obsidian, MS
  Teams, Signal, Discord, Slack, docs, etc. PNG (not SVG) is what those apps
  paste reliably, and it keeps transparency. The SVG is attached as a bonus
  MIME type. Convenience: `PresenceWidget.copy_to_clipboard()`, and a
  **copy 📋** button in the gallery.

## [0.4.0] — 2026-07-17

Solidity fixes (rendering-only; ALGO_VERSION 1 genome derivation unchanged,
golden SVG hashes re-pinned).

- **No more missing faces.** Dropped back-face culling in the color portrait
  and live widget; all faces are painted back-to-front, so a convex shard
  always fills its silhouette (culling could drop a near-edge-on face on a
  flat shard and leave a hole).
- **Minimum 8 vertices per shard.** A 6-vertex hull is a low-volume
  octahedron that can never satisfy the plumpness constraint, yielding flat
  "blade" shards; the floor lets the guard actually succeed, so shards are
  reliably chunky.

## [0.3.0] — 2026-07-17

Thinking behavior + scatter refinements (rendering-only; ALGO_VERSION 1 genome
derivation unchanged, golden SVG hashes re-pinned).

- **Breakup thinking no longer moves the shards.** They hold their positions;
  only their facets fragment (the per-facet "explode"). Previously the
  shard-level separation flung a far outlier way out of frame.
- **Outlier containment.** A per-shard home-distance cap (plus a slightly
  tighter overall spread cap) keeps a single high-`draw` shard from sitting
  off on its own, so heavily-fragmented avatars read as one grouped cluster.

## [0.2.0] — 2026-07-17

Rendering refinements (pre-1.0; genome derivation / `ALGO_VERSION 1` unchanged,
so `to_dict` identities are stable — only the rendered geometry moved, and the
golden SVG hashes were re-pinned accordingly).

- **Glassy transparency is now an intrinsic material property** of crystal and
  glass (scaled by translucency), not a user toggle. Stone and metal always
  render opaque. Removed the `transparent` flag / `set_transparent` and the
  demo's "glassy" checkbox.
- **Spread cap** on cluster reach: heavily-fragmented, many-shard avatars no
  longer scatter into sparse debris that underfills the frame — fragmentation
  still clearly separates the shards, bounded to a frame-filling group.

## [0.1.0] — 2026-07-17

Initial release. **Avatar generation: `ALGO_VERSION = 1`** (frozen, locked by
`tests/golden_v1.json`).

- Deterministic `Genome.from_seed`, frozen-versioned, with a sparse override
  overlay and optional `Brand` palette/material constraints.
- Pure-Python geometry: convex-hull shard meshes, genome-partitioned
  "broken-whole" clusters, heft/plumpness + presence constraints, and a
  spring+collision micro-physics.
- Headless `AvatarModel`: state machine, target smoothing, gaze/face-lock,
  blink/saccade scheduling, sound cues.
- Static SVG portraits: hidden-line line-art (black/white) and filled,
  shaded color; size-aware for small avatars.
- `AvatarController` mapping assistant-lifecycle events to states.
- Optional Qt extra: live `PresenceWidget` renderer and `audio` (synthesized
  chirps + live-mic 12-band spectrum).
