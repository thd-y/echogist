#!/usr/bin/env python3
"""TD-36 — repair saved summaries whose replies leaked tool markup into a field. Offline.

Before the fix in ``summarize.repair_leaked_markup``, a reply that wrote
``…</parameter>\\n<parameter name="main_skill">…`` INSIDE a string shipped that markup into
the document and left the fields after it empty: a blank key skill, a phase with no
anchors, ``</prose></invoke>`` printed under the prose. The misplaced text is all in the
saved ``.json``, so this moves it back with the SAME repair the pipeline now runs, then
validates every anchor against the summary's own transcript (found by its fingerprint)
and renders a fresh document next to the old one. No call, no key, no cost.

Reports by default; ``--apply`` writes. Each changed ``.json`` is first copied to
``<name>.json.pre-td36`` (never overwritten), and the old ``.pdf``/``.md`` is kept: the
new one is deduped beside it. Run from the repo root::

    .venv\\Scripts\\python.exe scripts\\repair_summaries.py            (report)
    .venv\\Scripts\\python.exe scripts\\repair_summaries.py --apply    (write + render)
"""

from __future__ import annotations

import argparse
import bisect
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, TypeVar

_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from echogist import config, paths, render, summarize  # noqa: E402
from echogist.summarize import ActionItem, Decision, Summary  # noqa: E402

_Item = TypeVar("_Item", Decision, ActionItem)
_BACKUP_SUFFIX = ".pre-td36"


def _by_time(items: tuple[_Item, ...], recovered: tuple[_Item, ...]) -> tuple[_Item, ...]:
    """Insert ``recovered`` among ``items`` by anchor time — phases are in time order, so
    this puts a phase's lost items where that phase's items would have been."""
    out = list(items)
    for item in recovered:
        keys = [summarize._tc_seconds(i.anchor) for i in out]
        out.insert(bisect.bisect_right(keys, summarize._tc_seconds(item.anchor)), item)
    return tuple(out)


def repair_summary(summary: Summary) -> tuple[Summary, list[str]]:
    """``summary`` with every leaked field moved back, plus one line per repair. Pure."""
    changes: list[str] = []
    header: dict[str, Any] = {
        "title": summary.title,
        "core_idea": summary.core_idea,
        "main_skill": summary.main_skill,
        "test_questions": [q.question for q in summary.test_questions],
        "main_themes": list(summary.main_themes),
    }
    fixed, recovered, lost = summarize.repair_leaked_markup(header, summarize._reconcile_schema())
    outline = fixed.get("phase_headings") if "phase_headings" in recovered else None
    if fixed != header:
        changes.append(
            f"header: stripped markup; moved back {recovered or '-'}; lost {lost or '-'}"
        )
        summary = replace(
            summary,
            title=fixed["title"],
            core_idea=fixed["core_idea"],
            main_skill=fixed["main_skill"],
            test_questions=summarize._test_questions(fixed["test_questions"])
            if "test_questions" in recovered
            else summary.test_questions,
            main_themes=summarize._str_list(fixed["main_themes"]),
        )
    sections = []
    decisions, actions = summary.decisions, summary.action_items
    schema = summarize._phase_schema()
    for n, section in enumerate(summary.synthesis, 1):
        raw: dict[str, Any] = {
            "heading": section.heading,
            "prose": section.prose,
            "anchors": list(section.anchors),
        }
        fixed, recovered, lost = summarize.repair_leaked_markup(raw, schema)
        if fixed != raw:
            changes.append(
                f"phase {n}: stripped markup; moved back {recovered or '-'}; lost {lost or '-'}"
            )
            section = replace(
                section,
                heading=fixed["heading"],
                prose=fixed["prose"],
                anchors=summarize._str_list(fixed["anchors"]),
            )
            decisions = _by_time(decisions, summarize._decisions(fixed.get("decisions")))
            actions = _by_time(actions, summarize._action_items(fixed.get("action_items")))
        sections.append(section)
    if outline is not None:
        sections = list(summarize._apply_normalized_headings(sections, outline, log=print))
    summary = replace(summary, synthesis=tuple(sections), decisions=decisions, action_items=actions)
    return summary, changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the repairs and render")
    parser.add_argument("--base", type=Path, default=_APP_ROOT, help="folder holding output/")
    args = parser.parse_args(argv)

    fmt = config.load_settings().output_format
    raw_dir = paths.summaries_raw(args.base)
    repaired = 0
    for json_path in sorted(raw_dir.glob("*.json")):
        try:
            summary = render.load_summary(json_path)
        except render.RenderError as exc:
            print(exc)
            continue
        fixed, changes = repair_summary(summary)
        if not changes:
            continue
        repaired += 1
        print(f"\n{json_path.name}")
        for line in changes:
            print(f"  {line}")
        matches = sorted(paths.transcripts(args.base).glob(f"*-{summary.source_fingerprint}.txt"))
        if not summary.source_fingerprint or not matches:
            print("  SKIPPED: its transcript is not in output/transcripts, so the recovered")
            print("  anchors cannot be validated. Nothing written for this file.")
            continue
        if not args.apply:
            continue
        fixed = summarize.validate_anchors(
            fixed, matches[-1].read_text(encoding="utf-8"), log=print, notice=print
        )
        backup = json_path.with_name(json_path.name + _BACKUP_SUFFIX)
        if not backup.exists():
            shutil.copy2(json_path, backup)
        summarize.write_summary_json(fixed, json_path)
        out = render.render(fixed, paths.summaries(args.base), fmt, base=json_path.stem)
        print(f"  written; original kept as {backup.name}; new document {out.name}")
    if not repaired:
        print("No saved summary carries leaked markup.")
    elif not args.apply:
        print(f"\n{repaired} file(s) to repair. Re-run with --apply to write them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
