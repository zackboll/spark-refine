# Success Metrics

> **Status (Task 007).** Part A lists the metrics for the current product:
> proof-pattern libraries, diagnostics, and usability. Part B keeps the
> original, generator-oriented metrics. They are **historical but still
> in use for proof-support measurement**: the proof-support LOC metrics
> in Part B are what produced the pivot
> ([ADR 0005](adr/0005-library-and-diagnostics-first.md)).
>
> Across both parts, **no aggregate accuracy score** is reported for the
> diagnostics. The corpus is small (49 result sets), and a single
> percentage would overstate what it can support. Results are reported
> per case and per category.

## North-star metric

**Developer-authored proof-support effort removed, and proof failures
understood faster, without weakening assurance.**

Because effort is hard to measure directly, the project should use several proxies rather than one vanity metric.

# Part A — Current metrics

## A1. Proof-pattern libraries

Measured per pattern on at least one application benchmark plus
independent validation instances. The reference values come from the
fixed pool with `SPARK_Refine_Prefix_Sets`
(`examples/fixed_pool/LIBRARY_METRICS.md`).

| Metric | Definition | Fixed pool |
|---|---|---|
| Per-instance mechanical SLOC `R` | local proof support left in the application (instantiation, invariant, adapter, local lemmas) | 36 → **10** |
| Local reduction | `(P − R) / P` against the manual baseline `P` | **72.2 %** |
| Library SLOC `L` | reusable library source, written once | 98 (all ghost) |
| Generic actual / configuration burden `A` | number of generic actuals and local configuration lines | 4 actuals; 6 configuration SLOC |
| Proof time | GNATprove wall time at the project's settings | ≈ 1.9 s → ≈ 2.2 s |
| VC count | total checks, and those located in library sources | 136 → 161 (46 in the library) |
| Prover robustness | single-prover matrix: which checks need which prover | Alt-Ergo still required; the fragile VC moved into library source |
| Hardest VC | max prover steps | 7 553 → 294 |
| Validation | independent instances proved; negative fixtures detected | 3 instances fully proved; L1–L6 detected |
| Trust debt | assumptions, axioms, justifications, suppressions | 0 (CI trust scan) |
| Client stability | public API / client-proof lines changed | 0 |

A pattern is worth adding only if these show a real per-instance saving
at an acceptable proof-time and robustness cost.

## A2. Diagnostics

Reference values: `diagnostics/DIAGNOSTICS_METRICS.md`. Every number is
asserted by a unit test.

| Metric | What is measured | Current |
|---|---|---|
| Known cases detected | per rule, against ablation-based ground truth | SRD001 9/9 structural masking-risk cases, incl. 6/6 ablation-confirmed secondary failures. SRD002 fires on all 4 known abstraction-gap fixtures (7 diagnostics) |
| Conservative warnings | warnings that are correct under the rule's claim but where no functional defect exists | SRD001: 3 (B1, B2, B6). SRD002: the false-client-assertion control fires, by design, at low confidence |
| Silence on controls | rule must not fire | SRD001 2/2 controls silent; SRD002 silent on all 6 implementation-failing controls |
| False / ambiguous correlation behavior | what happens when identities are ambiguous or sources disagree | SRD003 never pairs ambiguous or duplicate identities and reports them as metadata. SARIF/.spark disagreements are reported and lower confidence or block SRD002 |
| Degradation | behavior with missing, malformed or unsupported inputs | SRD002 skipped with an explicit reason; other rules unaffected; exit 0 |
| Fixture corpus size | sanitized real GNATprove results | 49 result sets, 137 tests |
| Fresh E2E coverage | real GNATprove runs analyzed unsanitized in CI | 3 cases, one per rule |
| Determinism | byte-identical output under shuffled inputs and reversed run order | tested |
| Version compatibility | toolchains validated | GNATprove 16.1.0; `.ali` `GNAT Lib v16` only |

Precision should be quoted only together with what counts as a positive.
For example, SRD001's precision is 9/9 for the structural pattern, but
6/9 when counted against hidden functional defects.

## A3. Product usability

