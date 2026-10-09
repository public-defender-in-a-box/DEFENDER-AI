# Phase 1 — Model Gateway, Failure Semantics, and Cassettes

**Audience:** Claude Code
**Prerequisite:** PR #13 merged to `main`.
**Read first:** `CLAUDE.md`, `SPEC.md`, and `docs/INVENTORY.md`.
**Amended October 9, 2026** after the pre-build review: team decisions recorded in
§0, model facts checked against Anthropic's live documentation, and the
`temperature` requirement replaced (it cannot be met; §5.3). The changes are
listed in §13.

**Authority note:** `docs/INVENTORY.md` outranks every narrative description of
this repository, including this document. The October 1 audit that SPEC v2.0 §2
quoted measured a clone 27 commits stale; see `CLAUDE.md` §8.1.

---

## 0. Team decisions that scope this phase

Settled October 4 and October 9, 2026:

1. **Models.** The primary model is **`claude-opus-5-5`** (ratified October 9).
   The system is comparative: a finding should not be an artifact of one model.
   Users can switch a run to a cheaper model to manage their own costs, chosen from
   a fixed allowlist (§8). The old default, `claude-sonnet-4-20250514`, was retired
   on June 15, 2026 and must not appear anywhere.
2. **The sensor switch lands in this phase**, bundled with failure semantics.
   `CLAUDE.md` §3.1 becomes true in code now rather than in Phase 5, because both
   changes govern what happens to a non-clean output, and splitting them would mean
   recording cassettes against behavior we intend to replace.
3. **No automatic model fallbacks.** Anthropic's server-side fallback feature
   reroutes a refused request to a different model. It stays off: it would swap the
   model mid-run without the run asking for it. A refusal is recorded as
   `RefusalError` (§3.1).
4. **No fallback outputs anywhere, including sentencing.** When a model call fails,
   the agent fails. The sentencing package's labeled fallbacks are removed (§3.2).
5. **Bring your own API key.** Each person who runs the tool supplies their own
   Anthropic API key through their environment. No key is committed, configured in
   CI or the shared cloud environment, or written to a cassette (§8.1).

Scoping call made in this spec, not by the team — **prompt migration is
incremental** (§7). Moving ~20 inline prompts while also replacing the gateway
would make this phase's failure modes uninterpretable.

---

## 1. Goal

> Every model call in the system goes through one typed gateway that validates
> its response against a declared schema, records what it cost, distinguishes an
> error from an abstention, and can be replayed from disk. CI exercises real
> model-response paths with **zero live network calls.** An agent failure is
> never again indistinguishable from an empty result.

### 1.1 Non-goals

Do not build, and push back if asked: persistence, locators or the `Assertion`
model, the Ethics Sensor's new classification layers (the *switch* is in scope,
the *rewrite* is Phase 5), the legal corpus, any evidence-analysis agent, the
synthetic-only ingest gate, and any UI. The model toggle in this phase is
configuration and a request parameter; a UI control for it belongs to Phase 2b.

Explicitly deferred to Phase 2a, not this phase: `(case_id, run_id)` keying and
the `depends_on` sequencing rewrite. Both are needed for bias probes and both
change `CaseState`; they belong with persistence so there is one migration rather
than three.

---

## 2. The gateway

Replace `services/llm_service.py`. Keep a shim (§9).

```python
Effort = Literal["low", "medium", "high", "xhigh", "max"]

class ModelCallRequest(BaseModel):
    prompt: str
    system: str
    max_tokens: int                   # per call site; see below
    effort: Effort = "high"           # pinned; see §5.3 and §8
    model: str | None = None          # None = the run's model; must be on the allowlist
    response_model: type[BaseModel]   # REQUIRED — no untyped calls
    prompt_id: str                    # e.g. "charge_processing.extract"
    prompt_version: str               # e.g. "v1"
    agent_id: str

class ModelCallRecord(BaseModel):
    request_hash: str
    model_requested: str
    model_returned: str               # from the response
    effort: Effort
    input_tokens: int
    output_tokens: int
    latency_ms: int
    retries: int
    cassette: Literal["hit", "miss", "recorded", "bypassed"]
    stop_reason: str | None
    cost_usd: float                   # actual, or would-be cost on a cassette hit (§6)
    at: datetime

class ModelCallResult(BaseModel, Generic[T]):
    data: T                           # validated instance of response_model
    record: ModelCallRecord
```

