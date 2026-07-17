"""Avatar audio layer — synthesized state chirps and live-mic analysis.

This is the one part of the library that needs Qt (QtMultimedia), so it is an
optional extra. `SoundBank` synthesizes the little state cues on the fly (no
asset files); `MicCapture` turns the default input device into an envelope +
12-band spectrum that drives the speaking waveform. Both degrade gracefully
when QtMultimedia is unavailable.

The target of `MicCapture` is anything with `set_amplitude(float|None)` and
`set_spectrum(list|None)` — i.e. an AvatarModel or the live widget.
"""

from __future__ import annotations

import math
import struct
import tempfile
import wave
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl

try:
    from PySide6.QtMultimedia import QSoundEffect

    HAVE_AUDIO = True
except ImportError:  # QtMultimedia is optional
    HAVE_AUDIO = False


def synth_wav(path: Path, segments: list[tuple[float, float, float]], rate: int = 44100) -> None:
    """Write a little sine chime: segments of (freq_hz, seconds, amplitude 0..1).

    freq 0 = silence gap. Each tone gets a fast attack and a natural decay,
    which is what makes it read as a friendly "chirp" instead of an alarm.
    """
    frames = bytearray()
    for freq, dur, amp in segments:
        n = int(rate * dur)
        attack = max(1, int(rate * 0.008))
        for i in range(n):
            env = min(1.0, i / attack) * (1.0 - i / n) ** 1.6
            val = int(32767 * amp * env * math.sin(2 * math.pi * freq * i / rate)) if freq else 0
            frames += struct.pack("<h", val)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


class SoundBank:
    """Synthesizes and plays the state chirps. Silent without QtMultimedia."""

    RECIPES = {
        # two rising tones — the Star Trek "bippity-boop" acknowledgment family
        "notify": [(880.0, 0.09, 0.38), (0.0, 0.03, 0.0), (1318.5, 0.16, 0.38)],
        "success": [(659.3, 0.07, 0.32), (987.8, 0.13, 0.32)],
        "error": [(233.1, 0.12, 0.40), (0.0, 0.04, 0.0), (196.0, 0.20, 0.40)],
        "listening": [(1174.7, 0.06, 0.22)],
    }

    def __init__(self, enabled: bool = True, cache_dir: Path | None = None):
        self.enabled = enabled and HAVE_AUDIO
        self._effects = {}
        if not self.enabled:
            return
        sound_dir = cache_dir or (Path(tempfile.gettempdir()) / "ai_identicon_sounds")
        sound_dir.mkdir(parents=True, exist_ok=True)
        for name, segments in self.RECIPES.items():
            wav = sound_dir / f"{name}.wav"
            if not wav.exists():
                synth_wav(wav, segments)
            fx = QSoundEffect()
            fx.setSource(QUrl.fromLocalFile(str(wav)))
            fx.setVolume(0.45)
            self._effects[name] = fx

    def play(self, name: str) -> None:
        if self.enabled and name in self._effects:
            self._effects[name].play()


class MicCapture:
    """Live mic → envelope + 12 Goertzel frequency bands driving a target.

    Pure-Python analysis (no numpy): RMS envelope plus one Goertzel filter
    per band, log-spaced 120 Hz–3.2 kHz, over the newest ~64 ms of audio.
    The target needs `set_amplitude` and `set_spectrum`.
    """

    BANDS = 12
    RATE = 16000

    def __init__(self, target):
        from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices

        device = QMediaDevices.defaultAudioInput()
        if device.isNull():
            raise RuntimeError("no audio input device")
        fmt = QAudioFormat()
        fmt.setSampleRate(self.RATE)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.Int16)
        self._target = target
        self._source = QAudioSource(device, fmt)
        self._io = None
        self._buf = bytearray()
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._io = self._source.start()
        self._timer.start(33)

    def stop(self) -> None:
        self._timer.stop()
        self._source.stop()
        self._io = None
        self._target.set_amplitude(None)
        self._target.set_spectrum(None)

    def _poll(self) -> None:
        if self._io is None:
            return
        data = self._io.readAll().data()
        if data:
            self._buf += data
        if len(self._buf) > 8192:
            self._buf = self._buf[-8192:]
        if len(self._buf) < 2048:
            return
        raw = bytes(self._buf[-2048:])  # newest 1024 samples (~64 ms)
        samples = struct.unpack(f"<{len(raw) // 2}h", raw)
        rms = math.sqrt(sum(x * x for x in samples) / len(samples)) / 32768.0
        env = min(1.0, rms * 9.0)
        self._target.set_amplitude(env)

        n = len(samples)
        powers = []
        for bi in range(self.BANDS):
            freq = 120.0 * (3200.0 / 120.0) ** (bi / (self.BANDS - 1))
            cw = 2.0 * math.cos(math.tau * freq / self.RATE)
            s1 = s2 = 0.0
            for x in samples:
                s0 = x + cw * s1 - s2
                s2 = s1
                s1 = s0
            powers.append(max(0.0, s1 * s1 + s2 * s2 - cw * s1 * s2) / (n * n))
        peak = max(powers) or 1.0
        self._target.set_spectrum([min(1.0, (pw / peak) ** 0.5 * env * 1.6) for pw in powers])
