# Defender AI — Architecture & Phase Plan v2.1

**Audience:** Claude Code
**Supersedes:** `GettingClaudeChatUpToSpeed(9.4.26).md` and the `18.9.2026`
local-only Defender Toolkit spec (different product; its citation and integrity
architecture is carried forward here, its scope limitations are not)
**Date:** October 2026. v2.1 (October 4, 2026) follows Phase 0: phases reordered
by capability gained, Phase 2 split into 2a and 2b, and §2, §3.2 and §5.3 rewritten
against the real tree.
**Companion phase documents:** `PHASE_1_MODEL_GATEWAY.md`,
`PHASE_3_EVIDENCE_ANALYSIS.md` (now Phase 4). Maintained alongside this file.

---

## 0. Read this first

Read `CLAUDE.md` before this document. It contains the invariants.

The single most important thing to understand: **the goal is the most capable
tool we can build.** The system is supposed to attempt the whole defender
workflow, including the parts a deployable product must never do, because it is
never deployed (`CLAUDE.md` §1.1). Its guardrails are sensors, not filters — if
you find yourself about to suppress an output, stop and record it instead, since
you cannot improve a failure you cannot see. And prefer a capability a user can
actually reach over one that exists only in the tree.

**Phase 0 is complete (PR #13).** Before starting any phase:

1. Read `docs/INVENTORY.md`. It is generated from the tree and checked in CI; it,
   not this document, is the authority on what exists, what is registered, and
   what the running app can reach.
2. Where this spec and the inventory disagree, say so and say which should win.
3. Report your plan for the phase, including anything here you think is wrong or
   impractical, and stop for approval (`CLAUDE.md` §8).

---

## 1. What this is

A multi-agent system that takes a synthetic criminal matter from charging
document through discovery analysis, research, intake, and attorney-facing work
product — built to be as capable as we can make it, and instrumented enough that
we know where it stands. The repo holds 24 agents; stop saying "nineteen."

**Jurisdiction:** Georgia. O.C.G.A. Title 16 (Crimes and Offenses), Title 17
(Criminal Procedure), Title 24 (Evidence).

**Worked vertical slice:** simple marijuana possession (≤1 oz) for the
analytical path, plus one synthetic matter with substantial discovery volume
(a felony with a phone extraction, a CAD log, and multi-angle body-camera
transcripts) for the evidence-analysis path. The possession case cannot exercise
the document-volume features; it has almost no discovery.

**What is new in v2:** a Tier 2 Evidence Analysis group (§7), a provenance
primitive that makes every assertion checkable (§5), and a measurement layer
(§8) that tells us whether a change made the tool better.

---

## 2. State of the repository

This section used to hold an audit dated October 1, 2026. It measured a local clone
27 commits stale and was wrong on nearly every count (`CLAUDE.md` §8.1;
`docs/RECONCILIATION_2026-10-04.md`). It is deliberately not replaced with another
snapshot. **The current state is `docs/INVENTORY.md`.**

Defects still open after Phase 0, each with the phase that closes it:

| Defect | Phase |
|---|---|
| `services/llm_service.py` (41 lines, 22 importers): no schema validation, no token accounting (`response.usage` is discarded), bare `json.loads`. Retries and timeouts are only the SDK's defaults. The default model `claude-sonnet-4-20250514` was **retired on June 15, 2026** (Anthropic's model-deprecations page), so every live call fails. | 1 |
| 45 `except Exception` blocks across 21 agent modules, most turning a failure into a well-formed empty success. | 1 |
| The Orchestrator blocks on `CRITICAL` ethics flags, and LOW-confidence outputs skip the ethics check entirely. | 1 |
| No persistence (`routes/_store.py` is a module-level dict); a case cannot be re-run; Orchestrator state (`_blocked`, `_merge_history`, `_human_review_required`) lives outside `CaseState`. | 2a |
| Sequencing compares positions in the `PipelineStage` enum, which cannot express a branching pipeline. | 2a |
| Two execution paths: routes drive agents, while `agents/graph.py` compiles a LangGraph pipeline no route uses (its `orchestrator_init_node`, holding a raw `id()`, is dead code). | 2a |
| 18 of 24 agents are unreachable from the app; 8 `CaseState` slots have no writer. | 2b |
| Frontend types for Motions, Plea/Trial and Sentencing were written against the old stubs' outputs, not the real agents. | 2b |
| `src/corpus/data/` is empty, and `.gitignore` excludes `src/corpus/data/*.json`. | 3 |
| Uploads accept any file and OCR images (`CLAUDE.md` §2, §7). | 2b, 4 |
| `packages/web/package.json` declares `"test": "jest"` with no jest installed. Auth accepts any email and returns a hardcoded attorney. | Deferred (§9.1) |

