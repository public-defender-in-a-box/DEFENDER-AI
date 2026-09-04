# Defender AI — Project Briefing for Claude Chat

> **How to use this document:** Paste it into a fresh Claude Chat conversation as
> your first message. It brings Chat up to speed on the whole project so it can
> write implementation specs that I hand to Claude Code. Regenerate it (ask Claude
> Code to update `docs/project-briefing.md`) whenever the codebase moves
> significantly, so the briefing does not drift from reality.

---

## 0. Your role, Claude Chat

I am building **Defender AI**, a multi-agent system that assists public defenders.
I do the actual coding through **Claude Code**, which works directly in the repo.

**Your job is not to write the code.** Your job is to help me think through goals
and then produce a **written spec** that I copy-paste to Claude Code as its task
description. A good spec for my workflow:

1. States the goal in one or two sentences — what should be true when this is done.
2. Names the exact files to create or modify, using real repo paths (given in §4).
3. Defines the data contracts precisely: input shape, output shape, where it lands
   in `CaseState`, what confidence score it carries.
4. Says how it plugs into the existing pipeline — which agent calls it, what the
   Orchestrator does with the output, whether the Ethics Monitor gates it.
5. Lists the legal/ethical guardrails that apply (see §3) — these are not optional
   and Claude Code should be told explicitly which ones bind this piece of work.
6. Specifies the tests: which fixtures, what golden output, what edge cases.
7. Calls out anything intentionally deferred, so Claude Code does not scope-creep.

Assume Claude Code has the repo, a `CLAUDE.md` with conventions, and can read any
file — so the spec should be about *intent and contracts*, not a code dump. When I
describe a goal vaguely, ask me the two or three questions that actually change the
design, then write the spec.

---

## 1. What Defender AI is

A **19-agent AI system that assists public defenders** with client intake, legal
research, case preparation, and attorney workflow. Built by a team of 4 law
students.

**The problem:** public defenders carry caseloads that make thorough preparation
on every case impossible. Clients get a few minutes of attorney time. Facts that
would support a suppression motion, a diversion argument, or a Brady demand never
surface because nobody had the hours to dig for them.

**The intended shape of the solution:** the system does the front-loaded, labor-
intensive work — parsing charging documents, pulling the statutory framework and
case law, conducting a thorough structured intake interview, scanning for
constitutional violations, drafting preliminary motions, mapping sentencing
exposure and diversion eligibility — and hands the attorney a prepared case file
with everything flagged, cited, and confidence-rated. The attorney's judgment is
the product. The system's job is to make sure that judgment is exercised on
complete information.

**Two distinct user populations, and the distinction is load-bearing:**
- **Clients** interact with the intake interview. Client-facing output **informs,
  never advises.** No legal conclusions, no predictions, no strategy.
- **Attorneys** receive everything else. Attorney-facing output is decision
  support, always marked as draft, always privileged.

---

## 2. Current state, honestly

This is a **working MVP skeleton with several deeply-built agents and a lot of
scaffolding**. It is not a finished product. Section 6 breaks down exactly what is
real versus stubbed — read that before writing any spec, because the single most
common failure mode is specifying work that assumes a stub is a working agent.

**MVP scope, deliberately narrow:**
- **Single jurisdiction:** Georgia (O.C.G.A. Title 16 — Crimes and Offenses;
  Title 17 — Criminal Procedure)
- **Single case type:** criminal, with simple marijuana possession (≤1 oz) as the
  worked-through vertical slice
- **Simplified for MVP:** Personal Circumstances is a structured form rather than
  conversational; Recency Monitor is manual corpus updates; Fact Gatherer is folded
  into the Intake Conductor; Case Law Agent runs on a closed corpus with no open
  research

---

## 3. Legal and ethical rules — NON-NEGOTIABLE

These are architectural constraints, not guidelines. Every spec you write should
name which of these bind the work. They are enforced in code by the Ethics &
Compliance Monitor, which runs on every agent output before it is written to state.

