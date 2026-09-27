# Task 004 — Reusable Prefix-Set Proof Library Experiment

**Status:** executed. **Decision (pre-registered rule): PIVOT**, at the
boundary (`R = 10`).
Full results: `examples/fixed_pool/LIBRARY_METRICS.md`.

Base: `origin/main` = `47a431c4e375a93372ed7f39daafdfb1cb768d8f` (PR #3
merged; Task 003 head `ab0bbb0` is an ancestor).

## Question

Task 003 needed `P = 36` SLOC of generic proof support. Does it need
**source generation**, or can a hand-written reusable SPARK generic
library carry it, leaving a small residual per-instance support `R`?

Pre-registered thresholds (unchanged after the result):

```text
PIVOT           R <= 10  (and soundness/reuse gates pass)
GENERATOR CASE  R >= 25  or library blocked by a SPARK/GNATprove limitation
REVIEW          11 <= R <= 24
```

## What was built

* `proof_patterns/`: `SPARK_Refine_Prefix_Sets`, a generic over
  `Element_Type (<>)`, `Index_Type range <>`, `Storage_Array` and the
  caller's own `SPARK.Containers.Functional.Sets` instance (formal
  package). Every entity is Ghost. It provides `Is_Unique`, `In_Prefix`,
  `Model` (post: length = count, membership = in prefix, count < universe
  or the prefix holds every identity), `Universe_Size` and
  `Lemma_Can_Add`. `L = 98` SLOC. Hand-written; nothing is generated.
* `proof_patterns/validation/`: 3 proof-only instances (1-value universe
  `7 .. 7`; 200 values `-50 .. 149` with a distinct 0-based index; an
  enumeration in 5 storage slots) plus a generic obligations package.
* `examples/fixed_pool/variants/library_backed/`: the Task 003 pool with
  the same production code and visible spec, rewired onto the library.
* Gates:
  * public-API token equivalence;
  * byte-identical client proof, tests and Task 003 sources since the
    Task 004 base;
  * inventories `--all`;
  * trust scan extended to the library;
  * library-backed build and both runtime test modes;
  * positive proof, with VCs split by application and library source;
  * negative fixtures L1–L6;
  * library validation instances;
  * a new CI job. The Task 003 job is untouched.
* Measurement:
  * library-backed ablation (residual, library-internal, masking);
  * the prover matrix with `--variant`.

## Findings

| | Manual (T003) | Library-backed (T004) |
|---|---:|---:|
| Checks | 136 / 0 unproved / 0 justified | 161 / 0 / 0 |
| Per-instance mechanical SLOC | `P = 36` | **`R = 10`** |
| Reusable library SLOC | — | `L = 98` |
| Semantic generic actuals | — | `A = 4` |
| Public API token changes | — | 0 |
| Wall (gate) | 1.8–1.9 s | 2.2 s |

`R` =

* 1 `private with`;
* 5 instantiation lines;
* 1 `Top := 0`;
* 1 `Type_Invariant => Free_Prefix.Is_Unique (…)`;
* 2 lines of `Free_Model` adapter.

No local loop invariant, lemma, lemma call, assertion, quantifier or
`Refined_Post` remains. The lemma call in `Release` was eliminated by
putting the finite-universe consequence into `Model`'s postcondition.

Generic limitation found: a `Ghost` generic cannot take the caller's
non-ghost set instance as a formal-package actual (`ghost package
expected for actual`). The library therefore marks each entity `Ghost`
instead, at zero per-instance cost. The instance lives in the private part
of `Fixed_Pool`, because the private type's `Type_Invariant` must see
`Is_Unique` (a body instance cannot). GNATprove accepted it without
complaint. Nothing was blocked.

Proof execution is **not** reused: GNATprove re-proves 46 library VCs
inside the pool instance, and 32–35 in each validation instance.
Single-prover fragility is unchanged: CVC5 fails 5 checks and Z3 fails 1
(now a library VC), while Alt-Ergo proves all. But the application
developer no longer writes, sees or tunes that VC.

Diagnostics:

* all application faults L1–L5 fail at the same `(rule, entity)` in
  application source as P1–P5;
* L6 (wrong model adapter) no longer spills into the lemma;
* invariant masking is unchanged (L1, L5).

Removing the invariant is noisier (8 failures instead of 2), because the
library's `Model` contract is guarded by `Is_Unique`. One GNATprove hint
("should mention P in a precondition") is misleading in that situation.

## Decision

```text
R = 10 <= 10, 0 assume/axioms/justifications, 3 validation instances prove,
public API unchanged, client proof unchanged                     -> PIVOT
```

> For this pattern, a reusable SPARK proof library eliminates enough
> per-instance proof engineering that source generation is not justified.

The margin is zero; see the sensitivity notes in `LIBRARY_METRICS.md` §1
(`R = 7` with the instantiation on two lines, `R = 9` without the
`Top := 0` line). No threshold was changed.

## Recommended direction

1. reusable proof-pattern library (this library is the first entry);
2. refinement / specification diagnostics;
3. optional thin convenience tooling around those libraries.

## Proposed Task 005 (not started): diagnostics first

**Invariant-masking and contract-sufficiency diagnostics over SARIF.**

* **Input:** a GNATprove run whose unproved set contains
  `VC_INVARIANT_CHECK` for a type `T`.
* **Action:** the tool automatically re-runs proof on a scratch copy with
  the invariant of `T` neutralised. It subtracts the invariant-removal
  baseline, which the library-backed pool shows can be large (8 checks),
  and reports the functional postconditions that were *masked*. Each is
  reported against the public requirement it belongs to.
* **Also detect** client-insufficient public contracts: public queries
  with no model postcondition (ring buffer `Is_Full`), and client
  arithmetic that is not derivable (pool `Free_Count`).
* **Measure** on the existing fixtures: ring buffer B3/B4, pool P1/P5 and
  L1/L5, all with known ground truth.
* **Success:** every known masked failure is reported with no false
  positives from the removal baseline, and the misleading "mention P in a
  precondition" hint is explained.

The bitmap representation is still not proposed; it does not bear on this
decision.
