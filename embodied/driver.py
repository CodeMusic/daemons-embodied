"""The driver: the ten calls that reach a body's servos, senses, speaker and lights (the design book, Part 4).

A wrapper's `driver.py` holds one class, `Driver`, built on `BaseDriver`. A body implements the calls it has.

    connect() / close()   open the hardware; leave it settled                    always
    status()              cell, heat, upright, whether each part answers          always
    stop()                halt every channel NOW; safe from any thread            always
    settle()              go to the posture the sheet names, and rest there       always
    move(targets, ms)     send joints toward angles, to arrive in ms              a body with joints
    run(native, args)     run one of the maker's own routines by its key          a body with native actions
    sense(name)           read one sense, in its kind's units                     each sense it has
    play(sound) / hear()  audio out, audio in                                     a body with a voice
    light(manner)         show a manner on its lights or its face                 a body with lights

`move`, `run`, `settle`, `play` and `light` return at once: the body program times what it started, and
`status().moving` says which channels are still at it.

Three rules bind every driver.

1. Nothing a model wrote ever reaches a driver. The body program reaches it only through `Checked`, below,
   which passes names and numbers it has checked against the sheet.
2. The driver refuses a target outside the sheet's range itself, even though `Checked` already has. The two
   checks are kept in two places on purpose: write the driver's own in the wrapper, and do not share code.
3. `stop()` is proved before anything else is written. The body check calls it in the middle of every action.
   **It waits for nothing**: not for a lock another call holds, not for a move to finish, not for a reply from the
   hardware that may never come. A driver that guards its hardware with a lock gives `stop()` a way round it.

There is one more call, `command(raw)`, for whatever a body has that the sheet cannot say. `Checked` has no such
call, so no action and nothing in the body program can reach it: only a developer's own code, holding the driver.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from .sheet import Refused, Sheet

ALWAYS = ("connect", "close", "status", "stop", "settle")
CALLS = ALWAYS + ("move", "run", "sense", "play", "hear", "light")  # ten rows of the book's table

RHYTHMS = ("steady", "breathe", "pulse", "dark")

_WORD = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class NotOffered(NotImplementedError):
    """This body has no such part, so its driver does not offer the call."""


@dataclass(frozen=True)
class Status:
    """What `status()` answers. A body leaves out what it cannot know."""

    cell_v: float | None = None
    cell_percent: float | None = None
    heat_c: float | None = None
    upright: bool | None = None
    parts: Mapping[str, bool] = field(default_factory=dict)  # does each part answer?
    moving: frozenset[str] = frozenset()  # the channels still at something
    pose: Mapping[str, float] | None = None  # where each joint was last sent (or is felt to be)


@dataclass(frozen=True)
class Sound:
    """Audio, in or out: 16-bit signed samples, one channel, little-endian."""

    pcm: bytes
    rate_hz: int = 16000

    @property
    def ms(self) -> int:
        return int(len(self.pcm) / 2 / self.rate_hz * 1000) if self.rate_hz else 0


@dataclass(frozen=True)
class Manner:
    """What a driver is asked to show on its lights or its face: a colour, a rhythm, a tempo."""

    colour: tuple[int, int, int] = (255, 255, 255)
    rhythm: str = "steady"
    tempo: float = 1.0  # 1 is its ordinary pace


@runtime_checkable
class Driver(Protocol):
    """The protocol every wrapper's driver meets."""

    hardware: bool
    natives: frozenset[str]

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def status(self) -> Status: ...
    def stop(self) -> None: ...
    def settle(self) -> None: ...
    def move(self, targets: Mapping[str, float], ms: int) -> None: ...
    def run(self, native: str, args: Mapping[str, float | str]) -> None: ...
    def sense(self, name: str) -> Mapping[str, Any]: ...
    def play(self, sound: Sound) -> None: ...
    def hear(self) -> Sound | None: ...
    def light(self, manner: Manner) -> None: ...
    def command(self, raw: Any) -> Any: ...