1. **Client-facing agents INFORM, never ADVISE.** No legal conclusions to clients.
   The Ethics Monitor pattern-matches a UPL phrase list ("I recommend", "you should
   plead", "you must", "the best option is", etc.) against client-facing output.
2. **Every attorney-facing output carries a privilege warning** —
   `ATTORNEY-CLIENT PRIVILEGED MATERIAL`.
3. **Every draft carries** `DRAFT — ATTORNEY REVIEW REQUIRED`.
4. **Plea/trial assessments are marked** `DECISION SUPPORT ONLY`.
5. **All citations are tagged with verification status** — `VERIFIED` (from the
   closed corpus) or `UNVERIFIED` (LLM-generated). Never present an unverified
   citation as authority.
6. **No client data in logs, error messages, or anywhere outside encrypted
   storage.**
7. **The attorney can override any recommendation.** The system logs the override
   and does not resist it.
8. **Confidence is mandatory on every output.** HIGH (>0.85), MEDIUM (0.6–0.85),
   LOW (<0.6). LOW-confidence output is flagged and withheld from the merge, not
   presented as reliable.
9. **Surface unfavorable precedent honestly.** Research agents are instructed to
   return both favorable and adverse authority.

**The Ethics Monitor's five enforcement pillars** (`cross_cutting/ethics_monitor.py`,
~1100 lines, the most heavily tested component in the repo — 39 tests):

| Pillar | What it catches |
|---|---|
| **Privilege Protection** | client data leaks, missing encryption flags, missing privilege/review disclaimers, training-data exposure |
| **UPL Boundary** | advice phrasing in client-facing output, missing client disclaimers, filings without attorney approval |
| **Bias Audit** | racial, socioeconomic, gender, age, geographic, disability bias in case law selection, sentencing predictions, plea recommendations |
| **Competence Floor** | confidence thresholds; LOW output flagged rather than surfaced |
| **Hallucination Detection** | fabricated citations, invalid statute references, phantom case names, unsupported factual claims |

Flags carry a priority that determines what the Orchestrator does:
`CRITICAL` = hard block, output not merged · `HIGH` = merged with flag, attorney
review required · `MEDIUM` = merged and logged · `LOW` = logged only.

---

## 4. Architecture

### 4.1 Agent hierarchy

```
TIER 0 — ORCHESTRATOR
    └── Case Orchestrator          tier0/orchestrator.py

TIER 1 — CONDUCTORS
    ├── Charge Processing Agent    tier1/charge_processing.py   (Step Zero — parses charging docs)
    ├── Pre-Interview Research     tier1/pre_interview.py       (builds legal foundation)
    ├── Intake Conductor           tier1/intake_conductor.py    (client-facing interview)
    └── Case Prep Conductor        tier1/case_prep.py           (attorney-facing synthesis)

TIER 2 — RESEARCH
    ├── Statute Agent              tier2_research/statute_agent.py
    ├── Case Law Agent             tier2_research/case_law_agent.py
    ├── Citation Verifier          tier2_research/citation_verifier.py
    └── Recency Monitor            tier2_research/recency_monitor.py

TIER 2 — INTAKE SPECIALISTS
    ├── Fact Gathering Agent       tier2_intake/fact_gatherer.py
    ├── Rights Violation Scanner   tier2_intake/rights_scanner.py
    ├── Collateral Consequences    tier2_intake/collateral_agent.py
    └── Personal Circumstances     tier2_intake/personal_circumstances.py

TIER 2 — ATTORNEY PREP
    ├── Motion Drafter             tier2_attorney/motion_drafter.py
    ├── Brady Compliance Agent     tier2_attorney/brady_agent.py
    ├── Disclosure Tracking Agent  tier2_attorney/disclosure_tracking.py
    ├── Plea/Trial Assessment      tier2_attorney/plea_trial_analyst.py
    └── Sentencing & Mitigation    tier2_attorney/sentencing_agent/   (own LangGraph sub-pipeline)

CROSS-CUTTING
    └── Ethics & Compliance Monitor  cross_cutting/ethics_monitor.py
```

All paths are relative to `packages/api/src/agents/`.

### 4.2 The two rules that define the architecture

1. **Agents never communicate directly.** All data flows through the canonical
   `CaseState` object, which the Orchestrator owns exclusively.
2. **The Orchestrator is an active state manager, not a passive router.** It
   enforces sequencing (an agent cannot run until its dependencies have completed),
   enforces the confidence threshold, routes every output through the Ethics
   Monitor before merging, exposes pipeline status to the frontend, and handles
   partial failure without collapsing the run.

### 4.3 Pipeline flow

