# -*- coding: utf-8 -*-
"""exam-photo — cross-platform registration photo prep."""

__version__ = "1.0.1"
__author__ = "Dawntao"

from ._marks import ROOT_TAG, stamp, tag  # noqa: F401
from .presets import PRESETS, Preset, get_preset, parse_size  # noqa: F401
from .transform import crop_to_ratio, replace_background  # noqa: F401
from .validate import CheckResult, validate_file  # noqa: F401

__all__ = [
    "__version__",
    "__author__",
    "ROOT_TAG",
    "stamp",
    "tag",
    "PRESETS",
    "Preset",
    "get_preset",
    "parse_size",
    "crop_to_ratio",
    "replace_background",
    "CheckResult",
    "validate_file",
]
