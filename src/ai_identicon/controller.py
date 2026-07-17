"""Avatar controller — maps assistant-lifecycle events to avatar states.

Keeping this mapping in one small adapter means the state logic lives neither
in the LLM/agent loop nor in the renderer: the app emits semantic lifecycle
events ("thinking", "streaming", "done", ...) and audio, and the controller
translates them into AvatarModel calls. Swap the sink (a headless model or the
live widget) without touching the event source.

The sink is anything with `set_state` / `set_amplitude` / `set_spectrum`
(an AvatarModel or a PresenceWidget). Pure Python — no Qt.
"""

from __future__ import annotations

from .model import AvatarState

# Semantic assistant-lifecycle events → avatar state. Several event names map
# to one state on purpose (an app's "generating"/"tool_call" are both "the
# assistant is working" = thinking).
EVENT_STATES = {
    "idle": AvatarState.IDLE,
    "ready": AvatarState.IDLE,
    "listening": AvatarState.LISTENING,
    "recording": AvatarState.LISTENING,
    "receiving": AvatarState.LISTENING,
    "thinking": AvatarState.THINKING,
    "generating": AvatarState.THINKING,
    "tool_call": AvatarState.THINKING,
    "working": AvatarState.THINKING,
    "speaking": AvatarState.SPEAKING,
    "streaming": AvatarState.SPEAKING,
    "notify": AvatarState.NOTIFY,
    "attention": AvatarState.NOTIFY,
    "done": AvatarState.SUCCESS,
    "success": AvatarState.SUCCESS,
    "error": AvatarState.ERROR,
    "failed": AvatarState.ERROR,
}


class AvatarController:
    """Translate assistant-lifecycle events + audio into avatar state.

    Notify/success/error are transient in the model (they play out and return
    to idle on their own), so after them the app can simply resume emitting
    whatever the assistant is actually doing.
    """

    def __init__(self, sink):
        self._sink = sink

    def event(self, name: str) -> AvatarState:
        """Apply a lifecycle event by name. Returns the state it mapped to.
        Unknown names raise KeyError (fail loud — a typo shouldn't be silent)."""
        state = EVENT_STATES[name]
        self._sink.set_state(state)
        return state

    def set_state(self, state: AvatarState) -> None:
        """Set an avatar state directly (bypassing the event vocabulary)."""
        self._sink.set_state(state)

    def on_audio(self, amplitude: float | None = None,
                 spectrum: list[float] | None = None) -> None:
        """Feed the current voice envelope and/or frequency bands."""
        if amplitude is not None:
            self._sink.set_amplitude(amplitude)
        if spectrum is not None:
            self._sink.set_spectrum(spectrum)

    def clear_audio(self) -> None:
        self._sink.set_amplitude(None)
        self._sink.set_spectrum(None)

    # convenience shortcuts for the common lifecycle points
    def idle(self):
        return self.event("idle")

    def listening(self):
        return self.event("listening")

    def thinking(self):
        return self.event("thinking")

    def speaking(self):
        return self.event("speaking")

    def notify(self):
        return self.event("notify")

    def success(self):
        return self.event("done")

    def error(self):
        return self.event("error")
