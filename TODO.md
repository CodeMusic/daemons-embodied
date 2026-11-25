# TODO -- daemons-embodied

Work that has been **decided and not done** for DAEMONS EMBODIED -- a daemon in a robot body -- kept the way DAEMONS
keeps its own (`DAEMONS/docs/TODO.md`): ids are permanent, a closed ticket is struck through with its commit, never
deleted. Its design is a book, DAEMONS' `docs/DAEMONS-embodied.pdf`, and the questions still **OPEN** in it are in
that book's Part 15 and in section 10 of DAEMONS' `docs/vision.md`; a ticket waits on a question by naming it.

**The table below is a mirror.** The tickets live in Redmine, in the `embodied` project (a sub-project of CONTEXT /
CONTENT beside `daemons`, `companion` and `eudaimonia`), with ids B-1 onward: B for BODIES (the user, 2026-11-24, by
multiple choice). DAEMONS' `tools/tickets.py` rebuilds this table from it every night at 04:45 and commits it here,
so a fresh clone can still read every ticket. Never edit a row by hand: open, claim and close tickets with the tool,
from the DAEMONS checkout, as the `body` lane:

    python3 tools/tickets.py mine --lane body --project embodied
    python3 tools/tickets.py new --lane body --project embodied --title "..." --from "the user, 2026-11-25"
    python3 tools/tickets.py claim B-2 --lane body --branch main
    python3 tools/tickets.py close B-2 --lane body --commit embodied@<sha>

The tickets follow the design book's phases, A to L (its Part 14). B-1 is the design itself and stays open while
anything of it is unbuilt.

| | Ticket | State | See |
|---|---|---|---|
| **B-1** | **DAEMONS EMBODIED: the reviewed design, kept true as it is built** (*the user, 2026-11-24*): The parent. A daemon in a robot body: one body program and a wrapper for each kind of body, the PiDog first. The design is DAEMONS' docs/DAEMONS-embodied.pdf (62 pages; source docs/manual-embodied/) and bible 9.38, reviewed by the user on 2026-11-24 by multiple choice: braces; a Pi Zero 2 W with an LLM630 Compute Kit as its brain; the body keeps a learned action; ROAM; no practice alone; one wake word of our own and a touch; where it thinks a setting (ON BOARD, MESH, HYBRID; a frontier model only on request and approval); it learns to speak as it learns to move. This ticket holds the book and the bible true as the tickets below change what is built, and the five things still open (the wake word, the kit on the bench, the book's voice in T-634, speech on the phone, the second robot). DRAFT. |  | DAEMONS docs/manual-embodied/, docs/vision.md 9.38; T-617, T-634, C-549 |
