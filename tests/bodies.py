"""Finding the wrappers the tests can run, without naming any kind of body."""

from __future__ import annotations

from pathlib import Path

from embodied import wrapper

ROOT = Path(__file__).resolve().parent.parent
WRAPPERS = ROOT / "wrappers"


def folders() -> list[Path]:
    """Every wrapper in the repository, the one to copy among them."""
    return wrapper.found(WRAPPERS)


def without_hardware() -> list[wrapper.Wrapper]:
    """The bodies that are only their sheets: these run on any computer."""
    out = []
    for folder in folders():
        if folder.name.startswith("_"):
            continue
        try:
            w = wrapper.load(folder)
        except ImportError:
            continue  # its maker's library is not on this computer
        if not w.driver_class.hardware:
            out.append(w)
    return out
