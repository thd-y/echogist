# CURRENT_CONTEXT
Schema: 1 | Updated: 2026-10-20T06:14:56+03:00 | Basis: main@6b1172a | Dirty: 0 | Tag: v3.2.0

## Deliverable
No active feature unit (no unit ID in any ledger). Last unit: doc-reconciler audit fixes after the state-file migration and invariants extraction.

## State
- [DONE] v3.2.0 released 2026-10-10: structured outputs (TD-36 closed), all tiers on 5.5 (TD-39 closed). Published from a rewritten history as `thd-y/echogist`; original is `echogist-private`.
- [DONE] Tag v3.2.0 re-pointed 2026-10-12 (was 9d7644a) to take in the F6 fix + tagging release.py.
- [DONE] State file moved to repo root (50c6784); 12 invariants extracted to docs/INVARIANTS.md (471575f); first keeper snapshot (c7799cf). Reconciler reports no stale pointers to the pre-move location.
- [DONE] Reconciler fixes committed in e681b0e (docs-only, 4 files): CLAUDE.md authority order + context list; TECHNICAL_DEBT.md:47 (T8 single home); INVARIANTS.md cost bullet de-numbered; CHANGELOG.md [Unreleased] Документация (2 entries). Previous snapshot committed in 6b1172a.
- [WIP] main is 5 commits ahead of origin (6b1172a, e681b0e, c7799cf, 471575f, 50c6784), none pushed. Operator: do NOT push.

## Decisions this cycle
2026-10-20: state file lives at repo root, maintained via global handoff protocol → CHANGELOG.md [Unreleased] Документация (e681b0e)
2026-10-20: invariants extracted to docs/INVARIANTS.md as an append-only ledger (471575f) → CHANGELOG.md [Unreleased] Документация (e681b0e)
2026-10-20: authority order = operator > CLAUDE.md > docs/INVARIANTS.md > CURRENT_CONTEXT.md; ENGINEERING_PLAN.md unranked historical (resolves old proposal #3) → CLAUDE.md#Source-of-Truth Priority (e681b0e)
2026-10-20: T8 single home = docs/TECHNICAL_DEBT.md; cost ratios single home = TD-40 + config/models.toml → those files (e681b0e)

## Open & blockers
- [owner] Push decision for the 5 unpushed commits; currently told not to push.
- [owner] T8 offline LLM-judge groundedness eval: P3 enhancement, not debt; single home docs/TECHNICAL_DEBT.md#T8.
- [owner] Open debts, all LOW: TD-37 (Windows-only branches not type-checked), TD-38 (dev venv is not the CI venv), TD-40 (economy and flagship on 5.5 unmeasured).
- [owner] TD-40 next step: first real runs of economy and flagship tiers; paid runs are Windows-only. Re-seed rule and ratios: docs/TECHNICAL_DEBT.md#TD-40, docs/INVARIANTS.md, config/models.toml.
- [owner] Increment 1b (mp3 re-encode rule): docs/designs/mp3-reencode-1b.md, DRAFT, NOT APPROVED, NOT IMPLEMENTED; needs /office-hours or /plan-eng-review first. Open questions: 222 MiB vs MB unit; `target_kbps` stored vs derived from `lame_quality`; whether the 222 MiB clause is redundant.
- [owner] "Streaming" (old Next #3): UNCLEAR. No doc in the repo defines it; 1b does not cover streaming.

## Verification
Reconciler audit (reported by parent, not run by keeper): no stale pointers; VERSION/pyproject/CHANGELOG/README agree on 3.2.0; TD-37/38/40 consistent. Parent reviewed `git diff`. Gate not run: docs-only commits, no code changed this cycle. No code PASS carried forward.

## Carry forward
- [unhomed] Calibration: run 2 (КУРС2025, 6, balanced) $3.7246, recorded only here. Run 1: docs/TECHNICAL_DEBT.md:241-242 (TD-23/TD-24). Run 3 ($4.4634, 18h18m): docs/TECHNICAL_DEBT.md:155-158, CHANGELOG.md:267. Run 4 spent $0.
- [unhomed] Run 3: 0 CJK slips, 6/6 transcripts reused by fingerprint, 1 loop block dropped where the old rule dropped 39 per 13 files.
- [unhomed] First real 5.5 run (занятие 3): $0.4275 vs $0.6706 on Sonnet 5, 3 min vs 6, +4% prose, 305/305 anchors exact.
- [unhomed] CI's first run caught 16 posix-only tests.
- win-smoke clip and live-call switch: scripts/win-smoke.bat:10-16.

## Read next
- CLAUDE.md#Source-of-Truth Priority — changed authority order
- docs/TECHNICAL_DEBT.md#TD-40 (also TD-37, TD-38, T8 at :47) — open debts
- docs/designs/mp3-reencode-1b.md — 1b draft and its open questions
- docs/INVARIANTS.md — product invariants ledger

## Pointers
Invariants: docs/INVARIANTS.md
