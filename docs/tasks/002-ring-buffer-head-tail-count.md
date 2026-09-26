# Task 002 — Benchmark Head/Tail/Count Representation Refinement

## Purpose

Task 001 proved a `Content + First + Length` circular buffer with only
19 SLOC of mechanical proof support, which weakened the `spark-refine`
generator hypothesis. Task 002 is an evidence-gathering experiment: re-prove
the **same public abstraction** over a deliberately redundant representation,

```text
Content + Head + Tail + Count      (Tail = Physical_Index (Head, Count))
```

and measure whether redundant concrete state creates enough generic
proof and refinement machinery to justify automation.

**No generator functionality was implemented.**

## Base and branch

* Reviewed base: `origin/main` = `0f6da9702ab5683157efa855df80e7c562c53d95`
  (merge of PR #1, the Task 001 baseline). Confirmed unchanged before
  starting.
* Branch: `feature/002-ring-buffer-head-tail-count`.

## Experimental controls

| Control | How it is enforced |
|---|---|
| Same public specification | `scripts/check_public_api_equivalence.py` compares the visible parts of `src/ring_buffer.ads` and `variants/head_tail_count/ring_buffer.ads` token by token, ignoring only comments and layout. It runs in CI. (The visible parts are in fact byte-identical.) |
| Same client proof | `proof/ring_buffer_client_proof.ad[sb]` unchanged. CI runs `git diff --exit-code 0f6da97 -- proof/... tests/...`. |
| Same runtime tests | `tests/ring_buffer_runtime_tests.adb` unchanged (same CI check). 536 checks pass for both representations, with and without `-gnata`. |
| Same abstract model | Derived SPARKlib `Functional.Vectors` sequence, built from `Head` and `Count`. `Tail` is not used. |
| Same toolchain and switches | Same `alire.toml` and the same `package Prove`. The representation is selected with `-XRING_BUFFER_REPR=head_tail_count`. |
| Task 001 reproducible | `src/`, `negative/`, `proof_inventory.toml` and the default gate/inventory/ablation invocations are unchanged. A still proves 116/116 and N1–N5 are still detected. |

## What was built

```text
examples/ring_buffer/
  variants/head_tail_count/ring_buffer.ads/.adb   representation B
  variants/head_tail_count/negative/*/fault.toml  B1–B6 negative fixtures
  proof_inventory_head_tail_count.toml            B line classification
  REFACTOR_METRICS.md                             all Task 002 measurements
  ring_buffer.gpr                                 + RING_BUFFER_REPR selector (separate obj/bin per repr.)
  scripts/check_public_api_equivalence.py         new: public-API gate
  scripts/refactor_churn.py                       new: A→B churn measurement
  scripts/check_proof_results.py                  + --variant, variant-aware negatives, trust scan of variants, step stats
  scripts/proof_inventory.py                      + --variant / --all
  scripts/ablate_proof_support.py                 + --variant, B cases, alternatives, control
.github/workflows/ci.yml                          one job: common controls, then A, then B
```

## Results

The full numbers, tables and reproduction commands are in
[`examples/ring_buffer/REFACTOR_METRICS.md`](../../examples/ring_buffer/REFACTOR_METRICS.md).

| | A: First + Length | B: Head + Tail + Count |
|---|---:|---:|
| Production SLOC | 54 | 58 |
| Specification SLOC | 19 | 19 |
| Mechanical proof-support SLOC | 19 | 21 |
| of which representation invariant | 0 | 2 |
| Lemmas / assertions / operation `Refined_Post`s | 0 / 0 / 0 | 0 / 0 / 0 |
| Checks | 116 proved | 134 proved |
| Unproved / justified | 0 / 0 | 0 / 0 |
| Wall time | ≈ 2 s | ≈ 2.1–2.8 s |

* **Representation invariant:**
  `Type_Invariant => Buffer.Tail = Physical_Index (Buffer.Head, Buffer.Count)`.
  It is necessary: without it, exactly `VC_POSTCONDITION @ Push` fails.
* **Push:** needed only the invariant, because it writes through `Tail`.
  A control run in which `Push` ignores `Tail` proves with no invariant.
* **Pop:** preserving `Tail = Physical_Index (Head', Count')` proved
  automatically. No lemma was needed.
* **Wraparound and modulo arithmetic:** automatic at levels 0–3, at
  `Max_Size` 16, 17 and 1000, and with CVC5, Z3 or Alt-Ergo alone.
* **Dynamic_Predicate:** fails 4 checks with natural field-by-field updates.
  It works only if `Clear`, `Push` and `Pop` are rewritten as whole-record
  updates, so it was not chosen.
* **Negative fixtures B1–B6:** all detected on the expected `(rule, entity)`.
  In B3 and B4 the invariant check *masks* the violated functional
  postcondition, which GNATprove then reports as proved. This was confirmed
  by rerunning both without the invariant.
* **Churn A→B:** public API, contracts, client proof and runtime tests all
  0 lines changed. Proof support: 6 lines renamed and 2 lines new.
* **Minimum metadata:** 5 role lines for A and 6 for B, against 19 and 21
  SLOC of support. A realistic manifest saves about 11–12 lines per
  structure.

## Decision

* **Hypothesis: WEAKER** (again). Redundant state cost 2 lines of
  invariant. There were no lemmas, no assertions and no per-operation
  contracts, and all arithmetic proved automatically.
* **Recommendation: MORE EVIDENCE.** Circular sequences map one-to-one onto
  SPARKlib sequence primitives, the most favourable case for automation. The
  next experiment is a **fixed object pool** (free-index stack represented
  against an abstract `Functional.Sets` free/allocated set). It uses a
  pre-registered GO/PIVOT rule, stated in `REFACTOR_METRICS.md` §12. If
  that pool is also cheap, the project should pivot to proof and
  specification diagnostics plus abstraction-contract validation, where the
  evidence of both tasks says the human effort actually is.

## Trust

No `pragma Assume`, no unchecked Why3 axioms, no `False_Positive` or
`Intentional` justifications, no proof-only `Import`, no `pragma Suppress`,
and no weakened public contract (the visible spec is byte-identical to
Task 001). No new external trust foundation was introduced.
