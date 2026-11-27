"""B-3: a body made only of its sheet. It answers every driver call and makes up a believable balance reading."""

from __future__ import annotations

import json
import math
import statistics
import threading
import time
import urllib.error
import urllib.request

import pytest

import bodies
from embodied import driver as drivers
from embodied import sheet as sheets
from embodied.clock import Clock, StepClock
from embodied.driver import Manner, Sound
from embodied.sheet import Refused


@pytest.fixture
def simulated():
    found = bodies.without_hardware()
    assert found, "the repository has a body with no hardware"
    return found[0]


@pytest.fixture
def clock():
    return StepClock()


@pytest.fixture
def it(simulated, clock):
    d = simulated.driver(clock=clock)
    d.connect()
    yield d
    d.close()


def test_it_answers_every_driver_call(simulated, it, clock):
    sheet = simulated.sheet
    assert all(drivers.offers(it, call) for call in drivers.CALLS)
    assert set(drivers.needs(sheet)) <= set(drivers.CALLS)
    status = it.status()
    assert status.upright is True and status.moving == frozenset()
    assert all(status.parts.values()) and {s.name for s in sheet.senses} <= set(status.parts)
    assert set(status.pose) == {j.id for j in sheet.joints}
    assert 0 < status.cell_percent <= 100
    it.settle()
    it.move({sheet.joints[0].id: sheet.joints[0].rest}, 200)
    for native in sorted(it.natives):
        it.run(native, {})
    for sense in sheet.senses:
        assert sheets.check_reading(sheet, sense, it.sense(sense.name)) == [], sense.name
    it.play(Sound(b"\x00\x00" * 1600))
    assert it.hear() is None
    it.light(Manner(colour=(255, 140, 0), rhythm="breathe"))
    it.stop()
    assert it.status().moving == frozenset()


def test_it_starts_and_is_left_in_the_posture_the_sheet_names(simulated, clock):
    sheet = simulated.sheet
    d = simulated.driver(clock=clock)
    d.connect()
    settled = sheet.posture(sheet.settle).pose
    assert all(d.status().pose[id] == a for id, a in settled.items())
    d.move({id: p for id, p in sheet.postures[-1].pose.items()}, 500)
    clock.sleep(1)
    d.close()
    assert all(d.status().pose[id] == a for id, a in settled.items())


def test_a_move_arrives_in_its_time(simulated, it, clock):
    joint = simulated.sheet.joints[0]
    start = it.status().pose[joint.id]
    target = start - 30
    it.move({joint.id: target}, 600)
    assert it.status().moving == {joint.channel}
    clock.sleep(0.3)
    assert it.status().pose[joint.id] == pytest.approx(start - 15)
    clock.sleep(0.31)
    assert it.status().pose[joint.id] == target and it.status().moving == frozenset()


def test_a_servo_cannot_outrun_its_top_speed(simulated, it, clock):
    joint = simulated.sheet.joints[0]
    start = it.status().pose[joint.id]
    target = joint.min
    it.move({joint.id: target}, 1)  # asked for in a millisecond
    clock.sleep(0.1)
    assert it.status().pose[joint.id] == pytest.approx(start - joint.top_speed * 0.1)
    clock.sleep(abs(target - start) / joint.top_speed)
    assert it.status().pose[joint.id] == target


def test_the_driver_refuses_what_is_outside_the_range_by_its_own_check(simulated, it, monkeypatch):
    def never(*a, **k):
        raise AssertionError("the driver's check is its own, not the body program's")

    monkeypatch.setattr(sheets.Sheet, "check_move", never)
    before = it.status().pose
    for joint in simulated.sheet.joints:
        for outside in (joint.max + 1, joint.min - 1):
            with pytest.raises(Refused):
                it.move({joint.id: outside}, 400)
    for bad in ({"no_such_joint": 0}, {simulated.sheet.joints[0].id: float("nan")}, {}):
        with pytest.raises(Refused):
            it.move(bad, 400)
    with pytest.raises(Refused):
        it.move({simulated.sheet.joints[0].id: 0}, 0)
    assert it.status().pose == before and it.status().moving == frozenset()


