# LAYOUT -- where each kind of code lives

*Kept true in the same commit as any folder change. The plan is the design book's Part 14; a folder marked
**to come** does not exist yet, and each is marked with its ticket when its first file lands.*

| Folder | What lives there | Since |
|---|---|---|
| `embodied/` | the body program: the one process that holds the hardware | B-2 (2026-11-25) |
| `embodied/sheet.py` | the sheet, read and checked: joints, senses by kind, voice, lights, postures, limits, lengths, the actions' records | B-2 |
| `embodied/driver.py` | the driver's ten calls (`BaseDriver`), and `Checked`, the body program's hold on a driver: every name and number checked against the sheet, and no `command` | B-2 |
| `embodied/wrapper.py` | loading a wrapper's folder: its sheet, then its `Driver` | B-2 |
| `embodied/clock.py` | time that can be handed in, so what is timed can be tested | B-2 |
| `embodied/brainstem/` | status, reflexes, STOP, the watchdog | to come |
| `embodied/cerebellum/` | the motion engine: timing, limits, channels, manner; what the body knows of itself | to come |
| `embodied/basal_ganglia/` | the repertoire and the gate | to come |
| `embodied/senses/` | readings into events | to come |
| `embodied/psychic/` | Bluetooth, Wi-Fi, the body's own door | to come |
| `embodied/hippocampus/` | events, kept and sent | to come |
| `turn/` | the daemon's turn, a client of the body program: `ears/`, `thinker/`, `voice/`, `words/`, `performance/` | to come |
| `practice/` | the trial harness; shown, tried, found; the night | to come |
| `wrappers/_template/` | copy this to add a body | to come (B-5) |
| `wrappers/sim/` | a body with no hardware: its sheet, its ten actions, a driver that answers every call, the stick figure and the page it draws itself on (`python3 -m wrappers.sim`) | B-3 (2026-11-25) |
| `wrappers/pidog/` | the first body | to come (B-13) |
| `tools/` | bodycheck, install, the service files | to come (B-4) |
| `tests/` | the checks: `python3 -m pytest` from the repository's root (`requirements-dev.txt`) | B-2 |

THE BRAIN's interface is not kept here: it is pinned by tag from a repository of its own (B-35).

**A rule the tests hold** (`tests/test_rules.py`): no `eval` and no shell anywhere in `embodied/`, `wrappers/` or
`tools/`; YAML is only ever read as data; nothing calls a driver's `command(raw)`; the word is spelled one way.