---

## 3. Architecture

### 3.1 The two rules that do not change

1. **Agents never communicate directly.** All data flows through `CaseState`,
   which the Orchestrator owns exclusively.
2. **The Orchestrator is an active state manager.** It enforces dependency
   sequencing, routes every output through the Ethics Sensor, records merge
   decisions, and handles partial failure without collapsing the run.

### 3.2 Agent hierarchy

Roles, and the module that implements each. **No status tags on purpose:** the
last set went stale within a week. `STATUS` (REAL / PARTIAL / STUB), registration,
reachability and test counts come from `docs/INVENTORY.md`.

```
TIER 0 — ORCHESTRATOR
    └── Case Orchestrator              tier0/orchestrator.py

TIER 1 — CONDUCTORS
    ├── Charge Processing              tier1/charge_processing.py
    ├── Discovery Intake               tier1/discovery_intake.py           [planned: Phase 4]
    ├── Pre-Interview Research         tier1/pre_interview.py
    ├── Intake Conductor               tier1/intake_conductor.py
    └── Case Prep Conductor            tier1/case_prep.py

TIER 2 — EVIDENCE ANALYSIS                                                 [planned: Phase 4]
    ├── Record Ledger                  tier2_evidence/record_ledger.py
    ├── Tabular Analyzer               tier2_evidence/tabular_analyzer.py
    ├── Timeline Builder               tier2_evidence/timeline_builder.py
    ├── Proof Matrix                   tier2_evidence/proof_matrix.py
    ├── Evidence Blocking              tier2_evidence/evidence_blocking.py
    └── Witness Profiler               tier2_evidence/witness_profiler.py

TIER 2 — RESEARCH
    ├── Research Orchestrator          tier2_research/research_orchestrator.py
    ├── Statutes                       tier2_research/ga_statutes_agent.py
    ├── Case Law (Georgia criminal)    tier2_research/ga_criminal_case_law.py
    ├── Case Law (constitutional)      tier2_research/constitutional_case_law.py
    ├── Citation Verification          tier2_research/citation_verification.py
    └── Recency Monitor                tier2_research/recency_monitor.py

TIER 2 — INTAKE SPECIALISTS
    ├── Rights Violation Scanner       tier2_intake/rights_scanner.py
    ├── Fact Gatherer                  tier2_intake/fact_gatherer.py
    ├── Collateral Consequences        tier2_intake/collateral_agent.py
    └── Personal Circumstances         tier2_intake/personal_circumstances.py

TIER 2 — ATTORNEY PREP
    ├── Motion Drafter                 tier2_attorney/motion_drafter.py
    ├── Disclosure Tracking            tier2_attorney/disclosure_tracking.py
    ├── Brady Candidate Surfacer       tier2_attorney/brady_agent.py
    ├── Plea/Trial Assessment          tier2_attorney/plea_trial_analyst.py
    └── Sentencing & Mitigation        tier2_attorney/sentencing_agent/    (10-node package)

CROSS-CUTTING
    ├── Ethics Monitor → Ethics Sensor cross_cutting/ethics_monitor.py → ethics_sensor.py
    │                                  (non-blocking from Phase 1; replaced in Phase 5)
    └── Measurement Recorder           cross_cutting/measurements.py        [planned]
```