def test_its_routines_are_a_closed_list(it):
    for key in ("eval", "__class__", "bark; rm", None, 7):
        with pytest.raises(Refused):
            it.run(key, {})
    with pytest.raises(Refused):
        it.run(sorted(it.natives)[0], {"anything": 1})
    with pytest.raises(Refused):
        it.sense("smell")


def test_stop_halts_every_channel_at_once(simulated, it, clock):
    sheet = simulated.sheet
    stand = sheet.postures[-1].pose
    it.move(dict(stand), 900)
    it.play(Sound(b"\x00\x00" * 16000))
    clock.sleep(0.4)
    assert it.status().moving
    it.stop()
    halted = it.status()
    assert halted.moving == frozenset()
    clock.sleep(5)
    assert it.status().pose == halted.pose  # nothing that was under way carried on
    assert any(halted.pose[id] != a for id, a in stand.items())  # and it stopped part-way, not at the end


def test_stop_drops_the_rest_of_a_routine(it, clock):
    routine = next(key for key in sorted(it.natives) if key != "bark")
    it.stop()
    it.run(routine, {})
    clock.sleep(0.2)
    it.stop()
    halted = it.status().pose
    clock.sleep(10)
    assert it.status().pose == halted


def test_stop_is_safe_before_it_is_connected_and_after_it_is_closed(simulated):
    d = simulated.driver()
    d.stop()
    d.connect()
    d.close()
    d.stop()
    with pytest.raises(RuntimeError):
        d.move({simulated.sheet.joints[0].id: 0}, 100)


class HoldingClock(Clock):
    """The real clock, in which one thread can be kept waiting: a way to hold the body in the middle of a call."""

    def __init__(self):
        self.kept = None  # the thread to keep
        self.waiting = threading.Event()  # it has arrived, still holding whatever it held
        self.let_go = threading.Event()

    def now(self) -> float:
        if threading.get_ident() == self.kept:
            self.waiting.set()
            self.let_go.wait(30)
        return time.monotonic()


def test_stop_does_not_wait_for_whoever_holds_the_body(simulated):
    """Rule 2: STOP is proved before anything is built on it. A stop asked for while another call holds the body
    returns at once, and still halts what that call began. Nothing here is timed against the computer's speed."""
    sheet = simulated.sheet
    clock = HoldingClock()
    d = simulated.driver(clock=clock)
    d.connect()
    before = d.status().pose
    stand = dict(sheet.postures[-1].pose)
    assert stand != {id: before[id] for id in stand}

    def a_move_kept_waiting():
        clock.kept = threading.get_ident()
        d.move(stand, 900)

    mover = threading.Thread(target=a_move_kept_waiting, daemon=True)
    asker = threading.Thread(target=d.status, daemon=True)
    stopper = threading.Thread(target=d.stop, daemon=True)
    try:
        mover.start()
        assert clock.waiting.wait(10)  # it is inside move(), holding the body
        asker.start()
        asker.join(0.2)
        assert asker.is_alive()  # the body really is held: any other call waits for it
        stopper.start()
        stopper.join(10)
        assert not stopper.is_alive(), "stop() waited for the call that held the body"
    finally:
        clock.let_go.set()
        for t in (mover, asker, stopper):
            if t.ident is not None:
                t.join(10)
    after = d.status()
    assert after.moving == frozenset() and after.pose == before  # the move it came in the middle of went nowhere
    time.sleep(0.05)
    assert d.status().pose == before
    d.close()


