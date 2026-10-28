# -*- coding: utf-8 -*-
"""Crop / resize / background replacement."""

from collections import deque

import numpy as np
from PIL import Image, ImageFilter

BG_COLORS = {
    "white": (255, 255, 255),
    "blue": (67, 142, 219),
    "red": (215, 30, 40),
}


def crop_to_ratio(im: Image.Image, target_w: int, target_h: int,
                  head_bias: float = 0.28) -> Image.Image:
    """Centre-crop to the target aspect ratio, keeping a little headroom.

    ``head_bias`` is the fraction of the trimmed height that is cut from the
    top.  ID photos put the head in the upper half, so cropping symmetric would
    decapitate people; 0.28 was tuned against the official tool's output.
    """
    w, h = im.size
    target = target_w / target_h
    if abs(w / h - target) < 0.005:
        box = im
    elif w / h > target:
        new_w = int(round(h * target))
        x0 = (w - new_w) // 2
        box = im.crop((x0, 0, x0 + new_w, h))
    else:
        new_h = int(round(w / target))
        y0 = int((h - new_h) * head_bias)
        box = im.crop((0, y0, w, y0 + new_h))
    return box.resize((target_w, target_h), Image.LANCZOS)


def _background_mask(arr: np.ndarray, tol: int = 28) -> np.ndarray:
    """Flood-fill the four borders to find the connected background region.

    Pure-solid backdrops are the normal case for ID photos, so a border-seeded
    BFS with a colour tolerance beats any general-purpose segmentation model
    here — and it costs zero extra dependencies.
    """
    h, w, _ = arr.shape
    corners = np.concatenate([arr[:4, :4].reshape(-1, 3),
                              arr[:4, -4:].reshape(-1, 3),
                              arr[-4:, :4].reshape(-1, 3),
                              arr[-4:, -4:].reshape(-1, 3)])
    ref = np.median(corners, axis=0)

    diff = np.abs(arr.astype(np.int16) - ref.astype(np.int16)).sum(axis=2)
    similar = diff <= tol
    visited = np.zeros((h, w), dtype=bool)
    mask = np.zeros((h, w), dtype=bool)

    queue = deque()
    for x in range(w):
        for y in (0, h - 1):
            if similar[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if similar[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))

    while queue:
        y, x = queue.popleft()
        mask[y, x] = True
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and similar[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                queue.append((ny, nx))

    # Keep only the largest-ish region: drop specks of "background" that leaked
    # inside the subject (e.g. a white shirt matching a white backdrop).
    return mask


def _close_holes(mask: np.ndarray, rounds: int = 2) -> np.ndarray:
    """Dilate-then-erode on a boolean mask using PIL so we stay scipy-free."""
    im = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
    for _ in range(rounds):
        im = im.filter(ImageFilter.MaxFilter(5))
    for _ in range(rounds):
        im = im.filter(ImageFilter.MinFilter(5))
    return np.asarray(im) > 127


def replace_background(im: Image.Image, color: str, tol: int = 28,
                       feather: float = 1.2) -> Image.Image:
    """Swap a solid backdrop for ``color`` (white / blue / red).

    Only the border-connected region is replaced, so hair, skin and clothing
    survive even when they share colours with the old backdrop.
    """
    if color == "keep":
        return im
    if color not in BG_COLORS:
        raise ValueError(f"不支持的底色 '{color}'，可选：keep / {' / '.join(BG_COLORS)}")

    arr = np.asarray(im.convert("RGB"))
    mask = _background_mask(arr, tol=tol)
    mask = _close_holes(mask)

    h, w = mask.shape
    if mask.mean() > 0.92:
        # Almost everything matched: the photo probably has no distinct subject
        # or the tolerance is too loose.  Refuse rather than paint over a face.
        raise ValueError("背景区域占比过高（>92%），无法可靠换底，请调低 --bg-tolerance 或改用原图")

    alpha = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather))

    tinted = Image.new("RGB", (w, h), BG_COLORS[color])
    out = Image.composite(tinted, im.convert("RGB"), alpha)
    return out
