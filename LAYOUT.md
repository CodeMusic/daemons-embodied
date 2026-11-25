# LAYOUT -- where each kind of code lives

*Kept true in the same commit as any folder change. On 2026-11-25 nothing below exists yet: this is the plan from
the design book's Part 14, and each folder is marked when its first file lands.*

| Folder | What lives there | Since |
|---|---|---|
| `embodied/` | the body program: the one process that holds the hardware | to come (B-2) |
| `embodied/brainstem/` | status, reflexes, STOP, the watchdog | to come |
| `embodied/cerebellum/` | the motion engine: timing, limits, channels, manner; what the body knows of itself | to come |
| `embodied/basal_ganglia/` | the repertoire and the gate | to come |
| `embodied/senses/` | readings into events | to come |
| `embodied/psychic/` | Bluetooth, Wi-Fi, the body's own door | to come |
| `embodied/hippocampus/` | events, kept and sent | to come |
| `embodied/sheet.py` | the sheet, read and checked | to come (B-2) |
| `turn/` | the daemon's turn, a client of the body program: `ears/`, `thinker/`, `voice/`, `words/`, `performance/` | to come |
| `practice/` | the trial harness; shown, tried, found; the night | to come |
| `wrappers/_template/` | copy this to add a body | to come (B-5) |
| `wrappers/sim/` | a body with no hardware | to come (B-3) |
| `wrappers/pidog/` | the first body | to come (B-13) |
| `tools/` | bodycheck, install, the service files | to come (B-4) |
| `tests/` | the checks | to come |

THE BRAIN's interface is not kept here: it is pinned by tag from a repository of its own (B-35).
