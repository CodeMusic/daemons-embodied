"""The sheet: a wrapper's description of its body, read and checked before the hardware is touched.

A sheet says what the body is, its joints, its senses by kind, its voice and lights, its postures, where STOP
leaves it, its limits, its lengths, and the actions it comes with (the design book, Part 4 and Part 5).

**Angles are degrees, lengths are metres, speeds are degrees a second**, on every body.

Nothing here touches hardware, runs a model's words, or knows what kind of body it is reading.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

SHEET_FILE = "sheet.yaml"

ORIGINS = ("given", "shown", "tried", "found", "joined")
CLASSES = ("gesture", "sound", "travel", "asks", "sends", "spends", "deletes", "moves")
FEELS = ("none", "position", "current")
AXES = ("pitch", "yaw", "roll")
STROKES = ("forward", "back")

STOP_WITHIN_MS = 150  # the book's time for stop(), unless a sheet's limits name its own
ANY = "any"  # an action's `from`: every posture the body has
SAME = "same"  # an action's `to`: the posture it started in

_ID = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,31}$")


class SheetError(ValueError):
    """The sheet did not read. `problems` holds every one found, not only the first."""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


class Refused(ValueError):
    """A name or a number the sheet does not allow. Nothing was sent to the body."""


# --------------------------------------------------------------------------------------------- the records


@dataclass(frozen=True)
class Joint:
    id: str
    channel: str
    min: float
    max: float
    rest: float
    top_speed: float  # degrees a second
    feels: str = "none"  # none, position or current: can it report where it is?

    def allows(self, angle: float) -> bool:
        return self.min <= angle <= self.max


@dataclass(frozen=True)
class Sense:
    name: str
    kind: str
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Voice:
    speaker: bool = False
    microphone: bool = False


@dataclass(frozen=True)
class Lights:
    kind: str
    count: int = 1


@dataclass(frozen=True)
class Posture:
    name: str
    pose: Mapping[str, float] = field(default_factory=dict)  # empty when the sheet only names it


@dataclass(frozen=True)
class Limits:
    tilt_deg: float | None = None
    hold_s: float | None = None
    rest_ratio: float | None = None
    stop_ms: int = STOP_WITHIN_MS


@dataclass(frozen=True)
class Link:
    """One straight piece of the body, for anything that draws it or reasons about its reach."""

    id: str
    parent: str  # "body", or the link it hangs from
    length_m: float
    at_m: tuple[float, float, float] = (0.0, 0.0, 0.0)  # where it joins the body: forward, left, up
    joint: str | None = None  # the joint that turns it, if one does
    axis: str = "pitch"
    zero_deg: float = 0.0  # its angle from its parent when the joint reads 0
    turns: int = 1  # 1, or -1 for a joint mounted the other way round
    foot: bool = False  # does its far end rest on the ground?


@dataclass(frozen=True)
class Frame:
    length_m: float
    width_m: float
    links: tuple[Link, ...] = ()


@dataclass(frozen=True)
class Takes:
    """One argument of an action: a number in a range, or one word of a closed list."""

    name: str
    default: float | str
    min: float | None = None
    max: float | None = None
    one_of: tuple[str, ...] = ()


@dataclass(frozen=True)
class Keyframe:
    ms: int
    pose: Mapping[str, float]


@dataclass(frozen=True)
class Does:
    native: str | None = None
    keyframes: tuple[Keyframe, ...] = ()
    generator: str | None = None
    numbers: Mapping[str, float] = field(default_factory=dict)  # a generator's numbers

    @property
    def form(self) -> str:
        if self.native is not None:
            return "native"
        if self.generator is not None:
            return "generator"
        return "keyframes"


@dataclass(frozen=True)
class Knows:
    ms: int = 0
    runs: int = 0
    clean: int = 0


@dataclass(frozen=True)
class Action:
    """One named thing the body can do. Its record keys `from`, `to` and `class` are `starts`, `ends`, `klass`."""

    name: str
    says: str
    origin: str
    uses: tuple[str, ...]
    starts: tuple[str, ...]  # every posture it may start in
    ends: str | None  # the posture it ends in; None when it ends where it started
    flows: bool
    klass: str
    finish: bool
    takes: tuple[Takes, ...]
    does: Does
    knows: Knows

    def ends_in(self, start: str) -> str:
        return self.ends if self.ends is not None else start

    @property
    def ms(self) -> int:
        """How long it is expected to take: its keyframes' times, or what the body has measured."""
        if self.does.form == "keyframes":
            return sum(k.ms for k in self.does.keyframes)
        return self.knows.ms

    def arguments(self, given: Mapping[str, Any] | None = None) -> dict[str, float | str]:
        """The arguments to run it with: each one given is checked, each one missing takes its default."""
        given = dict(given or {})
        out: dict[str, float | str] = {}
        for t in self.takes:
            value = given.pop(t.name, t.default)
            if t.one_of:
                if not isinstance(value, str) or value not in t.one_of:
                    raise Refused(f"{self.name}: '{t.name}' is not one of {', '.join(t.one_of)}")
            else:
                if not _is_num(value) or not (t.min <= value <= t.max):
                    raise Refused(f"{self.name}: '{t.name}' is outside {t.min:g} to {t.max:g}")
            out[t.name] = value
        if given:
            raise Refused(f"{self.name}: takes no '{sorted(given)[0]}'")
        return out


