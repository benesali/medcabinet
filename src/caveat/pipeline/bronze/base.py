"""Shared utilities for all CAVEAT bronze ingestors."""

from __future__ import annotations

import logging
import zipfile
from enum import StrEnum
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class SourceName(StrEnum):
    SUKL = "SÚKL"
    SUKL_HISTORY = "SÚKL-history"
    SUKL_SPC = "SÚKL-SPC"
    SUKL_PIL = "SÚKL-PIL"
    DDINTER = "DDInter"


def stream_download(url: str, dest: Path) -> None:
    """Stream *url* to *dest*, printing a progress indicator."""
    with (
        httpx.Client(follow_redirects=True, timeout=180) as client,
        client.stream("GET", url) as response,
    ):
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        received = 0
        with dest.open("wb") as fh:
            for chunk in response.iter_bytes(chunk_size=65536):
                fh.write(chunk)
                received += len(chunk)
                if total:
                    print(
                        f"\r  {received / total * 100:.1f}%  ({received:,} / {total:,} B)",
                        end="",
                        flush=True,
                    )
        print()


def extract_csvs(zip_path: Path, dest_dir: Path) -> list[Path]:
    """Extract all CSV members from *zip_path* into *dest_dir*, flattening subdirectories.

    Handles ZIP files created on Windows (backslash path separators in member names).
    """
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if not member.lower().endswith(".csv"):
                continue
            # Normalize Windows-style backslashes before deriving the basename.
            member_posix = member.replace("\\", "/")
            basename = Path(member_posix).name
            zf.extract(member, dest_dir)
            # zf.extract writes using the raw member name. On Linux, backslashes
            # are literal filename chars, so the file lands at dest_dir/member.
            extracted_at = dest_dir / member
            out = dest_dir / basename
            if extracted_at != out:
                extracted_at.rename(out)
            extracted.append(out)
            logger.info("Extracted: %s", out.name)
    if not extracted:
        raise RuntimeError(f"No CSV files found in ZIP: {zip_path}")
    return extracted
