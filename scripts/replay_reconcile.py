#!/usr/bin/env python3
"""TD-36 experiment — replay ONLY the reconcile call over a saved summary's phases.

Reconcile drops a field (the title 3 times in 7 documents, ``main_skill`` and the
phase-heading outline once each), and the saved artifacts cannot say whether the key
was ABSENT from the reply or present and EMPTY. The two have different fixes: the tool
schema's ``required`` is only enforced when the tool is ``strict``, so strict mode
cures an absent key and does nothing for an empty one. This script measures the split:
it rebuilds the exact reconcile request the app sends from a saved ``.json`` (the phase
prose is in it, so no phase is re-bought), sends it ``--runs`` times as shipped and
``--runs`` times with ``strict: true``, and tallies absent / empty per field.

**Killswitch.** A STANDALONE script, like ``scripts/check-models.py``: nothing under
``echogist/`` imports it, and its calls happen only inside :func:`main`, after a y/N
prompt that shows the worst-case cost. It writes nothing. Run on Windows (the key is in
``config/secrets.toml`` there), from the repo root::

    .venv\\Scripts\\python.exe scripts\\replay_reconcile.py ^
        "output\\summaries\\raw\\2026-09-05-Модуль Стратегия, занятие 2.json" --runs 5
"""

from __future__ import annotations

import argparse
import copy
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from echogist import config, guard, render, summarize  # noqa: E402


def strict_variant(request: dict[str, Any]) -> dict[str, Any]:
    """``request`` with its tool made ``strict``: every object closed to extra keys."""
    out = copy.deepcopy(request)
    tool = out["tools"][0]
    tool["strict"] = True

    def close(schema: dict[str, Any]) -> None:
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
            for prop in schema.get("properties", {}).values():
                close(prop)
        if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
            close(schema["items"])

    close(tool["input_schema"])
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("summary", type=Path, help="a saved output/summaries/raw/*.json")
    parser.add_argument("--runs", type=int, default=5, help="calls per variant (default 5)")
    parser.add_argument("--tier", default="balanced", help="models.toml tier (default balanced)")
    args = parser.parse_args(argv)

    try:
        cfg = config.load_model_config()
        tier = cfg.tier(args.tier)
        saved = render.load_summary(args.summary)
    except (config.ConfigError, render.RenderError) as exc:
        print(exc)
        return 1
    key = config.get_api_key()
    if not key:
        print("No API key: set ANTHROPIC_API_KEY or config/secrets.toml.")
        return 1
    if not saved.synthesis:
        print(f"{args.summary} has no phases to reconcile.")
        return 1

    shipped = summarize.build_reconcile_request(
        saved.synthesis, tier, cfg.summarize, language=saved.language
    )
    variants = {"shipped": shipped, "strict": strict_variant(shipped)}
    calls = args.runs * len(variants)
    in_tok = guard.estimate_input_tokens(shipped["messages"][0]["content"])
    worst = calls * (
        in_tok * tier.price_in_per_mtok + cfg.summarize.max_output_tokens * tier.price_out_per_mtok
    )
    print(
        f"{len(saved.synthesis)} phases, ~{in_tok:,} input tokens per call, {tier.model_id}.\n"
        f"{calls} reconcile calls; at most ${worst / 1e6:.2f} (every reply at the output cap)."
    )
    if input("Proceed? [y/N] ").strip().lower() != "y":
        print("Cancelled; nothing was sent.")
        return 0

    fields = shipped["tools"][0]["input_schema"]["required"]
    spent_in = spent_out = 0
    for name, request in variants.items():
        absent_n: Counter[str] = Counter()
        empty_n: Counter[str] = Counter()
        for i in range(1, args.runs + 1):
            try:
                outcome = summarize._default_caller(request, key)
            except summarize.SummarizeError as exc:
                print(f"{name} #{i}: {exc}")
                return 1
            spent_in += outcome.input_tokens
            spent_out += outcome.output_tokens
            absent, empty = summarize.reconcile_gaps(outcome.tool_input)
            absent_n.update(absent)
            empty_n.update(empty)
            extra = sorted(set(outcome.tool_input) - set(fields))
            print(
                f"{name} #{i}: stop_reason={outcome.stop_reason}, "
                f"out={outcome.output_tokens}, absent={absent or '-'}, empty={empty or '-'}"
                + (f", unexpected keys={extra}" if extra else "")
            )
        print(f"\n{name}, {args.runs} runs — field: absent / empty")
        for field in fields:
            print(f"  {field}: {absent_n[field]} / {empty_n[field]}")
        print()
    spent = spent_in * tier.price_in_per_mtok + spent_out * tier.price_out_per_mtok
    print(f"Actual cost: ${spent / 1e6:.4f} ({spent_in:,} input + {spent_out:,} output tokens).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
