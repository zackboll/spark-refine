# Minimum Viable Product

> **Status.** Task 007 redefined the MVP around capabilities that now
> exist. The original generator MVP (phases M0–M5) ran as an experiment.
> Its manual-baseline phases (M0, M5) were completed, and the generator
> phases (M1–M3) were not pursued: the evidence rejected source
> generation as the primary direction
> ([ADR 0005](adr/0005-library-and-diagnostics-first.md)). That plan is
> preserved below as history.

## Current MVP objective

Deliver a small, trustworthy proof-engineering toolkit that:

1. removes recurring proof support from applications with a reviewed,
   GNATprove-verified SPARK library; and
2. helps humans and agents understand GNATprove results, without ever
   becoming a proof authority.

## Current MVP scope

| Capability | Content | Status |
|---|---|---|
| Reusable proof pattern | `SPARK_Refine_Prefix_Sets` (`proof_patterns/`): unique array prefix → SPARKlib functional set | **implemented, validated** |
| Proof diagnostics | SRD001 invariant masking risk, SRD002 client-only proof gap, SRD003 prover-portfolio dependency | **implemented, validated** |
| Installed CLI | `spark-refine explain [PATH]` (SRD001, SRD002; one existing result set; conservative discovery; does not run GNATprove); `compare-provers` (SRD003); `rules`; `analyze` alias | **implemented, validated** |
| Machine-readable output | deterministic `format_version` 1 JSON with `code`, `category`, `action`, `confidence`, derived `summary`, per-rule `analysis` | **implemented, validated** |
| Trust behavior | read-only; no assumptions; no source rewriting; no proof-status decisions | **implemented, validated** |
| Agent guidance | `docs/AGENT_INTEGRATION.md`: loop, freshness, per-action guardrails | **documented** |

## Implemented

* `proof_patterns/`, which contains `SPARK_Refine_Prefix_Sets`:
  * `L = 98` SLOC, all ghost;
  * no assumptions, axioms, justifications, imports or suppressions.
* `examples/fixed_pool/variants/library_backed`, where the library
  replaces 36 manual SLOC with `R = 10` per-instance SLOC. The public
  API, client proof and runtime tests are unchanged.
* `diagnostics/`, the Python package `spark_refine_diagnostics`. It
  installs the `spark-refine` command, needs Python ≥ 3.11 and has no
  runtime dependencies. Its adapters:
  * SARIF for results;
  * `.spark` for unit ownership, proof metadata and consistency checks;
  * `.ali` as a narrow GNAT 16.1.0 dependency adapter, used only by
    SRD002.

## Validated

All validation uses the pinned FSF GNAT / GNATprove / SPARKlib 16.1.0
toolchain and runs in CI.

* **Library.**
  * The fixed-pool instance and three independent validation instances
    are fully proved.
  * Negative fixtures L1–L6 are all detected.
  * The trust scan is clean.
  * The unchanged public API and client proof are CI-gated.
* **Diagnostics.**
  * 49 sanitized real GNATprove result sets and 137 fixture-based tests.
  * SRD001 detects 9/9 structural masking-risk cases, including 6/6
    ablation-confirmed secondary failures. It also gives 3 conservative
    warnings where the abstract postcondition was in fact true.
  * SRD002 fires on every known abstraction-gap ablation and on the
    false-client-assertion control, which is why SRD002 claims a gap, not
    a contract defect. It stays silent on all implementation-failing
    controls.
  * SRD003 reports only `exact` or `unique_entity` matches.
  * See `diagnostics/DIAGNOSTICS_METRICS.md`. The corpus is small, and
    these are per-case results, not accuracy rates.
* **Fresh end-to-end.** One real GNATprove run per rule, analyzed
  unsanitized (CI job `diagnostics-e2e`).
* **Packaging.** The wheel is built, inspected, installed and run outside
  the repository, both as a regular and as an editable install. The
  suite also runs on Python 3.11 (CI job `diagnostics-packaging`).

## Out of scope for the current MVP

* running GNATprove (`explain` only reads existing results);
* editing sources, repairing proofs or changing contracts;
* Libadalang or any source-semantic analysis;
* source generation, manifests or source annotations;
* support for `.ali` versions other than `GNAT Lib v16`;
* concurrency, WCET and certification evidence.

## Future (not implemented)

Candidates, each gated on evidence:

