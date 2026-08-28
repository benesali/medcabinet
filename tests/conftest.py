from __future__ import annotations

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-apply markers based on test location."""
    for item in items:
        path = str(item.fspath)
        if "/eval/" in path or "\\eval\\" in path:
            item.add_marker(pytest.mark.eval)
        if "/integration/" in path or "\\integration\\" in path:
            item.add_marker(pytest.mark.integration)
