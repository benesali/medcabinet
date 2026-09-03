from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("caveat")
except PackageNotFoundError:
    __version__ = "dev"