```python
async def call_model(req: ModelCallRequest) -> ModelCallResult: ...
```

Requirements:

- **`response_model` is required.** There is no path that returns a bare `dict`.
  A per-agent response model is part of migrating each call site.
- **Use the API's structured outputs** (`output_config.format`, or the SDK's
  `messages.parse`, both present in the installed SDK) to constrain the reply to
  `response_model`'s schema, instead of fishing JSON out of free text.
  `MalformedResponseError` should then be rare; `SchemaMismatchError` still
  catches semantic validators.
- **Read text blocks, never `content[0]`.** Current models return thinking blocks
  before the answer (thinking is always on for Opus 5.5). Today's `call_llm` reads
  `response.content[0].text`; a thinking block has no `.text`, so switching the
  model without this gateway makes every agent crash, and most then return an
  empty "success" (§3). **The model change and the gateway must land together.**
- **Check `stop_reason` before reading content.** `"refusal"` raises
  `RefusalError`; `"max_tokens"` raises `TruncatedResponseError`.
- **`max_tokens` is set per call site.** Thinking tokens count toward it, so the
  old 4096 default truncates responses on current models.
- **Do not send `temperature`, `top_p` or `top_k`.** The installed Python SDK
  (1.x) no longer accepts them, and current models reject non-default values with
  a 400.
- **No `fallbacks` parameter and no fallback middleware** (§0.3).
- Retries and timeouts are **explicit and configurable**, not SDK defaults. Do
  not reimplement what the SDK does — configure it, then record the retry count
  the SDK actually used.
- **Record `response.usage`.** The current code discards it, which is why
  `cost_tracker` reports zeros everywhere.
- Record `model_returned`, not only `model_requested`. Current model IDs are pinned
  snapshots, so they should match; recording both proves it.
- **Pin the `anthropic` SDK version** in `requirements.txt` and `pyproject.toml`.
  Today it is `>=0.25.0`, so CI installs whatever is newest. Record the version in
  `docs/MODELS.md`.

---

## 3. Failure semantics

**This is the most important section in the phase.** There are 45
`except Exception` blocks across 21 agent modules (verified), and the dominant
pattern converts a failure into a well-formed empty success — a 401 from the API
produced a zero-charge result that the Orchestrator merged as a win. For a tool
whose headline numbers are failure and abstention rates, this inverts a metric:
errors are currently counted as correct abstentions.

### 3.1 The taxonomy

```python
class ModelCallError(Exception):
    """Base. Never caught by a bare `except Exception` in agent code."""

class TransportError(ModelCallError):          # network, 5xx, timeout, rate limit
class AuthError(ModelCallError):               # 401/403 or no key — loud, never retried
class RefusalError(ModelCallError):            # stop_reason "refusal"
class TruncatedResponseError(ModelCallError):  # stop_reason "max_tokens"
class MalformedResponseError(ModelCallError):  # not parseable
class SchemaMismatchError(ModelCallError):     # parsed, failed response_model validation
class CassetteMissError(ModelCallError):       # replay mode, no recording (§5.2)
```

**Abstention is not an error.** `CLAUDE.md` §4.5 makes "the record does not
address this" a correct answer, so it is expressed *in* a valid
`response_model` instance — an `abstained: bool` plus `abstention_reason` on
response models where it applies — never by raising, and never by returning an
empty payload.

### 3.2 What agents must do

- No agent may catch `ModelCallError` and return a valid-looking output. **There
  are no fallback outputs**, labeled or not (§0.4).
- Every `except Exception` in an agent module is either removed or narrowed to a
  specific exception with a comment saying why handling it there is correct.
- A failure propagates to `Orchestrator.handle_agent_failure`, which records
  `FAILED` with the error type and writes it to measurements.

**Scope: fix all 45 in this phase.** The review classified them:

| Group | Count | Today | Change |
|---|---|---|---|
| Wraps a model call | 23 | Returns an empty or fallback "success" | Removed as each call site migrates (§9); it is the same edit |
| Skips malformed items in model output ("Skipping malformed…") | 11 | Drops the item silently | Narrow to `ValidationError`; **count** the drops per agent, since a dropped item is a measurement |
| Loads bundled data files (sentencing seed data, program directory) | 7 | Falls back to empty data | Let it raise; missing seed data is a bug |
| Pipeline boundaries (`graph.py`, `research_orchestrator.py`) | 4 | Records a failure | Narrow to `ModelCallError` |

