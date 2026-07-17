"""ai-identicon — generative, animated avatars for AI agents.

A deterministic avatar grown from a seed string (an agent id, an AID, a
username — anything stable): an irregular faceted "presence" that reads as an
object with character, never a face. Same seed → same avatar, forever, under a
given ALGO_VERSION.

Layers (the core is pure-Python, zero dependencies):

* genome     — identity: frozen-versioned, brand-constrainable, override-able
* geometry   — pure math: shard meshes, cluster layout, physics, shading
* model      — headless behavior/state machine (advance by dt; read the pose)
* portrait   — static SVG portraits (line-art + filled color) for profile pics
* controller — map assistant-lifecycle events → avatar states

Optional Qt extra (`pip install ai-identicon[qt]`):

* widget     — live animated QWidget renderer
* audio      — synthesized state chirps + live-mic spectrum

The avatar is an identity *affordance*, not a security control: a look-alike
is grindable, so never let it stand in for a verifiable identifier.
"""

from .genome import (
    ALGO_VERSION,
    Brand,
    Genome,
    HUE_BUCKETS,
    MATERIALS,
    MATERIAL_PARAMS,
    THINKING_STYLES,
    VOICE_STYLES,
)
from .model import AvatarModel, AvatarState
from .portrait import color_svg, export_svg, line_art_svg
from .controller import AvatarController

__version__ = "0.5.0"

__all__ = [
    "__version__",
    "ALGO_VERSION",
    "Brand",
    "Genome",
    "HUE_BUCKETS",
    "MATERIALS",
    "MATERIAL_PARAMS",
    "THINKING_STYLES",
    "VOICE_STYLES",
    "AvatarModel",
    "AvatarState",
    "AvatarController",
    "color_svg",
    "line_art_svg",
    "export_svg",
]