```
Charging docs uploaded
  → Charge Processing (extracts charges, elements, penalties, enhancements)
  → Pre-Interview Research (statutes + case law → targeted question list)
  → Intake Conductor (5-phase client interview, WebSocket)
      ├── Fact Gathering        (folded into the Conductor for MVP)
      ├── Rights Violation Scanner
      ├── Collateral Consequences
      └── Personal Circumstances
  → Case Prep Conductor (synthesis)
      ├── Motion Drafter
      ├── Brady / Disclosure Tracking
      ├── Plea/Trial Assessment
      └── Sentencing & Mitigation
  → Attorney Review (memo, motions, Brady analysis, plea/trial assessment)

Ethics Monitor runs on every output, continuously, at every stage.
```

### 4.4 Pipeline stages (`PipelineStage` enum)

`CREATED → CHARGES_PROCESSING → CHARGES_PROCESSED → PRE_INTERVIEW_RESEARCH →
PRE_INTERVIEW_COMPLETE → INTAKE_IN_PROGRESS → INTAKE_COMPLETE →
CASE_PREP_IN_PROGRESS → CASE_PREP_COMPLETE → ATTORNEY_REVIEW → ATTORNEY_APPROVED`

The Orchestrator's `_AGENT_CONFIG` maps each agent to the `CaseState` field it
writes, the stage it enters, the stage it completes, whether it is client-facing,
and the stage that must already be reached before it may run.

### 4.5 Merge decisions

Every agent output produces one of: `MERGED`, `MERGED_WITH_FLAG`,
`BLOCKED_LOW_CONFIDENCE`, `BLOCKED_ETHICS_P1`, `FAILED`. The merge history is
queryable per case at `GET /api/v1/cases/{case_id}/merge-history` — this is the
main debugging surface for pipeline behavior.

---

## 5. Tech stack and repository layout

**Monorepo:** Turborepo, npm workspaces, two packages.

```
defender-ai/
├── CLAUDE.md                       # conventions Claude Code follows — see §8
├── docs/
│   ├── architecture.md
│   ├── data-contracts.md
│   ├── agent-specs.md
│   └── project-briefing.md         # this file
├── .github/workflows/ci.yml        # pytest, black --check, ruff, next lint
├── packages/
│   ├── api/                        # FastAPI + LangGraph backend (Python 3.11+)
│   │   ├── src/
│   │   │   ├── main.py             # app, CORS, router mounting
│   │   │   ├── config.py           # env settings
│   │   │   ├── agents/
│   │   │   │   ├── base_agent.py   # BaseAgent ABC — every agent inherits
│   │   │   │   ├── graph.py        # top-level LangGraph pipeline
│   │   │   │   ├── tier0/ tier1/ tier2_research/ tier2_intake/
│   │   │   │   ├── tier2_attorney/ cross_cutting/
│   │   │   ├── models/             # Pydantic v2 — SOURCE OF TRUTH for contracts
│   │   │   │   ├── case_state.py charges.py intake.py research.py
│   │   │   │   ├── rights.py motions.py ethics.py disclosure.py
│   │   │   ├── routes/             # cases, upload, intake (WS), review, agents
│   │   │   ├── services/           # llm_service, document_parser, storage_service
│   │   │   └── corpus/             # closed-corpus loader (data dir currently empty)
│   │   └── tests/                  # pytest + fixtures (sample charging docs)
│   └── web/                        # Next.js 14 App Router, TypeScript, Tailwind, shadcn/ui
│       ├── prisma/schema.prisma    # PostgreSQL schema
│       └── src/
│           ├── app/                # routes — see §5.2
│           ├── components/         # by feature domain
│           ├── lib/api-client.ts   # ALL backend calls go through here
│           ├── types/              # TS mirrors of the Pydantic models
│           ├── hooks/ providers/ middleware.ts
```

**LLM:** Claude via the Anthropic API. Every prompt goes through
`services/llm_service.py::call_llm()`, which handles the call and strips markdown
fences from the JSON response. Model is set by the `CLAUDE_MODEL` env var.

**One non-Anthropic dependency:** `packages/web/src/app/api/tts/route.ts` calls
OpenAI's TTS endpoint for the intake voice mode.

### 5.1 Key commands

```bash
npm run dev                                          # both packages
cd packages/web && npm run dev                       # frontend only
cd packages/api && uvicorn src.main:app --reload     # backend only
cd packages/api && pytest                            # Python tests
cd packages/web && npx prisma migrate dev            # migrations
npm run format                                       # prettier + black
```

### 5.2 Frontend routes that exist

