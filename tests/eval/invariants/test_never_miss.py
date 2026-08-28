"""
Layer 1 safety invariants — the never-miss set.

These tests represent clinically critical drug combinations where a missed
interaction is catastrophically worse than a false positive. CI fails hard
if any test here fails, regardless of overall test suite status.

Add combinations from the safety spec; never remove without a documented
clinical review.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.never_miss


@pytest.mark.skip(reason="placeholder — implement when Neo4j graph is seeded (Phase 1)")
def test_warfarin_nsaid_interaction_detected(neo4j_driver) -> None:
    """Anticoagulant + NSAID is a canonical never-miss combination."""
    result = neo4j_driver.execute_query(
        """
        MATCH (a:ActiveIngredient {inn: 'warfarin'})
              -[:INTERACTS_WITH|CONTRAINDICATED_WITH]-(b:ActiveIngredient {inn: 'ibuprofen'})
        RETURN count(*) AS found
        """,
    )
    assert result.records[0]["found"] >= 1, "warfarin ↔ ibuprofen interaction missing from graph"


@pytest.mark.skip(reason="placeholder — implement when Neo4j graph is seeded (Phase 1)")
def test_ssri_tramadol_serotonin_syndrome(neo4j_driver) -> None:
    """Serotonin syndrome risk — SSRI + tramadol."""
    result = neo4j_driver.execute_query(
        """
        MATCH (a:ActiveIngredient {inn: 'sertraline'})
              -[:INTERACTS_WITH|CONTRAINDICATED_WITH]-(b:ActiveIngredient {inn: 'tramadol'})
        RETURN count(*) AS found
        """,
    )
    assert result.records[0]["found"] >= 1, "sertraline ↔ tramadol (serotonin syndrome) interaction missing from graph"


@pytest.mark.skip(reason="placeholder — implement when Neo4j graph is seeded (Phase 1)")
def test_paracetamol_duplication_not_permitted(neo4j_driver) -> None:
    """Two drugs with paracetamol must surface a duplication warning."""
    result = neo4j_driver.execute_query(
        """
        MATCH (d1:Drug)-[:CONTAINS]->(ai:ActiveIngredient {inn: 'paracetamol'})
        MATCH (d2:Drug)-[:CONTAINS]->(ai)
        WHERE d1 <> d2
        RETURN count(*) AS pairs
        """,
    )
    assert result.records[0]["pairs"] >= 1, "No paracetamol-duplication pairs found — seeding incomplete"
