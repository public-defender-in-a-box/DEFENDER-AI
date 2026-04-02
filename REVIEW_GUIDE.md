# Sentencing & Mitigation Agent — Review Guide

**Reviewer:** You are reviewing one agent in a 19-agent system built by a team
of 4 law students. This guide gives you enough context to evaluate the agent
without having built the others.

---

## 1. What This Agent Does

The Sentencing & Mitigation Agent is a **Tier 2 Attorney Prep** agent that:

- Calculates sentencing exposure for Georgia simple marijuana possession (≤1 oz)
- Identifies diversion/deferral programs (conditional discharge, pretrial diversion, drug court, veterans court)
- Builds a structured mitigation fact sheet from client data
- Drafts a mitigation narrative using an LLM grounded in verified facts only
- Finds comparable sentencing outcomes from a local seed corpus
- Assembles a sentencing memo framework with attorney action badges

**It is never client-facing.** Every output carries:
- `"DRAFT — ATTORNEY REVIEW REQUIRED"` disclaimer
- `"ATTORNEY-CLIENT PRIVILEGED MATERIAL"` privilege warning

---

## 2. Where It Sits in the System

```
Tier 0: Case Orchestrator
  └── Tier 1: Charge Processing → Pre-Interview → Intake → Case Prep Conductor
        └── Tier 2 Attorney Prep:
              ├── Motion Drafter Agent
              ├── Plea/Trial Assessment Agent
              ├── Brady Agent
              └── ** Sentencing & Mitigation Agent ** (this one)
        Cross-cutting: Ethics & Compliance Monitor (runs on every output)
```

The Orchestrator owns a single `CaseState` object. Every agent:
- Inherits from `BaseAgent` (see `base_agent.py` included in this zip)
- Returns output via `wrap_output()` → `{"data": ..., "confidence": "HIGH"|"MEDIUM"|"LOW", "source": "<agent_id>", "timestamp": "<ISO>"}`
- Gets its output checked by the Ethics Monitor before merge into CaseState

---

## 3. Key Integration Points to Verify

### 3.1 BaseAgent Adapter (`agent.py`)

The LangGraph pipeline has its own typed input/output models. The `SentencingAgent`
class in `agent.py` wraps it so the Orchestrator can call `.run(input_data)` and
get back the standard `wrap_output` envelope.

**Review question:** Does `_map_case_state_to_input()` correctly bridge between
what the Orchestrator passes and what the pipeline expects? The fallback mapping
(lines 73–97) makes assumptions about CaseState field names — compare these
against the actual CaseState model (`case_state.py` included).

### 3.2 Upstream Contracts

This agent expects data from:

| Source Agent | Expected Fields | File to Check |
|---|---|---|
| Charge Processing | statute, conduct_type, quantity, enhancements | `models/inputs.py` → `OffenseDetails` |
| Personal Circumstances | employment, housing, treatment, dependents | `models/inputs.py` → `PersonalCircumstances` |
| Criminal History | prior convictions, drug offenses, CD usage | `models/inputs.py` → `PriorRecord` |

**Review question:** Do the field names and types in `SentencingAgentInput` match
what the upstream agents actually produce? Cross-reference with the Charge
Processing output format and Intake Summary format.

### 3.3 Downstream Consumers

| Consumer | What It Reads |
|---|---|
| Plea/Trial Assessment Agent | `guideline_range` (exposure summary) |
| Motion Drafter | `sentencing_memo` sections |
| Ethics Monitor | `confidence_score`, `ethics_flags`, `warnings` |
| Attorney Dashboard | Everything — editable narrative, comparables, memo |

**Review question:** Can the Plea/Trial Assessment Agent actually consume
`GuidelineRange`? The field names (`statutory_minimum`, `statutory_maximum`,
`fine_minimum`, `fine_maximum`, `probation_possible`) should match what
that agent expects.

### 3.4 Ethics Monitor Compatibility

The Ethics Monitor runs 5 checks on every agent output:
1. **Privilege protection** — checks for PII leaks
2. **UPL boundary** — blocks advisory language in client-facing outputs
3. **Bias audit** — scans for demographic terms
4. **Competence floor** — enforces confidence thresholds
5. **Hallucination detection** — catches fabricated statutes