* **proof-run orchestration**, e.g. a command that runs GNATprove and
  then explains, while keeping the exact GNATprove command visible;
* **Libadalang semantic enrichment**: callee and contract-conjunct
  identification for SRD002, and mapping failures to source
  abstractions;
* **additional evidence-backed proof patterns**, each with validation
  instances and a per-instance burden measurement;
* **editor integration** through ALS / VS Code / GNAT Studio, consuming
  the JSON;
* **agent integration** beyond the documented loop;
* **broader toolchain compatibility**, i.e. validated support for more
  GNATprove / `.ali` versions.

## MVP completion definition

The current MVP is complete when:

* every capability in the scope table is implemented, tested in CI and
  documented. This holds after Task 006;
* the documentation consistently describes that product and its trust
  boundary. This is Task 007;
* no document presents generation as the current path.

---

# Historical: generator MVP (M0–M5)

> **Status: historical.** Everything below is the original generator MVP
> and its status notes, preserved unchanged. The M0 and M5 manual
> baselines are the evidence
> behind the pivot. M1–M4 and the `spark_refine validate` / `generate` /
> `check` CLI were never implemented and are not planned.

## MVP objective

Prove or disprove one narrow hypothesis:

> For a conventional bounded circular buffer, can a small refinement declaration generate enough correct SPARK proof scaffolding to materially reduce human-authored proof support without adding trust assumptions?

The MVP is successful even if the answer is “only for representation X under constraints Y,” provided the result is measured and honest.

> **Status after Task 003 (evidence only; no generator exists).**
>
> | Benchmark | Mechanical support | Lemmas |
> |---|---:|---:|
> | Circular buffer A | 19 SLOC | 0 |
> | Circular buffer B | 21 SLOC | 0 |
> | Fixed pool (free-index stack → set) | 36 SLOC | 1 |
>
> All of it is generic. The pre-registered rule gives **REVIEW** for the
> fixed pool, so phases M1–M3 below remain **on hold**. The next
> experiment (not started) tests whether this generic support can be a
> reusable SPARK library instead of generated source.
> See `docs/tasks/003-fixed-pool-proof-baseline.md`.

> **Status after Task 004.** That experiment ran. With a hand-written
> reusable generic (`proof_patterns/SPARK_Refine_Prefix_Sets`, 98 SLOC),
> the fixed pool's per-instance proof support drops from 36 to **R = 10**
> SLOC (4 generic actuals), with an unchanged public API and client proof.
> The pre-registered rule gives **PIVOT** (R ≤ 10, at the boundary).
>
> * Source generation is **not justified** for this pattern, so phases
>   M1–M3 below are **not pursued** on current evidence.
> * The recommended direction is a reusable proof-pattern library plus
>   refinement/specification diagnostics.
>
> The history of this file is kept as-is. See
> `docs/tasks/004-prefix-set-proof-library.md`.

## Out of scope

The MVP does not need:

- arbitrary Ada parsing by hand;
- multiple patterns;
- VS Code integration;
- AI assistance;
- automatic arbitrary loop-invariant synthesis;
- concurrency;
- atomics/memory-order reasoning;
- WCET analysis;
- certification documents;
- dynamic third-party pattern plugins.

## Phase M0 — hand-written baseline

Create a ring-buffer example with:

- capacity fixed by a generic or constant;
- private bounded storage;
- `First + Length` representation;
- `Push` and `Pop`;
- an abstract sequence model;
- complete GNATprove proof;
- no unchecked assumptions.

Record which lines exist solely for proof support.

Classify them:

```text
model construction
representation predicate
index helpers
lemmas
loop invariants
operation refinement
other
```

This baseline is mandatory. We cannot claim to reduce proof effort without knowing what the manual proof costs.

**M0 result (Task 001).** The baseline exists in `examples/ring_buffer`
(capacity is a fixed constant, `Max_Size = 16`; generic capacity was
deliberately deferred). Classified manual proof support:

```text
model construction         9 SLOC
representation predicate   0
index helpers              0   (production Physical_Index reused by the model)
lemmas                     0
loop invariants            5 SLOC (2 invariants)
operation refinement       5 SLOC (Model'Refined_Post only; operations need none)
other                      0
total                     19 SLOC, all generic to circular sequences
```

Complete proof: 116/116 checks, ≈ 2 s. Details and the hypothesis assessment
(**weaker**) are in `examples/ring_buffer/BASELINE_METRICS.md`.