| Metric | What is measured | Current |
|---|---|---|
| Installability | clean install and run outside the repository | wheel and editable install gated in CI; Python ≥ 3.11; no runtime dependencies |
| Result discovery | behavior with zero, one or several result sets | exactly one is used; zero or several give exit 2 with a sorted candidate list; the tool never guesses |
| JSON stability | schema versioning and additive-only changes | `format_version` 1; Task 006 fields additive; Task 005 fields unchanged |
| Agent-consumable metadata | stable machine fields | `code`, `category`, `action`, `confidence`, derived `summary`, per-rule `evaluated` |
| Freshness safety | whether users can tell results may be stale | documented; enforced only by future orchestration |

Future usability metrics should include time-to-understand a failure on
real projects, measured with humans and with agents.

# Part B — Original proof-support metrics (historical, still used for measurement)

## 1. Proof-support LOC reduction

Define proof-support LOC as user-authored code whose primary purpose is connecting concrete representation to abstract proof semantics:

- ghost model adapters;
- representation predicates;
- generic representation lemmas;
- refinement helper contracts;
- pattern-specific loop invariants.

Do not count the public behavioral contract as waste. The contract is the requirement and should remain user-owned.

Initial target:

```text
>= 50% reduction for circular-buffer benchmark
```

This is a hypothesis, not a promised result.

> **Outcome.** The circular-buffer support was too small for the target
> to be meaningful: `P = 19` and `21` SLOC, all generic, with no lemmas.
> On the fixed pool (`P = 36`), a reusable **library** rather than a
> generator reached 72.2 % (`R = 10`). See Part A1 and ADR 0005.

## 2. Manual artifact count

Track counts of:

```text
model helper functions
representation predicates
lemmas
loop invariants
refined contracts
proof-only update statements
```

The goal is to reduce the number a developer must design and maintain.

## 3. Proof completeness

For a stable pattern fixture:

```text
unproved expected VCs = 0
```

No metric matters if the proof (originally: "the generated proof") is incomplete.

## 4. Trust debt

Track:

```text
generated assumptions
external axioms
suppressed checks relevant to proof
trusted pattern facts
```

Default target:

```text
generated assumptions = 0
```

Current equivalent: assumptions / axioms / justifications / suppressions
in proof-pattern libraries = 0, enforced by the CI trust scan. `explain`
also reports `pragma_assume` per run.

## 5. Representation-refactor locality

Measure what a representation change touches.

Desired behavior:

- public model contracts: unchanged;
- client proofs: unchanged;
- representation mapping: changed;
- library-provided proof layer: unchanged, re-proved per instance (originally: "generated proof layer: regenerated");
- small number of application-specific proof facts: potentially changed.

A useful normalized metric is:

```text
user-owned proof lines changed / total proof lines changed
```

Lower is better when the behavioral requirement is unchanged.

## 6. Time to green proof

On controlled development tasks, measure elapsed expert work from implementation to complete proof. This is noisy but ultimately more meaningful than LOC.

Use repeated tasks/patterns before drawing conclusions.

## 7. Proof performance

Record GNATprove:

- wall time;
- VC count;
- timeout count;
- solver steps when available;
- peak memory when practical.

Automation that saves authoring time but multiplies proof runtime by an order of magnitude may not be acceptable.

## 8. Generated-code readability

> Now applies to proof-pattern library source instead of generated code.

Use code-review questions rather than a fake numeric score initially:

- Can a SPARK developer identify why each generated helper exists?
- Can a failed obligation be traced to a pattern rule?
- Are names stable and descriptive?
- Is generated control flow simple?
- Does the code use standard SPARK idioms?

## 9. Diagnostic usefulness

Once `explain` exists, measure whether a developer can identify the failing abstraction boundary without reading generated internals.

> **Update.** `spark-refine explain` exists (Task 006), and it works
> without generated internals. Its current measurable properties are in
> Part A2. A study of human or agent usefulness on real projects has not
> been done yet.

## 10. Adoption metric

Do not optimize early for downloads/stars. More useful early adoption evidence is:

- independent projects using a pattern;
- external representation variants added without rewriting the core;
- external bug reports that identify real proof-pattern limitations;
- upstream interest from SPARK/Ada tooling contributors.
