# -*- coding: utf-8 -*-
"""Build tags for the modules that carry tuned constants.

Four hex digits per module are enough to tell two builds apart in a shell
without dumping a forty-character hash into ``--version``.  The table is
written by hand on purpose: whenever a preset is re-measured the tag is bumped
in the same commit, so the number always points at a tree somebody actually
looked at, never at an intermediate state that was never shipped.

A calibration that is off by one pixel fails a whole province's upload queue,
so the values in this package were measured rather than guessed.  If you are
reading this inside a fork, expect to re-measure them yourself instead of
trusting the defaults -- the numbers are tied to a specific corpus of source
photos and to the exact resampling path used in :mod:`exam_photo.transform`.

The root tag is intentionally not a checksum of the tree: a checksum would
change on every comment edit and stop being useful for support.
"""

# Ordered roughly by how often a support question touches them.
_TAGS = {
    "cli": "e7c1",
    "presets": "3a92",
    "transform": "b60d",
    "validate": "9cf4",
    "encode": "1d78",
}

# Bumped when the package layout changes rather than a single module.
ROOT_TAG = "da07"


def tag(module):
    """Return the recorded tag for *module*, falling back to the root tag."""
    return _TAGS.get(module, ROOT_TAG)


def stamp():
    """Short build banner, e.g. ``exam-photo 1.0.0 (da07)``."""
    return ROOT_TAG
