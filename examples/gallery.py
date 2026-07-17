#!/usr/bin/env python
"""Interactive gallery for ai-identicon — built entirely on the public API
(genome / model / widget / portrait / audio).

    pip install -e .[qt]
    python examples/gallery.py

Type a seed (or hit 🎲), watch the states, tweak the genome sliders, and save
SVG portraits. Everything you see is derived from the seed + your overrides.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from ai_identicon.genome import Genome, MATERIALS, THINKING_STYLES, VOICE_STYLES
from ai_identicon.model import AvatarState
from ai_identicon.widget import PresenceWidget
from ai_identicon.audio import SoundBank, MicCapture, HAVE_AUDIO
from ai_identicon.portrait import export_svg

_CAPTION = {
    AvatarState.IDLE: "idle — at rest in its own stance, breathing; blinks now and then",
    AvatarState.LISTENING: "listening — turned to face you; ripples drift in like arriving sound",
    AvatarState.SPEAKING: "speaking — facing you, its voice drawn as a waveform around it",
    AvatarState.NOTIFY: "notify — a chirp and an excited little spin; returns by itself",
    AvatarState.SUCCESS: "success — a warm pulse and spin-up; returns by itself",
    AvatarState.ERROR: "error — seized: rotation frozen, amber, one flinch",
}
_THINKING_CAPTION = {
    "breakup": "thinking (breakup) — comes apart to turn the pieces over, gaze down-right",
    "glow": "thinking (glow) — light building inside each shard: held concentration",
    "shimmer": "thinking (shimmer) — a thought rippling across its surface",
    "orbiter": "thinking (orbiter) — sparks of association circling the pieces",
}


class Demo(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ai-identicon — avatar gallery")
        self.resize(980, 660)
        self.setStyleSheet(
            "Demo{background:#0d1116;} QLabel{color:#8a97a5;font-size:13px;}"
            "QCheckBox{color:#8a97a5;} QLineEdit,QComboBox{background:#1a222c;"
            "color:#c7d2dc;border:1px solid #2a3542;border-radius:4px;padding:3px 6px;}"
            "QPushButton{background:#1a222c;color:#c7d2dc;border:1px solid #2a3542;"
            "border-radius:6px;padding:6px 10px;} QPushButton:hover{background:#24303d;}"
            "QPushButton:checked{background:#2d4256;border-color:#4a6a86;}")

        self._seed = "bmev5p5akc"
        self._sounds = SoundBank(enabled=True)
        self.orb = PresenceWidget(self._build_genome(), sounds=self._sounds)
        self.caption = QLabel()
        self.caption.setAlignment(Qt.AlignCenter)
        self._mic: MicCapture | None = None

        # state buttons
        state_row = QHBoxLayout()
        self._state_btns = {}
        for st in AvatarState:
            b = QPushButton(st.value)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, s=st: self._go(s))
            self._state_btns[st] = b
            state_row.addWidget(b)

        # toggles + view/save
        ctl = QHBoxLayout()
        self.sound_cb = QCheckBox("sound")
        self.sound_cb.setChecked(self._sounds.enabled)
        self.sound_cb.setEnabled(HAVE_AUDIO)
        self.sound_cb.toggled.connect(lambda on: setattr(self._sounds, "enabled", on and HAVE_AUDIO))
        self.mic_cb = QCheckBox("mic")
        self.mic_cb.setEnabled(HAVE_AUDIO)
        self.mic_cb.toggled.connect(self._toggle_mic)
        self._view_btns = {}
        for mode, label in (("white", "view ⬜"), ("black", "view ⬛"), ("color", "view 🎨")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, mo=mode: self._toggle_view(mo))
            self._view_btns[mode] = b
        copy = QPushButton("copy 📋")
        copy.clicked.connect(self._copy)
        save = QPushButton("save SVG")
        save.clicked.connect(self._save)
        for wdg in (self.sound_cb, self.mic_cb):
            ctl.addWidget(wdg)
        ctl.addStretch()
        for b in self._view_btns.values():
            ctl.addWidget(b)
        ctl.addWidget(copy)
        ctl.addWidget(save)

        left = QVBoxLayout()
        left.addWidget(self.orb, 1)
        left.addWidget(self.caption)
        left.addLayout(state_row)
        left.addLayout(ctl)

        # genome panel
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        seed_row = QHBoxLayout()
        self.seed_edit = QLineEdit(self._seed)
        self.seed_edit.editingFinished.connect(self._reseed)
        dice = QPushButton("🎲")
        dice.setFixedWidth(36)
        dice.clicked.connect(self._random_seed)
        seed_row.addWidget(self.seed_edit)
        seed_row.addWidget(dice)
        form.addRow("Seed", seed_row)

        self.sliders = {}

        def sl(label, key, mn, mx, val):
            s = QSlider(Qt.Horizontal)
            s.setRange(mn, mx)
            s.setValue(val)
            s.valueChanged.connect(self._apply)
            self.sliders[key] = s
            form.addRow(label, s)

        g = self.orb.genome
        sl("Faces", "faces", 4, 120, g.faces)
        sl("Shapes", "shapes", 1, 5, g.shapes)
        sl("Fragmentation", "frag", 0, 100, int(g.frag * 100))
        sl("Roughness", "roughness", 0, 100, int(g.roughness * 100))
        sl("Translucency", "translucency", 0, 100, int(g.translucency * 100))
        sl("Hue", "hue", 0, 359, g.hue)
        sl("Colors", "n_colors", 1, 3, g.n_colors)
        self.mat_box = QComboBox()
        self.mat_box.addItems(list(MATERIALS))
        self.mat_box.setCurrentIndex(g.material)
        self.mat_box.currentIndexChanged.connect(self._apply)
        form.addRow("Material", self.mat_box)
        sl("Shine", "shine", 0, 100, int(g.shine * 100))
        sl("Elong X", "ex", 0, 100, int(g.elong[0] * 100))
        sl("Elong Y", "ey", 0, 100, int(g.elong[1] * 100))
        sl("Elong Z", "ez", 0, 100, int(g.elong[2] * 100))
        form.addRow(QLabel("— personality —"))
        sl("Expressive", "express", 0, 100, int(g.express * 100))
        sl("Tempo", "tempo", 0, 100, int(g.tempo * 100))
        sl("Sharpness", "sharp", 0, 100, int(g.sharp * 100))
        self.think_box = QComboBox()
        self.think_box.addItems(list(THINKING_STYLES))
        self.think_box.setCurrentIndex(g.thinking)
        self.think_box.currentIndexChanged.connect(self._apply)
        form.addRow("Thinking", self.think_box)
        self.voice_box = QComboBox()
        self.voice_box.addItems(list(VOICE_STYLES))
        self.voice_box.setCurrentIndex(g.voice)
        self.voice_box.currentIndexChanged.connect(self._apply)
        form.addRow("Voice", self.voice_box)
        form.addRow(QLabel("— presence (volume band) —"))
        for label, key, val in (("Vol min", "vmin", 65), ("Vol max", "vmax", 120)):
            s = QSlider(Qt.Horizontal)
            s.setRange(5, 300)
            s.setValue(val)
            s.valueChanged.connect(self._apply_vol)
            self.sliders[key] = s
            form.addRow(label, s)

        panel = QWidget()
        panel.setFixedWidth(300)
        panel.setLayout(form)
        root = QHBoxLayout(self)
        root.addLayout(left, 1)
        root.addWidget(panel)

        from PySide6.QtCore import QTimer
        self._cap_timer = QTimer(self)
        self._cap_timer.timeout.connect(self._update_caption)
        self._cap_timer.start(150)

    # ---- genome assembly from controls (exercises the overrides overlay) ----

    def _overrides(self) -> dict:
        s = self.sliders
        return dict(
            faces=s["faces"].value(), shapes=s["shapes"].value(),
            frag=s["frag"].value() / 100, roughness=s["roughness"].value() / 100,
            translucency=s["translucency"].value() / 100, hue=s["hue"].value(),
            n_colors=s["n_colors"].value(), material=self.mat_box.currentIndex(),
            shine=s["shine"].value() / 100,
            elong=(s["ex"].value() / 100, s["ey"].value() / 100, s["ez"].value() / 100),
            express=s["express"].value() / 100, tempo=s["tempo"].value() / 100,
            sharp=s["sharp"].value() / 100, thinking=self.think_box.currentIndex(),
            voice=self.voice_box.currentIndex(),
        )

    def _build_genome(self) -> Genome:
        return Genome.from_seed(self._seed)

    def _apply(self):
        self.orb.set_genome(Genome.from_seed(self._seed, overrides=self._overrides()))

    def _apply_vol(self):
        self.orb.model.vol_min = self.sliders["vmin"].value() / 100
        self.orb.model.vol_max = self.sliders["vmax"].value() / 100
        self._apply()

    def _reseed(self):
        self._seed = self.seed_edit.text().strip() or "bmev5p5akc"
        g = Genome.from_seed(self._seed)
        self._sync(g)
        self.orb.set_genome(g)

    def _random_seed(self):
        self._seed = "".join(random.choices("abcdefghjkmnpqrstuvwxyz23456789", k=10))
        self.seed_edit.setText(self._seed)
        self._reseed()

    def _sync(self, g: Genome):
        s = self.sliders
        for k, v in (("faces", g.faces), ("shapes", g.shapes), ("hue", g.hue),
                     ("n_colors", g.n_colors)):
            s[k].blockSignals(True); s[k].setValue(v); s[k].blockSignals(False)
        for k, v in (("frag", g.frag), ("roughness", g.roughness),
                     ("translucency", g.translucency), ("shine", g.shine),
                     ("express", g.express), ("tempo", g.tempo), ("sharp", g.sharp)):
            s[k].blockSignals(True); s[k].setValue(int(v * 100)); s[k].blockSignals(False)
        for k, v in zip(("ex", "ey", "ez"), g.elong):
            s[k].blockSignals(True); s[k].setValue(int(v * 100)); s[k].blockSignals(False)
        for box, idx in ((self.mat_box, g.material), (self.think_box, g.thinking),
                         (self.voice_box, g.voice)):
            box.blockSignals(True); box.setCurrentIndex(idx); box.blockSignals(False)

    # ---- interaction ----

    def _go(self, state: AvatarState):
        for b in self._view_btns.values():
            b.setChecked(False)
        self.orb.set_preview(None)
        self.orb.set_state(state)

    def _toggle_view(self, mode: str):
        if self._view_btns[mode].isChecked():
            for mo, b in self._view_btns.items():
                b.setChecked(mo == mode)
            self.orb.set_preview(mode)
        else:
            self.orb.set_preview(None)

    def _toggle_mic(self, on: bool):
        if on:
            try:
                self._mic = MicCapture(self.orb.model)
                self._mic.start()
            except Exception as exc:
                self.mic_cb.setChecked(False)
                self.caption.setText(f"mic unavailable: {exc}")
        elif self._mic:
            self._mic.stop()
            self._mic = None

    def _copy(self):
        # copy the current portrait variant (or color when showing the live
        # avatar) to the clipboard as a pasteable PNG
        variant = self.orb.preview_mode or "color"
        self.orb.copy_to_clipboard(variant=variant)
        self.caption.setText(f"copied {self._seed} ({variant}) to clipboard — paste anywhere")

    def _save(self):
        outdir = Path(__file__).resolve().parent / "avatars"
        g = self.orb.genome
        for variant in ("black", "white", "color"):
            export_svg(g, outdir / f"{self._seed}-{variant}.svg", variant=variant,
                       vol_min=self.orb.model.vol_min, vol_max=self.orb.model.vol_max)
        self.caption.setText(f"saved {self._seed} black/white/color → examples/avatars/")

    def _update_caption(self):
        pv = self.orb.preview_mode
        st = self.orb.state
        for s, b in self._state_btns.items():
            b.setChecked(pv is None and s == st)
        if pv:
            self.caption.setText(f"portrait — {pv} lines/fill")
        elif st == AvatarState.THINKING:
            self.caption.setText(_THINKING_CAPTION[self.orb.model.thinking_style])
        else:
            self.caption.setText(_CAPTION[st])


def main() -> int:
    app = QApplication(sys.argv)
    Demo().show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
