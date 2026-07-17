"""Avatar behavior layer — a headless, Qt-free animation model.

`AvatarModel` owns everything time-driven: the current state, the smoothed
per-state targets, the tumble/gaze choreography, blink and saccade
scheduling, the transient auto-return, and the shard micro-physics. It knows
nothing about painting — it advances by `dt` and exposes the pose + animation
scalars a renderer needs. That separation is what lets us unit-test behavior
(state transitions, determinism, fragmentation) with no display.

The renderer (live widget or a frame grab) calls `advance(dt)` each frame and
reads `cluster`, `cur`, `ax`/`ay`, `blink()`, `bloom()`, `breath()`, etc.
Audio-reactive input arrives via `set_amplitude` / `set_spectrum`; state
changes emit a one-shot sound cue the renderer can drain via `take_cue()`.
"""

from __future__ import annotations

import math
import random
from enum import Enum

from .genome import Genome, THINKING_STYLES, VOICE_STYLES
from . import geometry


class AvatarState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    NOTIFY = "notify"
    SUCCESS = "success"
    ERROR = "error"


# Per-state visual targets; everything is smoothed toward these, so any state
# transitions to any other without special cases.
#   tint/tint_mix  semantic color + how strongly it overrides identity color
#   scale/glow/core_dim  size, halo, facet brightness
#   spin           tumble-rate multiplier (cognitive activity)
#   think_mix/trace_mix  gate the thinking effect / the listening-speaking ring
#   face_mix       0 = free spin, 1 = yaw locked to the gaze target
#   gaze_yaw/gaze_pitch  where to face when locked (0,0 = front, at the user)
STATE_TARGETS = {
    AvatarState.IDLE: dict(tint=(255, 255, 255), tint_mix=0.0, scale=1.00, glow=1.00, core_dim=1.00, spin=1.0, think_mix=0.0, trace_mix=0.0, face_mix=0.0, gaze_yaw=0.0, gaze_pitch=0.0),
    AvatarState.LISTENING: dict(tint=(120, 210, 255), tint_mix=0.10, scale=1.10, glow=1.30, core_dim=1.06, spin=0.7, think_mix=0.0, trace_mix=1.0, face_mix=1.0, gaze_yaw=0.0, gaze_pitch=0.0),
    AvatarState.THINKING: dict(tint=(150, 120, 250), tint_mix=0.40, scale=0.94, glow=0.90, core_dim=0.78, spin=1.0, think_mix=1.0, trace_mix=0.0, face_mix=1.0, gaze_yaw=0.35, gaze_pitch=0.22),
    AvatarState.SPEAKING: dict(tint=(255, 255, 255), tint_mix=0.0, scale=1.02, glow=1.15, core_dim=1.04, spin=1.3, think_mix=0.0, trace_mix=1.0, face_mix=1.0, gaze_yaw=0.0, gaze_pitch=0.0),
    AvatarState.NOTIFY: dict(tint=(255, 190, 90), tint_mix=0.85, scale=1.16, glow=1.50, core_dim=1.10, spin=2.0, think_mix=0.0, trace_mix=0.0, face_mix=0.0, gaze_yaw=0.0, gaze_pitch=0.0),
    AvatarState.SUCCESS: dict(tint=(90, 220, 160), tint_mix=0.85, scale=1.08, glow=1.40, core_dim=1.05, spin=1.5, think_mix=0.0, trace_mix=0.0, face_mix=0.0, gaze_yaw=0.0, gaze_pitch=0.0),
    AvatarState.ERROR: dict(tint=(250, 110, 85), tint_mix=0.85, scale=0.95, glow=0.75, core_dim=0.95, spin=0.05, think_mix=0.0, trace_mix=0.0, face_mix=0.0, gaze_yaw=0.0, gaze_pitch=0.0),
}

# Transient states play out and settle back to IDLE on their own; the
# conversational states (listening/thinking/speaking) hold until changed.
TRANSIENT = {AvatarState.NOTIFY: 1.5, AvatarState.SUCCESS: 1.2, AvatarState.ERROR: 2.2}

_STYLE_SPIN = {"breakup": 1.2, "glow": 0.5, "shimmer": 0.55, "orbiter": 0.5}
TRACE_SAMPLES = 72


