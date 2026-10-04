# CLAUDE.md — Defender AI

Read this file completely, then `SPEC.md`. Do not write code until you have read
both and reported your plan.

---

## 1. What this project is

**Defender AI is a research instrument, not a product.**

It is a multi-agent system that attempts the full public defender workflow —
charge analysis, discovery review, legal research, client intake, motion
drafting, plea assessment, sentencing exposure — end to end. It is built by four
law students as an independent study.

Its purpose is **to find out how far current models and tooling can be pushed on
this task, and to document precisely where and why they fail.** The deliverable
is the system *plus* a rigorous account of its limits. A measured failure is a
result. An unmeasured success is nothing.

This framing is load-bearing and it changes the engineering. Read §3 carefully,
because the rules here are not the rules you would write for a product.

### 1.1 It will never be used on a real matter

No real client. No real discovery. No deployment. No practitioner uses this to
prepare an actual case. That constraint is what makes the ambition legitimate: a
system that drafts motions and assesses pleas would be unauthorized practice of
law if it touched a real defendant, and it does not.

Enforce it structurally, not by policy — see §2.

### 1.2 Who the research audience is

Faculty readers, a criminal defense clinic, and the practitioners who were
interviewed during design. They will ask: *what did it get wrong, how often, and
how would you know?* Build so that question has an answer.

---

## 2. Invariant: synthetic data only

> **No real case material enters this system. Not discovery, not charging
> documents, not client statements, not police reports, not transcripts, not a
> redacted version of any of them.**

Every fixture is fabricated. Fake names, fake Bates numbers, fake officers, fake
addresses, fake lab reports.

**Enforce it structurally:**

1. Every ingested artifact carries a `provenance_class` field, which is an enum
   with exactly one permitted value in this project: `SYNTHETIC`. The ingest path
   rejects anything else.
2. A test asserts that no fixture file in the repository contains a real Georgia
   case number pattern matched against a known-format regex, and that all
   fixtures live under `tests/fixtures/synthetic/`.
3. The CLI and every API response carry a `NOT FOR USE ON REAL MATTERS` banner.
   It is not a config flag. Do not add one.
4. If a team member wants to test against real material, the answer is no. If
   they want to test against *their own* public records request output, still no
   — it contains third parties.

This is the one invariant with no research exception. Everything else in this
document bends to measurement; this does not.

---

## 3. The guardrails are instruments, not filters

This is the most important section and the one most likely to be misread.

A product version of this system would block its own unsafe outputs. **This
version records them instead.** A blocked output is lost data. We are trying to
measure how often and how badly the system crosses lines, which requires letting
it cross them and capturing what happened.

### 3.1 What this means concretely

The Ethics & Compliance Monitor is renamed and re-roled: it is an **Ethics
Sensor**. It does not gate the pipeline. It classifies every output and writes a
record. The Orchestrator merges the output regardless and attaches the
classification.

| Old behavior | New behavior |
|---|---|
| `CRITICAL` flag blocks the merge | Output merges, tagged `judgment_class` + severity, recorded |
| UPL phrase list suppresses output | Output retained; violation classified, scored, counted |
| LOW confidence withheld | Retained and labeled; withholding is a measurement we can compute later |

The one exception: **anything that would leave the machine toward a real person
is still a hard block.** There is no such path in v1 and you should not build
one.

### 3.2 Every output declares what kind of act it is

Add a required `judgment_class` to the output envelope:

```python
class JudgmentClass(str, Enum):
    RECITAL = "RECITAL"              # restates the record; cites a source
    INFERENCE = "INFERENCE"          # draws a factual conclusion from the record
    LEGAL_ANALYSIS = "LEGAL_ANALYSIS"  # applies law to fact
    LEGAL_CONCLUSION = "LEGAL_CONCLUSION"  # asserts a legal result
    ADVICE = "ADVICE"                # recommends a course of action
    FILING = "FILING"                # text intended for a court
```

The system is permitted — expected — to produce all six. The point is that each
one is labeled, so we can report: *of 2,400 generated assertions, 61% were
recitals with verified citations, 22% were inferences, and 9% were advice the
system was never asked to give.* That last number is a finding. You cannot get
it from a system that suppressed them.

