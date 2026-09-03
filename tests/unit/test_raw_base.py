"""Unit tests for caveat.pipeline.raw.base shared utilities."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from caveat.pipeline.raw.base import SourceName, extract_csvs


class TestSourceName:
    def test_values_are_strings(self) -> None:
        assert isinstance(SourceName.SUKL, str)
        assert SourceName.SUKL == "SÚKL"
        assert SourceName.DDINTER == "DDInter"

    def test_all_names_defined(self) -> None:
        names = {s.value for s in SourceName}
        assert "SÚKL" in names
        assert "DDInter" in names
        assert "WHO-INN" in names


def _make_zip(tmp_path: Path, members: dict[str, bytes]) -> Path:
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return zip_path


class TestExtractCsvs:
    def test_flat(self, tmp_path: Path) -> None:
        zp = _make_zip(tmp_path, {"a.csv": b"x\n"})
        dest = tmp_path / "out"
        dest.mkdir()
        result = extract_csvs(zp, dest)
        assert [r.name for r in result] == ["a.csv"]

    def test_subdirectory_flattened(self, tmp_path: Path) -> None:
        zp = _make_zip(tmp_path, {"sub/a.csv": b"x\n"})
        dest = tmp_path / "out"
        dest.mkdir()
        result = extract_csvs(zp, dest)
        assert result[0] == dest / "a.csv"

    def test_backslash_flattened(self, tmp_path: Path) -> None:
        zp = _make_zip(tmp_path, {"sub\\a.csv": b"x\n"})
        dest = tmp_path / "out"
        dest.mkdir()
        result = extract_csvs(zp, dest)
        assert result[0].name == "a.csv"

    def test_non_csv_skipped(self, tmp_path: Path) -> None:
        zp = _make_zip(tmp_path, {"a.csv": b"x\n", "b.txt": b"y\n"})
        dest = tmp_path / "out"
        dest.mkdir()
        assert len(extract_csvs(zp, dest)) == 1

    def test_empty_zip_raises(self, tmp_path: Path) -> None:
        zp = _make_zip(tmp_path, {"readme.txt": b"hi"})
        dest = tmp_path / "out"
        dest.mkdir()
        with pytest.raises(RuntimeError, match="No CSV files found"):
            extract_csvs(zp, dest)
