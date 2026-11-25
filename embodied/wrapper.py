"""A wrapper is one folder: a sheet and a driver. This loads one, and knows nothing of what kind it is.

The folder holds `sheet.yaml` and `driver.py`; `driver.py` holds a class named `Driver`, built on `BaseDriver`.
The folder is given by a person or a body's own configuration, never by a model.
"""

from __future__ import annotations

import importlib
import re
import sys
import types
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import sheet as sheets
from .driver import BaseDriver
from .sheet import Sheet

DRIVER_FILE = "driver.py"


class WrapperError(ValueError):
    """The folder is not a wrapper that can be loaded."""


@dataclass(frozen=True)
class Wrapper:
    folder: Path
    sheet: Sheet
    driver_class: type[BaseDriver]
    package: str

    def driver(self, **options: Any) -> BaseDriver:
        """A new driver for this body. Options are the body's own configuration, never kept in the repository."""
        return self.driver_class(self.sheet, **options)

    def module(self, name: str) -> types.ModuleType:
        """Another module of the wrapper's own folder."""
        return importlib.import_module(f"{self.package}.{name}")


def load(folder: str | Path) -> Wrapper:
    """Read the folder's sheet, then load its driver. Raises SheetError or WrapperError."""
    folder = Path(folder).resolve()
    sheet = sheets.read(folder)
    return Wrapper(folder, sheet, load_driver(folder), _package(folder))


def load_driver(folder: str | Path) -> type[BaseDriver]:
    """The folder's `Driver` class, without reading its sheet."""
    folder = Path(folder).resolve()
    if not (folder / DRIVER_FILE).is_file():
        raise WrapperError(f"{folder.name}: there is no {DRIVER_FILE} beside the sheet")
    package = _package(folder)
    if package not in sys.modules:
        # The folder becomes a package of its own, so the driver can import the modules beside it.
        pkg = types.ModuleType(package)
        pkg.__path__ = [str(folder)]
        sys.modules[package] = pkg
    module = importlib.import_module(f"{package}.driver")
    driver_class = getattr(module, "Driver", None)
    if not isinstance(driver_class, type) or not issubclass(driver_class, BaseDriver):
        raise WrapperError(f"{folder.name}: {DRIVER_FILE} needs a class named Driver, built on BaseDriver")
    return driver_class


def found(wrappers: str | Path) -> list[Path]:
    """Every wrapper folder under a `wrappers/` directory: each folder that holds a sheet."""
    root = Path(wrappers)
    return sorted(p.parent for p in root.glob(f"*/{sheets.SHEET_FILE}"))


def _package(folder: Path) -> str:
    digest = format(zlib.crc32(str(folder).encode("utf-8")), "08x")
    return "embodied_wrapper_" + re.sub(r"\W", "_", folder.name) + "_" + digest