def test_stop_is_safe_from_any_thread_at_any_moment(simulated):
    """Rule 2 again, with real time and real threads: nothing errs, nothing hangs, and it ends halted.

    What is timed is the usual call. On a busy computer one call in many thousands is slow because its thread was
    not given the processor, which no body can answer for; that stop() itself waits for nothing is the test above."""
    sheet = simulated.sheet
    d = simulated.driver()
    d.connect()
    errors, took, done = [], [], threading.Event()
    poses = [dict(p.pose) for p in sheet.postures if p.pose]

    def mover():
        n = 0
        while not done.is_set():
            try:
                d.move(poses[n % len(poses)], 50)
                d.run(sorted(d.natives)[n % len(d.natives)], {})
                d.status(), d.sense(sheet.senses[0].name), d.look()
            except Exception as e:  # noqa: BLE001
                errors.append(e)
            n += 1

    def stopper():
        mine = []
        while not done.is_set():
            try:
                t0 = time.perf_counter()
                d.stop()
                mine.append(time.perf_counter() - t0)
            except Exception as e:  # noqa: BLE001
                errors.append(e)
        took.extend(mine)

    threads = [threading.Thread(target=mover) for _ in range(3)] + [threading.Thread(target=stopper) for _ in range(4)]
    for t in threads:
        t.start()
    time.sleep(0.5)
    done.set()
    for t in threads:
        t.join(5)
    assert errors == [] and not any(t.is_alive() for t in threads)
    assert took and statistics.median(took) * 1000 < sheet.limits.stop_ms
    d.stop()
    halted = d.status().pose
    time.sleep(0.05)
    assert d.status().pose == halted and d.status().moving == frozenset()
    d.close()


def test_its_balance_reading_is_believable(simulated, it, clock):
    sheet = simulated.sheet
    limit = sheet.limits.tilt_deg
    name = sheet.sense_of("balance").name

    def lean(posture):
        it.move(dict(sheet.posture(posture).pose), 800)
        clock.sleep(1)
        readings = [it.sense(name) for _ in range(40)]
        assert len({(r["roll_deg"], r["pitch_deg"]) for r in readings}) > 10  # it is never perfectly still
        return sum(r["roll_deg"] for r in readings) / 40, sum(r["pitch_deg"] for r in readings) / 40

    leans = {p.name: lean(p.name) for p in sheet.postures}
    for roll, pitch in leans.values():
        assert abs(roll) < 1 and math.hypot(roll, pitch) < limit  # no posture of its own is a fall
    assert any(abs(pitch) < 1 for _, pitch in leans.values())  # it stands or lies level
    assert any(10 < pitch < limit for _, pitch in leans.values())  # and sitting, its nose is up

    again = simulated.driver(clock=StepClock())
    again.connect()
    first = simulated.driver(clock=StepClock())
    first.connect()
    assert [again.sense(name) for _ in range(5)] == [first.sense(name) for _ in range(5)]  # the same seed, the same noise


def test_a_hand_can_tip_it_and_set_it_level(simulated, it):
    name = simulated.sheet.sense_of("balance").name
    assert it.status().upright
    it.tip(roll_deg=70)
    assert not it.status().upright and it.sense(name)["roll_deg"] > 60
    it.level()
    assert it.status().upright


def test_with_its_servo_power_off_nothing_moves(simulated, it, clock):
    sheet = simulated.sheet
    before = it.status().pose
    it.power(False)
    it.move(dict(sheet.postures[-1].pose), 500)
    it.run(next(key for key in sorted(it.natives) if key != "bark"), {})
    it.settle()
    clock.sleep(3)
    assert it.status().pose == before
    it.power(True)
    it.move(dict(sheet.postures[-1].pose), 500)
    clock.sleep(1)
    assert it.status().pose != before


def test_the_world_reaches_its_senses(simulated, it):
    sheet = simulated.sheet
    it.hand(0.08)
    assert it.sense(sheet.sense_of("range").name)["m"] == pytest.approx(0.08, abs=0.02)
    it.hand(None)
    assert it.sense(sheet.sense_of("range").name)["m"] is None
    pad = sheet.sense_of("touch").params["pads"][0]
    it.pat(pad, "forward")
    assert it.sense(sheet.sense_of("touch").name) == {"pad": pad, "stroke": "forward"}
    it.pat(None)
    assert it.sense(sheet.sense_of("touch").name) == {"pad": None, "stroke": None}
    it.sound_from(47)
    assert it.sense(sheet.sense_of("sound_bearing").name)["deg"] == 40  # in the sheet's steps of 20
    heard = Sound(b"\x01\x00" * 100)
    it.say_to_it(heard)
    assert it.hear() is heard and it.hear() is None
    it.cell(6.5)
    assert it.status().cell_v == 6.5 and it.status().cell_percent == pytest.approx(5.0)


