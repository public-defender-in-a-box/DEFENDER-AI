# Defender AI — Architecture & Phase Plan v2.0

**Audience:** Claude Code
**Supersedes:** `GettingClaudeChatUpToSpeed(9.4.26).md` (inaccurate — see §2) and
the `18.9.2026` local-only Defender Toolkit spec (different product; its
citation and integrity architecture is carried forward here, its scope
limitations are not)
**Date:** October 2026

---

## 0. Read this first

Read `CLAUDE.md` before this document. It contains the invariants.

The single most important thing to understand: **this is a research instrument.**
The system is supposed to attempt the whole defender workflow, including the
parts a deployable product must never do. Its guardrails are sensors, not
filters. If you find yourself about to suppress an output, stop — record and
classify it instead.

**Before writing any code, produce a reconciliation report.** §2 states the
repository's measured condition as of October 1, 2026. Verify it, then report:

1. What has changed since that audit.
2. Where this spec contradicts a decision already in the code, and which should
   win.
3. Anything here you think is wrong, impractical, or would weaken the study.

Then propose a revised Phase 0 and stop.

---

## 1. What this is

A nineteen-agent system that takes a synthetic criminal matter from charging
document through discovery analysis, research, intake, and attorney-facing
work product — instrumented throughout so that its failures are measurable.

**Jurisdiction:** Georgia. O.C.G.A. Title 16 (Crimes and Offenses), Title 17
(Criminal Procedure), Title 24 (Evidence).

**Worked vertical slice:** simple marijuana possession (≤1 oz) for the
analytical path, plus one synthetic matter with substantial discovery volume
(a felony with a phone extraction, a CAD log, and multi-angle body-camera
transcripts) for the evidence-analysis path. The possession case cannot exercise
the document-volume features; it has almost no discovery.

**What is new in v2:** a Tier 2 Evidence Analysis group (§7), a provenance
primitive that makes every assertion checkable (§5), and a measurement layer
(§8) that turns the pipeline into an experiment.

---

## 2. Verified state of the repository

> **Superseded, October 4, 2026.** This section measured a local clone last updated
> March 21, 2026, not the repository. The verified state is in
> `docs/RECONCILIATION_2026-10-04.md`; the current state is `docs/INVENTORY.md`
> (generated, CI-checked). Phase 0 was revised and executed per that report's §4–5.

Measured October 1, 2026 by direct inspection of all branches and the full
fifteen-commit history. Treat narrative claims about this codebase — including
these — as stale after Phase 0 builds the generator.

### Real

| Component | Lines | Tests | Note |
|---|---|---|---|
| `tier1/intake_conductor.py` | 1,101 | ~6 | Five-phase interview. Largest build. |
| `tier1/charge_processing.py` | 783 | ~5 | Works. Most load-bearing component. |
| `tier2_attorney/motion_drafter.py` | 563 | ~17 | Plus 409 lines of five Georgia templates. Best tested. |
| `tier0/orchestrator.py` | 476 | ~3 | Sequencing, confidence gate, merge decisions. Sound. |
| `tests/test_pipeline_integration.py` | 566 | — | Real coverage of upload → state. |
| `tier1/pre_interview.py` | 234 | 0 | Partial. |

### Not real, despite prior documentation

- `cross_cutting/ethics_monitor.py` — **140 lines, 0 tests.** Four checks: a LOW
  confidence flag, a substring scan of eight hardcoded phrases, a disclaimer
  presence check, one agent-specific check. No bias audit. No hallucination
  detection. Defeated by paraphrase.
- `tier2_attorney/sentencing_agent.py` — 57-line stub. The multi-node sentencing
  sub-pipeline described in prior docs **has never existed in any commit.**
- Disclosure tracking — **no such file has ever existed.**
- Thirteen Tier 2 agents are 35–65 line stubs: docstring, one prompt,
  `wrap_output()`. No corpus lookup, no post-processing, no tests.
- `src/corpus/data/` contains only `.gitkeep`. Every citation ever produced by
  this system is unverified by construction.
- `services/llm_service.py` — 42 lines. No retry, no timeout, no token
  accounting, no schema validation, bare `json.loads`. Its docstring claims all
  three features it lacks. All nineteen agents route through it.
- `routes/_store.py` — module-level dict. Every case lost on restart. The Prisma
  schema in `packages/web/prisma/` is unused by the backend.
