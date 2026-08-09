"""Console-script entry points.

Kept separate from `gallery` so the Qt import failure can be turned into a
sentence instead of a traceback. The gallery imports PySide6 at module scope
(its widgets subclass Qt classes, so the import cannot be deferred into a
function), which means someone who installed the core without the `qt` extra
would otherwise meet a bare ModuleNotFoundError naming a package they never
asked for.
"""

from __future__ import annotations

_QT_HINT = (
    "The gallery needs the optional Qt extra, which is not installed.\n"
    "\n"
    '    pip install "ai-identicon[qt]"\n'
    "\n"
    "The core library (genomes and SVG portraits) has no dependencies and\n"
    "works without it — only the live animated widget needs Qt."
)


def gallery() -> int:
    """Launch the interactive gallery. Entry point for `ai-identicon-gallery`."""
    try:
        from .gallery import main
    except ImportError as exc:
        if (exc.name or "").split(".")[0] == "PySide6":
            raise SystemExit(_QT_HINT) from None
        raise
    return main()
