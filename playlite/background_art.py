"""Prepare dimmed background artwork without blocking GUI animations."""
from PIL import Image, ImageFilter
from PyQt6.QtGui import QImage


def prepare(source, blur, base_colour, darkness=84, target=None):
    if isinstance(source, str):
        with Image.open(source) as opened:
            artwork = opened.convert('RGBA')
    else:
        image = source.convertToFormat(QImage.Format.Format_RGBA8888)
        artwork = Image.frombytes('RGBA', (image.width(), image.height()),
                                  image.constBits().asstring(image.sizeInBytes()))
    if target:
        # Keep the complete source frame; viewport cropping belongs to the painter.
        # A stable screen-sized image avoids re-cropping after each window resize.
        edge = max(1, max(int(value) for value in target))
        scale = edge / max(artwork.size)
        artwork = artwork.resize(tuple(max(1, round(value * scale)) for value in artwork.size),
                                 Image.Resampling.LANCZOS)
    else:
        artwork.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    if blur:
        # Match the former 1000-pixel preview's apparent blur at display resolution.
        radius = max(0, min(100, blur)) * max(artwork.size) / 1000
        artwork = artwork.filter(ImageFilter.GaussianBlur(radius))
    visibility = 1 - max(0, min(100, darkness)) / 100
    artwork.putalpha(artwork.getchannel('A').point(lambda value: round(value * visibility)))
    dimmed = Image.alpha_composite(Image.new('RGBA', artwork.size, base_colour), artwork).convert('RGB')
    rendered = dimmed
    data = rendered.tobytes()
    return QImage(data, rendered.width, rendered.height, rendered.width * 3,
                  QImage.Format.Format_RGB888).copy()
