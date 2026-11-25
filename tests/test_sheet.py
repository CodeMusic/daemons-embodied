"""B-2: the sheet is read and checked before the hardware is touched."""

from __future__ import annotations

import math

import pytest

from conftest import write_body
from embodied import sheet as sheets
from embodied.sheet import Refused, SheetError


def test_a_complete_sheet_reads(body):
    s = sheets.read(body)
    assert (s.body, s.shape, s.maker) == ("testbody", "arm", "nobody")
    assert [j.id for j in s.joints] == ["shoulder", "elbow"]
    assert s.joint("elbow").feels == "position"
    assert s.channels == ("arm", "voice", "lights")
    assert s.sense("ears").kind == "sound_bearing"
    assert s.sense_of("cell").params["low_v"] == 6.8
    assert s.voice.speaker and s.voice.microphone
    assert s.lights.count == 11
    assert s.posture("up").pose == {"shoulder": 60, "elbow": 90}
    assert s.settle == "down"
    assert (s.limits.tilt_deg, s.limits.hold_s, s.limits.rest_ratio, s.limits.stop_ms) == (40, 5, 2.0, 150)
    assert [link.id for link in s.frame.links] == ["upper", "lower"]
    assert s.frame.length_m == 0.117 and s.frame.links[1].foot
    assert [a.name for a in s.actions] == ["RAISE", "WAVE"]
    assert sheets.problems(body) == []


def test_the_file_itself_may_be_named(body):
    assert sheets.read(body / "sheet.yaml").body == "testbody"


def test_postures_may_be_only_named(tmp_path, good):
    good["postures"] = ["down", "up"]
    s = sheets.read(write_body(tmp_path / "b", good))
    assert [p.name for p in s.postures] == ["down", "up"] and s.posture("up").pose == {}


def test_a_body_you_can_only_command_has_no_joints(tmp_path):
    sheet = {"body": "commanded", "name": "A finished robot", "shape": "biped", "postures": ["rest"], "settle": "rest"}
    action = {
        "HELLO": {
            "name": "HELLO", "says": "greet whoever is there", "origin": "given", "uses": ["voice"], "from": "rest",
            "flows": True, "class": "sound", "does": {"native": "hello"}, "knows": {"ms": 800},
        }
    }
    sheet["voice"] = {"speaker": True}
    s = sheets.read(write_body(tmp_path / "b", sheet, action))
    assert s.joints == () and s.frame is None and s.channels == ("voice",)
    assert s.action("HELLO").ends_in("rest") == "rest"


def _joint(n, **changes):
    def change(sheet):
        sheet["joints"][n].update(changes)
    return change


def _drop(*path):
    def change(sheet):
        d = sheet
        for key in path[:-1]:
            d = d[key]
        del d[path[-1]]
    return change


def _set(value, *path):
    def change(sheet):
        d = sheet
        for key in path[:-1]:
            d = d[key]
        d[path[-1]] = value
    return change


@pytest.mark.parametrize(
    "change, says",
    [
        (_drop("body"), "is missing 'body'"),
        (_set("Test Body", "body"), "'body' is a short plain name"),
        (_set("", "name"), "'name' is what the app calls"),
        (_drop("settle"), "is missing 'settle'"),
        (_set("flying", "settle"), "not one of its postures"),
        (_set({}, "postures"), "name at least one posture"),
        (_set(1, "colour"), "does not know the key 'colour'"),
        (_joint(0, min=90, max=-90), "its range is empty"),
        (_joint(0, rest=120), "its rest 120 is outside its own range"),
        (_joint(0, top_speed=0), "'top_speed' must be more than 0"),
        (_joint(0, feels="pain"), "'feels' is one of none, position, current"),
        (_joint(0, min="-90"), "'min' is not a number"),
        (_joint(0, min=-math.pi / 2, max=math.pi / 2, rest=0), "reads like radians"),
        (_joint(1, id="shoulder"), "is named twice"),
        (_joint(0, speed=3), "does not know the key 'speed'"),
        (_set({"kind": "smell"}, "senses", "nose"), "'smell' is not a kind of sense"),
        (_drop("senses", "balance", "rate_hz"), "is missing 'rate_hz'"),
        (_set(4000, "senses", "range", "max_m"), "lengths are metres"),
        (_set(8400, "senses", "cell", "full_v"), "reads like millivolts"),
        (_set(7.0, "senses", "cell", "empty_v"), "its volts are out of order"),
        (_set([], "senses", "touch", "pads"), "'pads' is a list"),
        (_set("yes", "voice", "speaker"), "'speaker' is true or false"),
        (_set(0, "lights", "count"), "'count' is how many it has"),
        (_drop("limits", "tilt_deg"), "'tilt_deg' must say how far it may tilt"),
        (_drop("limits", "hold_s"), "'hold_s' must be given"),
        (_set(120, "limits", "tilt_deg"), "'tilt_deg' is 120, above 90"),
        (_set(200, "postures", "up", "elbow"), "'elbow' at 200 is outside its range 0 to 120"),
        (_set(5, "postures", "up", "wrist"), "this body has no joint 'wrist'"),
        (_set(117, "frame", "body", "length_m"), "reads like millimetres"),
        (_set("knee", "frame", "links", 1, "parent"), "its parent 'knee' is not the body nor a link above it"),
        (_set("wrist", "frame", "links", 1, "joint"), "this body has no joint 'wrist'"),
        (_set("spin", "frame", "links", 0, "axis"), "'axis' is one of pitch, yaw, roll"),
        (_set("../elsewhere", "actions"), "'actions' is a folder inside the wrapper's own"),
    ],
)
def test_what_is_wrong_is_said(tmp_path, good, change, says):
    change(good)
    found = sheets.problems(write_body(tmp_path / "b", good))
    assert any(says in line for line in found), found
    with pytest.raises(SheetError):
        sheets.read(tmp_path / "b")