| Route | Audience | What it does |
|---|---|---|
| `/login`, `/register` | attorney | NextAuth credentials (dev stub — accepts any email) |
| `/upload` | attorney | upload a charging document, kicks off the pipeline |
| `/cases` | attorney | case list |
| `/cases/[caseId]` | attorney | case detail + memo review |
| `/cases/[caseId]/timeline` | attorney | pipeline/stage timeline |
| `/cases/[caseId]/motions` | attorney | draft motions (renders `draft_motions`) |
| `/cases/[caseId]/plea-trial` | attorney | plea/trial assessment, `DECISION SUPPORT ONLY` banner |
| `/cases/[caseId]/sentencing` | attorney | sentencing analysis |
| `/cases/[caseId]/review` | attorney | tiered review + annotation + comprehension check |
| `/intake`, `/intake/[sessionId]` | client | WebSocket chat interview, optional voice mode |
| `/status` | client | client-facing status view |

`middleware.ts` protects `/cases/*` and `/upload/*`; client and auth routes are public.

### 5.3 Backend endpoints that exist

```
GET  /health
GET  /api/v1/agents                              # agent registry
GET  /api/v1/agents/{agent_id}
GET  /api/v1/cases                               # list
GET  /api/v1/cases/{case_id}                     # full CaseState
GET  /api/v1/cases/{case_id}/status              # stage, blocked?, flags, error
GET  /api/v1/cases/{case_id}/merge-history       # Orchestrator merge decisions
GET  /api/v1/cases/{case_id}/summary             # human-readable HTML summary
POST /api/v1/upload                              # PDF/PNG/JPG/TXT → creates case, runs pipeline in background
GET  /api/v1/intake/{case_id}/validate
POST /api/v1/intake/{case_id}/finalize           # unstick an interview at INTAKE_IN_PROGRESS
WS   /api/v1/ws/intake/{session_id}              # live intake interview
GET  /api/v1/cases/{case_id}/review
POST /api/v1/cases/{case_id}/review/{section_id}/annotate
POST /api/v1/cases/{case_id}/review/{section_id}/approve
POST /api/v1/cases/{case_id}/review/{section_id}/comprehension
```

Plus a sentencing-agent router (`/analyze`, `/exposure`, `/diversion`,
`/cases/{case_id}/comparables`) that exists but **is not currently mounted in
`main.py`** — see §7.

---

## 6. Data contracts

Pydantic models in `packages/api/src/models/` are the **source of truth**. The
TypeScript types in `packages/web/src/types/` mirror them and must be kept in sync
manually.

### 6.1 The output envelope

Every agent returns via `BaseAgent.wrap_output()`:

```python
{
    "data": {...},                    # agent-specific payload
    "confidence": "HIGH"|"MEDIUM"|"LOW",
    "source": "<agent_id>",
    "timestamp": "<ISO-8601>",
}
```

`BaseAgent` also provides `score_confidence(float) -> ConfidenceLevel`
(≥0.85 HIGH, ≥0.6 MEDIUM, else LOW), `log_action()`, and `get_audit_log()`.
Every agent subclasses `BaseAgent`, sets `agent_id` and `agent_name`, and
implements `async def run(self, input_data: dict) -> dict`.

### 6.2 CaseState

```python
class CaseState(BaseModel):
    # Identity
    id: str
    created_at / updated_at: datetime
    jurisdiction: str = "IL"          # NOTE: stale default — MVP is Georgia. See §7.
    case_number: str | None

    # Pipeline
    stage: PipelineStage = CREATED
    stage_history: list[StageHistoryEntry]

    # Attorney
    attorney_id: str
    attorney_config: dict

    # Agent output slots — all nullable, filled as the pipeline advances
    charge_processing, pre_interview_research, intake_summary, case_prep_memo,
    statute_analysis, case_law_research, citation_verification, fact_gathering,
    rights_violation_analysis, collateral_consequences, personal_circumstances,
    draft_motions, brady_analysis, disclosure_tracking, plea_trial_assessment,
    sentencing_analysis: dict | None

    # Cross-cutting
    ethical_flags: list[dict]
    audit_log: list[dict]
    review_status: dict[str, str]
    documents: list[DocumentRecord]

    def advance_stage(self, new_stage) -> None      # with history tracking
```

**Adding a new agent means adding a slot here** and an `_AGENT_CONFIG` entry in the
Orchestrator. Any spec for a new agent must say which slot it writes.

### 6.3 Supporting enums