@dataclass(frozen=True)
class Sheet:
    body: str
    name: str
    shape: str
    maker: str
    joints: tuple[Joint, ...]
    senses: tuple[Sense, ...]
    voice: Voice
    lights: Lights | None
    postures: tuple[Posture, ...]
    settle: str
    limits: Limits
    frame: Frame | None
    actions: tuple[Action, ...]
    folder: Path | None = None

    @property
    def channels(self) -> tuple[str, ...]:
        """Each part that does one thing at a time: the joints' channels, then voice, then lights."""
        seen: list[str] = []
        for j in self.joints:
            if j.channel not in seen:
                seen.append(j.channel)
        if self.voice.speaker and "voice" not in seen:
            seen.append("voice")
        if self.lights is not None and "lights" not in seen:
            seen.append("lights")
        return tuple(seen)

    def joint(self, id: str) -> Joint | None:
        return next((j for j in self.joints if j.id == id), None)

    def sense(self, name: str) -> Sense | None:
        return next((s for s in self.senses if s.name == name), None)

    def sense_of(self, kind: str) -> Sense | None:
        return next((s for s in self.senses if s.kind == kind), None)

    def posture(self, name: str) -> Posture | None:
        return next((p for p in self.postures if p.name == name), None)

    def action(self, name: str) -> Action | None:
        return next((a for a in self.actions if a.name == name), None)

    def check_move(self, targets: Mapping[str, float], ms: int) -> None:
        """The body program's own check of a move. Raises Refused; the driver checks again (Part 4)."""
        if not isinstance(targets, Mapping) or not targets:
            raise Refused("a move needs at least one joint")
        if not _is_int(ms) or ms < 1:
            raise Refused("a move's time is a whole number of milliseconds, 1 or more")
        for id, angle in targets.items():
            joint = self.joint(id) if isinstance(id, str) else None
            if joint is None:
                raise Refused(f"this body has no joint '{id}'")
            if not _is_num(angle):
                raise Refused(f"{id}: an angle is a number of degrees")
            if not joint.allows(angle):
                raise Refused(f"{id}: {angle:g} is outside {joint.min:g} to {joint.max:g} degrees")


# ---------------------------------------------------------------------------------------- senses, by kind

# Each kind has fixed units. `params` is what a sheet may say of a sense of that kind (True: it must);
# `reads` is the reading a driver returns for it, as a table of plainly named fields.
SENSE_KINDS: dict[str, dict[str, Any]] = {
    "balance": {"params": {"rate_hz": True}, "reads": "roll_deg, pitch_deg, turn_dps"},
    "range": {"params": {"min_m": True, "max_m": True}, "reads": "m (None when nothing is in range)"},
    "touch": {"params": {"pads": True, "strokes": False}, "reads": "pad, stroke"},
    "sound_bearing": {"params": {"step_deg": True}, "reads": "deg (None when it is quiet)"},
    "sight": {"params": {}, "reads": "frame, format"},
    "cell": {"params": {"full_v": True, "low_v": True, "empty_v": True}, "reads": "v, percent"},
    "heat": {"params": {"warm_c": True}, "reads": "c"},
    "joint_feel": {"params": {}, "reads": "position_deg and/or current_a, each a table by joint"},
}


