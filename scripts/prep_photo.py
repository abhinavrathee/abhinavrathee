"""Prepare Abhinav's light-background headshot for the ASCII SVG generator.

The portrait already has a clean pale background, so this keeps the original
photo treatment, crops a centered square around the head and shoulders, and
uses only Pillow (the reference version's undeclared rembg/OpenCV dependencies
made the generator fail on a fresh machine).

Usage: python scripts/prep_photo.py [input.png] [output.png]
"""
import os
import sys

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "assets", "abhinav-profile.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

image = Image.open(INP).convert("RGB")
width, height = image.size
side = min(width, height)
# Center the crop slightly above the vertical midpoint so the face stays the focus.
left = (width - side) // 2
top = max(0, min(height - side, int((height - side) * 0.38)))
image = image.crop((left, top, left + side, top + side))
image = ImageOps.grayscale(image)
image = ImageOps.autocontrast(image, cutoff=1)
image = ImageEnhance.Contrast(image).enhance(1.12)
image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=115, threshold=3))
image.save(OUT)
print(f"wrote {OUT}: {image.width} x {image.height}")
