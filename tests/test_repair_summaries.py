"""TD-36 saved-summary repair tests: the pure core (no files, no render).

``scripts/repair_summaries.py`` is a standalone script, so it is loaded by file path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from echogist.summarize import ActionItem, Decision, Summary, SynthesisSection

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "repair_summaries.py"
_spec = importlib.util.spec_from_file_location("repair_summaries", _SCRIPT)
assert _spec is not None and _spec.loader is not None
repair_summaries = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repair_summaries)


def _summary(core_idea: str, sections: tuple[SynthesisSection, ...]) -> Summary:
    return Summary(
        title="T",
        core_idea=core_idea,
        decisions=(Decision("early", "r", "[00:00:10]"), Decision("late", "r", "[00:30:00]")),
        action_items=(),
        language="ru",
        synthesis=sections,
    )


def test_a_saved_leak_is_moved_back_and_its_items_land_in_time_order() -> None:
    leaked = SynthesisSection(
        "H",
        'Проза [00:10:00].</prose>\n<parameter name="anchors">["00:10:00"]</parameter>\n'
        '<parameter name="decisions">[{"decision":"middle","rationale":"r",'
        '"anchor":"00:10:00"}]</parameter>\n<parameter name="action_items">[{"task":"t",'
        '"owner":"","estimate":"","anchor":"00:10:00"}]</parameter>\n</invoke>',
        (),
    )
    summary = _summary('Мысль.</parameter>\n<parameter name="main_skill">Навык.', (leaked,))

    fixed, changes = repair_summaries.repair_summary(summary)

    assert (fixed.core_idea, fixed.main_skill) == ("Мысль.", "Навык.")
    assert fixed.synthesis[0].prose == "Проза [00:10:00]."
    assert fixed.synthesis[0].anchors == ("00:10:00",)  # validated later, against the transcript
    assert [d.decision for d in fixed.decisions] == ["early", "middle", "late"]
    assert fixed.action_items == (ActionItem("t", "", "", "00:10:00"),)
    assert len(changes) == 2


def test_a_clean_summary_reports_nothing_and_comes_back_equal() -> None:
    clean = _summary("Мысль.", (SynthesisSection("H", "Проза.", ("[00:00:10]",)),))
    assert repair_summaries.repair_summary(clean) == (clean, [])


def test_a_leaked_outline_is_applied_to_the_phase_headings() -> None:
    sections = (SynthesisSection("old 1", "a", ()), SynthesisSection("old 2", "b", ()))
    summary = _summary(
        'Мысль.</parameter>\n<parameter name="phase_headings">["Новый 1", "Новый 2"]', sections
    )
    fixed, _ = repair_summaries.repair_summary(summary)
    assert [s.heading for s in fixed.synthesis] == ["Новый 1", "Новый 2"]