def test_every_problem_is_found_not_only_the_first(tmp_path, good):
    good["joints"][0]["feels"] = "pain"
    good["settle"] = "flying"
    del good["limits"]["rest_ratio"]
    assert len(sheets.problems(write_body(tmp_path / "b", good))) == 3


def test_a_sheet_is_data_and_never_code(tmp_path):
    folder = tmp_path / "b"
    folder.mkdir()
    (folder / "sheet.yaml").write_text("body: !!python/object/apply:os.getcwd []\n")
    assert sheets.problems(folder) == ["sheet.yaml: is not YAML that can be read, line 1"]


def test_no_sheet_at_all(tmp_path):
    assert sheets.problems(tmp_path) == ["sheet.yaml: there is no such file"]


# ---------------------------------------------------------------------------------------------- actions


def _action(which, **changes):
    def change(actions):
        for key, value in changes.items():
            if value is None:
                actions[which].pop(key, None)
            else:
                actions[which][key] = value
    return change


@pytest.mark.parametrize(
    "change, says",
    [
        (_action("RAISE", says=None), "is missing 'says'"),
        (_action("RAISE", says="  "), "'says' is its one line of description, and it is missing"),
        (_action("RAISE", name="raise it"), "'name' is in capitals"),
        (_action("RAISE", origin="stolen"), "'origin' is one of given, shown, tried, found, joined"),
        (_action("RAISE", **{"class": "untrusted"}), "'class' is one of gesture"),
        (_action("RAISE", uses=["legs"]), "this body has no channel 'legs'"),
        (_action("RAISE", **{"from": "flying"}), "'from' names 'flying'"),
        (_action("RAISE", to="flying"), "'to' names 'flying'"),
        (_action("RAISE", flows="sometimes"), "'flows' is true or false"),
        (_action("RAISE", does={"keyframes": [{"ms": 400, "pose": {"elbow": 121}}]}), "'elbow' at 121 is outside its range"),
        (_action("RAISE", does={"keyframes": [{"ms": 0, "pose": {"elbow": 20}}]}), "'ms' is a whole number of milliseconds"),
        (_action("RAISE", does={"keyframes": [{"ms": 100, "pose": {"elbow": 0}}, {"ms": 100, "pose": {"elbow": 120}}]}),
         "over its top speed 300"),
        (_action("RAISE", does={"native": "lift", "keyframes": []}), "exactly one of native, keyframes or generator"),
        (_action("RAISE", does={"command": "anything at all"}), "does not know the key 'command'"),
        (_action("RAISE", does={"native": "os.system"}), "'native' is a short plain name"),
        (_action("WAVE", knows=None), "a native routine needs 'knows: {ms: ...}'"),
        (_action("WAVE", knows={"ms": 900, "runs": 2, "clean": 3}), "ran cleanly more often than it ran"),
        (_action("WAVE", takes=[{"name": "times", "min": 1, "max": 5, "default": 9}]), "its default is outside its own range"),
        (_action("WAVE", takes=[{"name": "way", "one_of": ["wide"], "default": "small"}]), "its default is not one of its own words"),
        (_action("WAVE", name="RAISE"), "'RAISE' is already in raise.yaml"),
    ],
)
def test_what_is_wrong_with_an_action_is_said(tmp_path, good, good_actions, change, says):
    change(good_actions)
    found = sheets.problems(write_body(tmp_path / "b", good, good_actions))
    assert any(says in line for line in found), found