Three single-prompt stubs are kept on purpose next to the research agents that
superseded them: `statute_agent.py`, `case_law_agent.py`, `citation_verifier.py`.
They are labeled `STUB` in every output and serve as a naive-baseline comparison.

Two placements are open and get decided when the agent is wired or replaced:

- **Disclosure Tracking** overlaps the Brady Candidate Surfacer (a stub) and
  Discovery Intake. Decide in Phase 2b, when it is wired.
- **Fact Gatherer** is a real agent. Whether Record Ledger population subsumes it
  is decided in Phase 4, against its replacement, not before.

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

Matters with no discovery (the possession case) skip Discovery Intake and Evidence
Analysis. Phase 2a's per-agent `depends_on` makes that expressible.

### 3.4 New pipeline stages

Insert into `PipelineStage` after `CHARGES_PROCESSED`:

```
DISCOVERY_INGEST → DISCOVERY_INGESTED → EVIDENCE_ANALYSIS → EVIDENCE_ANALYSIS_COMPLETE
```

From Phase 2a, sequencing comes from per-agent `depends_on` slot lists.
`PipelineStage` remains a status for display, not the dependency rule.

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

The `jurisdiction` default is already `"GA"` (Phase 0).

These slots, and the §5 provenance primitive, land together in Phase 2a's
migration so `CaseState` changes shape once. If Phase 1 needs `run_metadata` or
`measurements` earlier, it adds them then.

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

Models are bad at character offsets, and PDF text extraction introduces ligatures,
hyphenation and whitespace drift. A byte-for-byte check against a *model-produced*
locator would mostly count those, not fabrication. So the work is split:

1. The model supplies the assertion, a **verbatim quote**, and a hint (artifact and
   page). It never computes offsets.
2. A deterministic **resolver** searches the stored source for the quote and
   computes the locator. `source_text` is the stored text at that computed locator,
   so it is byte-identical to the source by construction.
3. Each assertion gets one outcome, counted per agent in
   `measurements.verification_failures`:
   - `NOT_FOUND`: the quote occurs nowhere in the matter's sources. **Drop the
     assertion.** Do not repair it, do not surface it with a warning; log the
     dropped text with agent, model and prompt version. This rate is the
     fabrication rate.
   - `FOUND_ELSEWHERE`: the quote is real but not where the hint said. Keep it with
     the computed locator, so the reader sees its true source, and count the miss.
   - `FOUND_AFTER_NORMALIZATION`: found only after one documented canonicalization
     (Unicode NFC, whitespace collapsed, ligatures expanded). Keep it and count it
     separately, so extraction noise never inflates the fabrication rate.

Tabular locators verify by re-execution instead: re-run the stored `predicate`
against the artifact (whose SHA-256 must still match) and compare `row_count` and
the row set.

The drop count is a headline number. A model whose quotes are `NOT_FOUND` 30% of
the time is a finding, and you only get that number by dropping rather than
fixing.

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

The detailed, buildable spec for this group is `PHASE_3_EVIDENCE_ANALYSIS.md`
(file name kept; the group is now Phase 4). What follows is the architectural
summary.

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

### 7.3 Why this group matters

1. It is the only capability both practitioners asked for that is also
   immediately tractable.
2. **It is almost entirely deterministic**, so it works at full quality
   regardless of model strength. That makes it the study's control condition and
   the cleanest result we can produce: here is what code does perfectly, here is
   where handing the task to a model degraded it, measured.
3. It is the first heavy user of the §5 provenance primitive (schema built in
   Phase 2a), so it proves that primitive under load.
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

How you find out whether the tool is getting better. Build it in Phase 5 and
backfill metrics for everything already built. It is instrumentation in service
of capability (`CLAUDE.md` §1) — do not let a metric displace a feature.

Per run, record to a `measurements` store:

