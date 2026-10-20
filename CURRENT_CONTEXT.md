# CURRENT_CONTEXT
Schema: 1 | Updated: 2026-10-20T05:42:36+03:00 | Basis: main@471575f | Dirty: 0 | Tag: v3.2.0

## Deliverable
No active feature unit (no unit ID in any ledger). Last unit: state-file migration to repo root under the global handoff protocol, and invariants extraction.

## State
- [DONE] v3.2.0 released 2026-10-10: structured outputs (TD-36 closed), all tiers on 5.5 (TD-39 closed). Published from a rewritten history as `thd-y/echogist`; original is `echogist-private`.
- [DONE] Tag v3.2.0 re-pointed 2026-10-12 (was 9d7644a) to take in the F6 fix + tagging release.py.
- [DONE] CURRENT_CONTEXT.md moved to repo root. Pointers fixed in README.md:92, docs/TECHNICAL_DEBT.md:47, docs/archive/OPERATOR_TESTING_PLAYBOOK.md:158 (50c6784). Parent reports grep "docs/CURRENT_CONTEXT" = 0 lines.
- [DONE] CLAUDE.md "State" and "State Update Protocol" sections removed; CLAUDE.md points to root CURRENT_CONTEXT.md (50c6784).
- [DONE] 12 product invariants extracted verbatim from the old snapshot into docs/INVARIANTS.md (471575f), append-only ledger.
- [WIP] 50c6784 and 471575f not pushed; main is 2 commits ahead of origin.

## Decisions this cycle
2026-10-20: state file lives at repo root, maintained via global working-context handoff protocol (replaces the project-local protocol) → operator, not yet in ledger
2026-10-20: invariants extracted to docs/INVARIANTS.md as an append-only ledger (471575f) → operator, not yet in ledger (the file exists, but the decision is not recorded in TECHNICAL_DEBT or CHANGELOG)
2026-10-20: proposal #5 (3.2.0 date mismatch) dropped; not a conflict, both dates true (released 2026-10-10, tag re-pointed 2026-10-12) → operator, not yet in ledger

## Open & blockers
- [owner] Push 50c6784 and 471575f (docs-only, gate-exempt per CLAUDE.md; push per repo policy).
- [owner] T8 offline LLM-judge groundedness eval: P3 enhancement, not debt (docs/TECHNICAL_DEBT.md:47, :297).
- [owner] Open debts, all LOW: TD-37 (Windows-only branches not type-checked), TD-38 (dev venv is not the CI venv), TD-40 (economy and flagship on 5.5 unmeasured).
- [owner] TD-40 next step: first real runs of economy (Haiku 5.5, `disabled`/`high`) and flagship (Opus 5.5, `medium`, always thinks). Paid runs are Windows-only. Re-seed each ratio from its tier's "Actual cost" line (output/input, +~5%); economy 0.52 and flagship 0.80 are guesses.
- [owner] Increment 1b (mp3 re-encode rule): docs/designs/mp3-reencode-1b.md, DRAFT, NOT APPROVED, NOT IMPLEMENTED; needs /office-hours or /plan-eng-review first. Open questions: 222 MiB vs MB unit; `target_kbps` stored vs derived from `lame_quality`; whether the 222 MiB clause is redundant.
- [owner] "Streaming" (old Next #3): UNCLEAR. No doc in the repo defines it; 1b does not cover streaming.

## Verification
Not run. 50c6784 and 471575f are docs-only; nothing under echogist/, tests/, scripts/, config/ changed this cycle. No PASS carried forward.

## Carry forward
- PROPOSAL awaiting operator approval (doc-reconciler baseline 2026-10-20, not a decision): #3 demote docs/archive/ENGINEERING_PLAN.md in the CLAUDE.md authority order (archived "locked build spec" ranks above the live state file).
- Calibration: run 1 (7 RU lectures, Haiku) $2.4003, see docs/TECHNICAL_DEBT.md:241-242 (TD-23/TD-24). Recorded only here: run 2 (КУРС2025, 6, balanced) $3.7246. Run 3 ($4.4634, 18h18m) is in docs/TECHNICAL_DEBT.md:155-158 and CHANGELOG.md:259; run 4 spent $0.
- Run 3, recorded only here: 0 CJK slips, 6/6 transcripts reused by fingerprint, 1 loop block dropped where the old rule dropped 39 per 13 files.
- First real 5.5 run (занятие 3), recorded only here: $0.4275 vs $0.6706 on Sonnet 5, 3 min vs 6, +4% prose, 305/305 anchors exact.
- CI's first run caught 16 posix-only tests (recorded only here).
- `win-smoke.bat` runs off gitignored `tests/fixtures/audio/smoke.mp3` (recorded only here); no paid run needed.

## Read next
- CLAUDE.md — authority order, hard constraints (proposal #3 target)
- docs/TECHNICAL_DEBT.md#TD-40 (also TD-37, TD-38, T8 at :47) — open debts
- docs/designs/mp3-reencode-1b.md — 1b draft and its open questions
- docs/INVARIANTS.md — product invariants ledger

Invariants: docs/INVARIANTS.md
