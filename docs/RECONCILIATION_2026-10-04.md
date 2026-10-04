# Reconciliation Report: SPEC v2.0 and CLAUDE.md (research edition) vs. the repository

**Date:** October 4, 2026
**Measured against:** `origin/main` @ `c927729` (April 13, 2026), plus all 19 remote branches
**Method:** direct inspection of the tree and history, test runs (both CI-style and via
`pyproject.toml`), trial merges of every unmerged branch, and GitHub PR and CI history.
**Status:** report only. No code has been changed. Phase 0 is proposed in §4 and needs
approval before work starts.

---

## 0. Bottom line

1. **The October 1 audit (SPEC §2, CLAUDE.md §8.1) measured a stale local clone, not the
   repository.** Its numbers match the tree as of **commit `6dc9251`, March 21, 2026**,
   27 commits behind `origin/main`. Three figures pin this down:
   - TypeScript is exactly **1,307 lines across 34 files** at `6dc9251`, the figure in
     CLAUDE.md §8.1.
   - Ethics Monitor is exactly 140 lines, Intake Conductor 1,101, and Orchestrator 476
     at `6dc9251`.
   - "motion-drafter is 2 commits ahead, 563 lines" matches local `motion-drafter` at
     `e5ffeaa`. "Mark-Rights-Violation-Scanner is 2 commits ahead" matches `e11f544`.

   This is consistent with the OneDrive copy not having fetched since about March 22.
2. **Nothing has been committed to any branch since September 4, 2026.** So "what changed
   since the audit" is nothing. What differs is the snapshot versus reality, and the gap
   is large:

   | | Audit (Mar 21 tree) | `origin/main` today |
   |---|---|---|
   | Python | 6,158 lines | **15,365 lines / 93 files** |
   | TypeScript | 1,307 lines / 34 files | **4,303 lines / 68 files** |
   | Test functions | 43 | **185** (255 with the three clean open branches merged) |

3. **The drift happened in the opposite direction from what the spec assumes.** The
   September 4 briefing (`docs/project-briefing.md` on the unmerged branch
   `claude/defender-ai-overview-dlap4b`) is largely **accurate for `main`**:
   - Intake about 1,360 lines.
   - Ethics Monitor about 1,130 lines with 39 tests.
   - Disclosure Tracking 23 tests, Rights Scanner 20 tests.
   - Sentencing has 71 tests, and 114 + 71 tests in total.

   The document that described an unreal codebase was the audit. The remedy is the same
   (a generated inventory), but **the stale §8.1 numbers must not be committed into the
   invariants file.**
