# CLAUDE.md — Defender AI

Read this file completely, then `SPEC.md`. Do not write code until you have read
both and reported your plan.

---

## 1. What this project is

**Defender AI is an attempt to build the most capable system we can for the work
a public defender does, and to find out how much of that work it can actually
do.**

Charge analysis, discovery review, legal research, client intake, motion
drafting, plea assessment, sentencing exposure — the whole workflow, end to end.
Built by four law students. The question driving it is how far current models and
tooling can be pushed on this task, and the answer is supposed to be a working
tool, not a description of one.

**The goal is the tool.** Measurement exists to tell us where the tool stands and
which changes improve it. It is the instrument panel, not the destination. When
the choice is between a capability that works and a metric that reports, build
the capability and instrument it afterward.

Two consequences govern the engineering:

- **Reach beats polish.** A capability no user can trigger is worth less than a
  rough one they can. As of October 2026, 18 of 24 agents cannot be reached from
  the running application — see §8.1. Closing that gap is worth more than any new
  agent.
- **Confident wrong answers are the one unacceptable failure.** Not because they
  spoil a measurement, but because a tool that invents a citation or silently
  returns an empty result is worse than no tool. §4 is non-negotiable for that
  reason alone.

### 1.1 It is not deployed, and will not be

No real client, no real discovery, no practitioner using it to prepare an actual
case. This is not a limit on ambition — build the most capable thing you can —
it is a fact about what software can lawfully do. No program holds bar
admission, and a system that drafts motions and assesses pleas would be
unauthorized practice of law the moment it touched a real defendant.

So build it as capable as possible, and enforce the synthetic boundary
structurally rather than by policy. See §2.

### 1.2 How we know whether it is working

Faculty, a criminal defense clinic, and the practitioners interviewed during
design will all ask the same question: *what can it actually do, and where does
it break?* That question needs an answer backed by something other than a demo
that went well once. Hence §3 and §6 — enough instrumentation to know whether
last week's change helped.

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

This is the one invariant with no exception. Every other rule in this document
can bend if a more capable tool requires it; this one cannot.

---

## 3. The guardrails are instruments, not filters

This is the most important section and the one most likely to be misread.

A deployable version of this system would block its own unsafe outputs. **This
version records them instead.** Two reasons, and the second is the practical
one: a blocked output tells you nothing about why it was blocked, and you cannot
improve a capability you cannot see fail. Suppression at this stage hides exactly
the behavior we need to fix.

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

These do **not** relax, for the reason in §1: a confident wrong answer is the one
unacceptable failure. An assertion without a source cannot be checked, so it is
dangerous as output and useless for telling whether the tool is improving.

1. **Every generated assertion carries a locator and verbatim source text.** The
   model supplies the quote; code finds it in the stored source and computes the
   locator, so `source_text` is byte-identical to the source by construction. The
   model never computes offsets. See `SPEC.md` §5.3.
2. **A claim whose quote cannot be found in the source is dropped and counted.** Do
   not repair it. Do not surface it with a warning. Drop it, increment the
   verification-failure counter for its failure type (`SPEC.md` §5.3), and log the
   claim text for analysis.
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
permissive *Harper* standard. **HB 478** (passed March 30, 2022; effective July 1,
2022) repealed § 24-7-707 and extended § 24-7-702's *Daubert* framework to
criminal cases, applying to any motion made or hearing or trial commenced on or
after July 1, 2022. A corpus that returns *Harper*-era authority for the current
standard without a `SUPERSEDED` marker will produce confidently wrong analysis,
and the model will not catch it, because its training data contains both eras.

The marker is easy to get wrong in both directions:

- **Trigger on the date of the underlying proceeding, not the opinion date.** A
  2024 appellate opinion reviewing a 2021 trial correctly applies former
  § 24-7-707; a 2021 opinion is not wrong about what governed in 2021.
- **Attach `SUPERSEDED` to the legal proposition**, here the admissibility standard
  for expert testimony in criminal cases, not to the whole opinion. The same
  opinion may be good law on every other issue it decides.

These dates were checked on October 4, 2026 against summaries of the enrolled act;
confirm them against the act's text when the corpus is built. Treat this as the
worked example for the whole recency problem.

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

## 6. Reproducibility, because otherwise you are guessing

You will change prompts, swap models, and rewire agents constantly. Without a
record of what ran, you cannot tell whether a change improved the tool or whether
the model had a good day. That is the whole reason this section exists.

Persist, for each run:

- `run_id`, timestamp, git commit SHA
- model name and version, and the `effort` setting (current models accept no
  `temperature` or seed; see `PHASE_1_MODEL_GATEWAY.md` §5.3)
- prompt template version per agent (prompts are versioned files, not inline
  strings — see §9)
- input fixture identifier
- complete output, including dropped assertions and sensor measurements

If a prompt changes and the output quality moves, you must be able to say which
change moved it. Everything else in this section follows from that.

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

**`docs/INVENTORY.md` is the only authority on what this repository contains.**
It is generated from the tree by `scripts/inventory.py` and CI fails if it is
stale. Everything below is a snapshot and will age; the file will not.

A retraction worth knowing about, because it nearly rerouted the project: an
audit dated October 1, 2026 claimed this repository was less than half its actual
size (6,158 lines of Python against 15,365; 43 tests against 185) — a 140-line
Ethics Monitor, no sentencing package, no Disclosure Tracking agent. **Every one of those claims was false.** The audit
measured a local clone 27 commits stale and never fetched. Real `main` carried a
1,127-line Ethics Monitor with 39 tests, a 41-file sentencing package with 71
tests, and a 573-line Disclosure Tracking agent. The September 4 project briefing
that the audit attacked was substantially accurate.

The lesson is the rule at the top of this section, and it applies to prose
written by a human or a model, confidently or otherwise.

Snapshot at PR #13 (October 4, 2026), from `docs/INVENTORY.md`:

- 17,042 lines of Python across 90 files in `packages/api/src`; 7,678 lines of
  tests; 4,195 lines of TypeScript. 268 test functions; `pytest` reports 293
  passed, 3 skipped.
- 24 agents: 17 REAL, 1 PARTIAL, 6 STUB. Ten are registered in `_AGENT_CONFIG`.
- **Only six are reachable from the running application** — Orchestrator, Ethics
  Monitor, Charge Processing, Pre-Interview Research, Intake Conductor, and the
  Case Prep stub. One of those six is a stub. This is the project's largest gap
  between code written and capability available.
- Eight `CaseState` output slots have no writer.
- `src/corpus/data/` holds zero corpus files, so every citation the system has
  ever produced is unverified by construction.
- No persistence: `routes/_store.py` is a module-level dict. Cases are lost on
  restart and **a case cannot be re-run**, because `can_run_agent` refuses an
  agent whose slot is already filled.
- 45 `except Exception` blocks across 21 agent modules, most of which convert a
  failure into a well-formed empty success.
- The Ethics Monitor is REAL code but keyword-based; Phase 5 replaces it.

**Invariants not yet enforced in code.** Do not assume these hold until the phase
that builds them has landed:

- §2, synthetic-only: no `provenance_class`, no fixture test, no banner. Uploads
  are accepted as-is. Banner and fixture test: Phase 2b. `provenance_class`:
  Phase 4 (Discovery Intake).
- §3.1, sensor not filter: the Orchestrator still blocks on `CRITICAL` ethics
  flags (`BLOCKED_ETHICS_P1`), and LOW-confidence outputs skip the ethics check
  entirely. The blocking switch is Phase 1.
- §7, contraband: image uploads are OCR'd rather than quarantined. Phase 4.

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
