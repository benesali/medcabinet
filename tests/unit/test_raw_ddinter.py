"""Unit tests for the DDInter raw ingestor."""

from __future__ import annotations

from pathlib import Path

from caveat.pipeline.raw.ddinter import snapshot_dir


class TestSnapshotDir:
    def test_path_structure(self, tmp_path: Path) -> None:
        result = snapshot_dir(tmp_path, "2.0")
        assert result == tmp_path / "ddinter" / "2.0"

    def test_different_version(self, tmp_path: Path) -> None:
        assert snapshot_dir(tmp_path, "3.0") == tmp_path / "ddinter" / "3.0"