4. **Phase 0 as written does not fit the real tree:**
   - (a) One of its two merges is already done. The other conflicts. Three more
     branches the spec never mentions (open PRs #5 and #6, plus the plea/trial branch)
     carry about 4,100 lines of real agent source and about 3,300 lines of tests. All
     three merge cleanly.
   - (b) The renormalize commit would be empty: the repository contains zero CRLF files.
   - (c) Applied literally, it would unregister Case Prep, a stub that the live intake
     flow runs after every interview.
   - (d) and (e) are sound.
5. **CI on `main` has been red since March 21.** The last green push to `main` was run
   #9 on `6dc9251`. The current cause is `python-lint`: black flags 3 files, and ruff is
   unpinned. Tests pass in CI only because 71 tests never run.

---

## 1. Verification of SPEC §2, claim by claim

### 1.1 "Real" components

| Claim | `origin/main` | Verdict |
|---|---|---|
| `intake_conductor.py` 1,101 lines, ~6 tests | **1,364 lines.** 2 functions in `test_intake.py`, plus integration coverage | Size stale |
| `charge_processing.py` 783, ~5 tests | 783. 2 in `test_charge_processing.py`, plus integration | Correct size |
| `motion_drafter.py` 563, ~17 tests, "REAL" | **63-line stub on `main`.** The real version (584 lines after black, 5 templates, 337-line test) is on **open PR #7, which conflicts** | Real, but not on `main` |
| `orchestrator.py` 476, ~3 tests | **492.** 2 in `test_orchestrator.py`, plus integration | Size stale |
| `test_pipeline_integration.py` 566 | 565 lines, 26 test functions (3 need an API key and skip in CI) | Correct |
| `pre_interview.py` 234, 0 tests | 234. Has a `TestPreInterviewAgent` class in the integration tests | Test claim wrong |

### 1.2 "Not real, despite prior documentation"

| Claim | `origin/main` | Verdict |
|---|---|---|
| Ethics Monitor: 140 lines, 0 tests, no bias audit, no hallucination detection | **1,127 lines, 39 tests, 5 "pillars"** (merged in PRs #8 and #9, March 31). The "bias audit" is a demographic keyword list. "Hallucination detection" is a regex for O.C.G.A. title validity, a hardcoded `year > 2026` future-citation check (expires in 3 months), and a phrase list | **Size and test claims wrong.** The substantive critique holds: it is keyword-based and defeated by paraphrase. It also **hard-blocks** (see §2) |
| Sentencing: 57-line stub; the sub-pipeline "has never existed in any commit" | **Wrong.** `tier2_attorney/sentencing_agent/` is a 10-node LangGraph sub-pipeline: 4,246 lines including 71 tests, Georgia seed data, and externalized prompts (PRs #10 and #11, April 1–2). **But it is orphaned:** never invoked, its router is not mounted, it is absent from `_AGENT_CONFIG`, and its tests are skipped by CI. The 57-line `sentencing_agent.py` is **dead code shadowed by the package** (Python resolves the package first) | Wrong |
| Disclosure tracking: "no such file has ever existed" | **Wrong.** `disclosure_tracking.py` (573 lines) plus 23 tests, on `main` since March 23 (PR #3). It **is** in `_AGENT_CONFIG` but **nothing ever invokes it** | Wrong |
| Thirteen Tier 2 agents are 35–65 line stubs | **12 stub files on `main`:** `recency_monitor` 35, `case_prep` 48 (Tier 1), `personal_circumstances` 49, `citation_verifier` 51, `statute_agent` 51, `fact_gatherer` 52, `collateral_agent` 54, `case_law_agent` 57, `sentencing_agent.py` 57 (dead), `brady_agent` 61, `plea_trial_analyst` 61, `motion_drafter` 63. Open branches replace or supersede 8 of them, and the dead sentencing stub is deleted on another branch, leaving only `recency_monitor`, `brady_agent`, and `case_prep` (§1.4) | Roughly right on `main`; wrong for the project |
| `corpus/data/` empty | Confirmed. **Also:** `.gitignore` excludes `packages/api/src/corpus/data/*.json`, so Phase 4's corpus would be silently left out of commits. `corpus/loader.py` defaults to `"IL"` | Correct, with a hazard |
| `llm_service.py` 42 lines, no retry, timeout, accounting, or validation, bare `json.loads`; docstring overclaims | 41 lines (after black). The docstring overclaims as described. **Nuance:** the Anthropic SDK client already retries twice and has a default timeout, so the real gaps are typed validation, failure semantics, token accounting, recording, and model pinning. **New:** the default model `claude-sonnet-4-20250514` reached end-of-life on **June 15, 2026**, so every live call fails today | Mostly correct |
| `_store.py` module-level dict; Prisma unused by the backend | Confirmed. **Also:** `packages/web/src/lib/prisma.ts` is imported by nothing, so Prisma is unused by the frontend too. **Also:** the Orchestrator keeps `_blocked`, `_merge_history`, and `_human_review_required` on the Python object, **outside `CaseState`**. Persisting `CaseState` alone will lose them | Correct, and understated |
| Five of nineteen agents in `_AGENT_CONFIG`, with disclosure mapping to a nonexistent file | Keys: `charge_processing`, `pre_interview_research`, `intake_conductor`, `case_prep`, `case_prep_conductor` (alias), `disclosure_tracking`. **Five agents is right, but disclosure maps to a real file.** Only four are ever invoked. The real Rights Scanner is not registered at all | Count right, reason wrong |
| Rights Scanner unmerged; `main` has a 65-line stub | **Wrong.** Merged March 24 (PR #4). On `main` with 20 tests, but **never invoked** by any route or graph | Wrong |

### 1.3 Repository hygiene (SPEC "found October 4")

| Claim | Reality |
|---|---|
| `main` is behind both feature branches | `Mark-Rights-Violation-Scanner` is **0 commits ahead** (merged). `motion-drafter` is 3 ahead and is **open PR #7, which conflicts** in `models/__init__.py`. The real picture is in §1.4: 19 remote branches, 9 with unmerged commits |
| CRLF churn: 104 files, 9,747/9,747 | **Not in the repository.** `git ls-files --eol` shows 180 text files, all LF, **zero CRLF**. The churn lives only in the Windows/OneDrive working copy. A `.gitattributes` file is still worth adding to prevent recurrence, but `git add --renormalize .` will produce **no commit**. The fix is a fresh clone outside OneDrive |
| Repository inside OneDrive | Can't verify from here. It is consistent with a clone that has not fetched since about March 22. **Before abandoning that copy, check it for unpushed commits or uncommitted work** |

### 1.4 Branches the spec does not mention

| Branch | Unmerged | Contents | Merge into `main` |
|---|---|---|---|
| `research-agents` (**open PR #6**) | 5 commits | GA criminal case law (350), constitutional case law (315), GA statutes (317), citation verification (526), research orchestrator (254), CourtListener client (245), **cost tracker (136)**, 692-line test file | **Clean.** Tests: 202 pass |
| `Fact-Gathering-Agent` (**open PR #5**) | 6 | Real `fact_gatherer` (308), `collateral_agent` (269), `personal_circumstances` (331), a new `intake_sub_agents` graph node, 888-line test file | **Clean.** 206 pass |
| `claude/plea-trial-assessment-agent-wcljt` | 4 | Real plea/trial analyst (478, plus models and prompts), 533-line test file | **Clean.** 211 pass |
| All three together | | | **Clean. 255 pass, 3 skipped** |
| `motion-drafter` (**open PR #7**) | 3 | Real Motion Drafter and 5 templates | **Conflict:** `models/__init__.py` |
| `claude/motion-drafter-agent-spec-hgCCq` | 5 | Same base plus "address 10 issues from spec review" fixes that never reached PR #7. **It also deletes** `brady_agent.py`, `plea_trial_analyst.py`, and `sentencing_agent.py` | Conflict. Cherry-pick the fixes only |
| `claude/sentencing-mitigation-agent-hMQAI` | 1 | **Fixes the IL→GA defaults in 7 files**, deletes the shadowed sentencing stub, adds `.env.example` | **Clean** |
| `claude/frontend-foundation-setup-sIaBo` | 4 | Round-2 frontend remediation, launch scripts, Docker. Deletes intake components that `main` later modified | Conflict (2 intake components) |
| `claude/debug-intake-interviewer-V4EXJ` | 2 | July fix for an intake hang, based on April 4 code | Conflict. Probably superseded by `main`'s April 11 fixes; verify |
| `claude/defender-ai-overview-dlap4b` | 1 | The September 4 briefing | Superseded by the generator |

Note: `motion-drafter` and the plea/trial branch both add `tests/fixtures/sample_case_state.py`
(475 vs. 855 lines) and `tests/agents/tier2_attorney/test_motion_drafter.py`. They will
conflict with each other.

### 1.5 Known defects (SPEC §2)

| Claim | Reality |
|---|---|
| `jurisdiction` defaults to `"IL"` | Confirmed in `CaseState`, `config.DEFAULT_JURISDICTION`, and `corpus/loader.py` (twice). **The fix already exists** on `claude/sentencing-mitigation-agent-hMQAI` and merges cleanly |
| `graph.py` truncated | Confirmed. **Also:** the compiled `pipeline` is used by **no route**, only by tests. The production path is `upload.py`'s background task plus the intake WebSocket, both driving one long-lived `OrchestratorAgent` held in `_store` |
| Fresh orchestrator per node; `_orchestrator_ref` holds `id()` | The `id()` lives only in `orchestrator_init_node`, which **is never added to the graph**. It is dead code and trivial to delete. The real persistence problem is the out-of-state fields in §1.2 |
| `"test": "jest"` with no jest | Confirmed: no jest in the lockfile |
| Auth accepts any email | Confirmed. Also, `routes/review.py` is all TODOs: `comprehension_check` always returns `passed: True` |

### 1.6 Found, not in the audit

- **CI red on `main` since March 21.** The latest run (#33) fails only `python-lint`, and
  black flags `ethics_monitor.py`, `intake_conductor.py`, and `routes/intake.py`. **Ruff is
  unpinned:** ruff 0.11 passes the code, but the current ruff release reports 148 errors on
  the same code. Lint can turn red with no code change.
- **The CI `testpaths` override is real.** `pytest tests/` runs 114 tests. `pytest` (which
  honors `pyproject.toml`) runs 185. The 71 sentencing tests have never run in CI.
- **Silent failure turns errors into data.** An auth failure (HTTP 401) during Charge
  Processing returned a **well-formed result with zero charges** (`_empty_extraction`),
  which would merge into `CaseState`. There are 9 `except Exception` blocks across agent
  code. For a study, an error must not look like an abstention or an empty finding.
- **LOW-confidence outputs skip the ethics check entirely.** `receive_agent_output`
  returns early before calling the monitor. The future Sensor would be blind to exactly
  the outputs most likely to be bad.
- **Stub confidence values are hardcoded constants** (`wrap_output(result, confidence=0.7)`).
  For stubs, `confidence` is not a measurement.
- **Case Prep, a 48-line stub, runs automatically after every intake** (since April 11). Its
  prompt asks for a "recommended defense theory" and "recommendation" fields.
- **Third-party data egress.** Voice mode sends interview text to **OpenAI TTS**
  (`/api/tts`) and uses the browser Web Speech API (Chrome sends audio to Google). Neither
  is captured in any run metadata, and it is a non-Anthropic model in the loop.
- **Upload OCRs PNG and JPG files**, which directly conflicts with CLAUDE.md §7.
- **Fixture realism.** `sample_accusation.txt` uses `Case No. 2024-SC-04821` and plausible
  names, officer, and badge. These are presumably fabricated, but they are indistinguishable
  by format from real material (see §3.6).
- **Two committed zip archives** at the repository root: `sentencing-agent.zip` (57 files)
  and `frontend-phase1-review.zip` (73 files). Both are stale code snapshots that include an
  old `CLAUDE.md`. They will pollute any grep or tree-derived inventory.

---

## 2. Where the spec contradicts the code, and which should win

| # | Topic | Code says | SPEC / new CLAUDE.md says | Recommendation |
|---|---|---|---|---|
| 1 | **Blocking** | Orchestrator returns `BLOCKED_ETHICS_P1` and halts the pipeline. The monitor sets `blocked=True` on CRITICAL flags | Sensor, not filter. Merge always, record the classification | **Spec wins.** Keep the counterfactual: record `would_have_blocked=True` so "how often a product would have blocked" remains a measurement. Make the LOW-confidence path run the monitor too |
| 2 | **Which CLAUDE.md** | The repo's `CLAUDE.md`: "Ethics Monitor runs on every agent output before it's written", "Client-facing agents INFORM, never ADVISE (NON-NEGOTIABLE)", Postgres/Prisma, "Fact Gatherer integrated" | New CLAUDE.md: research instrument, guardrails as instruments, SQLite | **New one wins, but it has to be committed.** Every Claude Code session, including this one, loads the repo's file and gets the opposite rules. Replace §8.1 before committing |
| 3 | **Disclosure Tracking** | Real (573 lines, 23 tests), registered | Absent from the §3.2 hierarchy. §2 says it never existed | **Code wins.** Keep it. Map it as the implementation behind "Brady Candidate Surfacer" (`brady_agent.py` is a 61-line stub), or as a Discovery Intake consumer. Do not delete tested work |
| 4 | **Sentencing** | Real 10-node package, orphaned | `[STUB]` | **Code wins.** Run its tests in CI now. Wiring it into the Orchestrator can wait for Phase 2's sequencing work. Its scope gate (marijuana ≤1 oz) matches the vertical slice |
| 5 | **Research agents** (PR #6) | Different file names (`ga_statutes_agent`, `ga_criminal_case_law`, `constitutional_case_law`, `citation_verification`, `research_orchestrator`), **live CourtListener API calls**, new `LEGAL_RESEARCH_*` stages and slots, **an existing cost tracker** | Stub file names. Corpus first (Phase 4). Token accounting is a Phase 1 job | **Merge the code**, then delete the four stubs it supersedes and update the agent map. Live API results change over time, which breaks reproducibility (CLAUDE.md §6). Route them through the Phase 1 cassette layer and the Phase 4 corpus. **Reuse `cost_tracker.py` in Phase 1** |
| 6 | **Fact Gatherer** (PR #5) | Real 308-line extractor, plus real Collateral and Personal Circumstances, plus a new graph node | Delete `fact_gatherer.py`. Leave `graph.py` alone until Phase 3 | **Merge PR #5.** Keep `fact_gatherer` until Phase 3c decides whether Record Ledger population subsumes it: deleting a tested extractor before its replacement exists loses a comparison point. The added node does not "fix" the truncated intake and case_prep nodes, so §9.1 is respected |
| 7 | **Case Prep stub** | Registered, and auto-run after every intake | Phase 0(c): stubs must be absent from `_AGENT_CONFIG` | **Conflict.** Literal (c) breaks the live intake → case prep chain. See §3.5 for an alternative rule |
| 8 | **Sequencing** | `can_run_agent` compares positions in the `PipelineStage` enum, and each merge sets one linear `stage` | Adds stages and a fan-out graph (§3.3, §3.4) | **Spec's intent wins, but the mechanism must change.** Use per-agent `depends_on` state slots (CLAUDE.md's agent map already has a "Depends On" column). An enum whose order *is* the dependency rule cannot express parallel branches, and a later merge can move `stage` backward. Phase 2 |
| 9 | **One state per case** | One `CaseState` per case. An agent cannot run if its slot is already filled | "Every pipeline run is a recorded experiment". Bias probes run the same matter many times | **Spec wins.** Key state by `(case_id, run_id)`. Phase 2 |
| 10 | **Database** | Old CLAUDE.md: Postgres via Prisma (unused) | SQLite plus Alembic in `packages/api` | **Spec wins** |
| 11 | **Ingest** | Upload accepts any PDF, image, or TXT and OCRs images | CLAUDE.md §2 synthetic-only (structural); §7 quarantine images | **CLAUDE.md wins.** §2 belongs in Phase 0, because it is the one invariant with no research exception. §7 goes in Phase 3a |
| 12 | **Voice mode egress** | OpenAI TTS plus Web Speech API | §3.1 "anything leaving the machine toward a real person"; §6 reproducibility | **Your call.** I recommend removing it or recording it in run metadata; at minimum, document it |

---

## 3. What I think is wrong, impractical, or would weaken the study

1. **Byte-for-byte verification against model-produced locators measures the wrong thing
   (§5.3).**
   - Models do not produce reliable character offsets, and PDF text extraction introduces
     ligatures, hyphenation, smart quotes, and whitespace drift. The drop count would be
     dominated by offset arithmetic and extraction noise, not fabrication. The headline
     "hallucination rate" would be inflated and not comparable across models.
   - **Proposal:** the model emits a verbatim quote plus an artifact and page hint. A
     deterministic resolver searches the stored text and *computes* the locator. Then
     drop and count by failure type:
     - `NOT_FOUND`: fabricated quote.
     - `FOUND_ELSEWHERE`: mislocated.
     - `FOUND_AFTER_NORMALIZATION`: cosmetic difference only.
   - Fix one documented canonicalization (NFC plus whitespace collapse) for the drop
     decision, and log raw-byte mismatches separately. Nothing is repaired and the drop
     rule survives, but the number now means what the study says it means.

2. **Verification is undefined for non-text locators.**
   - What is `source_text` for a `CellLocator` or `RowSetLocator`? Define it per kind:
     - Cell: a canonical serialization of the named cells.
     - Row set: re-execute and compare `row_count` plus a hash of the row indices.
   - `RowSetLocator.predicate` should be structured (registry analysis ID, parameters,
     artifact SHA-256, code version) rather than a free string. The closed registry
     already makes that natural.
   - Store a hash of the row indices rather than inlining 8,412 integers into
     `CaseState` JSON.

3. **"Pre-2022 criminal expert-testimony authority = SUPERSEDED" is the wrong trigger.**
   - HB 478 passed March 30, 2022, **took effect July 1, 2022**, repealed § 24-7-707, and
     applies to "any motion made or hearing or trial commenced on or after that date."
     Sources: [Ga. Gen. Assembly, HB 478](https://www.legis.ga.gov/api/legislation/document/20212022/204217),
     [Governor's signed-legislation copy](https://gov.georgia.gov/document/2022-signed-legislation/hb-478/download),
     [SGR summary](https://www.sgrlaw.com/newsroom/publications/hb-478-passed-the-georgia-general-assembly-to-establish-the-daubert-evidentiary-standard-in-georgia-criminal-cases).
   - (a) The cutoff is July 1, 2022, not the calendar year.
   - (b) It turns on when the *trial-court proceeding* happened, not the opinion date. A
     2024 appellate opinion reviewing a 2021 trial correctly applies former § 24-7-707.
   - (c) `SUPERSEDED` must attach to the **proposition** (the admissibility standard), not
     the opinion. The same opinion may be good law on every other issue.
   - A per-opinion date flag mislabels in both directions and corrupts the recency
     measurement. It still makes an excellent planted trap for Phase 6.

4. **The "nineteen agents" number is gone.** The §3.2 hierarchy has 25 entries (23 agents
   plus 2 cross-cutting). It omits Disclosure Tracking and the research orchestrator.
   Let the generated inventory own the count.

5. **Stubs can serve as a naive baseline, not just as an embarrassment.**
   - A one-prompt stub is the "naive single-prompt" condition, and the engineered agent is
     the treatment. With the deterministic analyses, that gives a **three-way comparison**:
     deterministic, naive prompt, engineered agent.
   - Git history holds the stub version of every agent the branches replaced.
   - Phase 0(c)'s "assert absent from `_AGENT_CONFIG`" rules this out. **Proposed rule:**
     every agent module declares `STATUS`. A `STUB` may be registered only if it stamps
     `agent_status: "STUB"` into its output envelope. A test enforces both. This also
     resolves conflict #7.

6. **The synthetic-only rule as written is not structural.**
   - `provenance_class` on a web upload is a self-asserted label.
   - A "real Georgia case-number format" regex will flag *realistic synthetic* fixtures
     (the current one uses `2024-SC-04821`), and format alone cannot tell real from fake.
   - **Structural alternative:**
     - (a) Every synthetic case number and Bates prefix carries a reserved marker (for
       example `SYN-`), and a test asserts every case-number-shaped string in fixtures
       has it.
     - (b) Ingest accepts only files whose SHA-256 appears in a committed manifest under
       `tests/fixtures/synthetic/`. Nothing that is not in the repository can enter the
       system.

7. **"Banner on every API response."** Injecting a field into every JSON body changes
   response shapes (lists, WebSocket frames) and breaks the frontend. Use a response header
   plus the CLI banner, a UI banner, and a field on the `CaseState` envelope. Same intent,
   no client breakage, still not a config flag.

8. **Evidence before intake (§3.3) needs a skip path.** The possession slice has no
   discovery. Under enum-order sequencing, intake would require
   `EVIDENCE_ANALYSIS_COMPLETE`, so the possession case could not reach intake without a
   fake no-op stage. This is one more reason for `depends_on` (#8 in §2).

9. **Phase 1 should be rescoped.**
   - The SDK already retries and times out.
   - Spend the effort on:
     - Per-agent typed schemas.
     - **Failure semantics:** no silent empty outputs.
     - Token accounting (reuse PR #6's `cost_tracker.py`).
     - The cassette layer.
     - **Deliberately pinning the model the study evaluates.** The current default is past
       end-of-life. Which model is studied is a research decision, not a config detail.
   - The "43 tests instead of 200" rationale is wrong (185 exist), but the cassette
     argument still stands: no model-response path runs in CI.

10. **Minor points:**
    - "Pattern jury instructions have zero hallucination risk" is overstated: selecting the
      wrong instruction or filling the wrong element are still errors, and licensing is
      open question 2.
    - `PHASE_3_EVIDENCE_ANALYSIS.md` is referenced but is not in the repository or in what
      I was given. It blocks Phase 3, not Phase 0.

---

## 4. Revised Phase 0: ground truth

Same goal as the spec, nothing new built. When it finishes: `main` contains all the real
code, CI is green and runs every test, the invariants file in the repository is the one
the team actually means, and the inventory is generated rather than written. Phase 0
produces no demonstrable output.

| Step | Work | Notes |
|---|---|---|
| **0.0** (team, not me) | On the OneDrive machine, run `git status` and `git log --branches --not --remotes` in the old copy. Push anything real. Make a fresh clone outside OneDrive. **Don't renormalize the old copy.** | The audit copy hasn't fetched since about March 22 and may hold unpushed work |
| **0.1** | Commit the new `CLAUDE.md`, with §8.1 replaced by "see `docs/INVENTORY.md`" plus corrected facts, and `SPEC.md` with §2 annotated as superseded by this report | Must come first: every session loads the repo's `CLAUDE.md` |
| **0.2** | **Get `main` green before merging anything.** Run black on 3 files. Pin `ruff`. CI runs `pytest` honoring `testpaths` (185 tests, including 71 sentencing) | Each later merge is then judged against green |
| **0.3** | Merge in order, one PR each, green after each: **(a)** `claude/sentencing-mitigation-agent-hMQAI` (IL→GA, dead stub, `.env.example`). **(b)** PR #7 plus only the `motion_drafter.py` and `prompts.py` fixes from `a70f962`, resolving `models/__init__.py`. **(c)** PR #6. **(d)** PR #5. **(e)** the plea/trial branch, reconciling its fixtures with (b). **(f)** frontend round 2: owner reviews the 2 conflicts. **(g)** Close superseded branches, then delete the merged ones | (c), (d), (e) verified together: 255 pass. **Needs owner sign-off:** PRs #5, #6, #7 belong to teammates |
| **0.4** | Remove misleading artifacts: the two zip archives, `orchestrator_init_node`/`_orchestrator_ref`, and the stubs superseded by 0.3 (`statute_agent`, `case_law_agent`, `citation_verifier`, plus the sentencing stub via 0.3a). Update the `CLAUDE.md` agent map | Leave `fact_gatherer` until Phase 3c |
| **0.5** | Every agent module declares `STATUS = "REAL" \| "PARTIAL" \| "STUB"`. Tests: (1) every module declares it; (2) a registered `STUB` stamps `agent_status` into its envelope (§3.5); (3) every `_AGENT_CONFIG` key resolves to an agent whose `agent_id` matches; (4) a reachability report: registered **and** invoked from a route or graph | "Wired" means reachable, not only registered. Today Disclosure is registered but never invoked |
| **0.6** | `scripts/inventory.py` writes `docs/INVENTORY.md`. Per agent: lines, `STATUS`, registered?, state slot, invoked from (AST scan of routes and graph), tests and test-function count. Plus totals and the branch list. **CI fails if the committed file differs from a fresh regeneration** | Closes the drift failure mode in both directions |
| **0.7** | `.gitattributes` with `* text=auto eol=lf` | Prevention only. Expect the renormalize step to commit nothing |
| **0.8** (decide) | **Invariant alignment, behavior changes:** (i) Orchestrator merges on P1 and records `would_have_blocked`; the LOW path runs the monitor. (ii) Synthetic-only: move fixtures to `tests/fixtures/synthetic/`, adopt the `SYN-` convention plus a test, gate upload to manifest hashes, add the banner header | (i) is about 40 lines and keeps keyword-triggered halts out of Phase 1's recorded runs. (ii) is the one rule with no exception |

**Explicitly not in Phase 0:** `graph.py` (Phase 3), persistence, `depends_on`, `run_id`
(Phase 2), model choice and failure semantics (Phase 1), contraband quarantine (Phase 3a).

### Decisions needed before starting

1. **Merging teammates' work.** May I merge PRs #5, #6, #7 and the plea/trial branch, or
   should their authors?
2. **Step 0.8.** In Phase 0, or deferred: (i) to Phase 5 and (ii) to Phase 3a?
3. **Stub policy.** Unregister all stubs (spec) or "registered stubs must self-label" (my
   recommendation)? This determines whether Case Prep keeps auto-running after intake.
4. **Disclosure Tracking's place** in the hierarchy, and **keeping `fact_gatherer`** until
   Phase 3c.
5. **Voice mode and OpenAI TTS:** keep, record, or remove.
6. **Where `SPEC.md` lives**, and whether `PHASE_3_EVIDENCE_ANALYSIS.md` exists yet.

---

## 5. Addendum: decisions and Phase 0 as executed (October 4, 2026)

### 5.1 Decisions

| Question | Decision |
|---|---|
| Merging teammates' work | Merge PRs #5, #6, #7. The plea/trial branch was merged too, under the same rationale ("we leave this to the agents") |
| Step 0.8 | **Deferred.** That covers the Orchestrator blocking switch and, with it, the synthetic-only gate. Recorded in CLAUDE.md §8.1 as invariants not yet enforced |
| Stub policy | **Registered stubs stay registered, with labeled output** |
| PR | Watch PR #13. Fix CI immediately |
| Not asked, defaults taken | Disclosure Tracking kept as is. `fact_gatherer` kept. Voice mode untouched. `SPEC.md` placed at the repository root next to `CLAUDE.md` |

### 5.2 What was done (PR #13)

| Step | Result |
|---|---|
| 0.1 | `CLAUDE.md` (the research edition) and `SPEC.md` committed. CLAUDE.md §8.1 now points to the generated inventory and lists the deferred invariants. The §9 stub rule now reads "registered stubs are labeled". A short command list was added. SPEC §2 is marked superseded |
| 0.2 | CI fixed: black on 3 files; ruff pinned to `0.16.10` with an explicit rule set (`E4, E7, E9, F`); CI runs `pytest` honoring `testpaths`, so the 71 sentencing tests now run |
| 0.3 (a) | `claude/sentencing-mitigation-agent-hMQAI` merged: IL→GA in 7 files, the shadowed sentencing stub deleted, `.env.example` added. One test that asserted `"IL"` was updated |
| 0.3 (b) | PR #7 merged. `models/__init__.py` resolved as the union of both sides. PR's `motion_drafter.py` taken. An unused import fixed. The `-hgCCq` "10 spec-review fixes" were **not** cherry-picked (see §5.3) |
| 0.3 (c), (d) | PRs #6 and #5 merged cleanly |
| 0.3 (e) | Plea/trial branch merged. Its fixture moved to `tests/fixtures/plea_trial_case_state.py` because PR #7's same-named fixture has a different shape. Black and 6 unused imports fixed; the branch had never been linted. Its review zip dropped |
| 0.4 | `sentencing-agent.zip` and `frontend-phase1-review.zip` removed. **Superseded stub files kept** (statute, case law, citation verifier): they are labeled `STUB`, and they serve as the naive single-prompt baseline (§3.5) |
| 0.5 | `STATUS` in all 24 agent modules (17 REAL, 1 PARTIAL, 6 STUB). `BaseAgent.wrap_output` stamps `agent_status`. `tests/test_agent_registry.py` (36 test cases) asserts statuses, stub labeling, registered stubs, unwired agents, config keys, and state slots. Three of these rules (declared status, registered stubs, unwired agents) were checked by breaking them once |
| 0.6 | `scripts/inventory.py` writes `docs/INVENTORY.md`. A new CI job, `inventory`, fails when the file is stale (checked by making a stale edit) |
| 0.7 | `.gitattributes` added. `git add --renormalize .` changed nothing, as predicted |

**Test numbers:**

| | Before | After |
|---|---|---|
| CI | 114 tests ran (71 never ran); `python-lint` red since March 21 | **293 passed, 3 skipped** (the 3 need an API key); black, ruff, and the inventory check green locally |
| Test functions | 185 | **268** in 18 files (parametrized tests counted once) |

### 5.3 Not done, and why

- **0.0** is for the team: check the OneDrive copy for unpushed work, then make a fresh clone.
- **0.3 (f), (g)** were not in the approved set and need an owner's look:
  - `claude/frontend-foundation-setup-sIaBo`: round-2 frontend fixes. They conflict with, and delete, intake components that `main`'s voice mode now uses.
  - `claude/motion-drafter-agent-spec-hgCCq`: spec-review fixes to the Motion Drafter. The same commits delete the Brady, plea/trial, and sentencing files, so they need selective cherry-picking.
  - `claude/debug-intake-interviewer-V4EXJ`: probably superseded by `main`'s April 11 intake fixes.
  - `claude/defender-ai-overview-dlap4b`: superseded by the inventory.
  - Branches already merged can be deleted. I left branch deletion to the team.
- **Dead `orchestrator_init_node` / `_orchestrator_ref`**: left in place. `graph.py` stays untouched until Phase 2 or 3 (SPEC §9.1).
- **0.8**: deferred, see §5.1.

### 5.4 Found while merging

- **PR #6's tests make live calls.** Of its 20 tests, 9 run an agent. Only 2 of those 9 mock `call_llm`. The other 7 make real Anthropic and CourtListener calls and pass because the agents catch the failure and return empty results. In CI they hit the network. The Phase 1 cassette layer is the fix.
- **Wiring, per `docs/INVENTORY.md`:**
  - Of 24 agents, 10 are registered with the Orchestrator, and only **6 are reachable from `main.py`** (actually runnable through the app).
  - 9 of 18 `CaseState` agent-output slots have no writer.
  - The newly merged research agents are registered but not reachable from any route.
- **The default model is past end-of-life,** so no live run works yet. This is Phase 1.

### 5.5 What this makes measurable

- Every agent output now says whether it came from a stub, a partial agent, or a real one. A later measurement can split any metric by implementation tier. That is the naive-baseline comparison from §3.5.
- Every commit now has a machine-generated count of agents that exist, are registered, and are reachable.