def check_reading(sheet: Sheet, sense: Sense, reading: Any) -> list[str]:
    """Is this what a sense of its kind reads, in its kind's units? Returns what is wrong, or nothing."""
    wrong: list[str] = []
    where = f"sense '{sense.name}' ({sense.kind})"
    if not isinstance(reading, Mapping):
        return [f"{where}: a reading is a table of named fields"]

    def number(key: str, lo: float | None = None, hi: float | None = None, may_be_none: bool = False) -> None:
        if key not in reading:
            wrong.append(f"{where}: its reading has no '{key}'")
            return
        v = reading[key]
        if v is None and may_be_none:
            return
        if not _is_num(v):
            wrong.append(f"{where}: '{key}' is not a number")
        elif lo is not None and v < lo:
            wrong.append(f"{where}: '{key}' is {v:g}, below {lo:g}")
        elif hi is not None and v > hi:
            wrong.append(f"{where}: '{key}' is {v:g}, above {hi:g}")

    kind = sense.kind
    if kind == "balance":
        number("roll_deg", -180, 180)
        number("pitch_deg", -180, 180)
        number("turn_dps")
    elif kind == "range":
        number("m", 0, sense.params["max_m"], may_be_none=True)
    elif kind == "touch":
        pad = reading.get("pad", "missing")
        if pad is not None and pad not in sense.params["pads"]:
            wrong.append(f"{where}: 'pad' is not one of its pads, nor None")
        stroke = reading.get("stroke", "missing")
        if stroke is not None and stroke not in STROKES:
            wrong.append(f"{where}: 'stroke' is not forward, back or None")
    elif kind == "sound_bearing":
        number("deg", 0, 360, may_be_none=True)
    elif kind == "sight":
        if not isinstance(reading.get("frame"), (bytes, bytearray)) or not reading.get("frame"):
            wrong.append(f"{where}: 'frame' is not a picture's bytes")
        if not isinstance(reading.get("format"), str):
            wrong.append(f"{where}: 'format' does not say what kind of picture it is")
    elif kind == "cell":
        number("v", 0)
        number("percent", 0, 100)
    elif kind == "heat":
        number("c", -40, 150)
    elif kind == "joint_feel":
        tables = [k for k in ("position_deg", "current_a") if k in reading]
        if not tables:
            wrong.append(f"{where}: its reading has neither 'position_deg' nor 'current_a'")
        for key in tables:
            table = reading[key]
            if not isinstance(table, Mapping) or any(
                sheet.joint(j) is None or not _is_num(v) for j, v in table.items()
            ):
                wrong.append(f"{where}: '{key}' is not a table of this body's joints and numbers")
    return wrong


# ------------------------------------------------------------------------------------------------ reading


def read(path: str | Path) -> Sheet:
    """Read a wrapper's sheet (its folder, or the file). Raises SheetError naming everything wrong with it."""
    sheet, found = _read(Path(path))
    if found or sheet is None:
        raise SheetError(found)
    return sheet


def problems(path: str | Path) -> list[str]:
    """Everything wrong with a sheet, as lines a person can read. Empty when it is complete."""
    return _read(Path(path))[1]


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _reads_like_radians(*angles: float) -> bool:
    """A range written in radians: every angle within a turn, and one of them a plain part of pi."""

    def part_of_pi(a: float) -> bool:
        q = abs(a) / (math.pi / 4)
        return round(q) >= 1 and abs(q - round(q)) < 0.004 and abs(a - round(a)) > 0.02

    nonzero = [a for a in angles if a != 0]
    return bool(nonzero) and all(abs(a) <= 2 * math.pi + 0.01 for a in angles) and any(map(part_of_pi, nonzero))


class _Reader:
    """Gathers every problem instead of stopping at the first."""

    def __init__(self) -> None:
        self.problems: list[str] = []

    def say(self, where: str, text: str) -> None:
        self.problems.append(f"{where}: {text}")

    def table(self, v: Any, where: str, required: tuple[str, ...] = (), optional: tuple[str, ...] = ()) -> dict:
        if not isinstance(v, dict):
            self.say(where, "is not a table of keys and values")
            return {}
        for k in v:
            if k not in required and k not in optional:
                self.say(where, f"does not know the key '{k}'")
        for k in required:
            if k not in v:
                self.say(where, f"is missing '{k}'")
        return v

    def number(
        self, d: dict, key: str, where: str, lo: float | None = None, hi: float | None = None, above: float | None = None
    ) -> float | None:
        if key not in d:
            return None
        v = d[key]
        if not _is_num(v):
            self.say(where, f"'{key}' is not a number")
            return None
        if above is not None and not v > above:
            self.say(where, f"'{key}' must be more than {above:g}")
            return None
        if lo is not None and v < lo:
            self.say(where, f"'{key}' is {v:g}, below {lo:g}")
            return None
        if hi is not None and v > hi:
            self.say(where, f"'{key}' is {v:g}, above {hi:g}")
            return None
        return float(v)

    def ident(self, d: dict, key: str, where: str) -> str | None:
        if key not in d:
            return None
        v = d[key]
        if not isinstance(v, str) or not _ID.match(v):
            self.say(where, f"'{key}' is a short plain name: small letters, digits and underscores")
            return None
        return v

    def flag(self, d: dict, key: str, where: str, default: bool = False) -> bool:
        v = d.get(key, default)
        if not isinstance(v, bool):
            self.say(where, f"'{key}' is true or false")
            return default
        return v

    def length(self, d: dict, key: str, where: str) -> float | None:
        v = self.number(d, key, where, lo=0)
        if v is not None and v >= 5:
            self.say(where, f"'{key}' is {v:g}: that reads like millimetres, and lengths are metres")
            return None
        return v


