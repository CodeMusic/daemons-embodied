"""B-2: the driver's ten calls, and the body program's hold on them."""

from __future__ import annotations

import pytest

from conftest import write_body
from embodied import driver as drivers
from embodied import sheet as sheets
from embodied import wrapper as wrappers_
from embodied.driver import BaseDriver, Checked, Manner, NotOffered, Sound, Status
from embodied.sheet import Refused


class Recorder(BaseDriver):
    """A driver that only writes down what reached it."""

    natives = frozenset({"wave"})

    def __init__(self, sheet):
        super().__init__(sheet)
        self.calls = []

    def connect(self): self.calls.append(("connect",))
    def close(self): self.calls.append(("close",))
    def status(self): return Status(upright=True)
    def stop(self): self.calls.append(("stop",))
    def settle(self): self.calls.append(("settle",))
    def move(self, targets, ms): self.calls.append(("move", targets, ms))
    def run(self, native, args): self.calls.append(("run", native, args))
    def sense(self, name): self.calls.append(("sense", name)); return {"m": 1.0}
    def play(self, sound): self.calls.append(("play", sound))
    def hear(self): return None
    def light(self, manner): self.calls.append(("light", manner))
    def command(self, raw): self.calls.append(("command", raw))


@pytest.fixture
def held(body):
    sheet = sheets.read(body)
    recorder = Recorder(sheet)
    return Checked(sheet, recorder), recorder


def test_the_ten_calls():
    assert drivers.ALWAYS == ("connect", "close", "status", "stop", "settle")
    assert drivers.CALLS == drivers.ALWAYS + ("move", "run", "sense", "play", "hear", "light")
    assert isinstance(Recorder.__new__(Recorder), drivers.Driver)


def test_a_bare_driver_has_written_nothing(body):
    bare = BaseDriver(sheets.read(body))
    for call in drivers.ALWAYS:
        with pytest.raises(NotImplementedError):
            getattr(bare, call)()
        assert not drivers.offers(bare, call)
    for call, args in (("move", ({}, 1)), ("run", ("x", {})), ("sense", ("x",)), ("play", (None,)), ("hear", ()),
                       ("light", (None,)), ("command", ("x",))):
        with pytest.raises(NotOffered):
            getattr(bare, call)(*args)
        assert not drivers.offers(bare, call)


def test_a_driver_takes_only_the_options_it_knows(body):
    with pytest.raises(TypeError):
        BaseDriver(sheets.read(body), port="anything")


def test_what_a_sheet_needs_of_its_driver(body, tmp_path):
    full = sheets.read(body)
    assert drivers.needs(full) == drivers.CALLS
    assert all(drivers.offers(Recorder(full), call) for call in drivers.CALLS)
    bare = {"body": "bare", "name": "Bare", "shape": "box", "postures": ["rest"], "settle": "rest"}
    assert drivers.needs(sheets.read(write_body(tmp_path / "bare", bare, {}))) == drivers.ALWAYS


def test_what_is_checked_is_passed_on(held):
    hold, recorder = held
    hold.connect()
    hold.settle()
    hold.move({"shoulder": 45, "elbow": 30}, 400)
    hold.run("wave", {"times": 3, "way": "wide"})
    hold.sense("range")
    hold.play(Sound(b"\x00\x00" * 160))
    hold.light(Manner(colour=(255, 120, 0), rhythm="breathe", tempo=0.5))
    hold.close()
    assert [c[0] for c in recorder.calls] == ["connect", "settle", "move", "run", "sense", "play", "light", "close"]
    assert recorder.calls[2] == ("move", {"shoulder": 45.0, "elbow": 30.0}, 400)
    assert recorder.calls[3] == ("run", "wave", {"times": 3, "way": "wide"})


@pytest.mark.parametrize(
    "call, args",
    [
        ("move", ({"shoulder": 91}, 400)),
        ("move", ({"wrist": 0}, 400)),
        ("move", ({"shoulder": 0}, -5)),
        ("run", ("eval", {})),
        ("run", ("wave", {"times": float("nan")})),
        ("run", ("wave", {"way": "wide; rm -rf"})),
        ("run", ("wave", {"times": [1, 2]})),
        ("run", ("wave", {"__class__": 1})),
        ("run", (None, {})),
        ("sense", ("smell",)),
        ("sense", (None,)),
        ("play", ("bark.wav",)),
        ("play", (Sound(b"\x00\x00", rate_hz=1),)),
        ("light", (Manner(colour=(300, 0, 0)),)),
        ("light", (Manner(rhythm="strobe"),)),
        ("light", ("red",)),
    ],
)
def test_what_the_sheet_does_not_allow_never_reaches_the_driver(held, call, args):
    hold, recorder = held
    with pytest.raises(Refused):
        getattr(hold, call)(*args)
    assert recorder.calls == []


def test_stop_goes_straight_through(held):
    hold, recorder = held
    hold.stop()
    assert recorder.calls == [("stop",)]


def test_the_body_program_cannot_reach_command(held):
    hold, recorder = held
    assert not hasattr(hold, "command")
    with pytest.raises(AttributeError):
        hold.command("anything")
    with pytest.raises(AttributeError):
        hold._anything_else = 1  # nor can one be added to it
    assert recorder.calls == []


def test_a_body_without_the_part_refuses_the_call(tmp_path):
    bare = {"body": "bare", "name": "Bare", "shape": "box", "postures": ["rest"], "settle": "rest"}
    sheet = sheets.read(write_body(tmp_path / "bare", bare, {}))
    hold = Checked(sheet, Recorder(sheet))
    for call, args in (("play", (Sound(b"\x00\x00"),)), ("hear", ()), ("light", (Manner(),)), ("move", ({"a": 1}, 5))):
        with pytest.raises(Refused):
            getattr(hold, call)(*args)


# ------------------------------------------------------------------------------------------ loading a wrapper

DRIVER = '''
from embodied.driver import BaseDriver, Status
from .beside import WORD

class Driver(BaseDriver):
    hardware = False
    def __init__(self, sheet, port=None):
        super().__init__(sheet)
        self.port = port
    def status(self): return Status(parts={WORD: True})
'''


def test_a_wrapper_is_a_sheet_and_a_driver(body):
    (body / "driver.py").write_text(DRIVER)
    (body / "beside.py").write_text("WORD = 'beside'\n")
    w = wrappers_.load(body)
    d = w.driver(port="a port")
    assert w.sheet.body == "testbody" and d.port == "a port" and not d.hardware
    assert d.status().parts == {"beside": True}  # it can import what lies beside it
    assert w.module("beside").WORD == "beside"
    assert wrappers_.found(body.parent) == [body]


def test_a_folder_without_a_driver_is_not_a_wrapper(body):
    with pytest.raises(wrappers_.WrapperError, match="there is no driver.py"):
        wrappers_.load(body)
    (body / "driver.py").write_text("class Driver: pass\n")
    with pytest.raises(wrappers_.WrapperError, match="built on BaseDriver"):
        wrappers_.load(body)


def test_a_sound_knows_how_long_it_is():
    assert Sound(b"\x00\x00" * 16000).ms == 1000
