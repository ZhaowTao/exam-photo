# -*- coding: utf-8 -*-
"""Validation rules mirroring what the official tool and review portals check."""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from PIL import Image

JPEG_NAMES = {"JPEG", "MPO"}


@dataclass
class CheckResult:
    ok: bool = True
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def fail(self, msg: str) -> None:
        self.ok = False
        self.issues.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "issues": self.issues,
            "warnings": self.warnings,
            "meta": self.meta,
        }


def _corner_pixels(arr: np.ndarray, ratio: float = 0.12) -> np.ndarray:
    h, w, _ = arr.shape
    k = max(4, int(min(h, w) * ratio))
    return np.concatenate([
        arr[:k, :k].reshape(-1, 3),
        arr[:k, -k:].reshape(-1, 3),
        arr[-k:, :k].reshape(-1, 3),
        arr[-k:, -k:].reshape(-1, 3),
    ])


def classify_background(arr: np.ndarray) -> str:
    """Return one of: white / blue / red / unknown."""
    med = np.median(_corner_pixels(arr), axis=0)
    r, g, b = float(med[0]), float(med[1]), float(med[2])
    bright = (r + g + b) / 3.0

    if bright > 225 and (max(r, g, b) - min(r, g, b)) < 18:
        return "white"
    if b > 110 and b - r > 35 and b > g + 12:
        return "blue"
    if r > 110 and r - b > 45 and r - g > 45:
        return "red"
    return "unknown"


def check_background(arr: np.ndarray, res: CheckResult, allowed=("white", "blue")) -> None:
    kind = classify_background(arr)
    med = np.median(_corner_pixels(arr), axis=0)
    res.meta["background"] = kind
    res.meta["background_rgb"] = [round(float(v)) for v in med]
    if kind == "unknown":
        r, g, b = med
        res.warn(
            f"背景中位色 RGB({r:.0f},{g:.0f},{b:.0f}) 既非纯白也非标准蓝/红，"
            "官方工具会直接拒收，建议换纯色底证件照"
        )
    elif kind not in allowed:
        res.warn(f"底色判定为 {kind}，但该考试要求 {allowed}，请确认公告")


def check_face_heuristic(im: Image.Image, res: CheckResult) -> None:
    """Cheap 'is there a face here' heuristic — no OpenCV, no model download.

    The official tool runs a Haar cascade and rejects photos with zero or
    more-than-one face.  We can't replicate that reliably without OpenCV, so we
    only flag images whose centre region looks as flat as the background.
    """
    gray = np.asarray(im.convert("L"), dtype=np.float32)
    h, w = gray.shape
    center = gray[int(h * 0.15):int(h * 0.55), int(w * 0.30):int(w * 0.70)]
    border = np.concatenate([gray[:int(h * 0.08), :].ravel(),
                             gray[:, :int(w * 0.06)].ravel()])
    if center.size == 0 or border.size == 0:
        return
    ratio = float(center.std() / (border.std() + 1e-6))
    res.meta["face_contrast_ratio"] = round(ratio, 2)
    if ratio < 2.0:
        res.warn(f"画面中部细节/背景对比仅 {ratio:.2f}，可能不是正面人像照片")


def jpeg_segments(path: str) -> List[str]:
    names = {
        0xE0: "JFIF", 0xE1: "EXIF", 0xE2: "ICC", 0xEE: "Adobe",
        0xC0: "SOF0", 0xC1: "SOF1", 0xC2: "SOF2", 0xC4: "DHT",
        0xDB: "DQT", 0xDD: "DRI", 0xDA: "SOS",
    }
    with open(path, "rb") as fh:
        data = fh.read()
    i, segs = 2, []
    while i < len(data) - 1:
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker == 0xDA:
            segs.append("SOS")
            break
        if marker in (0xD8, 0xD9):
            i += 2
            continue
        length = int.from_bytes(data[i + 2:i + 4], "big")
        segs.append(names.get(marker, f"{marker:02X}"))
        i += 2 + length
    return segs


def validate_file(
    path: str,
    expect_w: Optional[int] = None,
    expect_h: Optional[int] = None,
    max_kb: Optional[float] = None,
    allowed_bg=("white", "blue"),
    check_face: bool = True,
) -> CheckResult:
    import os

    res = CheckResult()
    try:
        im = Image.open(path)
    except Exception as exc:  # noqa: BLE001
        res.fail(f"打不开文件：{exc}")
        return res

    res.meta["format"] = im.format
    res.meta["size"] = im.size

    if im.format not in JPEG_NAMES:
        res.fail(f"格式为 {im.format}，官方只接受 JPG/JPEG")
        return res

    w, h = im.size
    if expect_w and expect_h:
        if (w, h) != (expect_w, expect_h):
            res.fail(f"尺寸 {w}x{h} 与要求的 {expect_w}x{expect_h} 不一致")
    else:
        if w < 295 or h < 413:
            res.warn(f"尺寸 {w}x{h} 低于人社部最低要求 295x413")

    if h and w:
        ratio = w / h
        if abs(ratio - 295 / 413) > 0.02:
            res.warn(f"宽高比 {ratio:.3f} 偏离标准证件照 0.714，可能被拉伸")

    size = os.path.getsize(path)
    res.meta["bytes"] = size
    if max_kb and size > max_kb * 1024:
        res.fail(f"体积 {size/1024:.1f}KB 超过上限 {max_kb}KB")

    segs = jpeg_segments(path)
    res.meta["segments"] = segs
    for bad in ("EXIF", "ICC", "SOF2", "DRI"):
        if bad in segs:
            res.warn(f"含 {bad} 段，个别老式上传接口会拒收（本工具输出默认不含）")

    arr = np.asarray(im.convert("RGB"))
    check_background(arr, res, allowed_bg)
    if check_face:
        check_face_heuristic(im, res)
    return res
