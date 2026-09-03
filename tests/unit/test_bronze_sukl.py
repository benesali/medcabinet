"""Unit tests for the SÚKL DLP Bronze ingestor (caveat.pipeline.bronze.sukl).

Network-free: all tests use either pure functions or in-memory / tmp_path fixtures.
"""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import pytest

from caveat.pipeline.bronze.base import extract_csvs
from caveat.pipeline.bronze.sukl import (
    _version_from_pdf_url,
    _version_from_url,
    history_snapshot_dir,
    history_url,
    snapshot_dir,
)

# ---------------------------------------------------------------------------
# _version_from_url
# ---------------------------------------------------------------------------


class TestVersionFromUrl:
    def test_standard_url(self) -> None:
        url = "https://opendata.sukl.cz/soubory/SOD20260827/DLP20260827.zip"
        assert _version_from_url(url) == "20260827"

    def test_different_date(self) -> None:
        url = "https://opendata.sukl.cz/soubory/SOD20250101/DLP20250101.zip"
        assert _version_from_url(url) == "20250101"

    def test_unrecognised_url_returns_unknown(self) -> None:
        assert _version_from_url("https://example.com/file.zip") == "unknown"


# ---------------------------------------------------------------------------
# _version_from_pdf_url
# ---------------------------------------------------------------------------


class TestVersionFromPdfUrl:
    def test_spc_url(self) -> None:
        url = "https://opendata.sukl.cz/soubory/SOD20260827/SPC20260827.zip"
        assert _version_from_pdf_url(url, "SPC") == "20260827"

    def test_pil_url(self) -> None:
        url = "https://opendata.sukl.cz/soubory/SOD20260827/PIL20260827.zip"
        assert _version_from_pdf_url(url, "PIL") == "20260827"

    def test_unrecognised_returns_unknown(self) -> None:
        assert _version_from_pdf_url("https://example.com/other.zip", "SPC") == "unknown"


# ---------------------------------------------------------------------------
# snapshot_dir / history_snapshot_dir / history_url
# ---------------------------------------------------------------------------


class TestPathHelpers:
    def test_snapshot_dir(self, tmp_path: Path) -> None:
        result = snapshot_dir(tmp_path, date(2026, 9, 2))
        assert result == tmp_path / "sukl" / "dlp" / "2026-09-02"

    def test_history_snapshot_dir(self, tmp_path: Path) -> None:
        result = history_snapshot_dir(tmp_path, 2025, 8)
        assert result == tmp_path / "sukl" / "dlp_history" / "2025-08"

    @pytest.mark.parametrize(
        "month, expected_suffix",
        [
            (1, "DLP202601.zip"),
            (8, "DLP202608.zip"),
            (12, "DLP202612.zip"),
        ],
    )
    def test_history_url(self, month: int, expected_suffix: str) -> None:
        url = history_url(2026, month)
        assert url.endswith(expected_suffix)
        assert "SOD2026" in url


# ---------------------------------------------------------------------------
# _extract_csvs
# ---------------------------------------------------------------------------


def _make_zip(tmp_path: Path, members: dict[str, bytes]) -> Path:
    """Build a ZIP at tmp_path/test.zip with the given {name: content} members."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return zip_path


class TestExtractCsvs:
    def test_flat_csv_extracted(self, tmp_path: Path) -> None:
        zip_path = _make_zip(tmp_path, {"file.csv": b"a;b\n1;2\n"})
        dest = tmp_path / "out"
        dest.mkdir()
        result = extract_csvs(zip_path, dest)
        assert len(result) == 1
        assert result[0].name == "file.csv"
        assert result[0].read_bytes() == b"a;b\n1;2\n"

    def test_subdirectory_member_flattened(self, tmp_path: Path) -> None:
        zip_path = _make_zip(tmp_path, {"subdir/file.csv": b"col\nval\n"})
        dest = tmp_path / "out"
        dest.mkdir()
        result = extract_csvs(zip_path, dest)
        assert len(result) == 1
        assert result[0] == dest / "file.csv"

    def test_backslash_member_flattened(self, tmp_path: Path) -> None:
        # Simulate a Windows-created ZIP with backslash path separators.
        zip_path = _make_zip(tmp_path, {"subdir\\file.csv": b"x\n1\n"})
        dest = tmp_path / "out"
        dest.mkdir()
        result = extract_csvs(zip_path, dest)
        assert len(result) == 1
        assert result[0].name == "file.csv"

    def test_non_csv_members_skipped(self, tmp_path: Path) -> None:
        zip_path = _make_zip(
            tmp_path,
            {
                "data.csv": b"a\n1\n",
                "readme.txt": b"ignore me",
                "schema.xml": b"<x/>",
            },
        )
        dest = tmp_path / "out"
        dest.mkdir()
        result = extract_csvs(zip_path, dest)
        assert len(result) == 1
        assert result[0].name == "data.csv"

    def test_multiple_csvs_all_returned(self, tmp_path: Path) -> None:
        zip_path = _make_zip(
            tmp_path,
            {
                "a.csv": b"1\n",
                "b.csv": b"2\n",
                "c.csv": b"3\n",
            },
        )
        dest = tmp_path / "out"
        dest.mkdir()
        result = extract_csvs(zip_path, dest)
        assert {r.name for r in result} == {"a.csv", "b.csv", "c.csv"}

    def test_no_csvs_raises(self, tmp_path: Path) -> None:
        zip_path = _make_zip(tmp_path, {"readme.txt": b"nothing here"})
        dest = tmp_path / "out"
        dest.mkdir()
        with pytest.raises(RuntimeError, match="No CSV files found"):
            extract_csvs(zip_path, dest)
