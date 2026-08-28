from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def neo4j_driver():
    """Real Neo4j driver — eval tests use the actual graph, never mocks."""
    from neo4j import GraphDatabase

    from caveat.config import settings

    driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    yield driver
    driver.close()