- Only **five of nineteen** agents appear in the Orchestrator's `_AGENT_CONFIG`:
  charge processing, pre-interview research, intake conductor, case prep,
  disclosure tracking (which maps to a nonexistent file). The other fourteen have
  no state slot and no path into `CaseState`.
- A 524-line Rights Violation Scanner with 20 tests is unmerged on
  `Mark-Rights-Violation-Scanner`; `main` carries a 65-line stub.

### Repository hygiene problems found October 4, 2026

These block clean work and must be fixed in Phase 0 before anything else.

- **`main` is behind both feature branches.** Two of the four substantial
  components are not on `main`:
  - `motion-drafter` is 2 commits ahead (the real 563-line Motion Drafter, its
    five templates, and 335 lines of tests). `main` carries a 61-line stub.
  - `Mark-Rights-Violation-Scanner` is 2 commits ahead (the 524-line Rights
    Violation Scanner and 20 tests). `main` carries a 65-line stub.

  Anyone reconciling against `main` is reconciling against the oldest state of
  the project. Merge both before any other Phase 0 work.

- **Line-ending churn makes `git diff` useless.** 104 files report as modified
  with exactly 9,747 insertions and 9,747 deletions — every line deleted and
  re-added unchanged. This is CRLF/LF normalization churn, almost certainly from
  the repository living inside a OneDrive-synced folder on Windows. No content is
  at risk, but no diff is readable and formatting checks are unreliable. Fix with
  a `.gitattributes` containing `* text=auto eol=lf`, then
  `git add --renormalize .` and commit the normalization as its own commit.

- **The repository is inside OneDrive.** `.git/index.lock` operations already
  fail intermittently. A synced folder and a git index are a known bad
  combination. Move the working copy outside OneDrive before Phase 1.

### Known defects to fix in passing

- `CaseState.jurisdiction` defaults to `"IL"` while the upload route and graph
  nodes default to `"GA"`. Fix to `"GA"`.
- `agents/graph.py` is truncated: `intake` and `case_prep` nodes only set a stage
  string. Real intake runs outside the graph through the WebSocket route.
- The Orchestrator constructs a fresh instance per graph node and re-hydrates
  state by hand, holding a `_orchestrator_ref` containing a raw `id()`. This will
  not survive persistence.
- `packages/web/package.json` declares `"test": "jest"` with no jest installed.
- Auth accepts any syntactically valid email and returns a hardcoded attorney.

---

## 3. Architecture

### 3.1 The two rules that do not change

1. **Agents never communicate directly.** All data flows through `CaseState`,
   which the Orchestrator owns exclusively.
2. **The Orchestrator is an active state manager.** It enforces dependency
   sequencing, routes every output through the Ethics Sensor, records merge
   decisions, and handles partial failure without collapsing the run.

### 3.2 Revised agent hierarchy

```
TIER 0 — ORCHESTRATOR
    └── Case Orchestrator              tier0/orchestrator.py          [REAL]

TIER 1 — CONDUCTORS
    ├── Charge Processing              tier1/charge_processing.py     [REAL]
    ├── Discovery Intake               tier1/discovery_intake.py      [NEW]
    ├── Pre-Interview Research         tier1/pre_interview.py         [PARTIAL]
    ├── Intake Conductor               tier1/intake_conductor.py      [REAL]
    └── Case Prep Conductor            tier1/case_prep.py             [STUB]

TIER 2 — EVIDENCE ANALYSIS                                            [NEW GROUP]
    ├── Record Ledger                  tier2_evidence/record_ledger.py
    ├── Tabular Analyzer               tier2_evidence/tabular_analyzer.py
    ├── Timeline Builder               tier2_evidence/timeline_builder.py
    ├── Proof Matrix                   tier2_evidence/proof_matrix.py
    ├── Evidence Blocking              tier2_evidence/evidence_blocking.py
    └── Witness Profiler               tier2_evidence/witness_profiler.py

TIER 2 — RESEARCH
    ├── Statute Agent                  tier2_research/statute_agent.py       [STUB]
    ├── Case Law Agent                 tier2_research/case_law_agent.py      [STUB]
    ├── Citation Verifier              tier2_research/citation_verifier.py   [STUB]
    └── Recency Monitor                tier2_research/recency_monitor.py     [STUB]

TIER 2 — INTAKE SPECIALISTS
    ├── Rights Violation Scanner       tier2_intake/rights_scanner.py   [UNMERGED: 524 ln]
    ├── Collateral Consequences        tier2_intake/collateral_agent.py      [STUB]
    └── Personal Circumstances         tier2_intake/personal_circumstances.py [STUB]

TIER 2 — ATTORNEY PREP
    ├── Motion Drafter                 tier2_attorney/motion_drafter.py      [REAL]
    ├── Brady Candidate Surfacer       tier2_attorney/brady_agent.py         [STUB]
    ├── Plea/Trial Assessment          tier2_attorney/plea_trial_analyst.py  [STUB]
    └── Sentencing & Mitigation        tier2_attorney/sentencing_agent.py    [STUB]

CROSS-CUTTING
    ├── Ethics Sensor                  cross_cutting/ethics_sensor.py   [REPLACES monitor]
    └── Measurement Recorder           cross_cutting/measurements.py         [NEW]
```