Fix first: `tier2_research/citation_verification.py:470` returns `True` when the
holding check fails, so a failed verification counts as a verified holding.

**Sentencing fallbacks are removed:** `_fallback_arguments`
(`nodes/leniency_argument_builder.py`) and `_fallback_narrative`
(`nodes/mitigation_narrative_builder.py`), with their two tests in
`sentencing_agent/tests/test_llm_outputs.py`. Deleting a test for deleted code is
correct; report it.

Report the count fixed and any you deliberately left.

### 3.3 Tests currently passing on swallowed errors

These will change status after §3.2. **That is the correct outcome** — convert them
to cassette replay (§5) or to tests of the new failure behavior; do not restore
the swallowing to keep them green:

- Seven of PR #6's research tests make live Anthropic and CourtListener calls and
  pass only because the agents swallow the errors.
- `tests/agents/tier2_attorney/test_plea_trial_analyst.py` (around line 59) mocks
  the model with `side_effect=Exception(...)` and expects a fallback result.
- The two sentencing fallback tests above, which are removed.

Report how many tests changed status.

---

## 4. The sensor switch

Make `CLAUDE.md` §3.1 true in code. Two changes in
`tier0/orchestrator.py::receive_agent_output`:

1. **A CRITICAL ethics flag no longer discards the output or stops the
   pipeline.** The output merges, carrying the flag. Replace the
   `BLOCKED_ETHICS_P1` outcome with `MERGED_WITH_CRITICAL_FLAG`, retaining
   `BLOCKED_ETHICS_P1` in the enum only if historical merge records reference it.
2. **The ethics check no longer skips on LOW confidence.** Every output is
   checked. LOW confidence merges with its flag as it does today, but it is no
   longer exempt from inspection — the current skip means the lowest-quality
   outputs are the least examined, which is backwards.

**No conflict with the Ethics Monitor's 39 tests.** They assert the monitor's own
`blocked` flag; the switch is in the Orchestrator, which stops acting on that
flag. Keep the monitor's `blocked` and record it on the merge as
`would_have_blocked`, so "how often would a deployable product have blocked this"
stays measurable. No existing test asserts `BLOCKED_ETHICS_P1`, so the blocking
path is untested today; `test_critical_flag_merges` is its first coverage. Three
call sites that branch on `BLOCKED_ETHICS_P1` become dead and are removed:
`agents/graph.py` (two) and `routes/upload.py` (one).

The one surviving hard block: nothing that would transmit matter content to a
real person. No such path exists; do not add one.

`_blocked`, `_merge_history`, and `_human_review_required` currently live on the
Python object outside `CaseState`. **Do not move them in this phase** — that is
Phase 2a's persistence work. Note the dependency in your report.

---

## 5. Cassettes

### 5.1 Keying

Hash everything that can change the output:

```
sha256(model_requested ‖ effort ‖ system ‖ prompt ‖ max_tokens
       ‖ prompt_id ‖ prompt_version ‖ response_model.__name__ ‖ schema_version)
```

`model_requested` **must** be in the key. With more than one allowed model, a key
that omits it silently serves one model's recording for another and destroys the
comparison. `effort` must be in it for the same reason.

Store under `packages/api/tests/cassettes/<model>/<agent_id>/<hash>.json`,
committed. Safe to commit only because all fixtures are synthetic
(`CLAUDE.md` §2). A cassette stores the request body and the response body,
**never request headers**, so it can never contain an API key.

Synthetic-content check (replaces the original "no string from outside
`tests/fixtures/synthetic/`" test, which cannot work: model output contains
arbitrary text, and fixtures do not move to `synthetic/` until Phase 2b):

- each cassette records the fixture identifier(s) its request was built from, and
  a test asserts every identifier resolves to a committed fixture file;
- a test scans every cassette for real-looking Georgia case numbers, SSNs, phone
  numbers and API-key patterns (`sk-ant-`), and fails on any hit.

### 5.2 Modes

| Mode | Behavior |
|---|---|
| `replay` (default in CI and tests) | Hit → serve. **Miss → raise `CassetteMissError` and fail loudly.** Never fall through to a live call. Needs no API key. |
| `record` | Explicit env flag. Live call with the recorder's own key, write cassette, serve. |
| `live` | No cassette involvement. Development and normal use; never in CI. |

