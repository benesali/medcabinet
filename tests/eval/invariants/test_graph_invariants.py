"""
Layer 1 graph invariants — run in CI against the seeded graph.

These are deterministic Cypher-based assertions. A failed invariant means
the data pipeline is broken, not the application. Fix data before debugging
AI layers.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.eval, pytest.mark.integration]


@pytest.mark.skip(reason="placeholder — implement when Neo4j graph is seeded (Phase 1)")
def test_interaction_symmetry(neo4j_driver) -> None:
    """If A interacts with B then B interacts with A."""
    result = neo4j_driver.execute_query(
        """
        MATCH (a:ActiveIngredient)-[:INTERACTS_WITH]->(b:ActiveIngredient)
        WHERE NOT (b)-[:INTERACTS_WITH]->(a)
        RETURN count(*) AS asymmetric
        """,
    )
    assert result.records[0]["asymmetric"] == 0, "Asymmetric interactions found — data pipeline error"


@pytest.mark.skip(reason="placeholder — implement when Neo4j graph is seeded (Phase 1)")
def test_every_active_ingredient_has_inn(neo4j_driver) -> None:
    result = neo4j_driver.execute_query(
        "MATCH (ai:ActiveIngredient) WHERE ai.inn IS NULL OR ai.inn = '' RETURN count(*) AS missing",
    )
    assert result.records[0]["missing"] == 0, "ActiveIngredients without INN found"


@pytest.mark.skip(reason="placeholder — implement when Neo4j graph is seeded (Phase 1)")
def test_every_drug_has_active_ingredient(neo4j_driver) -> None:
    result = neo4j_driver.execute_query(
        "MATCH (d:Drug) WHERE NOT (d)-[:CONTAINS]->(:ActiveIngredient) RETURN count(*) AS orphaned",
    )
    assert result.records[0]["orphaned"] == 0, "Drugs with no active ingredient found"


@pytest.mark.skip(reason="placeholder — implement when Neo4j graph is seeded (Phase 1)")
def test_no_self_interaction(neo4j_driver) -> None:
    result = neo4j_driver.execute_query(
        "MATCH (ai:ActiveIngredient)-[:INTERACTS_WITH]->(ai) RETURN count(*) AS self_loops",
    )
    assert result.records[0]["self_loops"] == 0, "Drug self-interactions found"


@pytest.mark.skip(reason="placeholder — implement when Neo4j graph is seeded (Phase 1)")
def test_every_interaction_has_source(neo4j_driver) -> None:
    result = neo4j_driver.execute_query(
        """
        MATCH ()-[r:INTERACTS_WITH]->()
        WHERE NOT (r)-[:ASSERTED_BY]->(:Source)
        RETURN count(*) AS unsourced
        """,
    )
    assert result.records[0]["unsourced"] == 0, "Interactions without Source provenance found"