`fact_gatherer.py` is folded into the Intake Conductor and should be deleted
rather than left as a stub.

### 3.3 Revised pipeline

```
Charging documents ingested
  → Charge Processing            (charges, elements, penalties, enhancements)
  → Discovery Intake             (hash, dedup, classify, Bates arithmetic)
  → Evidence Analysis            (ledger → tabular → timeline → proof matrix → blocking)
  → Pre-Interview Research       (statutes + case law → targeted question list)
  → Intake Conductor             (five-phase interview; feeds the ledger)
  → Case Prep Conductor          (synthesis)
      ├── Motion Drafter
      ├── Brady Candidate Surfacer
      ├── Plea/Trial Assessment
      └── Sentencing & Mitigation
  → Attorney Review

Ethics Sensor classifies and records every output. It does not block.
```

Note the ordering change: **evidence analysis runs before intake.** Taxel's
process and Hines's both start from the production, and a ledger built from
discovery gives the Intake Conductor something to test the client's account
against — which is what makes the inconsistency detection meaningful rather than
a comparison against the charging document alone.

### 3.4 New pipeline stages

Insert into `PipelineStage` after `CHARGES_PROCESSED`:

```
DISCOVERY_INGEST → DISCOVERY_INGESTED → EVIDENCE_ANALYSIS → EVIDENCE_ANALYSIS_COMPLETE
```

---

## 4. CaseState changes

Add these slots. Every new agent must declare which one it writes, and get an
`_AGENT_CONFIG` entry; an agent without both is not wired in and must have a test
asserting so.

```python
# Discovery and evidence analysis
discovery_inventory:   dict | None    # Discovery Intake
record_ledger:         dict | None    # Record Ledger
tabular_analysis:      dict | None    # Tabular Analyzer
evidence_timeline:     dict | None    # Timeline Builder
proof_matrix:          dict | None    # Proof Matrix
evidence_blocking:     dict | None    # Evidence Blocking
witness_profiles:      dict | None    # Witness Profiler

# Measurement
measurements:          dict           # default_factory=dict — Sensor + per-run metrics
run_metadata:          dict           # git SHA, model name/version, prompt versions
```

Also: change `jurisdiction` default from `"IL"` to `"GA"`.

Keep the existing slots. Do not restructure `CaseState` into a nested shape in
this phase — the flat slot layout is working and the migration cost is not worth
paying yet.

---

## 5. The provenance primitive

This is the architectural keystone and everything downstream depends on it. Build
it before any evidence-analysis agent.

### 5.1 One locator type for every source medium

The insight that makes this work: documents, media, and spreadsheets must cite
through a **single discriminated union**, so that the timeline, the proof matrix,
and the contradiction detector do not care where a fact came from.

```python
class DocLocator(BaseModel):
    kind: Literal["document"] = "document"
    artifact_id: str
    page: int
    bates: str | None = None
    char_start: int
    char_end: int

class MediaLocator(BaseModel):
    kind: Literal["media"] = "media"
    artifact_id: str
    start_ms: int
    end_ms: int
    speaker: str | None = None

class CellLocator(BaseModel):
    kind: Literal["tabular"] = "tabular"
    artifact_id: str
    sheet: str
    row_index: int
    columns: list[str]

class RowSetLocator(BaseModel):
    """For aggregate claims over many rows."""
    kind: Literal["tabular_set"] = "tabular_set"
    artifact_id: str
    sheet: str
    row_indices: list[int]
    predicate: str          # the executed query, stored so the claim is reproducible
    row_count: int

Locator = Annotated[
    DocLocator | MediaLocator | CellLocator | RowSetLocator,
    Field(discriminator="kind"),
]
```

