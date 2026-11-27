"""The simulated body's driver: a body made only of its sheet.

It answers every driver call, makes up a believable balance reading from how it is standing, and can draw itself
as a stick figure in a browser page (page.py). It cannot say whether a gait walks.

Besides the driver's calls it has a WORLD: the things a person does to a real body with their hands. Tip it, set
it level, hold a hand in front of it, pat it, switch its servo power. Those are not the driver's calls and
nothing in the body program uses them.

Options, all its own: `clock` (time handed in), `powered` (False: its servos have no power, so nothing sent to
them moves), `page` (a port on this computer to draw itself on), `seed` (for the small noise in its readings).
"""

from __future__ import annotations

import math
import random
import threading
from collections import deque
from contextlib import contextmanager
from typing import Any, Iterator, Mapping

from embodied.clock import Clock
from embodied.driver import BaseDriver, Manner, Sound, Status
from embodied.sheet import Refused, Sheet

from . import figure as figures

# Its "maker's own routines": a closed table, looked up by key and by nothing else.
# Each is (frames, sound): frames are (ms, pose); a sound is (name, ms).
_STAND = {"lf_upper": 35, "lf_lower": 25, "rf_upper": 35, "rf_lower": 25}
_DOWN = {"lf_upper": 62, "lf_lower": -8, "rf_upper": 62, "rf_lower": -8}
ROUTINES: dict[str, tuple[tuple[tuple[int, dict[str, float]], ...], tuple[str, int] | None]] = {
    "bark": ((), ("bark", 450)),
    "push_up": (((450, _DOWN), (450, _STAND), (450, _DOWN), (450, _STAND)), None),
}

SETTLE_SPEED = 120.0  # degrees a second: it settles gently


def _flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no")
    return bool(value)


