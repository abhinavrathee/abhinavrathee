"""Prepare Abhinav's outdoor portrait for the ASCII SVG generator.

The source has a detailed leafy background.  OpenCV's seeded GrabCut pass keeps
the face, kurta, and crossed arms while making everything else white; white
pixels become spaces in ``make_ascii_svg.py``.  This gives the terminal art a
clear silhouette instead of turning the trees into visual noise.

Usage: python scripts/prep_photo.py [input.jpg] [output.png]
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "..", "assets", "portraits", "portrait-garden.jpg"
)
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

image = Image.open(INP).convert("RGB")
width, height = image.size
side = min(width, height)
left = (width - side) // 2
top = max(0, min(height - side, int((height - side) * 0.18)))
image = image.crop((left, top, left + side, top + side)).resize((900, 900), Image.Resampling.LANCZOS)

# Seed GrabCut with the known composition of this portrait: face in the upper
# centre, then shoulders and crossed arms through the lower half.  The broad
# polygon is deliberately *probable* foreground so the edge is still chosen
# from the photo rather than drawn as a hard cut-out.
bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
mask = np.full((900, 900), cv2.GC_BGD, dtype=np.uint8)
mask[68:895, 120:785] = cv2.GC_PR_BGD
cv2.ellipse(mask, (450, 275), (155, 195), 0, 0, 360, cv2.GC_FGD, -1)
body = np.array([[326, 390], [588, 390], [770, 895], [144, 895]], dtype=np.int32)
cv2.fillConvexPoly(mask, body, cv2.GC_PR_FGD)
mask[510:895, 280:635] = cv2.GC_FGD

bg_model = np.zeros((1, 65), np.float64)
fg_model = np.zeros((1, 65), np.float64)
cv2.grabCut(bgr, mask, None, bg_model, fg_model, 6, cv2.GC_INIT_WITH_MASK)
foreground = np.where(
    (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
).astype(np.uint8)

# GrabCut can retain high-contrast leaves directly behind the hair.  Constrain
# it to a soft, hand-tuned envelope of the subject's silhouette; the detailed
# edge still comes from GrabCut, while the foliage has no route into the art.
silhouette = np.zeros_like(foreground)
head = np.array(
    [[338, 125], [402, 105], [486, 108], [545, 145], [578, 218],
     [575, 310], [544, 385], [500, 435], [435, 455], [368, 420],
     [318, 355], [300, 270], [306, 190]], dtype=np.int32
)
torso = np.array(
    [[365, 395], [532, 395], [630, 448], [714, 560], [760, 795],
     [705, 895], [175, 895], [190, 690], [236, 562], [292, 470]],
    dtype=np.int32,
)
cv2.fillConvexPoly(silhouette, head, 255)
cv2.fillConvexPoly(silhouette, torso, 255)
foreground = cv2.bitwise_and(foreground, silhouette)

# Remove detached leaf fragments while preserving the connected portrait.
components, labels, stats, _ = cv2.connectedComponentsWithStats(foreground, 8)
if components > 1:
    largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    foreground = np.where(labels == largest, 255, 0).astype(np.uint8)
foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
foreground = cv2.GaussianBlur(foreground, (0, 0), 1.2)

rgb = np.asarray(image).astype(np.float32)
alpha = (foreground.astype(np.float32) / 255.0)[..., None]
isolated = (rgb * alpha + 255 * (1 - alpha)).astype(np.uint8)
# Keep an alpha channel for the dot-matrix renderer.  The RGB pixels outside
# the subject stay white so the original ASCII renderer (which reads luminance
# only) continues to treat them as spaces.
gray = Image.fromarray(isolated).convert("L")
gray = ImageOps.autocontrast(gray, cutoff=1)
gray = ImageEnhance.Contrast(gray).enhance(1.18)
gray = gray.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
alpha_image = Image.fromarray(foreground)
image = Image.merge("RGBA", (gray, gray, gray, alpha_image))
image.save(OUT)
print(f"wrote {OUT}: {image.width} x {image.height}; foreground {foreground.mean() / 255:.1%}")