### 3.3 The Sensor's job

For every agent output, classify and record:

1. **`judgment_class`** per assertion (above).
2. **Citation integrity** — of the assertions carrying citations, how many
   verify against the corpus; how many are unresolvable; how many are
   *plausible-but-nonexistent*, which is the most dangerous category and must be
   counted separately.
3. **Advice detection** — not a keyword list. A separate adversarial model call
   with a written rubric, scoring whether the output recommends an action to a
   reader. Keyword matching is kept only as a cheap pre-filter whose
   *disagreement* with the judge is itself logged, because the gap between the
   two is a result worth reporting.
4. **Bias probes** — run the same matter through the pipeline with demographic
   attributes varied and nothing else changed; record whether outputs differ.
   This is a measurement procedure, not a filter.
5. **Abstention rate** — how often the system correctly says the record does not
   address something.

Sensor output goes to a dedicated `measurements` store, never only into prose.

---

## 4. Anti-hallucination rules

These do **not** relax under the research framing. They are what makes
measurement possible: an uncited assertion cannot be scored, so it is worthless
as data and dangerous as output.

1. **Every generated assertion carries a locator and verbatim source text.** See
   `SPEC.md` §5. The `source_text` field must be byte-identical to the stored
   source at that locator.
2. **A claim whose source text does not match is dropped and counted.** Do not
   repair it. Do not surface it with a warning. Drop it, increment the
   verification-failure counter, and log the claim text for analysis.
3. **Never summarize from model memory.** Always pass the actual source text.
4. **Retrieve first, then generate.** Never generate and then retrieve to
   justify.
5. **Abstention is a correct answer** and must be a well-presented output, not an
   error state.
6. **Never blur model output and human-confirmed fact.** `confirmed_by_user`
   exists for this and the UI must show the difference at a glance.
7. **Rank, never filter.** Nothing is hidden from the reader because a model
   scored it unimportant. Deprioritize and keep reachable.

### 4.1 Citations must be falsifiable

A citation to Georgia authority is `VERIFIED` only on an exact match against the
local corpus, with the matched text stored. Everything else is `UNVERIFIED`.

Note the trap, which is real and worth a test: **O.C.G.A. § 24-7-707** formerly
governed expert opinion testimony in Georgia criminal proceedings under the
permissive *Harper* standard. HB 478 (passed March 2022) extended § 24-7-702's
*Daubert* framework to criminal cases. Georgia criminal opinions predating that
change state a standard that no longer applies. A corpus that returns them
without a `SUPERSEDED` marker will produce confidently wrong analysis, and the
model will not catch it, because its training data contains both eras.

Confirm the effective date and the current disposition of § 24-7-707 against
primary sources before relying on either section. Treat this as the worked
example for the whole recency problem.

---

## 5. Evidence integrity

Even with synthetic material, build these correctly — they are part of what is
being studied, and the measurements depend on them.

- **Never modify a source artifact.** Copy on ingest, mark read-only, work on
  copies.
- **Hash on intake, verify on access.** SHA-256 per file and per page image.
- **Append-only audit log.** Record model name, model version, and prompt
  version on every analysis run. Without this, no result is reproducible and the
  study is worthless.
- **Preserve provenance through every transform.** If a processing step loses the
  chunk → page → Bates chain, citations break. Do not add such a step.
- **Deletion is soft, reversible, logged.**

---

## 6. Reproducibility is a requirement, not a nicety

Every pipeline run is a recorded experiment. Persist, for each run:

- `run_id`, timestamp, git commit SHA
- model name and version, temperature, and any seed
- prompt template version per agent (prompts are versioned files, not inline
  strings — see §9)
- input fixture identifier
- complete output, including dropped assertions and sensor measurements

A result we cannot regenerate is not a result. If a prompt changes and the
numbers move, we must be able to say which change moved them.

---

## 7. Likely-contraband handling

Keep this even though fixtures are synthetic, because the handling path is part
of what a real system would need and it costs little to build.

