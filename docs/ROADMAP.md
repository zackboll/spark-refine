# Roadmap

The roadmap is evidence-gated. Dates are intentionally omitted. Each
item should proceed only if the previous evidence shows value.

> **Status.** Task 007 replaced the actionable generator phase sequence
> with the current one below
> ([ADR 0005](adr/0005-library-and-diagnostics-first.md)). The evidence
> history and the original phases 0–10 are preserved in later sections.

## Current direction

Two pillars, with GNATprove as the proof authority:

1. **reusable SPARK proof-pattern libraries**, grown one validated
   pattern at a time;
2. **proof-aware diagnostics** over GNATprove output, for humans, CI and
   agents.

## Completed

Task 021: bounded historical SHA256.Update maintenance pilot using the existing
worklist. **TARGET_REPAIRED_AND_VALIDATED**: 3→0 target unproved, 11→8 overall;
two fresh unchanged confirmations and independent runtime checks pass. Only a
retained external implementation patch, usage report and replay artifacts;
no production feature or contract change. Workflow usable, with little
incremental value observed in this known case; no causal speedup claim or
new product change justified. See [Task 021](tasks/021-proof-workflow-pilot.md).

Task 020: opt-in `--show-unproved` on `explain`, `analyze` and `prove`.
Every loaded normalized unproved occurrence is exposed in text and optional
`analysis.unproved_checks` JSON, independently of SRD diagnostics. No new
rule, loader, proof policy or repair; defaults stay unchanged. Pure/real
fixture, packaging and same-fresh-output E2E checks cover the interface;
Task 017's hash-verified raw artifacts expose all 11 checks with zero SRDs.
This enables a possible later usage trial, not a measured productivity claim.
See [Task 020](tasks/020-unproved-check-worklist.md).