class BaseDriver:
    """What a wrapper's `Driver` is built on. The five calls every body has must be written; the rest are
    written only by a body that has the part."""

    hardware: bool = True  # False for a body that is only its sheet
    natives: frozenset[str] = frozenset()  # the closed list of the maker's routines `run` accepts

    def __init__(self, sheet: Sheet, **options: Any):
        if options:
            raise TypeError(f"this driver takes no option '{sorted(options)[0]}'")
        self.sheet = sheet

    # --- always
    def connect(self) -> None:
        raise NotImplementedError("connect() is not written yet")

    def close(self) -> None:
        raise NotImplementedError("close() is not written yet")

    def status(self) -> Status:
        raise NotImplementedError("status() is not written yet")

    def stop(self) -> None:
        raise NotImplementedError("stop() is not written yet")

    def settle(self) -> None:
        raise NotImplementedError("settle() is not written yet")

    # --- only a body that has the part
    def move(self, targets: Mapping[str, float], ms: int) -> None:
        raise NotOffered("this body has no joints to move")

    def run(self, native: str, args: Mapping[str, float | str]) -> None:
        raise NotOffered("this body has no routines of its maker's")

    def sense(self, name: str) -> Mapping[str, Any]:
        raise NotOffered("this body has no senses")

    def play(self, sound: Sound) -> None:
        raise NotOffered("this body has no speaker")

    def hear(self) -> Sound | None:
        raise NotOffered("this body has no microphone")

    def light(self, manner: Manner) -> None:
        raise NotOffered("this body has no lights")

    def command(self, raw: Any) -> Any:
        raise NotOffered("this body takes no raw command")


def offers(driver: Any, call: str) -> bool:
    """Has this driver written the call, or is it the base's placeholder?"""
    theirs = getattr(type(driver), call, None)
    return theirs is not None and theirs is not getattr(BaseDriver, call, None)


def needs(sheet: Sheet) -> tuple[str, ...]:
    """The calls a body with this sheet must offer."""
    calls = list(ALWAYS)
    if sheet.joints:
        calls.append("move")
    if any(a.does.form == "native" for a in sheet.actions):
        calls.append("run")
    if sheet.senses:
        calls.append("sense")
    if sheet.voice.speaker:
        calls.append("play")
    if sheet.voice.microphone:
        calls.append("hear")
    if sheet.lights is not None:
        calls.append("light")
    return tuple(calls)


class Checked:
    """The body program's hold on a driver: every name and number is checked against the sheet before it is
    passed on, and there is no `command`. This is the first of the two checks; the driver's own is the second."""

    __slots__ = ("_sheet", "_driver")

    def __init__(self, sheet: Sheet, driver: Driver):
        self._sheet = sheet
        self._driver = driver

    def connect(self) -> None:
        self._driver.connect()

    def close(self) -> None:
        self._driver.close()

    def status(self) -> Status:
        return self._driver.status()

    def stop(self) -> None:
        # No check, no lock, no model: the reflex goes straight through.
        self._driver.stop()

    def settle(self) -> None:
        self._driver.settle()

    def move(self, targets: Mapping[str, float], ms: int) -> None:
        self._sheet.check_move(targets, ms)
        self._driver.move({id: float(angle) for id, angle in targets.items()}, ms)

    def run(self, native: str, args: Mapping[str, float | str] | None = None) -> None:
        if not isinstance(native, str) or native not in self._driver.natives:
            raise Refused(f"'{native}' is not one of this body's own routines")
        clean: dict[str, float | str] = {}
        for key, value in (args or {}).items():
            if not isinstance(key, str) or not _WORD.match(key):
                raise Refused("an argument's name is a short plain word")
            if isinstance(value, str):
                if not _WORD.match(value):
                    raise Refused(f"'{key}' is not a short plain word")
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise Refused(f"'{key}' is not a number")
            clean[key] = value
        self._driver.run(native, clean)

    def sense(self, name: str) -> Mapping[str, Any]:
        if not isinstance(name, str) or self._sheet.sense(name) is None:
            raise Refused(f"this body has no sense '{name}'")
        return self._driver.sense(name)

    def play(self, sound: Sound) -> None:
        if not self._sheet.voice.speaker:
            raise Refused("this body has no speaker")
        if not isinstance(sound, Sound) or not isinstance(sound.pcm, (bytes, bytearray)) or len(sound.pcm) % 2:
            raise Refused("a sound is 16-bit samples")
        if isinstance(sound.rate_hz, bool) or not isinstance(sound.rate_hz, int) or not 8000 <= sound.rate_hz <= 48000:
            raise Refused("a sound's rate is 8000 to 48000 samples a second")
        self._driver.play(sound)

    def hear(self) -> Sound | None:
        if not self._sheet.voice.microphone:
            raise Refused("this body has no microphone")
        return self._driver.hear()

    def light(self, manner: Manner) -> None:
        if self._sheet.lights is None:
            raise Refused("this body has no lights")
        if not isinstance(manner, Manner) or manner.rhythm not in RHYTHMS:
            raise Refused(f"a manner's rhythm is one of {', '.join(RHYTHMS)}")
        colour = manner.colour
        if (
            not isinstance(colour, tuple)
            or len(colour) != 3
            or not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in colour)
        ):
            raise Refused("a manner's colour is three whole numbers, 0 to 255")
        if isinstance(manner.tempo, bool) or not isinstance(manner.tempo, (int, float)) or not 0.1 <= manner.tempo <= 10:
            raise Refused("a manner's tempo is 0.1 to 10")
        self._driver.light(manner)
