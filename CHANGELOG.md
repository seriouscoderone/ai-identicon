# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org). The package version is
independent of `ALGO_VERSION` (the frozen avatar-generation contract): a
package release never changes an existing seed's avatar.

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
