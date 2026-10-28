# -*- coding: utf-8 -*-
"""Write the cleanest possible baseline JPEG under a byte budget."""

import io
import os

from PIL import Image


def encode_jpeg(im: Image.Image, max_bytes: int,
                min_quality: int = 20) -> tuple:
    """Return ``(quality, data)`` — the highest quality that fits the budget.

    Deliberately baseline, no EXIF, no ICC, no restart markers: several
    provincial registration portals still run JPEG parsers that choke on
    progressive files or on APP1/APP2 segments.
    """
    best = None
    for quality in range(95, min_quality - 1, -1):
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True,
                progressive=False, subsampling=0 if quality >= 85 else 2)
        data = buf.getvalue()
        if len(data) <= max_bytes:
            best = (quality, data)
            break

    if best is None:
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=min_quality, optimize=True,
                progressive=False, subsampling=2)
        best = (min_quality, buf.getvalue())
    return best


def save(im: Image.Image, path: str, max_bytes: int) -> dict:
    quality, data = encode_jpeg(im, max_bytes)
    with open(path, "wb") as fh:
        fh.write(data)
    return {
        "path": os.path.abspath(path),
        "quality": quality,
        "bytes": len(data),
        "kb": round(len(data) / 1024, 1),
        "within_budget": len(data) <= max_bytes,
    }