The miss-fails-loudly rule is the acceptance criterion that makes "zero live
network calls in CI" enforceable rather than aspirational. Back it with a
socket-blocking fixture in `conftest.py` so a new unmocked dependency fails
immediately instead of quietly reaching the network.

### 5.3 Determinism (replaces "Temperature")

The original spec asked for recordings at `temperature=0.0`. **That cannot be
done:** current models return a 400 for a non-default `temperature`, and the
Python SDK 1.x removed the parameter (passing it raises `TypeError`). There is no
sampling control left on these models.

So: pin `effort` (default `high`, identical across models, because the models'
own defaults differ — Opus 5.5 `medium`, Sonnet 5.5 `high`, Haiku 5.5 `medium` —
and comparing at defaults would mix up model and effort). Accept that two live
calls with the same key can differ; that is exactly why cassettes exist. Where
variance is itself the object of study, that is a Phase 6 sweep with many
recordings per key, not a Phase 1 concern.

### 5.4 CourtListener

The research agents make live HTTP calls to the CourtListener v3 API
(`https://www.courtlistener.com/api/rest/v3`). Apply the same record/replay at the
`services/courtlistener.py` boundary, keyed on the request URL and parameters, or
those tests stay network-dependent and §5.2's acceptance criterion fails.

Recording needs network access to `www.courtlistener.com`. The shared cloud
environment's network policy currently denies that host; whoever records either
runs locally or adds it to the environment's allowed domains. Check at recording
time that the v3 API is still served.

### 5.5 Who records

The recording pass needs a live API key, and per §0.5 the repository and the
shared environment have none. **A team member runs `record` mode with their own
key**, then commits the cassettes. Gateway mechanics (error mapping, retries,
keying, accounting) are tested without a key by injecting a mock HTTP transport
into the SDK client; agent-level replay tests need real recordings, so Phase 1
cannot complete until the recording pass has run for the study models (§8).

---

## 6. Token and cost accounting

`services/cost_tracker.py` exists, is used only by `research_orchestrator`, and
its `record_llm_call` is never called — so token counts are always zero and
pricing is hard-coded at $3/$15 per million.

- The gateway records every call unconditionally. Accounting is not opt-in and
  not the caller's responsibility.
- Per call: `agent_id`, `prompt_id`, `prompt_version`, `model_requested`,
  `model_returned`, `effort`, input/output tokens, latency, retries, cassette
  outcome, cost.
- **Move pricing out of code** into a data file keyed by model ID, with the
  effective date and the source URL. Prices change and a hard-coded constant
  silently falsifies every cost figure. The file must support tiered pricing:
  Haiku 5.5 charges more for prompts over 100,000 tokens.
- Reuse `cost_tracker`'s structures if they fit; replace them if they don't. Say
  which you did.

A cassette hit has zero token cost but should still record what the call *would*
have cost, so a replayed suite can report the cost of the experiment, per model.

Prices checked October 9, 2026 (per million tokens, input / output), from
`https://platform.claude.com/docs/en/about-claude/pricing`:

| Model | Input | Output | Cache read |
|---|---|---|---|
| `claude-opus-5-5` | $4 | $20 | $0.20 |
| `claude-sonnet-5-5` | $2 | $10 | $0.10 |
| `claude-haiku-5-5` (prompts ≤ 100K tokens) | $0.10 | $0.50 | $0.01 |
| `claude-haiku-5-5` (prompts > 100K tokens) | $0.50 | $2.50 | $0.05 |

---

## 7. Prompt versioning — incremental

`CLAUDE.md` §6 and §9 require versioned prompt files and a recorded version.
Today only sentencing, the Motion Drafter, and plea/trial comply; roughly twenty
agents build prompts as inline f-strings.

**Policy for this phase:**

- The gateway **requires** `prompt_id` and `prompt_version` on every call. This
  is enforced by the type signature, so it cannot be skipped.
- An inline prompt may satisfy it with a module-level constant and an explicit
  version string. It does not have to move to a file yet.
- **Any prompt touched in this phase moves to a file.** Any new prompt is a file.
- Produce `docs/PROMPT_DEBT.md`, generated by `scripts/inventory.py`, listing
  every prompt still inline. CI does not fail on it; it just has to be visible
  and shrinking.

Rationale: a recorded version string is what reproducibility actually needs. File
layout is hygiene, and doing it to twenty agents concurrently with a gateway
replacement means that when quality moves you won't know which change moved it.

---

## 8. Models and the cost toggle

