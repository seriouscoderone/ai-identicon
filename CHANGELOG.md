# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org). The package version is
independent of `ALGO_VERSION` (the frozen avatar-generation contract): a
package release never changes an existing seed's avatar.

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
