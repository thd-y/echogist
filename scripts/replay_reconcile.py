#!/usr/bin/env python3
"""TD-36 gate — replay one reconcile or phase call from a saved summary, per model variant.

Forced tool-use let Sonnet write its own tool-call markup inside the JSON strings, so
fields landed inside each other (5 of 7 Strategy documents). The pipeline now asks for
structured outputs instead. This script is the paid gate for that change and for the
model each tier runs: it rebuilds the EXACT request the app sends — the real
``build_reconcile_request`` / ``build_synthesis_request`` — from a saved ``.json`` (and,
for a phase, its transcript, found by fingerprint), sends it ``--runs`` times per
``--variant``, and reports per reply: stop reason, output tokens, seconds, blank required
fields, and any tool markup still written into a field.

A variant is ``MODEL[:THINKING[:EFFORT]]`` over the ``--tier`` it starts from, e.g.
``claude-sonnet-5``, ``claude-sonnet-5-5:between_tools:high``,
``claude-sonnet-5-5:adaptive:low``. An empty part keeps the tier's value.

**Killswitch.** A STANDALONE script, like ``scripts/check-models.py``: nothing under
``echogist/`` imports it, and its calls happen only inside :func:`main`, after a y/N
prompt that shows the worst-case cost. It writes nothing unless ``--dump`` names a file
for the raw replies. Run on Windows (the key comes from ``ANTHROPIC_API_KEY`` or
``config/secrets.toml``), from the repo root::

    .venv\\Scripts\\python.exe scripts\\replay_reconcile.py ^
        "output\\summaries\\raw\\2026-09-05-Модуль Стратегия, занятие 2.json" ^
        --variant claude-sonnet-5 --variant claude-sonnet-5-5:between_tools:high ^
        --runs 3 --phase 7 --dump phase7.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from echogist import chunk, config, guard, paths, render, summarize  # noqa: E402
from echogist.config import ModelTier  # noqa: E402

# $/MTok (in, out) for a variant model no models.toml tier carries yet. Anthropic's
# price table, 2026-10-06; used only for the y/N ceiling and the actual-cost line.
_KNOWN_PRICES = {
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5-5": (4.0, 20.0),
}


def parse_variant(spec: str, tier: ModelTier) -> ModelTier:
    """``tier`` with the variant's model, thinking and effort applied; prices follow the
    model. An unknown thinking/effort is refused here, before anything is sent."""
    model, thinking, effort = (spec.split(":") + ["", ""])[:3]
    out = replace(
        tier,
        model_id=model or tier.model_id,
        thinking=thinking or tier.thinking,
        effort=effort or tier.effort,
    )
    if out.thinking not in (None, *config._THINKING_TYPES):
        raise ValueError(f"unknown thinking '{out.thinking}' in variant '{spec}'")
    if out.effort not in (None, *config._EFFORT_LEVELS):
        raise ValueError(f"unknown effort '{out.effort}' in variant '{spec}'")
    return out


def priced(variant: ModelTier, tiers: dict[str, ModelTier]) -> ModelTier:
    """``variant`` carrying the prices of whichever tier runs its model, else the known
    table; a model with neither is refused, so the ceiling is never a guess."""
    for tier in tiers.values():
        if tier.model_id == variant.model_id:
            return replace(
                variant,
                price_in_per_mtok=tier.price_in_per_mtok,
                price_out_per_mtok=tier.price_out_per_mtok,
            )
    if variant.model_id in _KNOWN_PRICES:
        price_in, price_out = _KNOWN_PRICES[variant.model_id]
        return replace(variant, price_in_per_mtok=price_in, price_out_per_mtok=price_out)
    raise ValueError(f"no price known for '{variant.model_id}'; add it to models.toml")


def inspect_reply(fields: dict[str, Any], schema: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The required fields a reply left blank, and the fields whose text still carried
    tool markup (moved back by :func:`summarize.repair_leaked_markup`). Pure."""
    blank = [k for k in schema["required"] if summarize._is_blank(fields.get(k))]
    repaired, _, _ = summarize.repair_leaked_markup(fields, schema)
    leaked = [k for k in fields if repaired.get(k) != fields[k]]
    return blank, leaked


