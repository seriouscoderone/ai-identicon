"""Tests for the event→state controller (pure, no Qt)."""

from __future__ import annotations

import pytest

from ai_identicon.genome import Genome
from ai_identicon.model import AvatarModel, AvatarState
from ai_identicon.controller import AvatarController, EVENT_STATES


def _ctl():
    return AvatarController(AvatarModel(Genome.from_seed("bmev5p5akc")))


def test_events_map_to_expected_states():
    c = _ctl()
    assert c.event("thinking") == AvatarState.THINKING
    assert c.event("streaming") == AvatarState.SPEAKING
    assert c.event("done") == AvatarState.SUCCESS
    assert c.event("failed") == AvatarState.ERROR
    assert c._sink.state == AvatarState.ERROR


def test_synonyms_share_states():
    c = _ctl()
    assert EVENT_STATES["generating"] == EVENT_STATES["tool_call"] == AvatarState.THINKING
    assert EVENT_STATES["recording"] == EVENT_STATES["listening"] == AvatarState.LISTENING


def test_unknown_event_raises():
    with pytest.raises(KeyError):
        _ctl().event("wat")


def test_audio_passthrough():
    c = _ctl()
    c.on_audio(amplitude=0.5, spectrum=[0.1, 0.2, 0.3])
    assert c._sink.amplitude == 0.5
    assert c._sink.spectrum == [0.1, 0.2, 0.3]
    c.clear_audio()
    assert c._sink.amplitude is None and c._sink.spectrum is None


def test_shortcuts():
    c = _ctl()
    c.listening()
    assert c._sink.state == AvatarState.LISTENING
    c.thinking()
    assert c._sink.state == AvatarState.THINKING
