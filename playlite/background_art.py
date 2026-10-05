"""Prepare dimmed background artwork without blocking GUI animations."""
from PIL import Image, ImageFilter, ImageChops
from PyQt6.QtGui import QImage


def prepare(source, blur, base_colour):
    if isinstance(source, str):
        with Image.open(source) as opened:
            artwork = opened.convert('RGBA')
    else:
        image = source.convertToFormat(QImage.Format.Format_RGBA8888)
        artwork = Image.frombytes('RGBA', (image.width(), image.height()),
                                  image.constBits().asstring(image.sizeInBytes()))
    artwork.thumbnail((1000, 1000))
    if blur:
        artwork = artwork.filter(ImageFilter.GaussianBlur(max(0, min(100, blur))))
    artwork.putalpha(artwork.getchannel('A').point(lambda value: round(value * .16)))
    dimmed = Image.alpha_composite(Image.new('RGBA', artwork.size, base_colour), artwork).convert('RGB')
    noise = Image.effect_noise(dimmed.size, .65).convert('RGB')
    rendered = ImageChops.add(dimmed, noise, offset=-128)
    data = rendered.tobytes()
    return QImage(data, rendered.width, rendered.height, rendered.width * 3,
                  QImage.Format.Format_RGB888).copy()
