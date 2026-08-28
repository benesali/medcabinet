from __future__ import annotations

import caveat


def test_version_is_string() -> None:
    assert isinstance(caveat.__version__, str)
    assert len(caveat.__version__) > 0
