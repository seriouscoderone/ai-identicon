# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org). The package version is
independent of `ALGO_VERSION` (the frozen avatar-generation contract): a
package release never changes an existing seed's avatar.

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
