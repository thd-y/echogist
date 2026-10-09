"""TD-36 replay-script tests: the offline half only (the strict request rewrite).

``scripts/replay_reconcile.py`` is a standalone script, so it is loaded by file path.
Its live calls are the operator's Windows run, never CI.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from echogist import summarize

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "replay_reconcile.py"
_spec = importlib.util.spec_from_file_location("replay_reconcile", _SCRIPT)
assert _spec is not None and _spec.loader is not None
replay_reconcile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(replay_reconcile)


def _objects(schema: dict[str, Any]) -> list[dict[str, Any]]:
    found = [schema] if schema.get("type") == "object" else []
    for prop in schema.get("properties", {}).values():
        found += _objects(prop)
    if isinstance(schema.get("items"), dict):
        found += _objects(schema["items"])
    return found


def test_strict_variant_closes_every_object_and_leaves_the_shipped_request_alone() -> None:
    shipped = {"tools": [summarize._reconcile_tool_schema()]}
    strict = replay_reconcile.strict_variant(shipped)

    tool = strict["tools"][0]
    assert tool["strict"] is True
    objects = _objects(tool["input_schema"])
    assert len(objects) == 2  # the reply itself + one test question
    assert all(o["additionalProperties"] is False for o in objects)
    original = shipped["tools"][0]
    assert "strict" not in original
    assert not any("additionalProperties" in o for o in _objects(original["input_schema"]))