**Review question:** Does the sentencing output include the fields the Ethics
Monitor expects? Check `ethics_flags`, `confidence_score`, and ensure the
`privilege_warning` and `disclaimer` fields satisfy the privilege and UPL checks.

---

## 4. MVP Scope — What to Watch For

### 4.1 The Scope Gate Is Intentionally Narrow

The agent **only** handles:
- Simple possession of marijuana
- Quantity ≤ 1 ounce
- Georgia state court
- No enhancements (school zone, gang, etc.)

Everything else returns `"out_of_scope"` with a reason. This is correct and
intentional — the spec requires it. Do NOT suggest expanding scope without
understanding the legal implications.

### 4.2 Known Issue: Scope Mismatch With Other Agents

The Motion Drafter and Plea/Trial Analyst were built around **cocaine
possession** (O.C.G.A. § 16-13-30(a), Schedule II) test fixtures. The
sentencing agent will return `"out_of_scope"` for those cases.

**This is a team coordination issue, not a bug.** The team needs to decide:
- (A) Use a marijuana case for end-to-end demo (sentencing agent works, others need new fixtures), or
- (B) Expand sentencing scope to include cocaine (more legal work, more risk)

Flag this in your review if not already resolved.

### 4.3 Georgia-Specific Legal Accuracy

If you have Georgia criminal law knowledge, please verify:

| Claim | Statute | Check |
|---|---|---|
| Marijuana ≤1 oz is misdemeanor | O.C.G.A. § 16-13-2(b) | Max 12 months / $1,000 |
| Conditional discharge is one-time | O.C.G.A. § 16-13-2(a) | Up to 3 years probation |
| Weekend service if ≤6 months | O.C.G.A. § 17-10-3 | Threshold correct? |
| Veterans court statute | O.C.G.A. § 15-1-17 | NOT § 15-1-16 |
| Record restriction (not expungement) | O.C.G.A. § 35-3-37 | Not automatic |
| Accountability court is umbrella | O.C.G.A. § 15-1-18 | Not a standalone program |
| Probation fee $25/month | O.C.G.A. § 42-8-34(d)(2) | For § 16-13-2(b) cases |

The seed data is in `data/ga/statutes.json`. Prior draft errors (wrong statute
numbers, scope mistakes) were caught and corrected — see the regression tests
in `tests/test_integration.py::TestRegressionPriorDraftMistakes`.

---

## 5. Architecture Walkthrough

### 5.1 LangGraph Subgraph (10 nodes)

```
scope_gate ──[out_of_scope]──→ output_assembler → END
    │
    └──[in_scope]──→ authority_loader
                        → exposure_calculator
                        → diversion_checker
                        → mitigation_fact_sheet
                        → leniency_argument_builder  (LLM)
                        → mitigation_narrative_builder  (LLM)
                        → comparable_sentence_lookup
                        → memo_framework_builder
                        → output_assembler → END
```

**7 nodes are deterministic** (no LLM). Only 2 nodes call the LLM (leniency
arguments, mitigation narrative). Both have deterministic fallbacks if the
LLM call fails.

### 5.2 File Layout

```
sentencing_agent/
├── agent.py              ← BaseAgent adapter (Orchestrator entry point)
├── graph.py              ← LangGraph subgraph definition
├── config.py             ← Feature flags, paths, confidence weights
├── models/
│   ├── inputs.py         ← SentencingAgentInput and all input types
│   ├── outputs.py        ← SentencingAgentOutput and all output types
│   └── state.py          ← LangGraph TypedDict state
├── nodes/
│   ├── scope_gate.py             ← Node 0: MVP boundary enforcement
│   ├── authority_loader.py       ← Node 1: Load verified statute data
│   ├── exposure_calculator.py    ← Node 2: Deterministic sentencing range
│   ├── diversion_checker.py      ← Node 3: Program availability + eligibility
│   ├── mitigation_fact_sheet.py  ← Node 4: Structured facts with provenance
│   ├── leniency_argument_builder.py  ← Node 5: LLM-assisted arguments
│   ├── mitigation_narrative_builder.py ← Node 6: LLM-drafted narrative
│   ├── comparable_sentence_lookup.py   ← Node 7: Local corpus matching
│   ├── memo_framework_builder.py       ← Node 8: Template-based memo
│   └── output_assembler.py            ← Node 9: Merge + confidence scoring
├── prompts/              ← LLM prompt templates (system prompts)
├── data/ga/              ← Seed data (statutes, programs, comparables)
├── api/routes.py         ← FastAPI endpoints
└── tests/                ← 71 tests
```