def test_a_keyframe_may_only_move_the_channels_the_action_uses(tmp_path, good, good_actions):
    good["joints"].append({"id": "neck", "channel": "head", "min": -45, "max": 45, "rest": 0, "top_speed": 200})
    good_actions["RAISE"]["does"] = {"keyframes": [{"ms": 400, "pose": {"neck": 10}}]}
    found = sheets.problems(write_body(tmp_path / "b", good, good_actions))
    assert any("the channel 'head', which the action does not say it uses" in line for line in found), found


def test_an_action_record(body):
    s = sheets.read(body)
    raise_, wave = s.action("RAISE"), s.action("WAVE")
    assert (raise_.starts, raise_.ends, raise_.klass, raise_.flows, raise_.finish) == (("down",), "up", "gesture", False, True)
    assert raise_.does.form == "keyframes" and raise_.ms == 400
    assert wave.starts == ("down", "up") and wave.ends is None and wave.ends_in("up") == "up"
    assert wave.does.form == "native" and wave.does.native == "wave" and wave.ms == 900


def test_a_generator_is_read_as_a_form(tmp_path, good, good_actions):
    good_actions["RAISE"]["does"] = {"generator": "reach", "with": {"stride": 0.03, "lift": 12}}
    good_actions["RAISE"]["knows"] = {"ms": 1200}
    a = sheets.read(write_body(tmp_path / "b", good, good_actions)).action("RAISE")
    assert a.does.form == "generator" and a.does.numbers["lift"] == 12 and a.ms == 1200


def test_arguments_are_checked_and_defaults_filled(body):
    wave = sheets.read(body).action("WAVE")
    assert wave.arguments() == {"times": 2, "way": "wide"}
    assert wave.arguments({"times": 5, "way": "small"}) == {"times": 5, "way": "small"}
    for bad in ({"times": 6}, {"times": True}, {"times": "3"}, {"way": "sideways"}, {"speed": 2}):
        with pytest.raises(Refused):
            wave.arguments(bad)


# ---------------------------------------------------------------------------------- the body program's check


def test_a_move_inside_the_range_is_allowed(body):
    s = sheets.read(body)
    s.check_move({"shoulder": 90, "elbow": 0}, 400)
    s.check_move({"shoulder": -90.0}, 1)


@pytest.mark.parametrize(
    "targets, ms",
    [
        ({"shoulder": 91}, 400),  # one degree outside
        ({"shoulder": -91}, 400),
        ({"elbow": -1}, 400),
        ({"wrist": 0}, 400),
        ({"shoulder": float("nan")}, 400),
        ({"shoulder": float("inf")}, 400),
        ({"shoulder": True}, 400),
        ({"shoulder": "45"}, 400),
        ({}, 400),
        ({"shoulder": 0}, 0),
        ({"shoulder": 0}, 2.5),
        ({"shoulder": 0}, True),
        ({1: 0}, 400),
    ],
)
def test_a_move_the_sheet_does_not_allow_is_refused(body, targets, ms):
    with pytest.raises(Refused):
        sheets.read(body).check_move(targets, ms)


# ------------------------------------------------------------------------------------------- senses, by kind


@pytest.mark.parametrize(
    "sense, reading",
    [
        ("balance", {"roll_deg": 1.5, "pitch_deg": -3, "turn_dps": 0.2}),
        ("range", {"m": 0.42}),
        ("range", {"m": None}),
        ("touch", {"pad": "front", "stroke": "back"}),
        ("touch", {"pad": None, "stroke": None}),
        ("ears", {"deg": 40}),
        ("ears", {"deg": None}),
        ("eye", {"frame": b"\x89PNG", "format": "png"}),
        ("cell", {"v": 7.9, "percent": 81}),
    ],
)
def test_a_reading_in_its_kinds_units_passes(body, sense, reading):
    s = sheets.read(body)
    assert sheets.check_reading(s, s.sense(sense), reading) == []


@pytest.mark.parametrize(
    "sense, reading",
    [
        ("balance", {"roll": 1.5, "pitch": -3}),
        ("balance", {"roll_deg": 400, "pitch_deg": 0, "turn_dps": 0}),
        ("range", {"m": 420}),  # centimetres, by the look of it
        ("range", 0.42),
        ("touch", {"pad": "belly", "stroke": None}),
        ("touch", {"pad": "front", "stroke": "sideways"}),
        ("ears", {"deg": -20}),
        ("eye", {"frame": "a picture", "format": "png"}),
        ("cell", {"v": 7.9, "percent": 810}),
        ("cell", {"v": 7.9}),
    ],
)
def test_a_reading_in_the_wrong_units_is_caught(body, sense, reading):
    s = sheets.read(body)
    assert sheets.check_reading(s, s.sense(sense), reading) != []