def _locate(path: Path) -> tuple[Path, Path]:
    if path.is_dir():
        return path, path / SHEET_FILE
    return path.parent, path


def _load_yaml(file: Path, r: _Reader) -> Any:
    try:
        return yaml.safe_load(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        r.say(file.name, "there is no such file")
    except (OSError, UnicodeDecodeError) as e:
        r.say(file.name, f"cannot be read ({e.__class__.__name__})")
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        line = f", line {mark.line + 1}" if mark is not None else ""
        r.say(file.name, f"is not YAML that can be read{line}")
    return None


def _read(path: Path) -> tuple[Sheet | None, list[str]]:
    folder, file = _locate(path)
    r = _Reader()
    raw = _load_yaml(file, r)
    if r.problems:
        return None, r.problems
    raw = r.table(
        raw,
        "sheet",
        required=("body", "name", "shape", "postures", "settle"),
        optional=("maker", "joints", "senses", "voice", "lights", "limits", "frame", "actions"),
    )
    if not raw:
        return None, r.problems or ["sheet: is empty"]

    # --- what it is
    body = r.ident(raw, "body", "sheet")
    shape = r.ident(raw, "shape", "sheet")
    name = raw.get("name")
    if "name" in raw and (not isinstance(name, str) or not name.strip()):
        r.say("sheet", "'name' is what the app calls this kind of body, in words")
    maker = raw.get("maker", "")
    if not isinstance(maker, str):
        r.say("sheet", "'maker' is a name, in words")
        maker = ""

    joints = _read_joints(raw.get("joints"), r)
    by_id = {j.id: j for j in joints}
    senses = _read_senses(raw.get("senses"), r)
    voice = _read_voice(raw.get("voice"), r)
    lights = _read_lights(raw.get("lights"), r)
    postures = _read_postures(raw.get("postures"), by_id, r)
    names = [p.name for p in postures]

    settle = r.ident(raw, "settle", "sheet")
    if settle is not None and postures and settle not in names:
        r.say("sheet", f"'settle' is '{settle}', which is not one of its postures")

    limits = _read_limits(raw.get("limits"), joints, senses, r)
    frame = _read_frame(raw.get("frame"), by_id, r)

    channels: list[str] = []
    for j in joints:
        if j.channel not in channels:
            channels.append(j.channel)
    if voice.speaker:
        channels.append("voice")
    if lights is not None:
        channels.append("lights")

    actions = _read_actions(raw, folder, by_id, channels, postures, r)

    if r.problems:
        return None, r.problems
    sheet = Sheet(
        body=body,
        name=name.strip(),
        shape=shape,
        maker=maker.strip(),
        joints=tuple(joints),
        senses=tuple(senses),
        voice=voice,
        lights=lights,
        postures=tuple(postures),
        settle=settle,
        limits=limits,
        frame=frame,
        actions=tuple(actions),
        folder=folder,
    )
    return sheet, []


def _read_joints(raw: Any, r: _Reader) -> list[Joint]:
    if raw is None:
        return []  # a body you can only command has none
    if not isinstance(raw, list):
        r.say("joints", "is a list, one line a joint")
        return []
    joints: list[Joint] = []
    seen: set[str] = set()
    for n, item in enumerate(raw, 1):
        where = f"joint {n}"
        d = r.table(item, where, required=("id", "channel", "min", "max", "rest", "top_speed"), optional=("feels",))
        if not d:
            continue
        id = r.ident(d, "id", where)
        if id is not None:
            where = f"joint '{id}'"
            if id in seen:
                r.say(where, "is named twice")
            seen.add(id)
        channel = r.ident(d, "channel", where)
        lo = r.number(d, "min", where, lo=-3600, hi=3600)
        hi = r.number(d, "max", where, lo=-3600, hi=3600)
        rest = r.number(d, "rest", where)
        speed = r.number(d, "top_speed", where, above=0)
        feels = d.get("feels", "none")
        if feels not in FEELS:
            r.say(where, f"'feels' is one of {', '.join(FEELS)}")
            feels = "none"
        if lo is not None and hi is not None:
            if not lo < hi:
                r.say(where, f"its range is empty: min {lo:g} is not below max {hi:g}")
            elif _reads_like_radians(lo, hi):
                r.say(where, f"its range {lo:g} to {hi:g} reads like radians, and angles are degrees")
            elif rest is not None and not lo <= rest <= hi:
                r.say(where, f"its rest {rest:g} is outside its own range {lo:g} to {hi:g}")
        if None not in (id, channel, lo, hi, rest, speed):
            joints.append(Joint(id, channel, lo, hi, rest, speed, feels))
    return joints


def _read_senses(raw: Any, r: _Reader) -> list[Sense]:
    if raw is None:
        return []
    if not isinstance(raw, dict):
        r.say("senses", "is a table: each sense's own name, then its kind")
        return []
    senses: list[Sense] = []
    for name, item in raw.items():
        where = f"sense '{name}'"
        if not isinstance(name, str) or not _ID.match(name):
            r.say(where, "its name is a short plain name")
            continue
        if not isinstance(item, dict) or "kind" not in item:
            r.say(where, "does not say its kind")
            continue
        kind = item["kind"]
        if kind not in SENSE_KINDS:
            r.say(where, f"'{kind}' is not a kind of sense ({', '.join(SENSE_KINDS)})")
            continue
        spec = SENSE_KINDS[kind]["params"]
        d = r.table(
            item,
            where,
            required=("kind",) + tuple(k for k, must in spec.items() if must),
            optional=tuple(k for k, must in spec.items() if not must),
        )
        params = {k: v for k, v in d.items() if k != "kind"}
        before = len(r.problems)
        if kind == "balance":
            r.number(d, "rate_hz", where, above=0)
        elif kind == "range":
            lo, hi = r.length(d, "min_m", where), r.number(d, "max_m", where, above=0)
            if hi is not None and hi > 100:
                r.say(where, f"'max_m' is {hi:g}: lengths are metres")
            if lo is not None and hi is not None and not lo < hi:
                r.say(where, "'min_m' is not below 'max_m'")
        elif kind == "touch":
            pads = d.get("pads")
            if not isinstance(pads, list) or not pads or not all(isinstance(p, str) and _ID.match(p) for p in pads):
                r.say(where, "'pads' is a list of each pad's short plain name")
            params["pads"] = tuple(pads) if isinstance(pads, list) else ()
            params["strokes"] = r.flag(d, "strokes", where)
        elif kind == "sound_bearing":
            r.number(d, "step_deg", where, above=0, hi=180)
        elif kind == "cell":
            full, low, empty = (r.number(d, k, where, above=0) for k in ("full_v", "low_v", "empty_v"))
            if None not in (full, low, empty):
                if full > 100:
                    r.say(where, f"'full_v' is {full:g}: that reads like millivolts, and a cell is in volts")
                elif not empty < low < full:
                    r.say(where, "its volts are out of order: empty is below low, and low is below full")
        elif kind == "heat":
            r.number(d, "warm_c", where, lo=0, hi=150)
        if len(r.problems) == before:
            senses.append(Sense(name, kind, MappingProxyType(params)))
    return senses


def _read_voice(raw: Any, r: _Reader) -> Voice:
    if raw is None:
        return Voice()
    d = r.table(raw, "voice", optional=("speaker", "microphone"))
    return Voice(r.flag(d, "speaker", "voice"), r.flag(d, "microphone", "voice"))


def _read_lights(raw: Any, r: _Reader) -> Lights | None:
    if raw is None:
        return None
    d = r.table(raw, "lights", required=("kind",), optional=("count",))
    kind = r.ident(d, "kind", "lights")
    count = d.get("count", 1)
    if not _is_int(count) or count < 1:
        r.say("lights", "'count' is how many it has, 1 or more")
        count = 1
    return Lights(kind, count) if kind is not None else None


def _read_pose(raw: Any, where: str, by_id: dict[str, Joint], r: _Reader) -> dict[str, float]:
    pose: dict[str, float] = {}
    if not isinstance(raw, dict):
        r.say(where, "is a table of joints and their angles")
        return pose
    for id, angle in raw.items():
        joint = by_id.get(id) if isinstance(id, str) else None
        if joint is None:
            r.say(where, f"this body has no joint '{id}'")
        elif not _is_num(angle):
            r.say(where, f"'{id}' is not an angle")
        elif not joint.allows(angle):
            r.say(where, f"'{id}' at {angle:g} is outside its range {joint.min:g} to {joint.max:g}")
        else:
            pose[id] = float(angle)
    return pose


def _read_postures(raw: Any, by_id: dict[str, Joint], r: _Reader) -> list[Posture]:
    postures: list[Posture] = []
    if isinstance(raw, list):
        items = [(name, None) for name in raw]
    elif isinstance(raw, dict):
        items = list(raw.items())
    else:
        if raw is not None:
            r.say("postures", "is a list of names, or a table of each name and its joints' angles")
        return postures
    if not items:
        r.say("postures", "a body rests somehow: name at least one posture")
    seen: set[str] = set()
    for name, pose in items:
        if not isinstance(name, str) or not _ID.match(name) or name in (ANY, SAME):
            r.say("postures", f"'{name}' is not a short plain name (and not '{ANY}' or '{SAME}')")
            continue
        if name in seen:
            r.say("postures", f"'{name}' is named twice")
        seen.add(name)
        angles = _read_pose(pose, f"posture '{name}'", by_id, r) if pose is not None else {}
        postures.append(Posture(name, MappingProxyType(angles)))
    return postures


def _read_limits(raw: Any, joints: list[Joint], senses: list[Sense], r: _Reader) -> Limits:
    d = r.table(raw, "limits", optional=("tilt_deg", "hold_s", "rest_ratio", "stop_ms")) if raw is not None else {}
    tilt = r.number(d, "tilt_deg", "limits", above=0, hi=90)
    hold = r.number(d, "hold_s", "limits", above=0)
    rest = r.number(d, "rest_ratio", "limits", lo=0)
    stop_ms = d.get("stop_ms", STOP_WITHIN_MS)
    if not _is_int(stop_ms) or stop_ms < 1:
        r.say("limits", "'stop_ms' is a whole number of milliseconds")
        stop_ms = STOP_WITHIN_MS
    if any(s.kind == "balance" for s in senses) and "tilt_deg" not in d:
        r.say("limits", "it can feel its balance, so 'tilt_deg' must say how far it may tilt")
    if joints:
        for key in ("hold_s", "rest_ratio"):
            if key not in d:
                r.say("limits", f"it has joints, so '{key}' must be given")
    return Limits(tilt, hold, rest, stop_ms)


def _read_frame(raw: Any, by_id: dict[str, Joint], r: _Reader) -> Frame | None:
    if raw is None:
        return None
    d = r.table(raw, "frame", required=("body",), optional=("links",))
    b = r.table(d.get("body", {}), "frame body", required=("length_m", "width_m"))
    length, width = r.length(b, "length_m", "frame body"), r.length(b, "width_m", "frame body")
    links: list[Link] = []
    known = {"body"}
    raw_links = d.get("links", [])
    if not isinstance(raw_links, list):
        r.say("frame links", "is a list, one line a link")
        raw_links = []
    for n, item in enumerate(raw_links, 1):
        where = f"link {n}"
        e = r.table(
            item,
            where,
            required=("id", "parent", "length_m"),
            optional=("at_m", "joint", "axis", "zero_deg", "turns", "foot"),
        )
        if not e:
            continue
        id = r.ident(e, "id", where)
        if id is not None:
            where = f"link '{id}'"
            if id in known:
                r.say(where, "is named twice (or is named 'body')")
        parent = e.get("parent")
        if parent not in known:
            r.say(where, f"its parent '{parent}' is not the body nor a link above it in the list")
        at = e.get("at_m", [0.0, 0.0, 0.0])
        if not isinstance(at, list) or len(at) != 3 or not all(_is_num(v) for v in at):
            r.say(where, "'at_m' is three lengths: forward, left, up")
            at = [0.0, 0.0, 0.0]
        elif any(abs(v) >= 5 for v in at):
            r.say(where, "'at_m' reads like millimetres, and lengths are metres")
        elif "at_m" in e and parent != "body":
            r.say(where, "'at_m' is only for a link that joins the body")
        joint = e.get("joint")
        if joint is not None and joint not in by_id:
            r.say(where, f"this body has no joint '{joint}'")
        axis = e.get("axis", "pitch")
        if axis not in AXES:
            r.say(where, f"'axis' is one of {', '.join(AXES)}")
        turns = e.get("turns", 1)
        if turns not in (1, -1) or isinstance(turns, bool):
            r.say(where, "'turns' is 1, or -1 for a joint mounted the other way round")
        length_m = r.length(e, "length_m", where)
        zero = r.number(e, "zero_deg", where, lo=-360, hi=360) if "zero_deg" in e else 0.0
        foot = r.flag(e, "foot", where)
        if id is not None:
            known.add(id)
            if length_m is not None and zero is not None:
                links.append(Link(id, parent, length_m, tuple(float(v) for v in at), joint, axis, zero, turns, foot))
    if length is None or width is None:
        return None
    return Frame(length, width, tuple(links))


def _read_actions(
    raw: dict, folder: Path, by_id: dict[str, Joint], channels: list[str], postures: list[Posture], r: _Reader
) -> list[Action]:
    where = raw.get("actions", "actions/")
    if not isinstance(where, str) or not where or where.startswith(("/", "~")) or ".." in Path(where).parts:
        r.say("sheet", "'actions' is a folder inside the wrapper's own")
        return []
    actions_dir = folder / where
    if not actions_dir.is_dir():
        if "actions" in raw:
            r.say("sheet", f"its actions folder '{where}' is not there")
        return []
    actions: list[Action] = []
    seen: dict[str, str] = {}
    for file in sorted(actions_dir.glob("*.yaml")):
        action = _read_action(file, by_id, channels, postures, r)
        if action is None:
            continue
        if action.name in seen:
            r.say(f"action {file.name}", f"'{action.name}' is already in {seen[action.name]}")
            continue
        seen[action.name] = file.name
        actions.append(action)
    return actions


def _read_action(
    file: Path, by_id: dict[str, Joint], channels: list[str], postures: list[Posture], r: _Reader
) -> Action | None:
    where = f"action {file.name}"
    before = len(r.problems)
    raw = _load_yaml(file, r)
    if len(r.problems) > before:
        return None
    d = r.table(
        raw,
        where,
        required=("name", "says", "origin", "uses", "from", "flows", "class", "does"),
        optional=("to", "finish", "takes", "knows"),
    )
    if not d:
        return None
    name = d.get("name")
    if not isinstance(name, str) or not _NAME.match(name):
        r.say(where, "'name' is in capitals, with underscores between its words: SHAKE_PAW")
        name = None
    else:
        where = f"action {name}"

    says = d.get("says")
    if not isinstance(says, str) or not says.strip() or "\n" in says.strip():
        r.say(where, "'says' is its one line of description, and it is missing")
        says = ""
    origin = d.get("origin")
    if "origin" in d and origin not in ORIGINS:
        r.say(where, f"'origin' is one of {', '.join(ORIGINS)}")
    klass = d.get("class")
    if "class" in d and klass not in CLASSES:
        r.say(where, f"'class' is one of {', '.join(CLASSES)}")

    uses = d.get("uses")
    if "uses" in d:
        if not isinstance(uses, list) or not uses:
            r.say(where, "'uses' lists the channels it needs")
            uses = []
        for c in uses:
            if c not in channels:
                r.say(where, f"this body has no channel '{c}' ({', '.join(channels) or 'it has none'})")
    uses = tuple(uses or ())

    names = [p.name for p in postures]
    starts_raw = d.get("from")
    starts: tuple[str, ...] = ()
    if "from" in d:
        if starts_raw == ANY:
            starts = tuple(names)
        else:
            listed = starts_raw if isinstance(starts_raw, list) else [starts_raw]
            if not listed or not all(isinstance(p, str) for p in listed):
                r.say(where, "'from' is a posture, a list of postures, or 'any'")
                listed = []
            for p in listed:
                if p not in names:
                    r.say(where, f"'from' names '{p}', which is not one of this body's postures")
            starts = tuple(listed)
    ends = d.get("to", SAME)
    if ends == SAME:
        ends = None
    elif ends not in names:
        r.say(where, f"'to' names '{ends}', which is not one of this body's postures")

    flows = r.flag(d, "flows", where)
    finish = r.flag(d, "finish", where)
    takes = _read_takes(d.get("takes", []), where, r)
    does = _read_does(d.get("does"), where, by_id, uses, r)
    knows = _read_knows(d.get("knows"), where, r)
    if does is not None and does.form == "native" and knows.ms < 1:
        r.say(where, "a native routine needs 'knows: {ms: ...}': how long it takes is all the body can time it by")

    if len(r.problems) > before or name is None or does is None:
        return None
    return Action(name, says.strip(), origin, uses, starts, ends, flows, klass, finish, tuple(takes), does, knows)


def _read_takes(raw: Any, where: str, r: _Reader) -> list[Takes]:
    takes: list[Takes] = []
    if not isinstance(raw, list):
        r.say(where, "'takes' is a list of its arguments")
        return takes
    for n, item in enumerate(raw, 1):
        w = f"{where}, argument {n}"
        d = r.table(item, w, required=("name", "default"), optional=("min", "max", "one_of"))
        name = r.ident(d, "name", w)
        if name is None:
            continue
        default = d.get("default")
        if "one_of" in d:
            words = d["one_of"]
            if not isinstance(words, list) or not words or not all(isinstance(x, str) and _ID.match(x) for x in words):
                r.say(w, "'one_of' is a list of short plain words")
            elif default not in words:
                r.say(w, "its default is not one of its own words")
            elif "min" in d or "max" in d:
                r.say(w, "is either a number in a range or one word of a list, not both")
            else:
                takes.append(Takes(name, default, one_of=tuple(words)))
        else:
            lo, hi = r.number(d, "min", w), r.number(d, "max", w)
            if lo is None or hi is None:
                r.say(w, "a number needs its 'min' and 'max'")
            elif not lo <= hi:
                r.say(w, "its 'min' is above its 'max'")
            elif not _is_num(default) or not lo <= default <= hi:
                r.say(w, "its default is outside its own range")
            else:
                takes.append(Takes(name, default, min=lo, max=hi))
    return takes


def _read_does(raw: Any, where: str, by_id: dict[str, Joint], uses: tuple[str, ...], r: _Reader) -> Does | None:
    # Three forms and no fourth: nothing here can name the driver's command(raw).
    d = r.table(raw, f"{where}, 'does'", optional=("native", "keyframes", "generator", "with"))
    forms = [k for k in ("native", "keyframes", "generator") if k in d]
    if len(forms) != 1:
        r.say(where, "'does' takes exactly one of native, keyframes or generator")
        return None
    form = forms[0]
    if "with" in d and form != "generator":
        r.say(where, "'with' holds a generator's numbers, and this is not one")
    if form == "native":
        key = r.ident(d, "native", f"{where}, 'does'")
        return Does(native=key) if key is not None else None
    if form == "generator":
        key = r.ident(d, "generator", f"{where}, 'does'")
        numbers = d.get("with", {})
        if not isinstance(numbers, dict) or not all(isinstance(k, str) and _ID.match(k) and _is_num(v) for k, v in numbers.items()):
            r.say(where, "a generator's 'with' is a table of plain names and numbers")
            return None
        return Does(generator=key, numbers=MappingProxyType(dict(numbers))) if key is not None else None

    frames = d["keyframes"]
    if not isinstance(frames, list) or not frames:
        r.say(where, "'keyframes' is a list of poses, each with its time")
        return None
    out: list[Keyframe] = []
    last: dict[str, float] = {}
    for n, item in enumerate(frames, 1):
        w = f"{where}, keyframe {n}"
        e = r.table(item, w, required=("ms", "pose"))
        ms = e.get("ms")
        if not _is_int(ms) or ms < 1:
            r.say(w, "'ms' is a whole number of milliseconds, 1 or more")
            continue
        pose = _read_pose(e.get("pose"), w, by_id, r)
        for id, angle in pose.items():
            joint = by_id[id]
            if joint.channel not in uses:
                r.say(w, f"moves '{id}' on the channel '{joint.channel}', which the action does not say it uses")
            if id in last and abs(angle - last[id]) / (ms / 1000) > joint.top_speed + 1e-9:
                r.say(w, f"asks '{id}' for {abs(angle - last[id]) / (ms / 1000):.0f} degrees a second, over its top speed {joint.top_speed:g}")
            last[id] = angle
        out.append(Keyframe(ms, MappingProxyType(pose)))
    return Does(keyframes=tuple(out)) if len(out) == len(frames) else None


def _read_knows(raw: Any, where: str, r: _Reader) -> Knows:
    if raw is None:
        return Knows()
    d = r.table(raw, f"{where}, 'knows'", optional=("ms", "runs", "clean"))
    values = []
    for key in ("ms", "runs", "clean"):
        v = d.get(key, 0)
        if not _is_int(v) or v < 0:
            r.say(where, f"'knows' counts in whole numbers, and '{key}' is not one")
            v = 0
        values.append(v)
    if values[2] > values[1]:
        r.say(where, "'knows' says it ran cleanly more often than it ran")
    return Knows(*values)
