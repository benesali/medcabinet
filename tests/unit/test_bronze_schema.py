"""Unit tests for the Bronze PostgreSQL schema definitions."""

from __future__ import annotations

from caveat.pipeline.bronze import metadata
from caveat.pipeline.bronze.ddinter import ddinter_interactions
from caveat.pipeline.bronze.sukl import (
    SUKL_TABLES,
    sukl_atc,
    sukl_cancelled,
    sukl_contains,
    sukl_drugs,
    sukl_ingredients,
    sukl_synonyms,
)
from caveat.pipeline.bronze.who_inn import who_inn


class TestMetadata:
    def test_schema_name(self) -> None:
        assert metadata.schema == "bronze"

    def test_all_tables_registered(self) -> None:
        names = set(metadata.tables.keys())
        assert "bronze.sukl_drugs" in names
        assert "bronze.sukl_ingredients" in names
        assert "bronze.sukl_contains" in names
        assert "bronze.sukl_atc" in names
        assert "bronze.sukl_synonyms" in names
        assert "bronze.sukl_cancelled" in names
        assert "bronze.ddinter_interactions" in names
        assert "bronze.who_inn" in names


class TestMetadataColumns:
    """Every table must have the three technical metadata columns."""

    def _meta_col_names(self, table) -> set[str]:  # type: ignore[no-untyped-def]
        return {c.name for c in table.columns if c.name.startswith("_")}

    def test_sukl_drugs_has_meta(self) -> None:
        assert self._meta_col_names(sukl_drugs) == {"_source_file", "_load_ts", "_batch_id"}

    def test_sukl_ingredients_has_meta(self) -> None:
        assert self._meta_col_names(sukl_ingredients) == {"_source_file", "_load_ts", "_batch_id"}

    def test_sukl_contains_has_meta(self) -> None:
        assert self._meta_col_names(sukl_contains) == {"_source_file", "_load_ts", "_batch_id"}

    def test_ddinter_has_meta(self) -> None:
        assert self._meta_col_names(ddinter_interactions) == {"_source_file", "_load_ts", "_batch_id"}

    def test_who_inn_has_meta(self) -> None:
        assert self._meta_col_names(who_inn) == {"_source_file", "_load_ts", "_batch_id"}


class TestSuklDrugsColumns:
    def test_required_columns_present(self) -> None:
        col_names = {c.name for c in sukl_drugs.columns}
        for expected in ["KOD_SUKL", "NAZEV", "FORMA", "ATC_WHO", "REG", "VYDEJ", "RC"]:
            assert expected in col_names, f"Missing column: {expected}"

    def test_all_source_columns_are_text(self) -> None:
        for col in sukl_drugs.columns:
            if not col.name.startswith("_"):
                assert "TEXT" in str(col.type).upper(), f"{col.name} is not TEXT"


class TestSuklIngredientsColumns:
    def test_inn_columns_present(self) -> None:
        col_names = {c.name for c in sukl_ingredients.columns}
        assert "KOD_LATKY" in col_names
        assert "NAZEV_EN" in col_names
        assert "NAZEV_INN" in col_names


class TestSuklContainsColumns:
    def test_dose_columns_present(self) -> None:
        col_names = {c.name for c in sukl_contains.columns}
        assert "S" in col_names  # active/excipient flag
        assert "AMNT" in col_names
        assert "UN" in col_names


class TestDDInterColumns:
    def test_required_columns_present(self) -> None:
        col_names = {c.name for c in ddinter_interactions.columns}
        assert "Drug1" in col_names
        assert "Drug2" in col_names
        assert "Level" in col_names
        assert "Interaction" in col_names


class TestSuklTablesRegistry:
    def test_all_key_csvs_mapped(self) -> None:
        assert "dlp_lecivepripravky.csv" in SUKL_TABLES
        assert "dlp_lecivelatky.csv" in SUKL_TABLES
        assert "dlp_slozeni.csv" in SUKL_TABLES
        assert "dlp_atc.csv" in SUKL_TABLES
        assert "dlp_synonyma.csv" in SUKL_TABLES
        assert "dlp_zruseneregistrace.csv" in SUKL_TABLES

    def test_registry_maps_to_correct_tables(self) -> None:
        assert SUKL_TABLES["dlp_lecivepripravky.csv"][0] is sukl_drugs
        assert SUKL_TABLES["dlp_lecivelatky.csv"][0] is sukl_ingredients
        assert SUKL_TABLES["dlp_slozeni.csv"][0] is sukl_contains
        assert SUKL_TABLES["dlp_atc.csv"][0] is sukl_atc
        assert SUKL_TABLES["dlp_synonyma.csv"][0] is sukl_synonyms
        key = "dlp_cancelled.csv" if "dlp_cancelled.csv" in SUKL_TABLES else "dlp_zruseneregistrace.csv"
        assert SUKL_TABLES[key][0] is sukl_cancelled