---

## 6. What to Look For in Your Review

### 6.1 Correctness

- [ ] Does the scope gate correctly reject out-of-scope cases?
- [ ] Is the exposure calculation (0–365 days, $0–$1,000) legally accurate?
- [ ] Does conditional discharge eligibility logic match O.C.G.A. § 16-13-2(a)?
- [ ] Are diversion availability and eligibility properly separated (not conflated)?
- [ ] Does the confidence scoring make sense? (weights in `config.py`)

### 6.2 Safety / Ethics

- [ ] Can the LLM invent facts not in the mitigation fact sheet?
- [ ] Can the LLM invent statute citations?
- [ ] Are unsupported claims flagged in the narrative?
- [ ] Is the `privilege_warning` present on every output?
- [ ] Is the `disclaimer` present on every output?
- [ ] Are demographic fields excluded from LLM prompts? (bias audit tests)
- [ ] Does low confidence properly trigger ethics flags?

### 6.3 Integration

- [ ] Does `agent.py` produce the `wrap_output` envelope the Orchestrator expects?
- [ ] Can the Plea/Trial Assessment Agent consume `guideline_range`?
- [ ] Will the Ethics Monitor receive the fields it needs (`confidence_score`, `ethics_flags`)?
- [ ] Are the FastAPI routes consistent with the project's `/api/v1/` prefix pattern?

### 6.4 Code Quality

- [ ] Are there any unused imports or dead code?
- [ ] Do all nodes handle the "out of scope" case (skip gracefully)?
- [ ] Do LLM nodes fall back cleanly on failure?
- [ ] Is the seed data well-structured and self-consistent?
- [ ] Are the tests comprehensive? (scope gate edge cases, diversion logic, bias, regression)

### 6.5 Things That Are Intentionally NOT Here (MVP Decisions)

- No Pinecone / vector DB — seed corpus is local JSON
- No runtime web scraping — all data is pre-loaded
- No open case law research — closed corpus only
- No judge-specific sentencing predictions
- No .docx export — memo is structured data for the frontend
- Temperature config removed — model choice centralized in `llm_service.py`

---

## 7. Test Coverage Summary

| Test File | Tests | What It Covers |
|---|---|---|
| `test_scope_gate.py` | 14 | Accepts marijuana ≤1oz; rejects cocaine, PWID, sale, distribution, manufacture, >1oz, enhancements, missing quantity |
| `test_exposure_calculator.py` | 8 | Range 0–365 days, $0–$1000, weekend service, time served, special fees, key statutes |
| `test_diversion_checker.py` | 9 | Conditional discharge eligibility (6 scenarios), availability vs. eligibility separation, veterans court |
| `test_integration.py` | 10 | Full pipeline (mocked LLM), out-of-scope handling, partial output, confidence caps, 4 regression tests for prior legal errors |
| `test_llm_outputs.py` | 8 | JSON parsing, fallback generation, no invented citations |
| `test_bias_audit.py` | 7 | Demographic invariance, no race in corpus, prompt payload safety |

To run: `cd packages/api && pytest src/agents/tier2_attorney/sentencing_agent/tests/ -v`

---

## 8. Context Files Included in This Zip

Beyond the agent code itself, this zip includes reference files from the
broader project to help you understand the integration context:

- `_context/base_agent.py` — The BaseAgent class all agents inherit from
- `_context/case_state.py` — The CaseState model (canonical state object)
- `_context/ethics.py` — Ethics Monitor models and flag definitions
- `_context/llm_service.py` — The centralized LLM call wrapper
- `_context/graph.py` — The main pipeline graph (Tier 0 + Tier 1)
- `_context/CLAUDE.md` — Project-wide conventions and rules

These are READ-ONLY reference copies. Do not edit them — they belong to other
parts of the system.

---

## 9. How to Provide Feedback

For each suggestion, please note:
1. **Which file and line** the change applies to
2. **Whether it affects integration** with other agents
3. **Whether it changes legal semantics** (flag for attorney review if so)
4. **Priority:** Critical (blocks integration) / Important (should fix) / Nice-to-have

Thank you for reviewing.
