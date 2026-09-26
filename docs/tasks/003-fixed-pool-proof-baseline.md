# Task 003 — Fixed Object Pool Manual Proof Baseline

**Status:** executed. **Decision (pre-registered rule): REVIEW.**
Full results: `examples/fixed_pool/BASELINE_METRICS.md`.

## Question

Does refining a concrete free-index stack into a mathematical free set
(SPARKlib `Functional.Sets`) require substantial reusable proof support
that GNATprove and SPARKlib do not already provide?

## What was built

* `examples/fixed_pool/`: an independent benchmark with its own Alire
  crate and the same pins and proof switches as the ring buffer.
* **Representation:** `Free_Stack : array (Object_Id) of Object_Id`,
  `Top : 0 .. 32`. `Allocate` pops, `Release` pushes, and neither scans.
* **Model:** a derived ghost `Free_Model` (no stored ghost state).
  Allocated means "not in `Free_Model`".
* **Public contracts:** `Allocate` gives `Free_Model = Remove (Old, Id)`;
  `Release` gives `Free_Model = Add (Old, Id)`. Both also update
  `Free_Count`.
* **Supporting material:**
  * a representation-independent client proof;
  * runtime tests, both production and `-gnata`;
  * 6 negative fixtures;
  * a trust scan;
  * a line-exact proof inventory;
  * an ablation and invariant-masking study;
  * a single-prover matrix;
  * a CI job.

## Findings

| | Value |
|---|---:|
| Checks | 136 proved / 0 unproved / 0 justified |
| `P` (mechanical proof SLOC) | 36 |
| `G` (generic fraction) | 100 % |
| `M` (minimum metadata) | 5 |
| `P / M` | 7.2 |

The 36 SLOC of mechanical support break down as:

* 5 SLOC active-prefix uniqueness `Type_Invariant` (including the
  `Top := 0` default);
* 9 SLOC model loop;
* 5 SLOC `Refined_Post` (2 cardinality, 3 membership);
* 5 SLOC of two loop invariants;
* 12 SLOC for one lemma, a finite-universe pigeonhole bound.

No operation needs its own proof artifact. None of the candidate
uniqueness lemmas was needed: not-already-present, popped-not-earlier, or
`not Contains` → not-in-prefix. The solvers derive all of these from the
invariant plus the `Refined_Post`.

The one real lemma exists because `Release`'s `Top + 1` range check needs
"Id not free ⇒ `Top < Max_Objects`". SPARKlib has no universe or
complement for `Functional.Sets`, so this was proved via `Num_Overlaps`
against the model of the full identity stack. **Only Alt-Ergo proves it**;
CVC5 alone fails 6 checks and Z3 alone fails 1.

Invariant masking (Task 002) reproduced. P1 and P5 report only the
invariant failure, while their genuinely false functional postconditions
show as proved. They appear only when the invariant is removed.

## Decision

```text
GO    needs P>=50 and P/M>=3 and G>=0.80 : 36>=50 false   -> no
PIVOT needs P<30 or G<0.50               : false, false  -> no
=> REVIEW
```

## Open question and proposed next experiment (not started)

All of `P` is generic. What is unresolved is whether it needs **source
generation** or can be delivered as a **reusable SPARK generic ghost
library**, for example a `Prefix_Sets` package providing the prefix-to-set
model, a uniqueness predicate and the universe-bound lemma.

The proposed experiment re-proves this unchanged benchmark on top of such
a library and measures the residual per-instance support `R`:

* `R ≤ 10`: library + diagnostics (PIVOT).
* `R ≥ 25`: the generator case stands.

Proceeding to the bitmap representation is **not** proposed. It would not
resolve this question.