| Metric | Why it matters |
|---|---|
| Assertions emitted, by `judgment_class` | The headline result: how much of the output is recital versus advice |
| Verification failure rate, per agent | Hallucination rate, measured not estimated |
| Fabricated-citation count | Citations that are well-formed but name nonexistent authority. The most dangerous category. Count separately. |
| Keyword-filter vs. judge disagreement | Tells you whether the cheap check can be trusted, so you know when to spend a judge call |
| Abstention rate | How often the system correctly declines |
| Deterministic vs. model accuracy on the same task | The control condition from §6 |
| Bias probe deltas | Same matter, varied demographics, nothing else changed |
| Wall-clock and token cost per stage | Feasibility finding |

Metrics are emitted as structured records, never only as prose.

---

## 9. Phase plan

Each phase ends with a stop and a report. Phases 0–2 are prerequisites with no
demonstrable output; say so plainly rather than making them look like features.

**Ordering principle:** phases are ordered by **capability gained per unit of
work**, not by architectural tidiness. The goal is the most capable tool we can
build (`CLAUDE.md` §1); instrumentation serves that and therefore comes after the
capabilities it measures, not before.

The largest single gap in this project is not a missing feature. It is that
**18 of 24 agents cannot be reached from the running application** and nothing
survives a restart. There are roughly 9,000 lines of working, tested agent code — a
41-file sentencing package, five research agents, Disclosure Tracking, the Motion
Drafter, plea/trial, the Rights Scanner, three intake specialists — that no user can
invoke. Phase 2 (2a, then 2b) exists to close that, and it is why corpus work moved
ahead of new features.

