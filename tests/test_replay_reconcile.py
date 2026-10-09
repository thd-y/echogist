"""TD-36 replay-gate tests: the offline half only (variants, prices, reply inspection).

``scripts/replay_reconcile.py`` is a standalone script, so it is loaded by file path.
Its live calls are the operator's Windows run, never CI.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from echogist import summarize
from echogist.config import ModelTier

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "replay_reconcile.py"
_spec = importlib.util.spec_from_file_location("replay_reconcile", _SCRIPT)
assert _spec is not None and _spec.loader is not None
replay_reconcile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(replay_reconcile)

_TIER = ModelTier(
    name="balanced",
    model_id="claude-sonnet-5",
    context_window=1_000_000,
    price_in_per_mtok=3.0,
    price_out_per_mtok=15.0,
)


def test_a_variant_overrides_only_the_parts_it_names() -> None:
    v = replay_reconcile.parse_variant("claude-sonnet-5-5:between_tools:high", _TIER)
    assert (v.model_id, v.thinking, v.effort) == ("claude-sonnet-5-5", "between_tools", "high")
    bare = replay_reconcile.parse_variant("", _TIER)
    assert (bare.model_id, bare.thinking, bare.effort) == ("claude-sonnet-5", None, None)
    assert replay_reconcile.parse_variant("::low", _TIER).effort == "low"


@pytest.mark.parametrize("spec", ["claude-sonnet-5-5:disabled", "claude-sonnet-5-5::extreme"])
def test_a_variant_the_api_would_reject_is_refused_before_any_call(spec: str) -> None:
    with pytest.raises(ValueError, match="unknown"):
        replay_reconcile.parse_variant(spec, _TIER)


def test_prices_follow_the_variant_model_and_an_unknown_model_is_refused() -> None:
    tiers = {"balanced": _TIER}
    same = replay_reconcile.priced(replay_reconcile.parse_variant("", _TIER), tiers)
    assert (same.price_in_per_mtok, same.price_out_per_mtok) == (3.0, 15.0)
    newer = replay_reconcile.priced(
        replay_reconcile.parse_variant("claude-sonnet-5-5", _TIER), tiers
    )
    assert (newer.price_in_per_mtok, newer.price_out_per_mtok) == (2.0, 10.0)
    with pytest.raises(ValueError, match="no price known"):
        replay_reconcile.priced(replay_reconcile.parse_variant("claude-x-1", _TIER), tiers)


def test_inspect_reply_reports_blank_fields_and_markup_still_in_a_field() -> None:
    schema = summarize._reconcile_schema()
    fields = {
        "title": "",
        "core_idea": 'C.</parameter>\n<parameter name="main_skill">S.',
        "main_skill": "",
        "test_questions": [{"question": "q", "answer": "a"}],
        "main_themes": ["x"],
        "phase_headings": ["H"],
    }
    blank, leaked = replay_reconcile.inspect_reply(fields, schema)
    assert blank == ["title", "main_skill"]
    assert leaked == ["core_idea", "main_skill"]