- `ConfidenceLevel` — HIGH / MEDIUM / LOW / UNRATED
- `VerificationStatus` — VERIFIED / UNVERIFIED / CONFIRMED / UNCONFIRMED / OVERRULED / SUPERSEDED
- `ReviewStatus` — PENDING_REVIEW / IN_REVIEW / ATTORNEY_APPROVED
- `EthicalCategory` — PRIVILEGE / UPL / BIAS / COMPETENCE / CANDOR / IAC / HALLUCINATION
- `FlagPriority` — CRITICAL / HIGH / MEDIUM / LOW
- `ConfidenceRated[T]` — generic wrapper: `{data, confidence, source, timestamp}`

### 6.4 Database (Prisma / PostgreSQL)

`packages/web/prisma/schema.prisma`. Models: `User`, `Case`, `Charge`, `Document`,
`IntakeSession`, `ReviewAction`, `AuditLog`. `CaseState` is stored as a JSONB
column on `Case` for flexibility; charges and users are normalized for querying.
`ReviewAction` encodes the **tiered review model**: `HIGH_STAKES` requires a
written annotation, `MEDIUM_STAKES` a substantive edit, `LOWER_STAKES` an active
confirmation.

**Important:** the schema exists but the backend does **not** currently read or
write it — see §7.

---

## 7. Implementation status — what is real and what is a stub

**This is the most important section for spec-writing.** "Agent exists" and "agent
works" are very different states in this repo.

### Deeply implemented (real logic, real tests)

| Component | Size | Notes |
|---|---|---|
| **Intake Conductor** | ~1,360 lines | Five-phase interview (personal info, incident narrative, arrest/custody, prior history, priorities/concerns). LLM-driven question generation and response processing, inconsistency analysis between the client's account and the charges, subagent trigger dispatch, confidence scoring, ethical flag detection. Georgia-specific system prompt. |
| **Ethics & Compliance Monitor** | ~1,130 lines, 39 tests | All five pillars implemented. Cannot be overridden by any other agent. |
| **Charge Processing Agent** | ~780 lines | Parses charging documents into charges, elements, penalties, enhancements. |
| **Disclosure Tracking Agent** | ~570 lines, 23 tests | Brady/Giglio/Jencks ledger, dynamic checklist, gap and red-flag detection, deadline tracking, timeline, pre-trial compliance audit. **Note: this agent is missing from the CLAUDE.md agent map and from the `/api/v1/agents` registry.** |
| **Rights Violation Scanner** | ~520 lines, 20 tests | Constitutional violation detection from intake facts. |
| **Case Orchestrator** | ~490 lines | Sequencing, confidence gate, ethics gate, merge decisions, failure handling, status snapshots. |
| **Sentencing & Mitigation Agent** | own sub-package, ~2,000 lines, 71 tests | The most complete vertical slice. Its own LangGraph sub-pipeline of 10 nodes (scope gate → authority loader → exposure calculator → diversion checker → mitigation fact sheet → leniency arguments → mitigation narrative → comparable lookup → memo framework → output assembler), with the scope gate conditionally short-circuiting out-of-scope cases, typed input/output models, Georgia seed data (`statutes.json`, `marijuana_comparables.json`, `program_directory.json`), externalized prompt files, and a `BaseAgent` adapter so the Orchestrator can call it like any other agent. Scoped to simple marijuana possession ≤1 oz. |

### Thin stubs — a docstring, one LLM prompt, and `wrap_output()` (~50–65 lines each)

`statute_agent.py`, `case_law_agent.py`, `citation_verifier.py`,
`recency_monitor.py`, `fact_gatherer.py`, `collateral_agent.py`,
`personal_circumstances.py`, `motion_drafter.py`, `brady_agent.py`,
`plea_trial_analyst.py`, and the Tier 1 `case_prep.py`.

These have the right shape and a reasonable prompt, but no corpus lookup, no
verification logic, no structured post-processing, and no tests. Several carry
explicit `TODO: query closed corpus first` comments. `pre_interview.py` (~230
lines) sits in between — more than a stub, less than finished.

### Test coverage

~114 tests in `packages/api/tests/` (ethics monitor 39, pipeline integration 26,
disclosure 23, rights scanner 20, plus orchestrator/intake/charge processing) and
71 more inside the sentencing agent's own test directory.

---

## 8. Known gaps and inconsistencies

Real, verified issues in the current tree. Any spec that touches these areas
should say explicitly whether it fixes them or works around them.

1. **No persistence.** Cases live in an in-memory dict (`routes/_store.py`:
   `case_store: dict[str, OrchestratorAgent]`). The Prisma schema is fully designed
   but nothing in the backend reads or writes PostgreSQL. **Every case is lost on
   server restart.** Wiring persistence is probably the single highest-value
   infrastructure task remaining.