`RowSetLocator.predicate` is why aggregate claims are checkable: the claim "8,412
messages were produced and 72 hours are missing" stores the query that produced
it, so anyone can re-run it.

### 5.2 The Assertion

```python
class Assertion(BaseModel):
    id: str
    case_id: str
    text: str                        # the normalized asserted fact
    locator: Locator
    source_text: str                 # VERBATIM text at the locator
    extraction_method: Literal["deterministic", "model", "attorney"]
    judgment_class: JudgmentClass    # see CLAUDE.md §3.2
    confidence: ConfidenceLevel
    occurred_at: datetime | None = None
    time_precision: Literal["exact","minute","hour","day","month","year","unknown"] | None = None
    entity_ids: list[str] = []
    confirmed_by_user: bool = False
    superseded_by: str | None = None
```

### 5.3 The verification rule

Mechanical and testable:

> On write, fetch the stored source at `locator` and compare it byte-for-byte to
> `source_text`. On mismatch, **drop the assertion**, increment
> `measurements.verification_failures`, and log the dropped text for analysis.

Do not repair. Do not surface with a warning. The drop count is a headline
research metric — a model whose assertions fail verification 30% of the time is a
finding, and you only get that number by dropping rather than fixing.

---

## 6. Do it with code where code can do it

The strongest property of this project is that a large share of the painful work
is **not a model problem.** Solving those parts deterministically makes the system
faster, free, reliable — and, critically for the study, gives us a **control
condition**: a baseline of what perfect execution looks like, against which
model-dependent components can be measured.

| Task | Method |
|---|---|
| Bates extraction | Regex + positional heuristics (page corner, monotonic sequence) |
| Bates gap report | Arithmetic over ranges. Pure code. |
| Duplicate detection | SHA-256 exact; MinHash shingling for near-duplicates |
| Document boundaries | Layout signals: Bates discontinuity, header/footer change, blank pages, font profile shifts. Model only on ambiguity. |
| Text vs. scanned | PyMuPDF text-layer presence check |
| Date extraction | `dateparser` + regex over a fixed format set; model only for relative expressions |
| Entity *mention* detection | spaCy NER first pass; model only for resolution and role assignment |
| All tabular analysis | pandas. See §7.2. |
| Search | SQLite FTS5 + vector similarity. No generation. |

**Reserve the model for:** ambiguous document classification, entity resolution,
summarization, relevance assessment, contradiction detection, and the generative
attorney-prep work. Those are where its judgment adds something.

---

## 7. The Evidence Analysis group

The detailed, buildable spec for this group is `PHASE_3_EVIDENCE_ANALYSIS.md`.
What follows is the architectural summary.

### 7.1 Why this group, and why now

Two practitioners, interviewed two weeks apart, independently described the same
capability. Prof. Taxel's four-step process is discovery inventory → sourced
timeline → proof analysis (element by element, evidence mapped to each) →
evidence blocking, and he volunteered that proof analysis is where AI could help
most. Prof. Hines, who describes herself as on the skeptical train, named
reviewing large document drops and record tracking "much quicker and much more
reliably than humans" as obviously valuable, and said she would never go to trial
without a complete transcript of the arrest event.

Taxel also asked, specifically: cell-phone extractions arrive as Excel
spreadsheets containing enormous volumes of data — can this be expedited, and can
it produce "a map of the useful"?

That question is the most tractable thing either of them asked for, and it is
the subject of §7.2.

### 7.2 The Tabular Analyzer: model as planner, code as executor

The agent that analyzes extraction reports, call detail records, jail call logs,
and financial records. Its design principle is the reason it will work:

> **The model never sees the rows and never computes a number. It sees a
> statistical profile and chooses from a closed registry of analyses the code
> knows how to run. The code executes them.**

Five stages:

1. **Profile** — deterministic. Per sheet: row count, column names and inferred
   dtypes, null rates, min/max of date and numeric columns, categorical
   cardinality, detected phone-number / timestamp / coordinate columns. The
   profile is a few kilobytes regardless of whether the file has 400 rows or
   400,000.