- Detect image/video artifacts by type and **quarantine rather than process**.
- Do not render thumbnails, do not OCR, do not pass to any model.
- Report as "N files require manual handling and were not processed."
- Always on. No default-off setting.

---

## 8. How to work

**One phase at a time. Stop at the end of each and wait for approval.**

`SPEC.md` defines Phases 0–6. Do not run ahead. Do not begin the next phase
because the current one finished early.

When you finish a phase, report:

1. What you built, by module.
2. Test coverage, with the specific numbers.
3. Anything in `SPEC.md` that was wrong, impossible, or worse than an
   alternative.
4. What you did not do, and why.
5. Any measurement the phase makes possible that was not previously possible.

### 8.1 Trust the generated inventory, not prose

An audit dated October 1, 2026 described this repository as far smaller than it is:
it measured a local clone last updated March 21, 2026. The verified state is in
`docs/RECONCILIATION_2026-10-04.md`.

**Do not trust narrative documentation about this repository, including this
section.** `docs/INVENTORY.md` is generated from the tree by `scripts/inventory.py`,
and CI fails when it is stale. It is the only inventory to trust: which agents
exist, their `STATUS`, which are registered with the Orchestrator, which the running
app can actually reach, and which tests cover them.

**Invariants not yet enforced in code** (deferred by team decision, October 4, 2026,
until a phase needs them):

- §2: structural synthetic-only enforcement (`provenance_class`, the fixture test,
  the banner). Uploads are still accepted as-is.
- §3.1: the Orchestrator still blocks on `CRITICAL` ethics flags
  (`BLOCKED_ETHICS_P1`) and skips the ethics check for LOW-confidence outputs.
- §7: image and video uploads are still OCR'd rather than quarantined.

---

## 9. Engineering conventions

Carried forward from the existing repo where they work, with additions.

**Python (`packages/api/`)**
- Python 3.11+, Pydantic v2 for all data models.
- Every agent inherits `BaseAgent`; one agent per file, named after the agent.
- Every agent output carries `confidence`, `judgment_class`, and a locator per
  assertion.
- Type hints everywhere. No bare `Any` in new code.
- black + ruff, line length 100. `mypy` on `core`-equivalent modules.
- **Prompts live in versioned files**, not inline strings — you will need to diff
  them when output quality changes, and §6 requires recording which version ran.
- Prefer deterministic code over model calls wherever `SPEC.md` §6 says you can.
  It is faster, free, reliable, and it gives the study a control condition.

**TypeScript (`packages/web/`)**
- Strict TypeScript, no `any`. Types in `src/types/`.
- All API calls through `src/lib/api-client.ts`. No raw `fetch` in components.
- Server components by default.

**Testing**
- pytest. Synthetic fixtures only, under `tests/fixtures/synthetic/`.
- Every agent needs at least one golden-output test.
- Deterministic analyses get exact-output tests against planted ground truth.
- Model-dependent paths get cassette-replay tests (`SPEC.md` Phase 1).
- Every agent module declares `STATUS = "REAL" | "PARTIAL" | "STUB"`. A stub may
  stay registered in `_AGENT_CONFIG` because `BaseAgent.wrap_output` labels its
  output `agent_status: "STUB"`. `tests/test_agent_registry.py` lists registered
  stubs and unwired agents explicitly, so the directory can never again be mistaken
  for a system.

**Commands**

```bash
cd packages/api && pytest                     # all testpaths, incl. sentencing_agent/tests
cd packages/api && black src/ tests/ && ruff check src/
python scripts/inventory.py                   # regenerate docs/INVENTORY.md (CI checks it)
cd packages/api && uvicorn src.main:app --reload
cd packages/web && npm run dev
```

---

## 10. If you disagree

This document was written by someone who has read the practitioner interviews
and audited the codebase, but who is not a criminal defense lawyer and is not
the one who will be graded on this.

If something here is wrong, impractical, or would produce a worse study — **say
so before building it.** A well-argued objection is more useful than compliant
implementation of a bad design. In particular, push back if a rule in §3 or §4
would make a measurement impossible; that is the failure mode this framing is
most prone to.
