"""Copy an avatar to the system clipboard as a pasteable image (Qt extra).

PNG is the right format for this: it's the one clipboard image type every
target understands (Obsidian, MS Teams, Signal, Discord, Slack, docs...) and
it keeps transparency, so the portrait drops onto any background. SVG on the
clipboard is unreliable in those apps, so we put PNG on the clipboard and
merely *attach* the SVG as a bonus MIME type for the rare consumer that wants
vectors.

Needs a running QGuiApplication (any Qt app). Rasterization uses QtSvg.
"""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QMimeData
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from .genome import Genome
from .portrait import color_svg, line_art_svg


def _svg_for(genome: Genome, variant: str, size: int, vol_min: float, vol_max: float) -> str:
    if variant == "color":
        return color_svg(genome, size, vol_min=vol_min, vol_max=vol_max)
    return line_art_svg(genome, variant, size, vol_min=vol_min, vol_max=vol_max)


def render_png(genome: Genome, size: int = 512, variant: str = "color",
               background: str | None = None,
               vol_min: float = 0.65, vol_max: float = 1.2) -> QImage:
    """Rasterize an avatar portrait to a QImage (ARGB32).

    variant: "color" (opaque, reads on any background — the best default for
    pasting), or "black"/"white" line-art. background: a color string to fill
    behind it, or None for transparent (recommended — chat apps composite it
    onto their own background)."""
    svg = _svg_for(genome, variant, size, vol_min, vol_max)
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(QColor(background) if background else QColor(0, 0, 0, 0))
    p = QPainter(img)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    return img


def copy_to_clipboard(genome: Genome, size: int = 512, variant: str = "color",
                      background: str | None = None,
                      vol_min: float = 0.65, vol_max: float = 1.2) -> None:
    """Put the avatar on the system clipboard as a pasteable PNG image (with
    the SVG attached as a bonus MIME type). Requires a running QGuiApplication."""
    clip = QGuiApplication.clipboard()
    if clip is None:
        raise RuntimeError("no QGuiApplication — clipboard needs a running Qt app")
    img = render_png(genome, size, variant, background, vol_min, vol_max)

    mime = QMimeData()
    mime.setImageData(img)  # what most apps read for "paste image"
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")   # explicit image/png for apps that look for it
    buf.close()
    mime.setData("image/png", ba)
    svg = _svg_for(genome, variant, size, vol_min, vol_max)
    mime.setData("image/svg+xml", QByteArray(svg.encode()))  # bonus for vector-aware apps
    clip.setMimeData(mime)