2. **Jurisdiction default is stale.** `CaseState.jurisdiction`,
   `config.DEFAULT_JURISDICTION`, the Prisma `Case.jurisdiction` default, and
   `motion_drafter.py` all default to `"IL"`, while the MVP is Georgia and the
   upload route and graph nodes default to `"GA"`.
3. **The top-level LangGraph pipeline is truncated.** `agents/graph.py` runs
   Charge Processing → Pre-Interview Research for real; the `intake` and
   `case_prep` nodes are placeholders that only set a stage string. Actual intake
   runs through the WebSocket route instead, outside the graph.
4. **No Tier 2 agent is wired into the Orchestrator.** `_AGENT_CONFIG` contains
   only `charge_processing`, `pre_interview_research`, `intake_conductor`,
   `case_prep` / `case_prep_conductor`, and `disclosure_tracking`. Every other
   Tier 2 agent has no state slot mapping, no sequencing rule, and no path into
   `CaseState`.
5. **Orchestrator state is rebuilt per graph node.** Each node constructs a fresh
   `OrchestratorAgent` and manually re-hydrates fields from the state dict, with a
   `_orchestrator_ref` holding a raw `id()`. This is brittle and will not survive
   the move to database-backed state.
6. **The sentencing agent's API router is not mounted.** `main.py` includes cases,
   upload, intake, review, and agents — not the sentencing routes.
7. **CI does not run the sentencing agent's tests.** `pyproject.toml` sets
   `testpaths` to include them, but the workflow runs `pytest tests/ -v`, which
   overrides `testpaths`. 71 tests are silently skipped in CI.
8. **The closed corpus is empty.** `src/corpus/data/` contains only a `.gitkeep`,
   so every research agent falls through to LLM generation — which means every
   citation it produces is `UNVERIFIED` by definition.
9. **`call_llm` has no error handling.** No retry, no timeout, no token tracking
   (despite the docstring claiming centralized tracking), and a bare `json.loads`
   that raises on any malformed model response.
10. **Auth is a development stub.** `lib/auth.ts` accepts any syntactically valid
    email and returns a hardcoded attorney. Real authentication is required before
    this system touches real privileged client data.
11. **Frontend tests are not runnable.** `packages/web/package.json` declares
    `"test": "jest"` but has no jest dependency or config.
12. **The CLAUDE.md agent map omits Disclosure Tracking**, so the documented map
    lists 18 agents where the code has 19.

---

## 9. Conventions Claude Code enforces

From `CLAUDE.md` — specs should not contradict these.

**Python (`packages/api/`)**
- Python 3.11+, Pydantic v2 for all data models
- Every agent inherits `BaseAgent`; one agent per file, named after the agent
- Every agent output includes a `confidence: ConfidenceLevel`
- `ConfidenceRated[T]` wraps everything passed into `CaseState`
- Type hints everywhere; no `Any` unless unavoidable
- black + ruff, line length 100

**TypeScript (`packages/web/`)**
- Strict TypeScript, no `any`
- Shared types in `src/types/`
- Components in `src/components/`, organized by feature domain
- **All API calls go through `src/lib/api-client.ts`** — no raw `fetch` in components
- Server components by default; client components only when interactive

**Testing**
- pytest, fixtures in `tests/fixtures/` (includes sample Georgia charging documents:
  `sample_accusation.txt`, `sample_arrest_report.txt`)
- Every agent needs at least one golden-output test
- Integration tests: upload doc → assert on `CaseState` after the pipeline runs

---

## 10. What I'll ask you for

Typical requests, so you know the shape of the output I need:

- *"I want to build out the Statute Agent for real — closed corpus first, LLM
  fallback. Write me the spec."*
- *"Wire persistence so cases survive a restart. Spec it."*
- *"The Case Prep Conductor needs to actually orchestrate the four attorney-prep
  agents. Spec that, including the Orchestrator changes."*
- *"Design the closed corpus format for Georgia statutes and the loader interface."*
- *"I want a demo path that works end to end for one marijuana possession case.
  What's the minimum spec to get there?"*

When you write the spec, hand it to me as a single copy-pasteable block, written
as an instruction to Claude Code — goal, files, contracts, integration points,
guardrails, tests, out-of-scope. If the work is large, break it into numbered
phases I can feed one at a time, since Claude Code does better with a bounded
task than an open-ended one.