2. **Classify** — the model sees only the profile and returns a Pydantic-validated
   `SheetClassification`: a sheet kind (`calls`, `messages`, `chats`, `contacts`,
   `web_history`, `locations`, `installed_apps`, `device_info`, `media_metadata`,
   `cdr`, `jail_calls`, `financial`, `unknown`) plus a column-role mapping.
3. **Plan** — the model returns an `AnalysisPlan`: a list of analyses selected
   from the closed registry, with parameters filled. It cannot write a query; it
   picks from a menu. This is the property that eliminates the hallucinated-number
   failure mode entirely.
4. **Execute** — deterministic pandas. Each registered analysis returns `Finding`
   objects carrying `RowSetLocator`s.
5. **Narrate** — the model writes prose over *computed* findings only. Any
   sentence without a locator is dropped per §5.3.

The analysis registry — temporal gap scan, window activity around the alleged
offense time, counterparty frequency and emergence, clock skew across sources,
attribution signals, produced-volume versus cited-volume, location sequence
plausibility, selection-integrity and null-pattern checks — is specified in
`PHASE_3_EVIDENCE_ANALYSIS.md` §4.

### 7.3 Why this is the right thing to build next

1. It is the only capability both practitioners asked for that is also
   immediately tractable.
2. **It is almost entirely deterministic**, so it works at full quality
   regardless of model strength. That makes it the study's control condition and
   the cleanest result we can produce: here is what code does perfectly, here is
   where handing the task to a model degraded it, measured.
3. Building it forces the §5 provenance primitive into existence, which every
   later phase needs.
4. It is the most demonstrable feature in the system. "The State produced 8,412
   messages, quoted six, and the seventy-two hours before the alleged offense are
   absent from the production" is a sentence that lands with a practitioner.
5. Its outputs are arithmetic, so it carries no legal-judgment exposure even
   though the surrounding system deliberately does.

### 7.4 Media

Transcription is deferred, with schema hooks reserved now: `MediaLocator` exists
in §5.1 from the start, so timecoded transcripts become citable spans with no
migration. When built, use local Whisper with diarization; treat timecodes exactly
as Bates pages. JusticeText already does multi-angle synchronization well — if the
introduction Taxel offered happens, ingest their export rather than rebuilding it.
Resist "AI video understanding"; transcription and search are nearly all of the
value.

---

## 8. The measurement layer

What makes this a study rather than a demo. Build it in Phase 5 and backfill
metrics for everything already built.

Per run, record to a `measurements` store:

| Metric | Why it matters |
|---|---|
| Assertions emitted, by `judgment_class` | The headline result: how much of the output is recital versus advice |
| Verification failure rate, per agent | Hallucination rate, measured not estimated |
| Fabricated-citation count | Citations that are well-formed but name nonexistent authority. The most dangerous category. Count separately. |
| Keyword-filter vs. judge disagreement | The gap between cheap and real advice detection, which is itself publishable |
| Abstention rate | How often the system correctly declines |
| Deterministic vs. model accuracy on the same task | The control condition from §6 |
| Bias probe deltas | Same matter, varied demographics, nothing else changed |
| Wall-clock and token cost per stage | Feasibility finding |

Metrics are emitted as structured records, never only as prose.

---

## 9. Phase plan

Each phase ends with a stop and a report. Phases 0–2 are prerequisites with no
demonstrable output; say so plainly rather than making them look like features.

