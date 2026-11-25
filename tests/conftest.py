"""What the tests share: a small made-up body, written into a folder of its own for each test."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

# A body with two joints, one sense of each kind that needs describing, a voice and a light.
GOOD_SHEET = {
    "body": "testbody",
    "name": "A body for tests",
    "shape": "arm",
    "maker": "nobody",
    "joints": [
        {"id": "shoulder", "channel": "arm", "min": -90, "max": 90, "rest": 0, "top_speed": 300, "feels": "none"},
        {"id": "elbow", "channel": "arm", "min": 0, "max": 120, "rest": 10, "top_speed": 300, "feels": "position"},
    ],
    "senses": {
        "balance": {"kind": "balance", "rate_hz": 20},
        "range": {"kind": "range", "min_m": 0.02, "max_m": 4.0},
        "touch": {"kind": "touch", "pads": ["front", "rear"], "strokes": True},
        "ears": {"kind": "sound_bearing", "step_deg": 20},
        "eye": {"kind": "sight"},
        "cell": {"kind": "cell", "full_v": 8.4, "low_v": 6.8, "empty_v": 6.4},
    },
    "voice": {"speaker": True, "microphone": True},
    "lights": {"kind": "strip", "count": 11},
    "postures": {"down": {"shoulder": 0, "elbow": 10}, "up": {"shoulder": 60, "elbow": 90}},
    "settle": "down",
    "limits": {"tilt_deg": 40, "hold_s": 5, "rest_ratio": 2.0},
    "frame": {
        "body": {"length_m": 0.117, "width_m": 0.098},
        "links": [
            {"id": "upper", "parent": "body", "at_m": [0.05, 0.0, 0.0], "length_m": 0.042, "joint": "shoulder"},
            {"id": "lower", "parent": "upper", "length_m": 0.076, "joint": "elbow", "foot": True},
        ],
    },
    "actions": "actions/",
}

GOOD_ACTIONS = {
    "RAISE": {
        "name": "RAISE",
        "says": "lift the arm",
        "origin": "given",
        "uses": ["arm"],
        "from": "down",
        "to": "up",
        "flows": False,
        "class": "gesture",
        "finish": True,
        "takes": [],
        "does": {"keyframes": [{"ms": 400, "pose": {"shoulder": 60, "elbow": 90}}]},
        "knows": {"ms": 400, "runs": 0, "clean": 0},
    },
    "WAVE": {
        "name": "WAVE",
        "says": "wave the arm, as many times as asked",
        "origin": "given",
        "uses": ["arm"],
        "from": "any",
        "flows": True,
        "class": "gesture",
        "takes": [
            {"name": "times", "min": 1, "max": 5, "default": 2},
            {"name": "way", "one_of": ["wide", "small"], "default": "wide"},
        ],
        "does": {"native": "wave"},
        "knows": {"ms": 900},
    },
}


def write_body(folder: Path, sheet: dict | None = None, actions: dict | None = None) -> Path:
    """Write a wrapper's sheet and its actions into a folder, and return the folder."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sheet.yaml").write_text(yaml.safe_dump(GOOD_SHEET if sheet is None else sheet, sort_keys=False))
    records = GOOD_ACTIONS if actions is None else actions
    if records:
        (folder / "actions").mkdir(exist_ok=True)
        for name, record in records.items():
            (folder / "actions" / f"{name.lower()}.yaml").write_text(yaml.safe_dump(record, sort_keys=False))
    return folder


@pytest.fixture
def good() -> dict:
    """The made-up body's sheet, free to be changed by a test."""
    return copy.deepcopy(GOOD_SHEET)


@pytest.fixture
def good_actions() -> dict:
    return copy.deepcopy(GOOD_ACTIONS)


@pytest.fixture
def body(tmp_path: Path) -> Path:
    """The made-up body, written out whole."""
    return write_body(tmp_path / "testbody")
