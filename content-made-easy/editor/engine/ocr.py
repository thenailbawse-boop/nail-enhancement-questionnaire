#!/usr/bin/env python3
"""Prints the text lines it can read in an image, with their boxes (0..1, top-left origin), as JSON.
The same output as ocr.swift, for computers that aren't Macs (Linux, Windows, cloud sessions).
Uses RapidOCR, a free text reader that runs on the computer itself. Its models come inside the
package from PyPI, so nothing else downloads. Usage: ocr.py IMAGE"""
import json, sys


def read(path):
    from PIL import Image
    from rapidocr_onnxruntime import RapidOCR
    W, H = Image.open(path).size
    found, _ = RapidOCR()(path)
    out = []
    for box, text, conf in found or []:
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        x0, y0, x1, y1 = max(min(xs), 0), max(min(ys), 0), min(max(xs), W), min(max(ys), H)
        out.append({"text": text, "conf": float(conf), "x": x0 / W, "y": y0 / H, "w": (x1 - x0) / W, "h": (y1 - y0) / H})
    return out


if __name__ == "__main__":
    try:
        print(json.dumps(read(sys.argv[1])))
    except Exception:
        print("[]")