| Phase | Builds | Why here |
|---|---|---|
| **0** ✅ | Ground truth. Delivered in PR #13: merged five branches (PRs #5, #6, #7, the plea/trial branch, and the IL→GA fix), fixed CI (black, ruff pinned, `testpaths` honored), `STATUS` on every agent module stamped into every output envelope, `scripts/inventory.py` generating `docs/INVENTORY.md` with a CI staleness check, `.gitattributes`. | Complete. The reconciliation that preceded it found that the October 1 audit had described a 27-commit-stale clone (`CLAUDE.md` §8.1); the generator keeps that from happening again. |
| **1** | **Model gateway, failure semantics, and the sensor switch.** See `PHASE_1_MODEL_GATEWAY.md`. Typed gateway with required per-agent response schemas; the 45 `except Exception` blocks that turn failures into empty successes; two-model cassettes; CRITICAL flags merge instead of blocking. | First because it is a capability blocker, not a measurement nicety: today an auth failure makes Charge Processing return a well-formed zero-charge "success," and no agent's output is schema-validated. Nothing built on top of that can be trusted. 22 modules depend on the one file being replaced. |
| **2a** | **Persistence and re-runnability.** SQLite with Alembic in `packages/api` (**not** the Prisma schema — it lives in the web package and would guarantee drift); retire `_store.py`; key state on `(case_id, run_id)` so a case can be re-run; move `_blocked`, `_merge_history` and `_human_review_required` into persisted state; replace enum-position sequencing with per-agent `depends_on` slot lists so the pipeline can branch and skip; settle on **one** execution path (route handlers or the LangGraph graph, which no route uses today) and remove the other's dead code. Add the §4 slots and the §5 provenance primitive in the same migration (schema only; Phases 3 and 4 are its first writers). | Everything in 2b needs state that survives a restart and a case that can run more than once. Doing provenance in the same migration avoids a second `CaseState` rewrite later. `(case_id, run_id)` is also what makes any repeated run possible at all. |
| **2b** | **Reach.** Wire every REAL agent into `_AGENT_CONFIG` and make it runnable from the app, **one agent at a time**, filling the eight orphaned `CaseState` slots. Each agent needs: an input adapter that builds its input from `CaseState` (the agents were written against different `CaseState` shapes — the Motion Drafter and Plea/Trial fixtures disagree); an output contract shared by backend and frontend; a route; and one end-to-end test through the API. The frontend pages for Motions, Plea/Trial and Sentencing exist, but their types were written against the old stubs: the Sentencing page expects federal-guidelines fields (offense level, criminal history category) that do not exist in Georgia. Rewrite each page's types against the real agent. Start with Sentencing (71 tests; matches the possession slice). Also: the `NOT FOR USE ON REAL MATTERS` banner (response header, UI, CLI) and the synthetic-fixture test (`CLAUDE.md` §2), since 2b touches the whole API surface. | **The single largest capability jump available.** About 9,000 lines of working, tested agent code become usable. It is mostly integration against code that already works, but not only plumbing: input adapters and output contracts are real design work, which is why it goes one agent at a time. |
| **3** | **The Georgia corpus and real citation verification.** O.C.G.A. Titles 16, 17, 24 as structured records with section text. Georgia appellate opinions via Caselaw Access Project or CourtListener bulk data. Pattern jury instructions, criminal volume. Resolve every emitted cite against the corpus by the §5.3 resolver, store matched text, mark `VERIFIED` only on exact match. Attach `SUPERSEDED` to the *legal proposition* and trigger on the date of the underlying proceeding, not the opinion date (`CLAUDE.md` §4.1). | Moved up from 4. Until this lands, all five research agents produce confident fiction and their real capability is zero — which caps the whole tool regardless of how many agents are wired in. Also unblocks `.gitignore`, which currently excludes `src/corpus/data/*.json` and would silently keep the corpus out of commits. |
| **4** | **The Evidence Analysis group.** See `PHASE_3_EVIDENCE_ANALYSIS.md` (filename retained; it is now Phase 4). Substages: ingest and profiling, the tabular registry, ledger population, timeline and proof matrix, evidence blocking. Needs a skip path for matters with no discovery (§3.3). Discovery Intake also carries `provenance_class` on every ingested artifact and quarantines image and video files (`CLAUDE.md` §2, §7). | The genuinely new capability, and the one both practitioners asked for. Deliberately after corpus and reach: it is the biggest build on this list and it should sit on a foundation where agents are reachable and citations resolve. Its deterministic substages can start early if someone has spare capacity. |
| **5** | Replace the keyword Ethics Monitor with the three-layer Sensor and the measurement layer (§8): deterministic structural checks, citation verification against Phase 3, and an adversarial judge call with a written rubric. Backfill metrics for earlier phases. | Paraphrased advice is semantic; no keyword list catches it. After Phase 3 because citation verification is the layer that does the real work, and building the Sensor first means building it twice. |
| **6** | The regression and capability harness: 20–50 synthetic Georgia matters with planted ground truth — known elements, a planted suppression issue, a planted *Brady* problem, contradictory witness times, a fabricated-citation trap, a phone extraction with a known missing window. Score the system against all of it, on both pinned models. | This is how you find out how capable the tool actually is, and how you know whether the next change helped. Treat it as a regression suite you run constantly, not a one-off evaluation at the end. |

### 9.1 What is deliberately deferred

Media transcription (§7.4, hooks only). Real authentication. Multi-user. The
frontend `jest` setup. Do not fix `graph.py` in isolation: Phase 2a decides whether
it becomes the single execution path or is retired. Jury selection and the
suppression-hearing simulator are post-Phase-6 and should not be scoped now.

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
5. **Models — decided October 9, 2026.** Primary `claude-opus-5-5`; users can
   switch a run to a cheaper allowlisted model to manage cost; no automatic
   fallbacks; each user supplies their own API key. Comparison model
   `claude-sonnet-5-5`, confirmed October 9, 2026. See `PHASE_1_MODEL_GATEWAY.md`
   §0 and §8, and `docs/MODELS.md`.
6. **Validation partner.** Prof. Hines offered introductions — her husband,
   Amanda Grantham, and contacts in the Athens PD office. Under the research
   framing the ask is "help us find where this breaks," which is a much easier
   yes than "will you use this."
