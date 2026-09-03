"""Unit tests for the WHO INN raw ingestor."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from caveat.pipeline.raw.who_inn import download, snapshot_dir


class TestSnapshotDir:
    def test_path_structure(self, tmp_path: Path) -> None:
        assert snapshot_dir(tmp_path, "133") == tmp_path / "who_inn" / "133"

    def test_different_version(self, tmp_path: Path) -> None:
        assert snapshot_dir(tmp_path, "latest") == tmp_path / "who_inn" / "latest"


class TestDownloadIdempotent:
    def test_skips_when_manifest_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        dest = snapshot_dir(tmp_path, "133")
        dest.mkdir(parents=True)
        (dest / "manifest.json").write_text("{}")

        called: list[str] = []
        monkeypatch.setattr(
            "caveat.pipeline.raw.who_inn.stream_download",
            lambda url, path: called.append(url),
        )

        result = download(raw_root=tmp_path, url="https://example.com/inn.csv", version="133")
        assert result == dest
        assert called == []

    def test_force_redownloads(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        dest = snapshot_dir(tmp_path, "133")
        dest.mkdir(parents=True)
        (dest / "manifest.json").write_text("{}")

        csv_content = b"INN,Status\nparacetamol,recommended\nibuprofen,recommended\n"

        def fake_download(url: str, path: Path) -> None:
            path.write_bytes(csv_content)

        monkeypatch.setattr("caveat.pipeline.raw.who_inn.stream_download", fake_download)

        result = download(
            raw_root=tmp_path,
            url="https://example.com/inn.csv",
            version="133",
            force=True,
        )
        assert result == dest
        manifest = json.loads((dest / "manifest.json").read_text())
        assert manifest["source"] == "WHO-INN"
        assert manifest["row_count"] == 2


class TestDownloadCsv:
    def test_csv_manifest_written(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        csv_content = b"INN,Status\nparacetamol,recommended\n"

        def fake_download(url: str, path: Path) -> None:
            path.write_bytes(csv_content)

        monkeypatch.setattr("caveat.pipeline.raw.who_inn.stream_download", fake_download)

        dest = download(
            raw_root=tmp_path,
            url="https://example.com/inn_list_133.csv",
            version="133",
        )
        manifest = json.loads((dest / "manifest.json").read_text())
        assert manifest["source"] == "WHO-INN"
        assert manifest["source_version"] == "133"
        assert manifest["row_count"] == 1
        assert manifest["encoding"] == "utf-8"


class TestDownloadZip:
    def test_zip_extracts_csvs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        zip_bytes_path = tmp_path / "prep.zip"
        with zipfile.ZipFile(zip_bytes_path, "w") as zf:
            zf.writestr("inn_list.csv", "INN\nparacetamol\nibuprofen\n")

        def fake_download(url: str, path: Path) -> None:
            path.write_bytes(zip_bytes_path.read_bytes())

        monkeypatch.setattr("caveat.pipeline.raw.who_inn.stream_download", fake_download)

        dest = download(
            raw_root=tmp_path,
            url="https://example.com/inn_list.zip",
            version="133",
        )
        assert (dest / "inn_list.csv").exists()
        assert not (dest / "inn_list.zip").exists()
        manifest = json.loads((dest / "manifest.json").read_text())
        assert manifest["files"] == ["inn_list.csv"]
        assert manifest["row_count"] is None


class TestDownloadPdf:
    def test_pdf_stored_as_is(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pdf_content = b"%PDF-1.4 fake pdf content"

        def fake_download(url: str, path: Path) -> None:
            path.write_bytes(pdf_content)

        monkeypatch.setattr("caveat.pipeline.raw.who_inn.stream_download", fake_download)

        dest = download(
            raw_root=tmp_path,
            url="https://example.com/inn_list_133.pdf",
            version="133",
        )
        assert (dest / "inn_list_133.pdf").exists()
        manifest = json.loads((dest / "manifest.json").read_text())
        assert manifest["encoding"] == "binary"
        assert manifest["row_count"] is None
        assert "inn_list_133.pdf" in manifest["files"]