Checked against Anthropic's live documentation on October 9, 2026
(`platform.claude.com/docs/en/about-claude/models/overview` and
`.../model-deprecations`):

| Model | ID | Thinking | Default effort | Retirement, not sooner than |
|---|---|---|---|---|
| Claude Opus 5.5 | `claude-opus-5-5` | Always on | `medium` | September 22, 2027 |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | Adaptive | `high` | September 28, 2027 |
| Claude Haiku 5.5 | `claude-haiku-5-5` | Adaptive | `medium` | October 7, 2027 |

All have a 1M-token context window. Dateless IDs are pinned snapshots.

- **Primary: `claude-opus-5-5`** (ratified). Used unless a run selects otherwise.
- **The cost toggle.** A run may select a cheaper model from the allowlist
  `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`. Configuration:
  `CLAUDE_MODEL_PRIMARY` (default model) and `CLAUDE_MODELS_ALLOWED`
  (comma-separated). A per-run selection is a request parameter validated against
  the allowlist; **any model ID not on it is rejected with a clear error**, so
  runs stay comparable and costs predictable. The UI control is Phase 2b.
- **Comparison model for recorded runs: `claude-sonnet-5-5`, proposed — confirm
  before recording.** Cassettes are recorded for the primary and the comparison
  model. Haiku 5.5 is selectable for cost but has no recordings unless the team
  adds it, so it runs live only.
- **Effort is pinned at `high` for every model** (§5.3).
- Record the allowlist, the primary, the comparison model, the pinned effort, the
  SDK version, and each model's resolved `model_returned` in `docs/MODELS.md`, with
  the date and the documentation URLs checked.
- Do not pin from memory; re-check the live model list before recording.

### 8.1 API keys: bring your own

- The backend reads `ANTHROPIC_API_KEY` from the environment of whoever runs it
  (`.env`, documented in `.env.example`). It is never committed, never configured
  in CI or the shared cloud environment, never logged, never stored in `CaseState`
  or measurements, and never written to a cassette.
- `replay` mode needs no key. `live` and `record` modes fail fast at startup with
  an actionable message when the key is missing — an `AuthError`, never a silent
  empty run.
- Optional `COURTLISTENER_API_KEY` follows the same rules.

---

## 9. Migrating the call sites

Twenty-two modules import `call_llm`, with **36 call expressions** between them,
including two sentencing nodes and `routes/intake.py`.

**Approach: shim plus incremental migration.** Keep

```python
async def call_llm(prompt, system=..., max_tokens=4096) -> dict
```

as a deprecated wrapper over `call_model` that uses a permissive passthrough
response model, emits a `DeprecationWarning`, and records the call with
`prompt_version="unversioned"`. The shim must already read text blocks rather
than `content[0]` (§2), so unmigrated agents keep working on the new models.

Then migrate in this order, reporting progress:

1. **`charge_processing`** (3 calls) — most load-bearing; migrate first and let it
   shake out the interface.
2. **The five research agents** (10 calls), together with CourtListener
   record/replay (§5.4) **and the socket-blocking fixture**. The fixture breaks the
   seven network-leaking tests immediately, so it lands with the code that fixes
   them.
3. **`intake_conductor` and `routes/intake.py`** (4 calls) — they share the
   interview flow.
4. **The two sentencing nodes** — inside a 41-file package with 71 tests; the
   best-covered code in the repo and therefore the safest late migration. Their
   fallbacks are removed here (§3.2).
5. **Everything else**, including Disclosure Tracking (5 calls, the most of any
   module) and the stubs. Stubs need recordings too: they are the naive
   single-prompt baseline.

A test asserts the shim has zero callers when migration completes; until then it
asserts the count only decreases. Delete the shim at the end of the phase, or say
why it survived.

---

## 10. Acceptance criteria, as tests

- `test_no_live_network_in_ci` — a socket-blocking fixture is active across the
  suite; any attempted outbound connection fails the test that made it.
- `test_cassette_miss_raises` — replay mode with no recording raises
  `CassetteMissError` and never calls the API.
- `test_cassette_key_includes_model_and_effort` — the same prompt under two
  allowed models, or two effort levels, produces different keys and cannot
  cross-serve.
- `test_schema_mismatch_raises` — a recording mutated to violate its
  `response_model` raises `SchemaMismatchError`; no empty-but-valid output is
  produced.
