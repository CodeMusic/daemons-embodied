# daemons-embodied -- working agreement

A daemon in a robot body. The design is reviewed (2026-11-24) and its tickets are B-1 onward. **Phase A, the
foundations, is being built** (B-2 to B-5: the sheet, the driver's calls, the simulated body, the body check, the
wrapper to copy); no robot has moved yet. Tests: `python3 -m pytest` from this repository's root.

## Start here

- **Sessions are rooted in DAEMONS**, where this repository is linked as `embodied/`. Read DAEMONS' `CLAUDE.md`
  first: its rules bind here too.
- **The design is a book**: DAEMONS `docs/DAEMONS-embodied.pdf` (source `docs/manual-embodied/manual.md`), and the
  design bible's section 9.38. Read the part a ticket names before writing its code. Part 15 is what the user
  decided and what is still open.
- **[LAYOUT.md](LAYOUT.md) is the map of the code.** Keep it true in the same commit as any folder change.

## Tickets

They live in Redmine, in the `embodied` project (a sub-project of CONTEXT / CONTENT), ids **B-1 onward**, worked as
the lane **`body`**. [TODO.md](TODO.md) is their mirror, rebuilt every night: never edit a row by hand. From the
DAEMONS checkout:

    python3 tools/tickets.py mine --lane body --project embodied
    python3 tools/tickets.py new --lane body --project embodied --title "..." --from "the user, 2026-11-25"
    python3 tools/tickets.py claim B-2 --lane body --branch main
    python3 tools/tickets.py close B-2 --lane body --commit embodied@<sha>

## Rules the design fixes

Do not break one without an explicit decision by the user.

1. **Nothing a model wrote ever reaches a driver.** The body program passes only names and numbers it has checked
   against the sheet. No `eval`, no shell, anywhere a model's words travel.
2. **Every action passes the gate. STOP is a reflex outside any model**, and a wrapper proves it before anything
   else is built on it.
3. **The body program holds the hardware. The daemon's turn is its client.** A crash in the turn never leaves a
   servo mid-move.
4. **Mind and machine stay apart.** Who a daemon is stays in the companion. This repository is machinery, named for
   THE BRAIN's regions; it is handed a self as text and never builds one.
5. **A wrapper is one folder: a sheet and a driver.** No code outside `wrappers/` knows what kind of body it runs.
6. **A new action is untrusted** until it has run cleanly ten times with a person watching. PRACTICE needs a person
   present; nothing moves at night.
7. **Angles are degrees, lengths metres, speeds degrees a second**, on every body.

## What never goes in this repository

It is public. No key, password, token or network name: a body keeps those in its own configuration folder. No
daemon's SELF, no recording, no save, nothing personal. A test fails on anything that looks like a secret.

## Words

Every word a person reads or hears is DRAFT until the user approves it. DAEMONS is said DAY-mons: every line handed
to a voice is respelled first, and the other spelling of the word is never written.
