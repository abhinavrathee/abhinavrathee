"""Prepare the full outdoor portrait for the expanded README header.

This version deliberately keeps the trees and leaves. They add depth and
natural green highlights to the full-colour dot-matrix treatment; only the
crop is adjusted so Abhinav remains the visual focus.

Usage: python scripts/prepare_extended_portrait.py [input.jpg] [output.png]
"""
import os
import sys

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "..", "assets", "portraits", "portrait-garden.jpg"
)
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    HERE, "..", "assets", "extended", "portrait-source.png"
)

image = ImageOps.exif_transpose(Image.open(INP)).convert("RGB")
width, height = image.size

# This portrait is already square, but a vertical crop lets the person occupy
# the frame while preserving enough foliage to read as an intentional setting.
left = round(width * 0.12)
right = round(width * 0.88)
top = round(height * 0.03)
bottom = height
image = image.crop((left, top, right, bottom)).resize((820, 1120), Image.Resampling.LANCZOS)
image = ImageOps.autocontrast(image, cutoff=1)
image = ImageEnhance.Contrast(image).enhance(1.08)
image = image.filter(ImageFilter.UnsharpMask(radius=1.1, percent=105, threshold=3))
image.save(OUT)
print(f"wrote {OUT}: {image.width} x {image.height}; full outdoor scene retained")