class Driver(BaseDriver):
    hardware = False
    natives = frozenset(ROUTINES)

    def __init__(self, sheet: Sheet, clock: Clock | None = None, powered: Any = True, page: Any = None, seed: Any = 0):
        super().__init__(sheet)
        self._clock = clock or Clock()
        self._lock = threading.RLock()  # held by every call but stop(), through _held
        self._stops: deque[float] = deque()  # the moments stop() was asked for and not yet applied
        self._noise = random.Random(int(seed))
        self._connected = False
        self._powered = _flag(powered)
        self._page_port = int(page) if page not in (None, "") else None
        self._page = None

        # Rule 2, the driver's own copy of every joint's range. It does not use the body program's check.
        self._range = {j.id: (float(j.min), float(j.max)) for j in sheet.joints}
        self._speed = {j.id: float(j.top_speed) for j in sheet.joints}
        self._channel = {j.id: j.channel for j in sheet.joints}
        self._settled = {j.id: float(j.rest) for j in sheet.joints}
        self._settled.update(sheet.posture(sheet.settle).pose)

        now = self._clock.now()
        # Each joint's path: (time, angle) points it passes through. After the last one it stays there.
        self._path: dict[str, list[tuple[float, float]]] = {id: [(now, a)] for id, a in self._settled.items()}
        self._sound: tuple[str, float] | None = None  # what is playing, and until when
        self._manner: Manner | None = None
        self._heard: deque[Sound] = deque()
        self.commanded: list[Any] = []  # every raw command it was ever given

        # The world
        self._tip = (0.0, 0.0)  # roll, pitch pushed onto it by a hand
        self._hand_m: float | None = 1.5
        self._pat: tuple[str | None, str | None] = (None, None)
        self._bearing: float | None = None
        cell = sheet.sense_of("cell")
        self._cell = (cell.params["full_v"] - 0.3, now) if cell else None

    # ------------------------------------------------------------------------------------- the ten calls

    def connect(self) -> None:
        with self._held():
            self._connected = True
        if self._page_port is not None and self._page is None:
            from . import page

            self._page = page.serve(self, self._page_port)

    def close(self) -> None:
        with self._held():
            if self._connected and self._powered:
                # It has no servos to wait for: it is simply left settled.
                now = self._clock.now()
                self._path = {id: [(now, a)] for id, a in self._settled.items()}
            self._sound = None
            self._connected = False
        if self._page is not None:
            self._page.shutdown()
            self._page.server_close()
            self._page = None

    def status(self) -> Status:
        with self._held():
            now = self._clock.now()
            pose = self._pose(now)
            roll, pitch = self._lean(pose)
            limit = self.sheet.limits.tilt_deg
            v, percent = self._cell_now(now)
            parts = {s.name: True for s in self.sheet.senses}
            parts.update({"speaker": True, "microphone": True, "lights": True})
            return Status(
                cell_v=v,
                cell_percent=percent,
                heat_c=None,
                upright=None if limit is None else figures.tilt(roll, pitch) <= limit,
                parts=parts,
                moving=self._moving(now),
                pose=pose,
            )

    def stop(self) -> None:
        """Halt every channel now. Safe from any thread at any moment, connected or not.

        It waits for nothing, not even for the call that holds the body: it writes its moment down and returns.
        Every call that holds the body applies what was written first (`_held`), as of that moment, so whatever
        was under way then is halted where it was then, however late the body is next looked at."""
        self._stops.append(self._clock.now())  # one step, which no other thread can come between
        if self._lock.acquire(blocking=False):  # nobody holds the body: halt it here
            try:
                self._halt()
            finally:
                self._lock.release()

    def settle(self) -> None:
        with self._held():
            self._must_be_connected()
            now = self._clock.now()
            pose = self._pose(now)
            furthest = max((abs(a - pose[id]) for id, a in self._settled.items()), default=0.0)
            self._send(self._settled, max(0.4, furthest / SETTLE_SPEED), now)

    def move(self, targets: Mapping[str, float], ms: int) -> None:
        self._refuse_outside_range(targets)
        if isinstance(ms, bool) or not isinstance(ms, int) or ms < 1:
            raise Refused("a move's time is a whole number of milliseconds")
        with self._held():
            self._must_be_connected()
            self._send(targets, ms / 1000.0, self._clock.now())

    def run(self, native: str, args: Mapping[str, float | str]) -> None:
        routine = ROUTINES.get(native) if isinstance(native, str) else None
        if routine is None:
            raise Refused(f"'{native}' is not one of its routines")
        if args:
            raise Refused(f"'{native}' takes no arguments")
        frames, sound = routine
        for _, pose in frames:
            self._refuse_outside_range(pose)
        with self._held():
            self._must_be_connected()
            now = self._clock.now()
            begins = now  # when the frame being laid down begins
            started: set[str] = set()
            for ms, pose in frames:
                ends = begins + ms / 1000.0
                if self._powered:
                    for id, angle in pose.items():
                        if id not in started:
                            self._path[id] = [(now, _at(self._path[id], now))]
                            started.add(id)
                        last_t, last_a = self._path[id][-1]
                        if last_t < begins:
                            self._path[id].append((begins, last_a))  # it held still until this frame
                        arrives = begins + max(ms / 1000.0, abs(angle - last_a) / self._speed[id])
                        self._path[id].append((arrives, float(angle)))
                        ends = max(ends, arrives)
                begins = ends
            if sound is not None:
                self._sound = (sound[0], now + sound[1] / 1000.0)

    def sense(self, name: str) -> Mapping[str, Any]:
        sense = self.sheet.sense(name) if isinstance(name, str) else None
        if sense is None:
            raise Refused(f"it has no sense '{name}'")
        with self._held():
            self._must_be_connected()
            now = self._clock.now()
            kind = sense.kind
            if kind == "balance":
                pose = self._pose(now)
                roll, pitch = self._lean(pose)
                shake = 0.6 if self._moving(now) - {"voice"} else 0.12  # a moving body is a noisier one
                return {
                    "roll_deg": round(roll + self._noise.gauss(0, shake), 2),
                    "pitch_deg": round(pitch + self._noise.gauss(0, shake), 2),
                    "turn_dps": round(self._noise.gauss(0, 0.3), 2),
                }
            if kind == "range":
                lo, hi = sense.params["min_m"], sense.params["max_m"]
                if self._hand_m is None or self._hand_m > hi:
                    return {"m": None}
                return {"m": round(min(hi, max(lo, self._hand_m + self._noise.gauss(0, 0.003))), 3)}
            if kind == "touch":
                return {"pad": self._pat[0], "stroke": self._pat[1]}
            if kind == "sound_bearing":
                if self._bearing is None:
                    return {"deg": None}
                step = sense.params["step_deg"]
                return {"deg": (round(self._bearing / step) * step) % 360}
            if kind == "sight":
                return {"frame": self._frame(), "format": "pgm"}
            if kind == "cell":
                v, percent = self._cell_now(now)
                return {"v": v, "percent": percent}
        raise Refused(f"it cannot read a '{sense.kind}'")

    def play(self, sound: Sound) -> None:
        with self._held():
            self._must_be_connected()
            self._sound = ("speech", self._clock.now() + sound.ms / 1000.0)

    def hear(self) -> Sound | None:
        with self._held():
            self._must_be_connected()
            return self._heard.popleft() if self._heard else None

    def light(self, manner: Manner) -> None:
        with self._held():
            self._must_be_connected()
            self._manner = manner

    def command(self, raw: Any) -> Any:
        """Reached only by a developer's own code. It writes the command down and does nothing to the body."""
        with self._held():
            self.commanded.append(raw)
        return {"heard": raw}

    # ----------------------------------------------------------------------------------------- the world

    def tip(self, roll_deg: float = 0.0, pitch_deg: float = 0.0) -> None:
        """Push it over by this much, as a hand would."""
        with self._held():
            self._tip = (max(-180.0, min(180.0, float(roll_deg))), max(-180.0, min(180.0, float(pitch_deg))))

    def level(self) -> None:
        """Set it back on its feet."""
        self.tip(0.0, 0.0)

    def hand(self, m: float | None) -> None:
        """Hold something this far in front of it; None takes it away."""
        with self._held():
            self._hand_m = None if m is None else max(0.0, float(m))

    def pat(self, pad: str | None = None, stroke: str | None = None) -> None:
        """Touch one of its pads, perhaps stroking it; no pad lifts the hand."""
        touch = self.sheet.sense_of("touch")
        if pad is not None and (touch is None or pad not in touch.params["pads"]):
            raise ValueError(f"it has no pad '{pad}'")
        if stroke not in (None, "forward", "back"):
            raise ValueError("a stroke is forward or back")
        with self._held():
            self._pat = (pad, stroke if pad is not None else None)

    def sound_from(self, deg: float | None) -> None:
        """A sound from this many degrees round from its nose; None is quiet."""
        with self._held():
            self._bearing = None if deg is None else float(deg) % 360

    def say_to_it(self, sound: Sound) -> None:
        """Something for its microphone to hear."""
        with self._held():
            self._heard.append(sound)

    def power(self, on: bool) -> None:
        """Its servo power switch. With it off, what is sent to the servos moves nothing."""
        with self._held():
            self._powered = bool(on)

    def cell(self, v: float) -> None:
        """Set its cell to this many volts."""
        with self._held():
            if self._cell is not None:
                self._cell = (float(v), self._clock.now())

    def look(self) -> dict:
        """Everything the page draws."""
        with self._held():
            now = self._clock.now()
            pose = self._pose(now)
            roll, pitch = self._lean(pose)
            v, percent = self._cell_now(now)
            sound = self._sound[0] if self._sound and self._sound[1] > now else None
            manner = self._manner
            state = {
                "body": self.sheet.body,
                "name": self.sheet.name,
                "connected": self._connected,
                "powered": self._powered,
                "pose": {id: round(a, 1) for id, a in pose.items()},
                "moving": sorted(self._moving(now)),
                "posture": self._posture(pose),
                "roll_deg": round(roll, 1),
                "pitch_deg": round(pitch, 1),
                "tilt_deg": round(figures.tilt(roll, pitch), 1),
                "tilt_limit_deg": self.sheet.limits.tilt_deg,
                "cell_v": v,
                "cell_percent": percent,
                "sound": sound,
                "hand_m": self._hand_m,
                "pat": self._pat[0],
                "lights": None
                if self.sheet.lights is None
                else {
                    "count": self.sheet.lights.count,
                    "colour": list(manner.colour) if manner else None,
                    "rhythm": manner.rhythm if manner else None,
                },
            }
            frame = self.sheet.frame
        state["figure"] = figures.figure(frame, pose, roll, pitch) if frame is not None else None
        if frame is not None:
            state["frame"] = {"length_m": frame.length_m, "width_m": frame.width_m}
        return state

    # ------------------------------------------------------------------------------------------- inside

    @contextmanager
    def _held(self) -> Iterator[None]:
        """Hold the body for one call. Every call but stop() does, and a stop that was asked for is applied
        before the call does anything else."""
        with self._lock:
            self._halt()
            yield

    def _halt(self) -> None:
        """With the body held: halt it as of the earliest moment stop() wrote down."""
        if not self._stops:
            return
        # Only the holder takes moments off, so each one counted here is still there to take.
        at = min(self._stops.popleft() for _ in range(len(self._stops)))
        for id, path in self._path.items():
            self._path[id] = [(at, _at(path, at))]
        self._sound = None

    def _must_be_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("the body is not connected")

    def _refuse_outside_range(self, targets: Mapping[str, float]) -> None:
        """The second check (Part 4): the driver refuses a target outside the sheet's range by its own table."""
        if not isinstance(targets, Mapping) or not targets:
            raise Refused("a move needs at least one joint")
        for id, angle in targets.items():
            limits = self._range.get(id) if isinstance(id, str) else None
            if limits is None:
                raise Refused(f"it has no joint '{id}'")
            if isinstance(angle, bool) or not isinstance(angle, (int, float)) or not math.isfinite(angle):
                raise Refused(f"{id}: an angle is a number of degrees")
            if angle < limits[0] or angle > limits[1]:
                raise Refused(f"{id}: {angle:g} is outside {limits[0]:g} to {limits[1]:g} degrees")

    def _send(self, targets: Mapping[str, float], seconds: float, now: float) -> None:
        if not self._powered:
            return  # the command is taken, and no servo has the power to obey it
        for id, angle in targets.items():
            here = _at(self._path[id], now)
            # A servo cannot turn faster than its top speed: asked to, it arrives late.
            took = max(seconds, abs(angle - here) / self._speed[id])
            self._path[id] = [(now, here), (now + took, float(angle))]

    def _pose(self, now: float) -> dict[str, float]:
        return {id: _at(path, now) for id, path in self._path.items()}

    def _moving(self, now: float) -> frozenset[str]:
        channels = {self._channel[id] for id, path in self._path.items() if path[-1][0] > now}
        if self._sound is not None and self._sound[1] > now:
            channels.add("voice")
        return frozenset(channels)

    def _lean(self, pose: Mapping[str, float]) -> tuple[float, float]:
        frame = self.sheet.frame
        roll, pitch = figures.stance(figures.skeleton(frame, pose)) if frame is not None else (0.0, 0.0)
        return roll + self._tip[0], pitch + self._tip[1]

    def _posture(self, pose: Mapping[str, float]) -> str | None:
        for posture in self.sheet.postures:
            if posture.pose and all(abs(pose[id] - a) <= 1.0 for id, a in posture.pose.items()):
                return posture.name
        return None

    def _cell_now(self, now: float) -> tuple[float | None, float | None]:
        if self._cell is None:
            return None, None
        p = self.sheet.sense_of("cell").params
        v = max(0.0, self._cell[0] - 0.01 * (now - self._cell[1]) / 60.0)  # a hundredth of a volt a minute
        percent = max(0.0, min(100.0, (v - p["empty_v"]) / (p["full_v"] - p["empty_v"]) * 100.0))
        return round(v, 2), round(percent, 1)

    def _frame(self) -> bytes:
        """What its eye sees: a small grey picture, darker the nearer the hand is."""
        w, h = 16, 12
        near = 255 if self._hand_m is None else int(max(0.0, min(1.0, self._hand_m / 2.0)) * 255)
        rows = bytes(min(255, (near * (x + y + 4)) // (w + h)) for y in range(h) for x in range(w))
        return b"P5 %d %d 255\n" % (w, h) + rows


def _at(path: list[tuple[float, float]], now: float) -> float:
    """Where a joint is on its path at this moment."""
    if now <= path[0][0]:
        return path[0][1]
    for (t0, a0), (t1, a1) in zip(path, path[1:]):
        if now < t1:
            return a0 + (a1 - a0) * ((now - t0) / (t1 - t0)) if t1 > t0 else a1
    return path[-1][1]