| Phase | Builds | Why here |
|---|---|---|
| **0** | Ground truth, in this order: (a) merge `motion-drafter` and `Mark-Rights-Violation-Scanner` into `main`; (b) add `.gitattributes` and renormalize line endings as a standalone commit; (c) mark every stub with a module-level `STATUS = "STUB"` and a test asserting it is absent from `_AGENT_CONFIG`; (d) write a generator that derives the project inventory from the tree and run it in CI; (e) fix the CI `testpaths` override so no test directory is silently skipped. | A month of planning was lost to a briefing that described intentions as reality, and `main` currently lacks half the real code. Steps (a) and (b) must come first or every later reconciliation is against the wrong tree and every diff is unreadable. The generator in (d) is ~150 lines and permanently closes the drift failure mode. |
| **1** | Model gateway: retry with backoff, timeouts, token accounting, per-agent Pydantic response schemas with typed errors instead of bare `JSONDecodeError`. Then a cassette layer recording every request/response to disk keyed by prompt hash, replayed in tests. | Nineteen agents depend on one 42-line file; hardening it upgrades all of them. The cassette layer is why this ranks second — it makes integration tests free, fast and deterministic, which is the actual reason there are 43 tests instead of 200. Every later phase is cheaper to test once it exists. |
| **2** | The §5 provenance primitive, and persistence. SQLite with Alembic migrations in `packages/api` — **not** the Prisma schema, which lives in the web package and would guarantee drift. Retire `_store.py`. Fix the Orchestrator's per-node reconstruction and the `id()` reference. | Both change `CaseState`'s shape, so do them in one migration rather than two. Retrofitting provenance later means rewriting whatever is built in between. SQLite keeps the system portable to a laptop later without re-architecting. |
| **3** | **The Evidence Analysis group.** See `PHASE_3_EVIDENCE_ANALYSIS.md`. Substages: 3a ingest and profiling, 3b the tabular registry, 3c ledger population, 3d timeline and proof matrix, 3e evidence blocking. | The feature the practitioners asked for and the study's control condition. **3a and 3b are mostly deterministic and can begin in parallel with Phase 1** — the part of this feature that matters most needs the least foundation. |
| **4** | The Georgia corpus, for real. O.C.G.A. Titles 16, 17, 24 as structured records with section text. Georgia appellate opinions via Caselaw Access Project or CourtListener bulk data. Pattern jury instructions, criminal volume. Then make the citation verifier mean something: resolve every emitted cite against the corpus, store the matched text as a span, mark `VERIFIED` only on exact match, drop what will not resolve. Mark pre-2022 criminal expert-testimony authority `SUPERSEDED` (see `CLAUDE.md` §4.1). | The credibility unlock, and it must precede the Sensor rewrite because citation verification *is* the hallucination measurement. Building the Sensor first means building it twice. The pattern jury instructions are a closed-corpus template-fill problem with zero hallucination risk, and both practitioners asked for exactly that tool. |
| **5** | Replace the Ethics Monitor with the Ethics Sensor and the measurement layer (§8). Three layers: deterministic structural checks, citation verification against Phase 4, and an adversarial judge call with a written rubric. It classifies and records; it does not block. Backfill metrics for Phases 0–4. Test it properly. | Paraphrased advice is semantic and no keyword list will catch it. Layering means the cheap checks handle most cases and the expensive judge runs only on what survives — and the layers degrade independently. |
| **6** | The evaluation harness: 20–50 synthetic Georgia matters with planted ground truth — known elements, a planted suppression issue, a planted *Brady* problem, contradictory witness times, a fabricated-citation trap, and a phone extraction with a known missing window. Score the system against all of it. | The only phase that produces publishable output. It converts "we built a thing" into "we measured a thing," which is the difference between a demo and an independent study. It also becomes the regression suite. |

### 9.1 What is deliberately deferred

Media transcription (§7.4, hooks only). Real authentication. Multi-user. The
truncated `graph.py` intake and case-prep nodes stay truncated until Phase 3
lands — do not fix them in isolation, because the pipeline reshapes in §3.3.
Jury selection and the suppression-hearing simulator are post-Phase-6 and should
not be scoped now.

---

## 10. Open questions

1. **Which synthetic felony matter?** The evidence-analysis path needs a case with
   real discovery volume. Someone has to design it: the charges, the production,
   the planted issues, the phone extraction and its known gaps. This is legal
   work, not engineering, and it blocks Phase 6.
2. **Corpus acquisition.** Is O.C.G.A. full section text obtainable in bulk in
   machine-readable form, and under what terms? The pattern jury instructions are
   the same question and may be harder.
3. **Which extraction report format to target.** A synthetic Cellebrite-style
   workbook, a carrier CDR, or both? The column-role mapping in §7.2 stage 2
   depends on committing to at least one realistic shape.
4. **The bias probe design.** Varying demographic attributes and holding
   everything else constant sounds simple and is not. Worth deciding before
   Phase 5 rather than during it.
5. **Validation partner.** Prof. Hines offered introductions — her husband,
   Amanda Grantham, and contacts in the Athens PD office. Under the research
   framing the ask is "help us find where this breaks," which is a much easier
   yes than "will you use this."
