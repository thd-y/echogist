# Product invariants. Ledger; append-only; change only by decision.

- **The folder preview is AUTOMATIC and the three actions must agree with it.** `mp3` gets that
  walk's file LIST, not the root. An interrupted walk is silent about the folder, never a verdict;
  an empty PLAN means "already done" only if there were files to plan.
- **The loop detector measures REPETITION SHAPE, not vocabulary** (TD-33). A stuck decoder repeats
  one phrase verbatim (3-gram coverage 0.60-1.00); this lecturer repeats to teach (never above
  0.20). The old unique-word ratio deleted 5172 words of real lecture. WHOLE blocks only, still.
- **Two channels, from `summarize` AND `render`** (TD-29, TD-28). `log` = chatter, muted;
  `notice` = act on it, loud: a DROPPED anchor, a phase citing NOTHING over a timecoded
  transcript, a foreign script, a wrong-language document, an unfont-able character, an empty
  title or essence field. **Do not merge them**; pass `notice=` to EVERY `validate_anchors`
  call — the per-phase one drops.
- **The script check has TWO halves** ([design](./designs/script-check.md)): `foreign_findings`
  asks "is this script used here at all", `script_shares` "what SHARE is not the primary one"
  (TD-30) — the first cannot see a wholesale switch, since `en` allows Cyrillic so quotations stay
  silent. 0.25 is MEASURED from BOTH sides: run 3's six RU documents sit at 0.0013-0.0088, the
  first real EN-over-RU document at 0.0042. Notation is not a script.
- **One module, two engines** (`folder.py`): `convert_many` = parallel pool, `run_phase` =
  strictly sequential. **Do not push the run through the pool** — the gate must price a whole
  folder. Its plan is SORTED, not `os.walk` order. **The walk prunes `output` from `dirnames` and
  never sees the ROOT**, so `_flow_folder` refuses a root that IS the artifact tree (TD-29b) — by
  resolved path only: a folder the operator named `output` is theirs.
- **Name-claiming** is in memory (`folder._plan_output_paths`) — an on-disk claim survived
  `kill -9` as a fake artifact and poisoned dedup forever. One publish scheme,
  `naming.publish_text`, on EVERY durable write. **Casefold is asymmetric ON PURPOSE:**
  `_resume_key` folds, `naming.resolve_source` does not (folding dropped a recording).
- **Grouping lives in the artifact's NAME, and the tree stays FLAT** (TD-27). A summary is
  `<date>-<source stem>-<title>`; the date is the RUN's, taken ONCE per folder run (an 18h run
  crosses midnight and would split a course in two). The source part truncates from the HEAD —
  a download's noise is the site tag in front, the discriminator the lecture number at the back.
  `render` takes the `.json` stem as handed (sanitized, never re-capped), so the triplet shares
  it even past the cap. **Do not add a subdirectory** —
  `transcript_sources`, `summary_index`, `_pick_transcript` and `_sweep_stale_resumes` are all
  single-level `glob` and would find nothing. `paths` is the ONE layout definition; it computes
  and never creates.
- **Identity is CONTENT and lives in the transcript's NAME** (TD-31). `fp = sha256(size +
  head/tail 1 MiB)[:16]`; both joins key on it, so a move or rename costs nothing and two courses
  with identical filenames never share a transcript. **Taken ONCE from the original and inherited
  forward** — a re-encode (1b) carries its parent's value or it re-buys the summary. Never put
  metadata IN the .txt: `chunk._blocks` anchors it at `[00:00:00]`, citable past validation.
- **Ctrl-C stops the run, not the app** — `folder.Cancelled` carries the partial report, the WHOLE
  loop iteration is guarded (BaseException), and a resume partial is keyed by the recording's
  fingerprint (path when none) + language + tier, so the video and its saved transcript
  resume the same work, and a tier switch re-runs and never mixes.
- **Essence block** is phase prose only; reconcile ALWAYS runs; every emitted string is
  anchor-validated. **Two different answers to a short reply, on purpose:** an empty PHASE is a
  paid call whose stretch of the recording would go missing, so it FAILS the file loud (TD-34,
  costing one file — `folder.run_phase` carries on and `on_phase` already persisted the rest);
  an empty title or essence field is one short reconcile call over intact prose, so it is a
  `notice` and the run finishes (TD-36). **The failure then ends in ONE question, AFTER the
  cycle** — at the failure an 18h run would sit on a y/N for hours. Scoped by TYPE
  (`EmptyPhaseError`, a `SummarizeError` subclass so `_RECOVERABLE` is unchanged), never by
  message text; **default YES**, alone among the paid gates; asked once, retries only the lost
  files, and its report prices the retry, not the run. With `auto_accept_any_cost` on (no cost
  gate at all) ONE automatic retry pass precedes the question, which then covers only files
  still empty after it.
- **Cost model** projects output as `ratio x that call's input`. The input leg is near-exact over
  a whole folder (0.9987x) but runs ~1.10x on ONE file, so the output ratio carries most, not all,
  of the bias. **Target (operator, 2026-10-27): the FOLDER quote within ±15% of the bill** — not
  every single file over. Re-seed a tier from its own "Actual cost" line: output/input, NO extra
  margin (the reconcile term already adds ~15%); fitting the ratio over billed transcripts is the
  precise version (TD-43). economy's is fitted (0.20 → 1.13x), balanced's measured, flagship's a
  guess (`docs/TECHNICAL_DEBT.md` TD-40; evidence beside each value in `config/models.toml`).
  **The duration projection is ~1.5-1.7x the bill** (two courses). Token estimate: 3 rates by script.
- **Key:** env, then gitignored `config/secrets.toml` — absent in WSL, so paid runs are
  Windows-only. **`/mnt/c/Users/operator/Documents/echogist/output/` reads that tree from here, and
  reading the saved `.json` beats reading the log** — run 3's loudest WARN named the wrong cause.
