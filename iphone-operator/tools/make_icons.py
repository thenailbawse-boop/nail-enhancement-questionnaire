"""Draws the Creator Reset app icon and Safari extension icons (run: python3 tools/make_icons.py)."""
import os, sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP, BOTTOM = (226, 122, 150), (57, 38, 31)   # rose -> brand brown

def icon(size, rounded=False):
    img = Image.new("RGB", (size, size), BOTTOM)
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        d.line([(0, y), (size, y)], fill=tuple(int(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3)))
    s = size / 1024
    w = max(1, int(34 * s))
    # back card
    d.rounded_rectangle([300*s, 250*s, 760*s, 650*s], radius=60*s, outline=(255, 236, 240), width=w)
    # front card (photo)
    d.rounded_rectangle([230*s, 340*s, 690*s, 760*s], radius=60*s, fill=(255, 250, 250))
    d.polygon([(290*s, 700*s), (420*s, 540*s), (520*s, 640*s), (580*s, 580*s), (640*s, 700*s)], fill=(226, 122, 150))
    d.ellipse([540*s, 400*s, 610*s, 470*s], fill=(57, 38, 31))
    # sparkle
    cx, cy, r = 770*s, 270*s, 120*s
    d.polygon([(cx, cy-r), (cx+r*0.22, cy-r*0.22), (cx+r, cy), (cx+r*0.22, cy+r*0.22),
               (cx, cy+r), (cx-r*0.22, cy+r*0.22), (cx-r, cy), (cx-r*0.22, cy-r*0.22)], fill=(255, 255, 255))
    if rounded:
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size-1, size-1], radius=int(size*0.22), fill=255)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(img, (0, 0), mask)
        return out
    return img

icon(1024).save(os.path.join(ROOT, "App/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png"))
imgdir = os.path.join(ROOT, "SafariExtension/Resources/images")
os.makedirs(imgdir, exist_ok=True)
big = icon(1024, rounded=True)
for n in (48, 96, 128, 256, 512):
    big.resize((n, n), Image.LANCZOS).save(os.path.join(imgdir, f"icon-{n}.png"))
for n in (16, 32):
    big.resize((n, n), Image.LANCZOS).save(os.path.join(imgdir, f"toolbar-{n}.png"))
print("icons written")
