# CLAUDE.md

## Identity

EchoGist: a single-`.bat` Windows console tool. Input is a local audio/video file
or a saved transcript. Output is an MP3 track and/or a structured RU/EN summary
(PDF default, Markdown optional). Transcription is local GPU Whisper; summarization
is cloud Anthropic calls (one per phase + one reconcile). No online sources, no logins,
no history/analytics. Personal-use, Windows-only; developed in WSL2.

## Hard Constraints

**IMPORTANT: Non-negotiable. Stop and ask the operator before violating any.**

- **No destructive shell commands without explicit operator approval.**
  `rm -rf`, `git reset --hard`, `git clean -fd`, DDL `DROP` statements.
- **API key from `ANTHROPIC_API_KEY` env or local config file only. Never in code,
  never committed.**
- **Killswitch.** Live LLM calls are forbidden without a killswitch. `SUMMARIZE` is
  the only network stage; every stage left of it (incl. the token GUARD and cost
  estimate) is local and offline — no `count_tokens` or any network call. The
  pipeline must run end-to-end against a stub summarizer, locally, before every push.
- **Every push to `main` passes: ruff + ruff format + mypy + tests.** One exception: a
  docs-only commit may land without the gate — nothing under `echogist/`, `tests/`, `scripts/`
  or `config/` touched. A commit that mixes docs with code is a code commit and passes the gate.
  CI (`.github/workflows/ci.yml`) re-runs the same four on Windows and Linux, Python 3.11.
- **No manual workarounds.** Provisioning, fetching, and recovery must be automated
  and idempotent.
- **English is the language of the application.** Commit messages (subject and body),
  code, comments, docstrings, console strings, menu labels and log output are all English.
  Russian is reserved for the FINAL user-facing documents: `README.md`, `docs/USAGE.md`,
  `CHANGELOG.md`, and the generated summary artifacts (whose language is the operator's
  `summary_language` setting).

## Principles

- **Artifact-based recovery, not a job engine.** Durable state = the saved artifacts
  (`output/{audio,transcripts,summaries}`). The saved transcript is the checkpoint.
  No `job.json`, no history layer.
- **Pure stages.** Each pipeline stage is pure over an in-memory object so the whole
  pipeline is unit-testable with `SUMMARIZE` mocked.
- **Fidelity > completeness; the transcript is ground truth, read directly (TD-16 v2).**
  The transcript is split into a computed number of balanced, contiguous, NON-overlapping
  phases (`chunk.plan_phases`; short material = K=1, the whole transcript in one call), and
  each phase is synthesized DIRECTLY into faithful prose — one hop, no map-extracted
  intermediate, no coverage checklist, no grouping. Phases run sequentially and
  forward-only (each sees prior headings + the prior phase's real tail prose as
  do-not-restate context); a reconcile pass (ALWAYS, incl. K=1) writes the title, the
  ESSENCE BLOCK (главная мысль / главный навык / 3 проверочных вопроса + their answers)
  and main_themes from the phase prose, and never re-reads the transcript. Every emitted
  `[HH:MM:SS]` anchor is validated offline against the real block timecodes (accept / snap
  within 2s / drop) — that, plus the operator's manual re-check against the recording, IS
  the fidelity gate. No LLM-judge, no automated coverage signal. *Operator-approved
  2026-06-26; supersedes the TD-5 single-pass/map-reduce rule and TD-15 group-keep-all. A
  failed phase fails the whole run loud; re-run from the saved transcript SKIPS phases
  already persisted to disk (artifact-resume, not a job engine).*
- **Five fidelity properties (the v2 acceptance criterion).** A v2 summary must be:
  (1) **grounded** — every sentence traceable to the transcript; (2) **no fabrication** —
  nothing added that the author did not say (a bridge beyond the text is marked inline with
  `[интерпретация]:`); (3) **faithful stance** — no inversion or softening, caveats kept;
  (4) **no merged distinctions** — two distinct points never collapsed into one;
  (5) **coverage** — every point reflected, or consciously dropped (the manual gate).
  Plus the load-bearing invariant: **every anchor resolves to a real transcript timecode.**
- **Config is data, not code.** Model IDs, prices, model source URL, settings are
  editable without a code change.
- **Fail loud, return to menu.** Every error path = human-readable message + clean
  return to the main menu; never a crash, never silent truncation or skip.
- **Estimate Cyrillic high.** The local token estimate is language-aware and biased
  high so an over-long transcript is always caught.

## Release

Releases are cut with `scripts/release.py` + a GitHub PAT — **never `/ship`** (the gstack ship
skill is not used here). Flow for `vX.Y.Z`: bump `VERSION` and pyproject's `version` (a test
holds them equal), write the `## [X.Y.Z]` `CHANGELOG.md` section, commit it as
`release: vX.Y.Z — <tagline>` and push `main`, then `python3 scripts/release.py`: it checks HEAD
is that release, creates and pushes the annotated tag, and publishes. The PAT lives only in the
`ECHOGIST_GITHUB_TOKEN` env var (`~/.bashrc`, "Contents: Read and write"), never in git.

## Context Loading Policy

Read on demand, not up front: `docs/INVARIANTS.md` for product invariants,
`docs/archive/ENGINEERING_PLAN.md` for pipeline/console implementation,
`docs/TECHNICAL_DEBT.md` for active debt.

**At session start:**
1. Read the open items of `docs/TECHNICAL_DEBT.md` and the newest unfinished plan in `docs/superpowers/plans/`, if any
2. Report: active plan or open debts, blockers, git state (branch + dirty files)
3. Do not read further docs until the task requires them
4. If docs conflict with operator instruction — stop and ask

## Workflow (superpowers)

Default flow: `brainstorming` → `writing-plans` → execute **Native** (`executing-plans`: implement
every task in this session) with a fresh reviewer (`requesting-code-review`) at each seam between
program layers — not per task, roughly every 2–5 tasks, wherever one layer's work is done and the
next builds on it → full gate → commit on the operator's OK. Subagent-driven only when the operator asks. Specs and
plans live in `docs/superpowers/` (gitignored, local-only).

Apply superpowers skills at these gates:
- `brainstorming` — before any ambiguous or new-scope task
- `writing-plans` — before any multi-step implementation
- `requesting-code-review` — before every commit touching non-trivial code

Do not skip review gates for: DB, LLM prompts, evaluation, safety, CI/deploy.

Flag any new technical debt for `docs/TECHNICAL_DEBT.md`

## Source-of-Truth Priority

When documents conflict:
1. Explicit operator instruction in current session
2. This CLAUDE.md (guardrails take precedence over all docs)
3. `docs/INVARIANTS.md` (product invariants)
4. `docs/TECHNICAL_DEBT.md` and the active plan in `docs/superpowers/plans/` (live status — authoritative for priorities/blockers)

Historical reference, not ranked: `docs/archive/ENGINEERING_PLAN.md` (the original build spec).