- `test_auth_error_propagates` — a simulated 401 raises `AuthError` and reaches
  `handle_agent_failure`; **specifically assert Charge Processing does not return
  a zero-charge success**, which is the exact bug from §3.
- `test_missing_key_fails_fast` — `live` or `record` mode without
  `ANTHROPIC_API_KEY` raises `AuthError` before any request.
- `test_refusal_raises` and `test_truncation_raises` — `stop_reason` `"refusal"`
  and `"max_tokens"` raise their typed errors.
- `test_thinking_blocks_skipped` — a response whose first content block is a
  thinking block is parsed from its text blocks.
- `test_model_allowlist` — a model ID not on `CLAUDE_MODELS_ALLOWED` is rejected;
  every allowlisted model is accepted.
- `test_no_fallbacks_or_sampling_params` — no request body contains `fallbacks`,
  `temperature`, `top_p` or `top_k`.
- `test_cassettes_contain_no_secrets` — no cassette contains request headers or
  an `sk-ant-` string; every cassette's fixture identifiers resolve (§5.1).
- `test_abstention_is_not_error` — an abstaining response yields a valid
  `response_model` with `abstained=True`, and is counted as an abstention, not a
  failure.
- `test_usage_recorded` — every call produces a `ModelCallRecord` with non-zero
  token counts on a live/recorded call and a computed would-be cost on a hit.
- `test_critical_flag_merges` — a CRITICAL ethics flag yields
  `MERGED_WITH_CRITICAL_FLAG`, the output is present in `CaseState`, and the merge
  records `would_have_blocked`.
- `test_low_confidence_is_ethics_checked` — a LOW-confidence output is inspected,
  not skipped.
- `test_broad_except_count` — a static check over `src/agents/` asserting the
  `except Exception` count is zero, or matches a shrinking allowlist with
  documented reasons.
- `test_shim_callers_decreasing` — as described in §9.
- Full suite: `pytest` as CI runs it, offline, green, with **more** passing
  model-response paths than before, not fewer.

---

## 11. Report on completion

Per `CLAUDE.md` §8, plus specific to this phase:

- The primary, comparison and allowlisted models, the pinned effort, and the SDK
  version, as recorded in `docs/MODELS.md`.
- Count of `except Exception` blocks removed, and any retained with reasons.
- Count of tests that changed status, and which previously passed on swallowed
  errors.
- Cassette count and total size per model.
- Cost of the recording pass, per model.
- Newly measurable: tokens, latency and cost per agent, per prompt and per model;
  retry rates; failure rate by error type (including refusals and truncations);
  abstention rate as distinct from failure rate; malformed-item drop counts; and
  live-call count in CI (which should be zero).

---

## 12. Handoff prompt

> Read `CLAUDE.md`, then `SPEC.md`, then `docs/INVENTORY.md`, then
> `PHASE_1_MODEL_GATEWAY.md`.
>
> Do not write code yet. First:
>
> 1. Report anything that changed on `main` since PR #13 merged.
> 2. Re-check the live model list and pricing against §6 and §8, and get the team
>    to confirm the comparison model before any recording.
> 3. Report where this spec is wrong, impractical, or would weaken the tool.
>
> Then stop. I'll approve before you build.

---

## 13. Changes from the first draft (October 9 review)

- §0: models ratified (Opus 5.5 primary, cost toggle via allowlist); old default
  recorded as retired; decisions 3–5 added (no automatic fallbacks, no fallback
  outputs, bring your own key).
- §2: `temperature` replaced by pinned `effort`; per-model selection; structured
  outputs; thinking-block parsing; `stop_reason` checks; per-call `max_tokens`;
  SDK pinning.
- §3: `TruncatedResponseError` added; the 45 blocks classified; sentencing
  fallbacks removed; tests that will change status listed.
- §4: shown not to conflict with the Ethics Monitor's tests; `would_have_blocked`
  recorded; dead branches named.
- §5: `effort` replaces `temperature` in the cassette key; no headers in
  cassettes; workable synthetic-content check; §5.3 rewritten; CourtListener
  network access; §5.5 added.
- §6: live prices and tiered Haiku pricing.
- §8: rewritten for the cost toggle; §8.1 added.
- §9: call counts; socket fixture moved to step 2; `routes/intake.py` added to
  step 3; stubs included.
- §10: tests added for keys, refusals, truncation, thinking blocks, allowlist,
  forbidden parameters, and secret-free cassettes.
- §12: rewritten for after PR #13.