Task 019: **closed experiment, `DO_NOT_ADOPT_BITMAP_PATTERN`**. Manual P=54,
minimized library-backed R=56, library L=124 (−3.703704% reduction).
The 32-bit candidate reached complete local proofs; broader validation and
falsification were not completed. Post-measurement review stopped the remaining
campaigns after economic rejection. No further optimization of this candidate
is planned, no second supported bitmap pattern was adopted, and Prefix_Sets
remains the established reusable pattern.
See [closeout](tasks/019-bitmap-set-proof-pattern.md#observations-append-only-after-preregistration-commit).

Task 018: independent upstream qualification across the five proposed projects
found no committed natural GNATprove-16 failure with sufficient documented
SRD001/SRD002 structure. No functional external proof was run; the memcp spike
was rejected as uncommitted. Verdict **NO_NATURAL_POSITIVE_CANDIDATE_QUALIFIED**.
Defer positive external validation until an upstream case meets the gate;
do not broaden the rules. See [Task 018](tasks/018-external-positive-candidate.md).

Task 017: Ada_CRDT's independently selected WIP revision reproduces 11 natural
unproved checks (control: zero). Both SRD001 and ALI-backed SRD002 evaluate
successfully but emit zero diagnostics: none of the 11 meets their narrow rule
patterns. This is **EXTERNAL_FAILURE_REPRODUCED_NO_MATCHING_DIAGNOSTIC**, not
positive external validation. See [Task 017](tasks/017-positive-external-validation.md).

| Step | Task(s) | Outcome |
|---|---|---|
| Experimental baseline and generator hypothesis | 001, 002 | manual ring buffers A and B: `P = 19` and `21`. Hypothesis weakened twice |
| Fixed-pool baseline | 003 | `P = 36`, all generic. **REVIEW** |
| Fixed-pool library experiment | 004 | `SPARK_Refine_Prefix_Sets`, `R = 10` (−72.2 %). **PIVOT** away from source generation |
| Diagnostics MVP | 005 | SRD001–SRD003 over SARIF / `.spark` / `.ali` (SRD001/SRD002 per run, SRD003 across single-prover runs), 49 real-result fixtures, fresh E2E gate |
| `explain` CLI productization | 006 | installed `spark-refine explain`, conservative discovery, `format_version` 1 JSON with `category`/`action`, `docs/AGENT_INTEGRATION.md` |
| Documentation realignment | 007 | every current document describes the two-pillar product and its trust boundary; generator documents labelled historical/deferred |
| Fresh proof-run orchestration | 008 | `spark-refine prove -P project.gpr`: runs GNATprove (argv, exact command shown), analyzes only the result set that run created or changed, preserves GNATprove's exit code; `analysis.orchestration` in JSON; real E2E-D/E |
| Semantic SRD002 enrichment (experimental) | 009 | opt-in `--semantic`: Libadalang resolves each SRD002 failure to its exact call, callee, declaration and explicit `Pre` (conjuncts decomposed); sources gated on GNAT `.ali` source identity metadata (checksum + second-resolution timestamp; not byte-exact); failed-conjunct attribution measured **NOT ATTRIBUTABLE** from GNATprove 16.1.0 output, so never claimed; core package unchanged |

| SRD002 semantic triage groups | 010 | report-level `analysis.semantic.srd002_groups` and a text triage section: exact `VC_PRECONDITION` failures grouped by identical callee declaration + explicit `Pre`; everything else is ungrouped with a machine reason; every failure appears exactly once. `ring_no_is_full_post`: 3 Push failures → 1 group. Descriptive only (no cause, no group confidence, no conjunct). Diagnostics unchanged |
| Defensive semantic rendering | 011 | malformed internal semantic entries render as `semantic entry: incomplete`; one shared completeness contract (`semantic_shape.py`); valid output byte-identical |
| Per-conjunct re-proof experiment | 012 | pre-registered experiment (script outside the product, `diagnostics/scripts/conjunct_reproof_experiment.py`). Scratch copies of the Task 009 corpus replace a callee's `Pre` by ONE top-level conjunct, then GNATprove is re-run: 1 control + 5 probes. Result: **VALIDATED_ON_CONTROLLED_CORPUS**. Baseline 4/4 unproved; all 9 probe observations match (4 proved / 5 unproved / 0 justified); `First_Fails` [U, P] vs `Both_Fail` [U, U] distinguished. Only independent total conjuncts; no product change, `failed_conjunct` stays `null` |
| Ada call-binding conjunct re-proof experiment | 014 | **CALL_BINDING_METHOD_VALIDATED_ON_PREREGISTERED_SUPPORTED_CASES** on a controlled corpus: 26 Libadalang-resolved call occurrences, 7 resolved callee contracts, baseline + 15 unique callee-prefix programs, 60 per-occurrence prefix observations. Validated positional/named/reordered actuals, defaulted formals, explicit conversion handling, an `in out` formal, package state / `Proof_In` `Pre`, overload resolution by declaration identity, a generic instance → template `Pre` source, and a class-wide dispatching call → root `Pre'Class`. A8's unproved conversion VC remained auxiliary; its call-prefix result was **not** clean conjunct evidence. Scratch evidence only; no product change ([Task 014](tasks/014-ada-call-binding-reproof.md)) |
| External SPARK validation pilot | 015 | Pinned sml-ada fallback (Muen kernel setup unresolved): fresh GNATprove 16.1.0 proof, 356/356 checks proved; current core explain ingested output, SRD001 evaluated (0 diagnostics), SRD002 disabled (missing `sml.ali`); 19 SARIF/.spark mismatches. No functional failures manufactured or external source changed. [Evidence](tasks/015-external-validation-pilot.md) |

## Decisions

Task 016 separated check display attribution from authoritative dependency-unit
inventory. Pinned sml-ada's 12 analysed units have supported ALIs; `sml` was
introduced only by one unmatched termination SARIF result. The 19 unmatched
results remain disputed, not exempted by rule or proof status. SRD002 now
evaluates to zero on this fully proved run; an independent external positive
SRD002 case remains unvalidated. See [Task 016](tasks/016-external-artifact-compatibility.md).

* **Semantic enrichment stays opt-in (Task 010).** Libadalang is not a
  normal pip dependency, a cold hosted setup measured ~23.5 min
  (Task 009), and the core diagnostics package deliberately has zero
  runtime dependencies. `--semantic` (and with it the triage groups)
  therefore remains an explicit flag. This is not permanent: revisit
  automatic enablement if Libadalang distribution improves (for example
  a prebuilt wheel or a fast, cached install).

## Near term

* **Possible developer/agent usage evaluation.** Observe actual use of the
  established pattern and diagnostics under the authoritative-specification
  policy. This is a possible next direction, not a started task or a promised
  successful result. Task 020 delivers a reporting interface only; no usage
  trial or Task 021 has started.
* **External positive validation remains deferred** until an independently
  selected natural case qualifies. Tasks 016–018 do not supply that positive
  evidence. Normal reports retain `failed_conjunct: null`.

## Later

* **More reusable proof patterns where evidence warrants.** Each needs a
  benchmark showing that per-instance support is large and generic,
  independent validation instances, and measured proof-time effect.
* **Editor integration**: ALS / VS Code / GNAT Studio consuming the JSON,
  not a custom editor.
* **Stronger agent integration**: richer structured context for agents,
  still under the "do not weaken authoritative specifications" policy.
* **Certification and evidence outputs**: proof and trust summaries
  derived from GNATprove results. This is not a certification claim.
* **Broader toolchain compatibility**, for GNATprove / `.ali` versions
  beyond 16.1.0, validated before being claimed.

## Research / deferred

These items are not on the current path. Each would need new evidence.

* **Source generation** (manifest → IR → generated proof package). It was
  not justified for the demonstrated patterns. Revisit only if a pattern
  needs per-instance support that a generic library cannot carry.
* **Source annotations specifically for generation** (ADR 0004).
* **General invariant synthesis.** Pattern-derived invariants mostly
  live inside libraries now.
* **Concurrency / temporal bridge** (TLA+/PlusCal, SPSC queues).
* **WCET / timing integration.**
* **Upstream SPARK/GNATprove proposals** informed by real usage.

## Evidence history

> **Evidence so far (history preserved):**
>
> * **Task 001** (ring buffer A: `P = 19`) weakened the generator
>   hypothesis.
> * **Task 002** (ring buffer B: 21) weakened it again.
> * **Task 003** (fixed pool: 36, all generic) gave **REVIEW**.
> * **Task 004** decided library vs. generator: a hand-written reusable
>   generic (`proof_patterns/`) left `R = 10` per-instance SLOC, giving
>   **PIVOT**.
>
> The historical phases (see "Historical: original phase plan" below)
> were written before that evidence.
>
> * **Phase 2** (circular-sequence generator) and **Phase 3** are **not
>   pursued** on current evidence.
> * The project proceeds as:
>   1. a reusable SPARK proof-pattern library (grown one validated pattern
>      at a time, each with independent validation instances);
>   2. refinement/specification diagnostics, i.e. Phase 7 brought forward
>      (next: invariant-masking and contract-sufficiency diagnosis, as
>      proposed in `docs/tasks/004-prefix-set-proof-library.md`);
>   3. optional thin convenience tooling around the libraries.
>
> **Task 005** started item 2 with `diagnostics/`, a deterministic
> analyzer over GNATprove SARIF/.spark. It has three rules:
>
> * SRD001: invariant masking risk. All 9 structural masking-risk cases
>   were detected, and all 6 ablation-confirmed secondary failures were
>   among them.
> * SRD002: client-only proof gap; the public abstraction may be
>   insufficient. Confidence is medium or low, and the rule makes no
>   contract-deficiency claim.
> * SRD003: prover-portfolio dependency, for confidently matched checks
>   only.
>
> See `docs/tasks/005-proof-diagnostics-mvp.md` and
> `diagnostics/DIAGNOSTICS_METRICS.md`.
>
> **Task 006** productized the diagnostics as the installable Python
> command `spark-refine` (`pip install ./diagnostics`). It adds:
>
> * `spark-refine explain` with conservative result-set discovery;
> * `analyze` kept as an alias;
> * stable `category`/`action` fields and a derived `summary` in the JSON;
> * `docs/AGENT_INTEGRATION.md`.
>
> It adds no rule and does not use Libadalang. The `spark_refine explain`
> of Phase 7 below is therefore the Python `spark-refine explain` (with a
> hyphen), not a command of the Ada bootstrap executable. See
> `docs/tasks/006-explain-cli-productization.md`.
>
> **Task 007** realigned the documentation with this direction. It adds
> ADR 0005, rewrites the vision, architecture, MVP and roadmap, and
> labels the generator documents historical/deferred. It changes no
> behavior.

## Historical: original phase plan (generator-first)

> **Status: historical/deferred.** These are the original phases 0–10,
> kept unchanged except that headings are demoted one level. They are no
> longer the actionable plan:
>
> * Phases 0, 1 and the manual parts of 4–5 were carried out as
>   experiments (Tasks 001–004).
> * Phase 7 was brought forward, without generation, as Tasks 005–006.
> * Phases 2, 3 (as a generator dependency), 4's `diff`/`check`, 6 and 8
>   are deferred.
> * Phases 9–10 continue in the "Later" section above, in a different
>   form.

### Phase 0 — repository and research baseline

Deliverables:

- problem statement;
- landscape analysis;
- trust policy;
- architecture decisions;
- example manifest;
- CLI skeleton;
- benchmark design.

This bootstrap repository is Phase 0.

### Phase 1 — manual proof benchmark

Build and prove the circular-buffer baseline by hand.

Deliverables:

- complete SPARK implementation;
- GNATprove configuration;
- proof-support inventory;
- negative fixtures;
- baseline metrics.

No generator work should outrun this benchmark.

### Phase 2 — circular-sequence generator

Implement:

- TOML parsing;
- refinement IR;
- validation;
- deterministic source generation;
- first pattern;
- golden tests;
- forbidden-assumption scanner;
- proof CI.

Exit criterion: generated fixture reaches the same proof result as baseline.

### Phase 3 — semantic Ada integration

Add Libadalang.

Capabilities:

- resolve target entities;
- validate types/visibility;
- locate source declarations;
- detect conflicts;
- improve diagnostics;
- remove fragile string-based assumptions.

### Phase 4 — refactor support

Add:

```text
spark_refine diff
spark_refine check
```

Perform representation B benchmark and client-proof stability test.

### Phase 5 — second proof pattern

Preferred: fixed pool with a set-based abstract model.

This phase tests whether the core IR and pattern interface generalize beyond sequences.

If major architecture changes are required, make them now before promising third-party plugin stability.

### Phase 6 — source annotations

Prototype `pragma/aspect Annotate` syntax after real manifests reveal the stable concepts.

Goals:

- colocate role declarations with representation;
- keep project-level policy in TOML;
- preserve manifest-only mode.

### Phase 7 — proof-aware diagnostics

Ingest GNATprove machine-readable output.

Implement:

```text
spark_refine explain
```

Map VCs to:

- user requirement;
- refinement layer;
- pattern rule;
- generated declaration;
- likely representation concept.

### Phase 8 — pattern-derived invariant suggestions

Generate or suggest invariants from known pattern semantics.

Start with deterministic cases such as loops that copy a logical prefix or scan bounded storage.

Do not begin with general invariant synthesis.

### Phase 9 — editor integration

Expose structured JSON/LSP-friendly diagnostics. Integrate with existing Ada editor infrastructure instead of building a custom editor.

### Phase 10 — optional AI agent

Only after the deterministic architecture is stable.

Agent tasks may include:

- explaining failed obligations;
- proposing application-specific invariants;
- selecting existing lemmas;
- suggesting a missing refinement layer;
- generating a candidate representation mapping.

Guardrails must distinguish proof-support changes from requirement weakening.

### Long-term research branches

Potential independent tracks:

- concurrency/state-machine refinement;
- TLA+/PlusCal linkage;
- DMA/ownership-ring patterns;
- assurance/evidence reports;
- WCET metadata correlation;
- upstream SPARK language/tool proposals informed by real usage.
