# -*- coding: utf-8 -*-
"""Photo specs for Chinese public-exam / civil-service registration photos.

The values here were extracted from the official Windows tool
``PhotoProcess.exe`` (v1.0.0.25, 人社部人事考试中心) and its bundled
``photo.ini``.  Only ``rsks`` is hard-verified against that binary; the other
presets are commonly published sizes and must always be double-checked
against the announcement you are applying to.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    key: str
    width: int
    height: int
    max_kb: float
    label: str
    note: str = ""

    @property
    def size(self) -> tuple:
        return (self.width, self.height)


PRESETS = {
    # Hard-verified against PhotoProcess.exe / photo.ini
    "rsks": Preset(
        key="rsks",
        width=295,
        height=413,
        max_kb=10.0,
        label="人社部人事考试 / 国考 / 事业单位 / 烟草（1寸）",
        note="295x413 @ 75dpi 版式，官方工具固定输出此尺寸，文件约 10KB",
    ),
    # Common sizes — verify against your announcement
    "1inch": Preset(
        key="1inch",
        width=295,
        height=413,
        max_kb=20.0,
        label="1寸通用（25x35mm @300dpi）",
    ),
    "2inch": Preset(
        key="2inch",
        width=413,
        height=579,
        max_kb=40.0,
        label="2寸通用（35x49mm @300dpi）",
    ),
    "480x640": Preset(
        key="480x640",
        width=480,
        height=640,
        max_kb=100.0,
        label="480x640（部分省考/教师资格）",
    ),
    "cet": Preset(
        key="cet",
        width=144,
        height=192,
        max_kb=200.0,
        label="CET 四六级（144x192）",
    ),
    "small2": Preset(
        key="small2",
        width=413,
        height=531,
        max_kb=50.0,
        label="413x531（部分国企网申）",
    ),
}

DEFAULT_PRESET = "rsks"


def get_preset(key: str) -> Preset:
    if key not in PRESETS:
        keys = ", ".join(sorted(PRESETS))
        raise KeyError(f"未知规格 '{key}'，可选：{keys}")
    return PRESETS[key]


def parse_size(text: str) -> tuple:
    """Parse ``295x413`` / ``295*413`` / ``295X413`` into (w, h)."""
    normalized = text.lower().replace("*", "x").replace("×", "x")
    parts = normalized.split("x")
    if len(parts) != 2:
        raise ValueError(f"尺寸格式应为 宽x高，例如 295x413，收到：{text}")
    try:
        w, h = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError(f"尺寸必须是整数，收到：{text}")
    if w <= 0 or h <= 0:
        raise ValueError(f"尺寸必须为正数，收到：{text}")
    return w, h
