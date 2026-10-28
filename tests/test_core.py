# -*- coding: utf-8 -*-
"""Tests run on synthetic images — no personal photos are bundled."""

import io
import os

import numpy as np
import pytest
from PIL import Image

from exam_photo.encode import encode_jpeg, save
from exam_photo.presets import get_preset, parse_size
from exam_photo.transform import crop_to_ratio, replace_background
from exam_photo.validate import classify_background, jpeg_segments, validate_file


def make_fake_portrait(width=600, height=800, bg=(67, 142, 219)):
    """Blue backdrop + skin-toned ellipse where a head would be."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[:, :] = bg
    yy, xx = np.mgrid[0:height, 0:width]
    cy, cx = height * 0.38, width * 0.5
    ry, rx = height * 0.22, width * 0.20
    head = ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1.0
    arr[head] = (226, 186, 160)
    # A darker band as "hair" so the centre has texture
    hair = head & (yy < cy - ry * 0.15)
    arr[hair] = (42, 34, 30)
    return Image.fromarray(arr, mode="RGB")


def test_parse_size_variants():
    assert parse_size("295x413") == (295, 413)
    assert parse_size("295*413") == (295, 413)
    assert parse_size("295X413") == (295, 413)
    with pytest.raises(ValueError):
        parse_size("295")
    with pytest.raises(ValueError):
        parse_size("a x b")


def test_preset_lookup():
    preset = get_preset("rsks")
    assert preset.size == (295, 413)
    assert preset.max_kb == 10.0
    with pytest.raises(KeyError):
        get_preset("nope")


def test_crop_to_ratio_produces_exact_size():
    im = make_fake_portrait()
    out = crop_to_ratio(im, 295, 413)
    assert out.size == (295, 413)


def test_crop_keeps_head_when_source_is_too_tall():
    """A tall source should be trimmed from the bottom, not the forehead."""
    im = make_fake_portrait(width=400, height=1000)
    out = crop_to_ratio(im, 295, 413, head_bias=0.28)
    arr = np.asarray(out)
    # The head ellipse sits around 38% height in the source; after a top-biased
    # crop it must still land in the upper half of the result.
    top_half = arr[: arr.shape[0] // 2]
    non_bg = (np.abs(top_half.astype(int) - np.array([67, 142, 219])).sum(axis=2) > 40)
    assert non_bg.mean() > 0.15


def test_replace_background_swaps_only_backdrop():
    im = make_fake_portrait()
    out = replace_background(im, "white")
    arr = np.asarray(out)
    assert classify_background(arr) == "white"
    # Centre of the face must keep its skin tone
    cy, cx = int(arr.shape[0] * 0.38), int(arr.shape[1] * 0.5)
    assert arr[cy, cx][0] > 150


def test_replace_background_rejects_flat_image():
    flat = Image.new("RGB", (400, 560), (67, 142, 219))
    with pytest.raises(ValueError):
        replace_background(flat, "white")


def test_encode_respects_budget():
    im = make_fake_portrait().resize((295, 413))
    quality, data = encode_jpeg(im, max_bytes=10240)
    assert len(data) <= 10240
    assert quality >= 20


def test_encode_produces_baseline_without_exif():
    im = make_fake_portrait().resize((295, 413))
    _, data = encode_jpeg(im, max_bytes=20000)
    path = "/tmp/_exam_photo_test.jpg"
    with open(path, "wb") as fh:
        fh.write(data)
    try:
        segs = jpeg_segments(path)
        assert "SOF0" in segs
        assert "EXIF" not in segs
        assert "ICC" not in segs
    finally:
        os.remove(path)


def test_validate_flags_wrong_size(tmp_path):
    im = make_fake_portrait()
    path = tmp_path / "big.jpg"
    im.save(path, quality=92)
    res = validate_file(str(path), expect_w=295, expect_h=413, max_kb=10)
    assert res.ok is False
    assert any("尺寸" in issue for issue in res.issues)


def test_validate_accepts_correct_output(tmp_path):
    im = crop_to_ratio(make_fake_portrait(), 295, 413)
    path = str(tmp_path / "ok.jpg")
    info = save(im, path, max_bytes=10240)
    assert info["within_budget"]
    res = validate_file(path, expect_w=295, expect_h=413, max_kb=10)
    assert res.ok, res.issues


def test_transparent_png_becomes_white_not_black(tmp_path):
    """Regression: RGBA -> JPEG used to render the transparent area black."""
    from exam_photo.cli import _open_rgb

    arr = np.zeros((300, 200, 4), dtype=np.uint8)
    arr[..., :3] = (200, 30, 30)
    arr[..., 3] = 0  # fully transparent
    png = tmp_path / "t.png"
    Image.fromarray(arr, mode="RGBA").save(png)

    rgb = _open_rgb(png)
    corner = np.asarray(rgb)[0, 0]
    assert tuple(corner) == (255, 255, 255)