def _phase_request(
    saved: summarize.Summary,
    number: int,
    variant: ModelTier,
    cfg: config.ModelConfig,
    base: Path,
) -> dict[str, Any]:
    """The phase request the app sent, rebuilt: the transcript found by fingerprint, the
    same phase plan, and the saved earlier phases as the continuity context."""
    found = sorted(paths.transcripts(base).glob(f"*-{saved.source_fingerprint}.txt"))
    if not saved.source_fingerprint or not found:
        raise ValueError("its transcript is not in output/transcripts (matched by fingerprint)")
    phases = chunk.plan_phases(found[-1].read_text(encoding="utf-8"), cfg.chunk)
    if len(phases) != len(saved.synthesis):
        raise ValueError(
            f"the transcript plans {len(phases)} phases today but the summary has "
            f"{len(saved.synthesis)}; [chunk] changed since, so the replay would not match"
        )
    if not 1 <= number <= len(phases):
        raise ValueError(f"--phase must be 1..{len(phases)}")
    return summarize.build_synthesis_request(
        phases[number - 1],
        variant,
        cfg.summarize,
        language=saved.language,
        prior_context=summarize._prior_context(saved.synthesis[: number - 1]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("summary", type=Path, help="a saved output/summaries/raw/*.json")
    parser.add_argument(
        "--variant",
        action="append",
        help="MODEL[:THINKING[:EFFORT]]; repeat for several (default: the tier as is)",
    )
    parser.add_argument("--runs", type=int, default=3, help="calls per variant (default 3)")
    parser.add_argument("--tier", default="balanced", help="models.toml tier (default balanced)")
    parser.add_argument("--phase", type=int, help="replay phase N instead of the reconcile")
    parser.add_argument("--base", type=Path, default=_APP_ROOT, help="folder holding output/")
    parser.add_argument("--dump", type=Path, help="also write every raw reply to this .jsonl")
    args = parser.parse_args(argv)

    try:
        cfg = config.load_model_config()
        tier = cfg.tier(args.tier)
        saved = render.load_summary(args.summary)
        variants = [priced(parse_variant(spec, tier), cfg.tiers) for spec in (args.variant or [""])]
        requests = [
            _phase_request(saved, args.phase, v, cfg, args.base)
            if args.phase
            else summarize.build_reconcile_request(
                saved.synthesis, v, cfg.summarize, language=saved.language
            )
            for v in variants
        ]
    except (config.ConfigError, render.RenderError, ValueError) as exc:
        print(exc)
        return 1
    key = config.get_api_key()
    if not key:
        print("No API key: set ANTHROPIC_API_KEY or config/secrets.toml.")
        return 1
    if not saved.synthesis:
        print(f"{args.summary} has no phases.")
        return 1

    target = f"phase {args.phase}" if args.phase else "reconcile"
    in_tok = guard.estimate_input_tokens(
        requests[0]["system"] + requests[0]["messages"][0]["content"]
    )
    worst = args.runs * sum(
        in_tok * v.price_in_per_mtok + cfg.summarize.max_output_tokens * v.price_out_per_mtok
        for v in variants
    )
    print(
        f"{target} of {args.summary.name}: ~{in_tok:,} input tokens per call.\n"
        f"{args.runs * len(variants)} calls over {len(variants)} variant(s); "
        f"at most ${worst / 1e6:.2f} (every reply at the output cap)."
    )
    if input("Proceed? [y/N] ").strip().lower() != "y":
        print("Cancelled; nothing was sent.")
        return 0

    dump = args.dump.open("w", encoding="utf-8") if args.dump else None
    spent = 0.0
    try:
        for variant, request in zip(variants, requests, strict=True):
            name = ":".join(
                str(x or "-") for x in (variant.model_id, variant.thinking, variant.effort)
            )
            schema = request["output_config"]["format"]["schema"]
            seconds: list[float] = []
            for i in range(1, args.runs + 1):
                started = time.monotonic()
                try:
                    outcome = summarize._default_caller(request, key)
                except summarize.SummarizeError as exc:
                    print(f"{name} #{i}: FAILED — {exc}")
                    continue
                seconds.append(time.monotonic() - started)
                spent += (
                    outcome.input_tokens * variant.price_in_per_mtok
                    + outcome.output_tokens * variant.price_out_per_mtok
                )
                if dump:
                    record = {"variant": name, "run": i, "target": target, "fields": outcome.fields}
                    dump.write(json.dumps(record, ensure_ascii=False) + "\n")
                blank, leaked = inspect_reply(outcome.fields, schema)
                print(
                    f"{name} #{i}: stop_reason={outcome.stop_reason}, out={outcome.output_tokens}, "
                    f"{seconds[-1]:.0f}s, blank={blank or '-'}, markup in={leaked or '-'}"
                )
            if seconds:
                print(f"  {name}: median {statistics.median(seconds):.0f}s over {len(seconds)}\n")
    finally:
        if dump:
            dump.close()
            print(f"Raw replies: {args.dump}")
    print(f"Actual cost: ${spent / 1e6:.4f} (calls that FAILED are billed but not counted).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