## Phase M1 — manifest and IR

Implement:

```text
spark_refine validate
spark_refine generate
```

Parse TOML with a maintained Ada TOML library rather than building a custom parser.

The generator may initially require explicit fully-qualified entity names and a deliberately small representation schema.

## Phase M2 — semantic source resolution

Integrate Libadalang so the validator can confirm that configured entities exist and have compatible declarations.

Do not infer semantics from raw text/regex.

## Phase M3 — first generated proof layer

Generate a proof package containing at minimum:

- logical-to-physical mapping;
- mapping-in-range property;
- model-length relation;
- representation validity predicate;
- standard append/remove helper lemmas that the baseline proves need.

Avoid generating every imaginable lemma. Measure which ones eliminate real manual work.

> **Revised by M0 evidence.** For representation A the baseline needed only
> the model-length and element-wise relations (as `Model'Refined_Post`), the
> derived `Model` body, and its two prefix loop invariants. The
> mapping-in-range property, the representation validity predicate and the
> append/remove lemmas were **not** needed, because the provers and SPARKlib
> already handle them. M3 should start from the 3-artifact set in
> BASELINE_METRICS §11, and add further artifacts only when a benchmark
> (e.g. the A3 refactor) demonstrates the need. The manifest's `emit_lemmas`
> and `emit_representation_predicate` flags have no justification yet.
>
> Because the manual support is only 19 SLOC, a verbose manifest could cost
> more than it saves. M1/M3 should aim for a manifest no longer than the
> support it replaces, and the value case should be re-tested on A3 and
> Benchmark B before investing in Libadalang integration (M2).
>
> **A3 re-test (Task 002).** Representation B added exactly one artifact, the
> representation invariant (2 SLOC), and nothing else from this list. The
> minimum metadata that determines all B support is six role lines
> (`pattern`, `storage`, `first`, `count`, `index`, `next`), against 21 SLOC
> of support. The value case for M1–M3 is still unproven and now rests on
> Benchmark B.

## Phase M4 — stock GNATprove gate

CI proves the fixture with supported GNATprove.

Pass criteria:

```text
unproved generated VCs = 0
forbidden generated assumptions = 0
run-time check obligations for generated executable code = 0 or not applicable
```

Ghost code can be computationally inefficient but must obey SPARK proof rules.

## Phase M5 — refactor benchmark

Change the concrete representation to `Head + Tail + Count` or another meaningful variant while preserving the public model/contracts.

Measure:

- user-written lines changed;
- generated lines changed;
- manual proof artifacts rewritten;
- proof runtime;
- public client proof changes.

The ideal result is that client proofs do not change and most proof churn is generated.

**M5 result without a generator (Task 002).** `Head + Tail + Count` was
proved manually against the unchanged public spec, client proof and
runtime tests (0 lines changed in each; CI-gated). The manual refactor cost
6 renamed proof-support lines plus one new 2-line
`Type_Invariant => Tail = Physical_Index (Head, Count)`. No lemmas,
assertions or operation `Refined_Post`s were needed, and all wraparound
arithmetic (including `Tail` preservation across `Pop`) proved
automatically. Total support grew from 19 to 21 SLOC; checks went from
116 to 134, in ≈ 2–2.8 s. So "most proof churn is generated" would mean
generating about 8 lines. Hypothesis: **weaker** again. Recommendation:
**more evidence** from a set-based benchmark (fixed pool) before any M1–M3
investment. See `examples/ring_buffer/REFACTOR_METRICS.md` §11–12.

## CLI behavior for the MVP

```text
spark_refine --version
spark_refine validate [--manifest FILE]
spark_refine generate [--manifest FILE] [--out DIR]
spark_refine check [--manifest FILE]
```

`check` should eventually:

1. validate;
2. generate to a temporary location;
3. compare output to the checked-in/generated directory;
4. fail on drift.

Running GNATprove from `check` can be added after the generator is stable.

## MVP completion definition

The MVP is complete only when a report answers:

- How many proof-support lines did the manual baseline require?
- How many remain user-authored with `spark-refine`?
- Did all generated obligations prove?
- How much generated code was emitted?
- Was the generated code understandable in review?
- What changed during representation refactor?
- Did proof time regress materially?
- Which parts could not be automated and why?

A generator that emits 1,000 opaque lines to save 30 transparent lines is not automatically a success.
