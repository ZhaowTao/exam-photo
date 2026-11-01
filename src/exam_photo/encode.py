# -*- coding: utf-8 -*-
"""Write a baseline JPEG tuned to match the official tool's output.

The constants below are not guesses.  They were read back out of a file that
the national civil-service registration portal actually accepted, by
dequantising its DQT segments and matching them against the IJG tables:

===============  ==========================================  ============
segment          observed in an accepted upload              conclusion
===============  ==========================================  ============
DQT (luma)       IJG standard table * 1.25, first value 20  quality = 40
DQT (chroma)     IJG standard table * 1.25                  quality = 40
DHT              31 / 181 / 31 / 181 (standard tables)      optimize = False
SOF0 sampling    0x22 0x11 0x11                             subsampling = 4:2:0
APP0 (JFIF)      version 1.1, units=1, 96 x 96 dpi          dpi = (96, 96)
SOF0 type        baseline, 295 x 413                        progressive = False
===============  ==========================================  ============

``quality = 40`` specifically: libjpeg maps quality < 50 through
``5000 / quality``, so only ``40`` lands on a scaling factor of exactly 125.

Two encoder settings matter far more than the quality number and are easy to
get wrong:

* ``optimize=True`` emits *custom* Huffman tables (segment sizes 28/62/27/48).
  Any other encoder in the chain recognises immediately that this is not what
  the official tool produces.  We need ``optimize=False`` — the standard
  31/181/31/181 tables.
* JPEG has no DPI field except in the JFIF header, and Pillow defaults to
  unitless 1x1.  The official output carries ``units=1, 96x96``.  A file that
  looks identical in every image viewer still differs here in the first 20
  bytes.

The byte budget is applied afterwards as a safety net only: with the correct
parameters a 295x413 portrait lands around 6.5 KB, comfortably under the
10 KB ceiling.  We only step the quality down if a pathological source image
blows past the budget.
"""

import io
import os

from PIL import Image

# Parameters measured from an accepted upload — do not "tune" these.
OFFICIAL_QUALITY = 40
OFFICIAL_DPI = (96, 96)
OFFICIAL_SUBSAMPLING = 2  # 4:2:0
OFFICIAL_OPTIMIZE = False  # standard Huffman tables, not custom ones


def encode_jpeg(im: Image.Image, max_bytes: int,
                min_quality: int = 20) -> tuple:
    """Return ``(quality, data)``, preferring the official encoding.

    The first attempt always uses the exact official parameters.  Only if that
    exceeds ``max_bytes`` do we walk the quality down, keeping every other
    setting untouched so the file stays structurally identical.
    """
    ladder = [OFFICIAL_QUALITY]
    ladder += [q for q in range(OFFICIAL_QUALITY - 2, min_quality - 1, -2)]

    best = None
    for quality in ladder:
        buf = io.BytesIO()
        im.save(
            buf,
            format="JPEG",
            quality=quality,
            optimize=OFFICIAL_OPTIMIZE,
            progressive=False,
            subsampling=OFFICIAL_SUBSAMPLING,
            dpi=OFFICIAL_DPI,
        )
        data = buf.getvalue()
        if len(data) <= max_bytes:
            best = (quality, data)
            break

    if best is None:
        # Degenerate case: even min_quality overflows.  Emit the smallest file
        # we can rather than failing, and let the validator complain.
        buf = io.BytesIO()
        im.save(
            buf,
            format="JPEG",
            quality=min_quality,
            optimize=OFFICIAL_OPTIMIZE,
            progressive=False,
            subsampling=OFFICIAL_SUBSAMPLING,
            dpi=OFFICIAL_DPI,
        )
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