def test_command_is_written_down_and_moves_nothing(it):
    before = it.status().pose
    assert it.command("anything a developer likes") == {"heard": "anything a developer likes"}
    assert it.commanded == ["anything a developer likes"] and it.status().pose == before


# ------------------------------------------------------------------------- the stick figure, from the lengths


def _length(line):
    return math.dist(line["a"], line["b"])


def test_the_figure_is_drawn_from_the_sheets_lengths(simulated, it, clock):
    sheet = simulated.sheet
    frame = sheet.frame
    assert (frame.length_m, frame.width_m) == (0.117, 0.098)  # the published body
    assert {round(link.length_m, 3) for link in frame.links if link.foot} == {0.076}  # the lower legs
    look = it.look()
    by_id = {line["id"]: line for line in look["figure"]["lines"]}
    for link in frame.links:
        assert _length(by_id[link.id]) == pytest.approx(link.length_m, abs=1e-4), link.id
    outline = look["figure"]["outline"]
    assert math.dist(outline[0], outline[1]) == pytest.approx(frame.width_m, abs=1e-4)
    assert math.dist(outline[1], outline[2]) == pytest.approx(frame.length_m, abs=1e-4)


def test_standing_its_feet_are_on_the_ground_and_its_body_is_above_them(simulated, it, clock):
    sheet = simulated.sheet
    heights = {}
    for posture in sheet.postures:
        it.move(dict(posture.pose), 800)
        clock.sleep(1)
        look = it.look()
        assert look["posture"] == posture.name
        lines = look["figure"]["lines"]
        assert min(p[2] for line in lines for p in (line["a"], line["b"])) == 0  # something rests on the ground
        assert sum(1 for line in lines if line["foot"] and line["b"][2] < 0.002) >= 2
        heights[posture.name] = sum(c[2] for c in look["figure"]["outline"]) / 4
    assert max(heights.values()) > 0.09 and min(heights.values()) < 0.04  # it stands tall and lies low


def test_a_tipped_figure_is_drawn_tipped(it):
    level = it.look()["figure"]["outline"]
    it.tip(roll_deg=70)
    tipped = it.look()["figure"]["outline"]
    assert max(c[2] for c in tipped) - min(c[2] for c in tipped) > 0.08 > max(c[2] for c in level) - min(c[2] for c in level)


# ------------------------------------------------------------------------------------------------- its page


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.read()


def _post(port, body, kind="application/json"):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/world", data=json.dumps(body).encode(), headers={"Content-Type": kind}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_it_draws_itself_in_a_browser_page(simulated):
    page = simulated.module("page")
    d = simulated.driver()
    d.connect()
    server = page.serve(d, 0)
    port = server.server_address[1]
    try:
        assert server.server_address[0] == "127.0.0.1"  # this computer only
        html = _get(port, "/").decode()
        assert "DRAFT" in html and "<svg" in html
        look = json.loads(_get(port, "/look"))
        assert look["connected"] and len(look["figure"]["lines"]) == len(simulated.sheet.frame.links)
        assert _post(port, {"do": "tip", "roll": 70}) == 200 and not d.status().upright
        assert _post(port, {"do": "level"}) == 200 and d.status().upright
        assert _post(port, {"do": "power", "on": False}) == 200 and json.loads(_get(port, "/look"))["powered"] is False
        before = d.status().pose
        for refused in ({"do": "move", "lf_upper": 0}, {"do": "stop"}, {"do": "tip", "roll": "a lot"}, ["tip"]):
            assert _post(port, refused) == 400
        assert _post(port, {"do": "level"}, kind="text/plain") == 404
        assert d.status().pose == before  # the page is a hand on the body, never a driver's call
    finally:
        server.shutdown()
        server.server_close()
        d.close()
