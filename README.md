# daemons-embodied

**DAEMONS EMBODIED: a daemon in a robot body.** You talk to it; it answers as itself; and while it answers it wags,
sits or walks to you, because those movements are part of what it said. One body program for many bodies, and one
small wrapper for each kind of body. The first body is the SunFounder PiDog.

**Nothing here is built yet.** This repository was opened on 2026-11-25, with its design reviewed and its tickets
written. Its first code is ticket B-2.

## The design

- **The book**: [DAEMONS-embodied.pdf](https://github.com/CodeMusic/DAEMONS/blob/main/docs/DAEMONS-embodied.pdf)
  (62 pages, nine drawings; DRAFT). Its source is `docs/manual-embodied/` in
  [DAEMONS](https://github.com/CodeMusic/DAEMONS), printed by `python3 tools/manual.py --book embodied --write`.
- **The design bible**: section 9.38 of DAEMONS' `docs/vision.md`.

## The design in eleven lines

1. **One body program, and one wrapper for each kind of body.** A wrapper is a sheet that describes the body and a
   driver that moves it. Adding a body is one folder.
2. **Actions are the only way a daemon moves.** Every action passes one gate. STOP is a reflex outside any model.
3. **The answer is words with `{ACTIONS}` in braces**, performed as beats in the order written.
4. **Actions belong to the body. The self belongs to the daemon.**
5. **A body is a device that carries a daemon**, by the companion's own device list, key, carry and SELF.
6. **A body learns in three ways: SHOWN, TRIED and FOUND.** A new action is untrusted until it has proved itself.
7. **Bluetooth for what is near and small, Wi-Fi for the rest, and the body always dials out.**
8. **The machinery takes THE BRAIN's regions.** A body is one more host.
9. **Python on the body**, in this repository.
10. **Where a body thinks is a setting**: ON BOARD, MESH or HYBRID. A frontier model only when asked for and approved.
11. **A body learns to speak as it learns to move**: its words start few and grow, each kept in its daemon's own voice.

## The first build

A SunFounder PiDog (the first kit, Robot HAT V4) with the Raspberry Pi Zero 2 W that is in it and an M5Stack LLM630
Compute Kit as its brain. If the pair works, it is the part every later body is built round.

## Where things are

[LAYOUT.md](LAYOUT.md) is the map of the code, kept true as it is written. [TODO.md](TODO.md) is the list of
tickets, B-1 onward: a mirror of the project's Redmine, rebuilt every night.

## What is not here

No ROM and nothing of Nintendo's. No key, password or network name. Nothing personal: no daemon's SELF, no
recording, no save. No licence has been chosen yet.

## Its siblings

- [DAEMONS](https://github.com/CodeMusic/DAEMONS): the design bible, the tools, and this design's book.
- [daemons-companion](https://github.com/CodeMusic/daemons-companion): the app, the hub and the devices; who a daemon
  is lives there.
- [daemons-praxis](https://github.com/CodeMusic/daemons-praxis): the event log a body's days are written in.
- [daemons-eudaimonia](https://github.com/CodeMusic/daemons-eudaimonia): the dashboard where its tickets are seen.

DAEMONS is said DAY-mons.