class AvatarModel:
    """Headless animation state for one avatar. Drive with set_state() and
    advance(dt); read the pose/scalars for rendering."""

    def __init__(self, genome: Genome, vol_min: float = 0.65, vol_max: float = 1.2):
        self.vol_min = vol_min
        self.vol_max = vol_max
        self._amplitude: float | None = None   # external voice envelope, 0..1
        self._spectrum: list[float] | None = None  # live frequency bands
        self._cue: str | None = None    # one-shot sound cue for the renderer

        self.state = AvatarState.IDLE
        self._targets = dict(STATE_TARGETS[AvatarState.IDLE])
        self.cur = {k: (list(v) if isinstance(v, tuple) else float(v))
                    for k, v in self._targets.items()}

        self.t = 0.0
        self.state_t = 0.0
        self.blink_t = 999.0
        self.next_blink = 4.0
        self.shake_t = 999.0
        self.ay = 0.60
        self.ax_tumble = 0.0
        self.spin_impulse = 0.0
        self.sac = [0.0, 0.0]
        self.sac_target = (0.0, 0.0)
        self.next_saccade = 0.0
        self.rings: list[float] = []    # notify-ring birth times (renderer reads)

        self.set_genome(genome)

    # ----------------------------------------------------------------- setup

    def set_genome(self, genome: Genome) -> None:
        self.genome = genome
        self.cluster = geometry.build_cluster(genome, self.vol_min,
                                              max(self.vol_min, self.vol_max))
        self.palette, self.edge_rgb, self.mat = geometry.derive_appearance(genome)
        self._rng = random.Random(genome.mesh_seed ^ 0xFACEFEED)
        self.drift_seed = (genome.mesh_seed % 6283) / 1000.0
        self.thinking_style = THINKING_STYLES[genome.thinking % len(THINKING_STYLES)]
        self.voice_style = VOICE_STYLES[genome.voice % len(VOICE_STYLES)]
        brng = random.Random(genome.mesh_seed ^ 0xB1)
        self.bins = [dict(rate=brng.uniform(2.5, 16.0), phase=brng.uniform(0, math.tau),
                          gain=brng.uniform(0.5, 1.0)) for _ in range(TRACE_SAMPLES)]

    # ------------------------------------------------------------------- API

    def set_state(self, state: AvatarState) -> None:
        if state == self.state:
            return
        self.state = state
        self.state_t = 0.0
        self._targets = dict(STATE_TARGETS[state])
        k_e = self.k_e
        if state == AvatarState.NOTIFY:
            self.rings = [self.t, self.t + 0.18]
            self.spin_impulse = 5.0 * k_e
            self._cue = "notify"
        elif state == AvatarState.SUCCESS:
            self.spin_impulse = 4.5 * k_e  # same excited speed-up as notify
            self._cue = "success"
        elif state == AvatarState.ERROR:
            self.shake_t = 0.0
            self._cue = "error"
        elif state == AvatarState.LISTENING:
            self._cue = "listening"

    def set_amplitude(self, value: float | None) -> None:
        self._amplitude = None if value is None else max(0.0, min(1.0, value))

    def set_spectrum(self, bands: list[float] | None) -> None:
        self._spectrum = bands

    def take_cue(self) -> str | None:
        """Return and clear the pending one-shot sound cue, if any."""
        cue, self._cue = self._cue, None
        return cue

    @property
    def amplitude(self) -> float | None:
        """The externally-fed voice envelope, or None if unset."""
        return self._amplitude

    @property
    def spectrum(self) -> list[float] | None:
        """The externally-fed frequency bands, or None if unset."""
        return self._spectrum

    # ------------------------------------------------------------ properties

    @property
    def k_e(self) -> float:
        """Personality: amplitude of every gesture."""
        return 0.4 + 1.2 * self.genome.express

    @property
    def k_t(self) -> float:
        """Personality: the master clock — frequency of every gesture."""
        return 0.55 + 0.9 * self.genome.tempo

    def speech_env(self) -> float:
        """Voice envelope: live amplitude if fed, else a simulated cadence."""
        if self._amplitude is not None:
            return self._amplitude
        t = self.t
        v = 0.40 * math.sin(t * 7.3) + 0.35 * math.sin(t * 3.1) + 0.25 * math.sin(t * 13.7)
        gate = 0.35 + 0.65 * max(0.0, math.sin(t * 0.9 + 0.6)) ** 0.5
        return max(0.0, v) * gate

    def blink(self) -> float:
        """Brightness multiplier for the current blink (1.0 = eyes open)."""
        if self.blink_t < 0.18:
            return 1.0 - 0.65 * math.sin(math.pi * self.blink_t / 0.18)
        return 1.0

    def bloom(self) -> float:
        """Transient brightness swell for notify/success."""
        b = 1.0
        if self.state == AvatarState.NOTIFY:
            b += 0.8 * self.k_e * math.exp(-self.state_t * 3.0)
        elif self.state == AvatarState.SUCCESS:
            b += (0.5 * self.k_e * math.exp(-self.state_t * 3.0)
                  * (1 + 0.6 * math.sin(self.state_t * 18)))
        return b

    def breath(self) -> float:
        """Slow idle size oscillation, paced by tempo."""
        return 1.0 + 0.030 * math.sin(self.t * 2 * math.pi * self.k_t / 6.5)

    @property
    def ax(self) -> float:
        """Render pitch: resting tilt + a little sway, plus accumulated tumble
        and the (saccade-jittered) gaze pitch when face-locked."""
        fm = self.cur["face_mix"]
        return (self.genome.tilt + 0.20 * math.sin(self.t * 0.31) * (1.0 - 0.9 * fm)
                + self.ax_tumble
                + (self.cur["gaze_pitch"] + self.sac[1] * self.cur["think_mix"]) * fm)

    # ------------------------------------------------------------- advance

    def advance(self, dt: float) -> None:
        self.t += dt
        self.state_t += dt
        self.blink_t += dt
        self.shake_t += dt

        if self.state in TRANSIENT and self.state_t >= TRANSIENT[self.state]:
            self.set_state(AvatarState.IDLE)

        k_t = self.k_t

        if self.state in (AvatarState.IDLE, AvatarState.LISTENING) and self.blink_t > self.next_blink:
            self.blink_t = 0.0
            self.next_blink = self._rng.uniform(3.0, 6.5) / k_t

        # exponential smoothing toward the state targets = free easing
        s = 1.0 - math.exp(-dt * 6.0)
        for key, target in self._targets.items():
            cur = self.cur[key]
            if isinstance(cur, list):
                for i in range(3):
                    cur[i] += (target[i] - cur[i]) * s
            else:
                self.cur[key] += (target - cur) * s

        # tumble: yaw spins with activity; pitch accumulates only while working
        # then eases back to the resting stance. Rates scale by tempo.
        style_mul = _STYLE_SPIN[self.thinking_style]
        self.spin_impulse *= math.exp(-dt * 3.0)
        rate = self.cur["spin"] * (1.0 + self.cur["think_mix"] * (style_mul - 1.0))
        rate += self.spin_impulse
        fm = self.cur["face_mix"]

        # darting gaze while thinking — quick saccades in the down-right corner
        if self.state == AvatarState.THINKING and self.t >= self.next_saccade:
            self.next_saccade = self.t + self._rng.uniform(0.35, 1.1) / k_t
            self.sac_target = (self._rng.uniform(-0.10, 0.18), self._rng.uniform(-0.08, 0.14))
        elif self.state != AvatarState.THINKING:
            self.sac_target = (0.0, 0.0)
        sq = 1.0 - math.exp(-dt * 12.0)
        self.sac[0] += (self.sac_target[0] - self.sac[0]) * sq
        self.sac[1] += (self.sac_target[1] - self.sac[1]) * sq

        self.ay += 0.23 * rate * dt * k_t * (1.0 - fm)
        if fm > 0.01:  # face lock: turn the front (yaw 0) to the gaze target
            gaze = self.cur["gaze_yaw"] + self.sac[0] * self.cur["think_mix"]
            delta = (gaze - self.ay + math.pi) % math.tau - math.pi
            self.ay += delta * (1.0 - math.exp(-dt * 5.0)) * fm
        drive = max(0.0, rate - 1.0) * (1.0 - fm)
        self.ax_tumble += 0.16 * drive * dt * k_t
        if drive < 0.05:  # settle pitch to the nearest full turn = same stance
            self.ax_tumble %= math.tau
            target = 0.0 if self.ax_tumble < math.pi else math.tau
            self.ax_tumble += (target - self.ax_tumble) * (1.0 - math.exp(-dt * 1.2))

        # per-shard orientation drift: free when idle, eased to the canonical
        # pose while face-locked (so the live face matches the portrait)
        for sh in self.cluster:
            if fm < 0.5:
                sh["drift"] = (sh["drift"] + sh["selfr"] * 0.15 * dt * k_t) % math.tau
            else:
                target = 0.0 if sh["drift"] < math.pi else math.tau
                sh["drift"] += (target - sh["drift"]) * (1.0 - math.exp(-dt * 2.5))

        # shard micro-physics (springs + collisions), wander quieted while
        # face-locked; breakup thinking pushes the shards apart rhythmically
        if len(self.cluster) > 1:
            pulse = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(self.t * 1.15 * k_t)) ** 1.8
            sep = 1.0
            if self.thinking_style == "breakup":
                sep += 0.9 * self.cur["think_mix"] * pulse * self.k_e
            geometry.physics_step(self.cluster, dt, sep=sep,
                                  wander_amp=0.30 * (1.0 - 0.75 * fm),
                                  t=self.t, k_t=k_t)

        self.rings = [b for b in self.rings if self.t - b < 1.2]
