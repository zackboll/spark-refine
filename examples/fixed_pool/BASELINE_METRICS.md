# Task 003 — Fixed Object Pool Manual Proof Baseline: Metrics

Benchmark: a fixed-capacity allocator (`Max_Objects = 32`) built as a
free-index stack (`Free_Stack`, `Top`). It is refined against one
authoritative mathematical model, `Free_Model`, a
`SPARK.Containers.Functional.Sets` set of `Object_Id`. An identity counts
as allocated when it is not in `Free_Model`.

All numbers come from committed scripts:

| Source | Script |
|---|---|
| SLOC / classification | `scripts/proof_inventory.py` over `proof_inventory.toml` |
| Positive proof | `scripts/check_proof_results.py positive` (SARIF + `.spark`) |
| Negative fixtures | `scripts/check_proof_results.py negative` |
| Ablation / masking | `scripts/ablate_proof_support.py` |
| Single-prover runs | `scripts/prover_matrix.py` |

## 1. Toolchain and commands

| Component | Version |
|---|---|
| Alire | 2.1.1 |
| gnat_native | 16.1.0 |
| gnatprove | 16.1.0 (FSF) |
| sparklib | 16.1.0 (`SPARKLIB_MODE=full`) |
| gprbuild | 26.0.1 |

These are the same exact pins as the ring-buffer benchmark (`alire.toml`).

Proof switches (`fixed_pool.gpr`, package `Prove`) are identical to
Tasks 001/002: `-U --mode=all --level=2 --no-loop-unrolling
--report=statistics --checks-as-errors=on --warnings=error`. The gate adds
`-j0`.

```bash
cd examples/fixed_pool
alr -n build && ./bin/fixed_pool_runtime_tests
alr -n build -- -XFIXED_POOL_ASSERTIONS=on && ./bin/assertions/fixed_pool_runtime_tests
python3 scripts/proof_inventory.py
python3 scripts/check_proof_results.py trust-scan
python3 scripts/check_proof_results.py positive
python3 scripts/check_proof_results.py negative
python3 scripts/ablate_proof_support.py        # measurement only
python3 scripts/prover_matrix.py               # measurement only
```

## 2. Main metrics

| Metric | Value |
|---|---:|
| Production SLOC | 41 |
| Authoritative specification SLOC | 26 |
| Mechanical proof-support SLOC `P` | **36** |
| Generic mechanical SLOC | 36 |
| Generic fraction `G` | **100 %** |
| Minimum metadata SLOC `M` | **5** |
| `P / M` | **7.2** |
| Representation invariant SLOC | 5 (4 invariant + 1 `Top := 0` default) |
| Model construction SLOC | 9 |
| Membership-relation SLOC | 3 |
| Cardinality-relation SLOC | 2 |
| Helper lemma SLOC | 12 (11 lemma + 1 call) |
| Loop invariant SLOC | 5 |
| Explicit proof assertion SLOC (outside the lemma) | 0 |
| Operation refinement contract SLOC | 0 |
| Proof-only helper / state update SLOC | 0 / 0 |
| Total checks | 136 |
| Proved | 136 |
| Unproved | 0 |
| Justified | 0 |
| `pragma Assume` | 0 |
| Proof wall time (`--level=2 -j0`, gate) | 1.9–2.3 s |
| Client proof SLOC (not in `P`) | 48 |
| Runtime test SLOC (not in `P`) | 207 |

The `Top := 0` default line is counted as mechanical, which is the
conservative choice. Only the default is proof-motivated. Without it,
`P = 35`, and none of the conclusions below change.

The package has no operation-specific proof support. `Initialize`,
`Allocate` and `Release` have no `Refined_Post`, no assertions and no loop
invariants. The only statement added to an operation body is the lemma
call in `Release`.

## 3. SPARKlib 16.1.0 `Functional.Sets`: what was already provided

I inspected the installed specification
(`sparklib_16.1.0/src/full/spark-containers-functional-sets.ads`).
Operations used, with their contracts at the `SPARKlib_Full` level:

| Operation | Contract |
|---|---|
| `Empty_Set`, default init | `Is_Empty` (`Default_Initial_Condition`) |
| `Contains (S, E)` | uninterpreted, with `Iterable_For_Proof` |
| `Add (S, E)` | Pre (`SPARKlib_Defensive`): `not Contains`. Post: `Length + 1`, `Contains`, `S <= Result`, `Included_Except` |
| `Remove (S, E)` | Pre: `Contains`. Post: `Length - 1`, `not Contains`, `Result <= S`, `Included_Except` |
| `Length (S)` | `Big_Natural` |
| `"<="` | `for all Item of Left => Contains (Right, Item)` |
| `"="` | `Left <= Right and Right <= Left` (extensional) |
| `Is_Empty` | `Length = 0` and no members |
| `Num_Overlaps (L, R)` | `= Length (Intersection)`; `if L <= R then = Length (L) else < Length (L)`; symmetric for `R` |

The installed examples in `share/examples/spark/allocators`
(`List_Allocator` and others) model allocators with `Functional.Sets` and a
stored ghost `Model`. Their validity predicate carries an explicit
pairwise-distinctness quantifier, the same uniqueness idea used here. That
is prior art, not `spark-refine` value.

**Provided by SPARKlib/GNATprove, so not counted as `spark-refine` value:**
set equality, extensional `Add`/`Remove`, cardinality update on
`Add`/`Remove`, subset reasoning and the `Num_Overlaps` cardinality bound.
Every operation proof (`Allocate` = `Remove`, `Release` = `Add`)
discharges directly from these contracts.

**Not provided:** any link between `Length (S)` and the size of the element
type's range, i.e. that a set over `1 .. N` has at most `N` elements.
`Functional.Sets` has no universe or complement.
`Higher_Order.Create_Distinct` could build a universe set, but it needs an
access-to-function over `Big_Positive`. Reusing `Free_Model` of the full
identity stack is simpler, and that is what the lemma does.

## 4. Final proof support (all of `P`)

| Artifact | SLOC | Category | Generic |
|---|---:|---|---|
| `Top : Pool_Count := 0` default | 1 | representation invariant | yes |
| Active-prefix uniqueness `Type_Invariant` | 4 | representation invariant | yes |
| `Free_Model` body (empty set + `Add` loop) | 9 | model construction | yes |
| `Refined_Post`: `Length (Model) = Top` | 2 | cardinality relation | yes |
| `Refined_Post`: `Contains (Model, Id) = (exists I in 1..Top, Free_Stack (I) = Id)` | 3 | membership mapping | yes |
| Loop invariant `Length (R) = I` | 1 | loop invariant | yes |
| Loop invariant: membership = processed prefix | 4 | loop invariant | yes |
| `Lemma_Universe_Bound` (pigeonhole via `Num_Overlaps`) | 11 | helper lemma | yes |
| Lemma call in `Release` | 1 | helper lemma | yes |
| **Total `P`** | **36** | | **36 / 36** |

**Why each artifact is generic.** Any conventional free-index-stack pool
needs the same facts, whatever it stores alongside the identities:

* the uniqueness of the active prefix;
* the prefix-to-set relations (membership and cardinality);
* the set-building loop;
* the finite-universe bound, because `Release` accepts an arbitrary
  allocated id.

None of them mentions payloads, application invariants or
operation-specific behaviour. The only instance-specific ingredients are
names (`Free_Stack`, `Top`, `Object_Id`, `Max_Objects`, `Free_Model`).
All of them are resolvable from the type declarations plus the minimal
metadata in §10.

**Not needed** (each was a candidate listed in the task; none was
required):

* a non-duplicate lemma for model construction;
* a "popped element does not occur earlier" lemma for `Allocate`;
* a "`not Contains` → not in prefix" lemma for `Release`;
* invariant-preservation lemmas;
* operation `Refined_Post`s or proof assertions in operations;
* intermediate models;
* initialization loop invariants (the Ada 2022 aggregate proves directly);
* a stored ghost state.

The public capacity bound `Length (Free_Model) <= Max_Objects` is
specification. Removing it leaves every other check proved (ablation
`spec_no_public_model_bound`: 134/134). It is retained because the task
requires it as part of the authoritative model.

## 5. Scientific questions (task §31)

| Question | Answer (evidence) |
|---|---|
| Was an active-prefix uniqueness invariant necessary? | **Yes.** Without it: `VC_PRECONDITION@Free_Model` (the `Add` in the model loop) and `VC_POSTCONDITION@Allocate` (`no_uniqueness_invariant`). |
| Could `Length (Model) = Top` prove without it? | **No.** `Add`'s precondition in the model loop *is* prefix uniqueness. |
| Did Model construction need a "not already present" lemma? | **No.** Invariant + membership loop invariant discharge `Add`'s precondition automatically. |
| Could the solvers derive uniqueness of `Free_Stack (I)` from the invariant directly? | **Yes**, in the model loop, `Allocate` and `Release` (invariant preservation included). |
| Did `Allocate` need a "popped element not earlier in the prefix" lemma? | **No.** `Refined_Post` + invariant suffice for the `Remove` equality. |
| Did `Release` need a `not Contains (Model, Id)` → not-in-prefix lemma? | **No.** The membership equivalence in `Refined_Post` carries it. `Release` needed a different fact: the **capacity** bound `Top < Max_Objects`, a pigeonhole argument (§7, problem 1). |
| Did SPARKlib provide enough `Add`/`Remove`/cardinality facts? | **Yes, for every operation.** Only the finite-universe bound was missing (§3). |
| Did quantifier reasoning dominate over set operations? | Quantified representation facts are 24 of 36 SLOC. The other 12 are finite-cardinality reasoning. Set-operation semantics cost 0 SLOC. |
| Were any intermediate models needed? | **No.** |
| `Type_Invariant` or `Dynamic_Predicate`? | `Type_Invariant`. As a predicate, the component-wise `Release` fails `VC_PREDICATE_CHECK@Release` (`alt_dynamic_predicate`), as in Task 002. |

## 6. Ablation (every retained artifact is necessary)

Each row removes one artifact from a scratch copy and re-proves it with the
normal switches (`obj/ablation_summary.json`). Baseline: 136 proved, 0
unproved.

| Case | Proved | Unproved | Unproved obligations |
|---|---:|---:|---|
| `no_uniqueness_invariant` | 108 | 2 | `VC_PRECONDITION@Free_Model`, `VC_POSTCONDITION@Allocate` |
| `no_top_default` | 135 | 1 | `VC_INVARIANT_CHECK_ON_DEFAULT_VALUE@Fixed_Pool` |
| `alt_dynamic_predicate` | 117 | 1 | `VC_PREDICATE_CHECK@Release` |
| `no_refined_post` | 125 | 8 | posts of `Allocate`, `Free_Count`, `Initialize`, `Is_Exhausted`, `Is_Free`, `Release`; `VC_PRECONDITION@Allocate`; `VC_ASSERT@Lemma_Universe_Bound` |
| `no_refined_post_cardinality` | 132 | 3 | posts of `Free_Count`, `Free_Model`, `Lemma_Universe_Bound` |
| `no_refined_post_membership` | 129 | 6 | posts of `Allocate`, `Initialize`, `Is_Free`, `Release`; `VC_PRECONDITION@Allocate`; `VC_ASSERT@Lemma_Universe_Bound` |
| `weak_membership_prefix_in_model` (one direction only) | 132 | 4 | posts of `Allocate`, `Is_Free`, `Release`; `VC_PRECONDITION@Free_Model` |
| `no_loop_invariant_cardinality` | 132 | 1 | `VC_REFINED_POST@Free_Model` |
| `no_loop_invariant_membership` | 131 | 2 | `VC_PRECONDITION@Free_Model`, `VC_REFINED_POST@Free_Model` |
| `no_loop_invariants` | 128 | 2 | `VC_PRECONDITION@Free_Model`, `VC_REFINED_POST@Free_Model` |
| `no_lemma_call` | 133 | 1 | `VC_RANGE_CHECK@Release` (`Top + 1`) |
| `no_lemma_assert` | 132 | 1 | `VC_POSTCONDITION@Lemma_Universe_Bound` |
| `no_lemma_universe_witness` | 131 | 1 | `VC_POSTCONDITION@Lemma_Universe_Bound` |
| *spec* `spec_no_public_model_bound` | 134 | 0 | none (kept as authoritative spec, not in `P`) |
| *spec* `spec_no_count_posts` | 127 | 5 | client-proof assertions/posts/preconditions (§7, problem 5) |

The model-construction body cannot be ablated: it *is* the derived model.

## 7. Five hardest proof-design problems

| # | Missing property | GNATprove before fix | Artifact | Attempts | Generic? | Deterministically inferable? | Diagnostic more useful? |
|---|---|---|---|---:|---|---|---|
| 1 | Finite-universe bound: a set over `1 .. N` has ≤ N elements, so `Id` not free ⇒ `Top < N` | `range check might fail, cannot prove upper bound for P.Top + 1` (Release) | `Lemma_Universe_Bound` + call | 4 | yes | yes, from the identity range | partly: it could name the missing fact, but the proof still has to be written |
| 2 | Uniqueness of the active prefix | `precondition might fail` on `Add` in `Free_Model`; Allocate post | `Type_Invariant` | 1 | yes | yes, from storage + count roles | no |
| 3 | Set-building loop facts | `precondition might fail` + "loop at line 16 should mention R in a loop invariant" | 2 loop invariants | 1 | yes | yes | GNATprove's own hint was adequate |
| 4 | Invariant must hold on default value | `invariant check might fail on default value` | `Top := 0` | 1 | yes | yes | yes: a one-line suggestion |
| 5 | Clients cannot derive `Free_Count` arithmetic from `Length (Remove …)` through `Big_Integer` | client `assertion might fail` on `Free_Count (P) = Max_Objects - 2`; `precondition might fail` on `Allocate` after `Release` | `Free_Count` clauses in public `Allocate`/`Release` posts (**spec**, not `P`) | 1 | n/a (spec) | no: a spec decision | **yes**: "public contract insufficient for client" (as in Tasks 001/002) |

Problem 1 in detail:

* **Attempt 1.** A lemma taking `P : Pool` whose precondition called
  `Free_Model (P)`. It failed with `invariant check might fail … for "P"
  before the call`, because inside the package a `Pool` parameter of a
  private subprogram does not carry the invariant.
* **Attempt 2.** Generalised the lemma to an arbitrary set `S` with
  `Global => null`. It proved.
* **Attempts 3–4.** Inlined the same `Num_Overlaps` assertion into
  `Release` to drop the lemma. Under the racing configuration it proved in
  one run and timed out in the next, so I reverted. The lemma form passed
  5 out of 5 repeated gate runs, every ablation run and every negative run.

The key idea, using the model of the full identity stack as the universe
set, is not obvious. SPARKlib provides no universe construction.

## 8. Negative fixtures (gate: `check_proof_results.py negative`)

Every fixture must report each expected `(rule, entity)` pair in SARIF. A
nonzero exit status alone is not enough.

| Id | Fault | Expected (gated) | Observed unproved |
|---|---|---|---|
| P1 | `Initialize` duplicates identity 1 in the active prefix | `VC_INVARIANT_CHECK@Initialize` | same (135 proved / 1 unproved) |
| P2 | `Allocate` does not decrement `Top` | `VC_POSTCONDITION@Allocate` | same |
| P3 | `Allocate` returns `Free_Stack (1)`, still decrements `Top` | `VC_POSTCONDITION@Allocate` | same |
| P4 | `Release` pushes `Id + 1` (wrapping) instead of `Id` | `VC_INVARIANT_CHECK@Release`, `VC_POSTCONDITION@Release` | same (both) |
| P5 | `Release` pushes the current top again (duplicate) | `VC_INVARIANT_CHECK@Release` | same (136 proved / 1 unproved) |
| P6 | Model skips `Free_Stack (1)`; its `Refined_Post` and loop invariants are changed consistently, so the model function **proves** | `VC_POSTCONDITION@Free_Count`, `VC_POSTCONDITION@Is_Free` | also `Initialize`, `Is_Exhausted` posts and `VC_ASSERT@Lemma_Universe_Bound`. `Free_Model` itself has no failure. |

P6 is detected where the task wanted it: by the public operation
contracts, not by a failure inside the model body.

## 9. Invariant masking (task §23)

Three fixtures fail the representation invariant: P1, P4 and P5. Each was
re-proved in a scratch variant with the `Type_Invariant` removed (cases
`mask_*` in the ablation script).

| Fixture | Normal run | Invariant removed | Masked functional failures |
|---|---|---|---|
| P1 | `VC_INVARIANT_CHECK@Initialize` only | `VC_POSTCONDITION@Initialize`, `VC_POSTCONDITION@Allocate`, `VC_PRECONDITION@Free_Model` | **yes**: the `Initialize` post (`Free_Count = Max_Objects`) is really false, but it is shown as *proved* in the normal run |
| P4 | `VC_INVARIANT_CHECK@Release` **and** `VC_POSTCONDITION@Release` | `VC_POSTCONDITION@Release`, `VC_POSTCONDITION@Allocate`, `VC_PRECONDITION@Free_Model` | no: the functional failure is already visible |
| P5 | `VC_INVARIANT_CHECK@Release` only | `VC_POSTCONDITION@Release`, `VC_POSTCONDITION@Allocate`, `VC_PRECONDITION@Free_Model` | **yes**: the `Release` post (`Model = Add (Model'Old, Id)`) is really false, but it is shown as *proved* in the normal run |

This is the Task 002 phenomenon again, in a structurally different
benchmark: 2 of the 3 invariant-breaking faults hide a genuine functional
postcondition failure. P4 shows the masking is not systematic, which is
what makes it hard for a human to reason about. The normal fixtures were
not changed to expose the secondary failures.

`Allocate`/`Free_Model` failures in the masked runs are not caused by the
fault. They are the baseline cost of removing the invariant
(`no_uniqueness_invariant`).

## 10. Prover behaviour (task §28)

Normal gate (`--level=2 -j0`, provers racing): 136/136, 1.9–2.3 s wall.
The costliest check is `VC_ASSERT` in `Lemma_Universe_Bound` (Alt-Ergo,
7 553 steps, about 0.3 s) when Alt-Ergo wins the race.

Single-prover runs (`scripts/prover_matrix.py`, same `--level=2` limits,
nothing raised):

| Prover | All proved? | Unproved | Max steps (check) | Slowest check | Wall |
|---|---|---|---|---|---:|
| CVC5 only | **no** (130/136) | `VC_ASSERT@Lemma_Universe_Bound`, `VC_INVARIANT_CHECK@Allocate`, `VC_INVARIANT_CHECK@Release`, `VC_POSTCONDITION@Allocate`, `VC_POSTCONDITION@Initialize`, `VC_PRECONDITION@Free_Model` | 2 | 0.04 s | 1.7 s |
| Z3 only | **no** (135/136) | `VC_ASSERT@Lemma_Universe_Bound` | 76 (`Initialize` post) | 0.12 s | 6.7 s |
| Alt-Ergo only | **yes** (136/136) | none | 7 553 (lemma `VC_ASSERT`) | 0.26 s | 1.8 s |

This differs from the ring buffer, which all three provers proved alone.
Two points follow:

* The pigeonhole lemma is proved **only by Alt-Ergo**. The positive proof
  depends on the prover portfolio of `--level=2`, not on raised limits.
* CVC5 "gives up" quickly on the quantifier-heavy uniqueness and
  set-extensionality goals. Z3 handles those but not the `Num_Overlaps`
  step.

The gate keeps the Task 001/002 configuration (all three provers). This is
recorded as a robustness finding, not hidden.

## 11. Minimum metadata `M` (estimate only; not implemented)

This is derived from the finished proof, not from the existing
`spark-refine.toml` style. It is counted the same way as Task 002
(`REFACTOR_METRICS.md` §8): non-blank semantic lines.

```toml
pattern  = "free_index_stack"
storage  = "Free_Stack"
count    = "Top"
identity = "Object_Id"
model    = "Free_Model"
```

**M = 5.**

* `storage` and `count`: role assignment. As in Task 002, this is genuine
  user input.
* `model`: the public ghost function that the `Refined_Post` and the
  generated body attach to.
* `identity`: the universe of the pigeonhole lemma. It could be inferred
  as the element subtype of `storage`. It is kept because the lemma is
  only valid if the identity range is the storage capacity, and a tool
  should not guess that. Without it, `M = 4` and `P/M = 9.0`; the
  decision does not change.
* **Not needed:**
  * *Allocation end / LIFO direction.* No artifact depends on which end
    `Allocate` pops, because the model is a set.
  * *Index origin and capacity.* They come from the array declaration.
  * *Per-operation mappings and `emit_*` knobs.* No operation needs its
    own artifact. The single lemma call belongs in the operation that
    increments `count`, which a tool can locate.

## 12. Comparison with the circular buffer

| Metric | Ring A | Ring B | Fixed pool |
|---|---:|---:|---:|
| Mechanical proof SLOC `P` | 19 | 21 | **36** |
| Helper lemma SLOC | 0 | 0 | **12** |
| Representation invariant SLOC | 0 | 2 | **5** |
| Loop invariant SLOC | 5 | 5 | 5 |
| Minimum metadata SLOC `M` | 5 | 6 | 5 |
| `P / M` | 3.8 | 3.5 | 7.2 |
| Generic fraction `G` | 100 % | 100 % | 100 % |
| Total checks | 116 | 134 | 136 |
| Proves with every single prover | yes | yes | **no** (Alt-Ergo only) |
| Invariant masking observed | n/a | yes (B3, B4) | yes (P1, P5 of P1/P4/P5) |

**Why the pool differs.** A sequence model maps one-to-one onto
`Functional.Vectors` primitives. A set model built from a stack prefix
needs two facts the sequence did not:

* **injectivity** (the uniqueness invariant), because `Add` to a set
  requires absence where `Add` to a sequence does not;
* **a finite-universe cardinality bound**, because `Release` takes an
  arbitrary identity and capacity must follow from set theory.

Only the second fact needed a lemma, and it is the only one that stressed
the provers.

## 13. Pre-registered decision

```text
P      = 36
M      = 5
P / M  = 36 / 5 = 7.2
G      = 36 / 36 = 1.00

GO     requires P >= 50  AND P/M >= 3  AND G >= 0.80
         36 >= 50     -> FALSE           => not GO
PIVOT  requires P < 30  OR  G < 0.50
         36 < 30      -> FALSE
         1.00 < 0.50  -> FALSE           => not PIVOT
=> REVIEW
```

**Decision: REVIEW.** No generator and no pivot is selected.

### What remains uncertain

The ratio and generic-fraction criteria pass by a wide margin. Only
absolute size fails: 36 SLOC is between PIVOT (< 30) and GO (≥ 50).

All the support is generic, and not all of it is trivial: the pigeonhole
lemma took 4 attempts and needs Alt-Ergo. The unresolved question is
therefore **the delivery mechanism**: does generic support need a source
*generator*, or does a reusable SPARK *generic library* deliver it?

* **Library-able in principle:**
  * `Lemma_Universe_Bound` (12 SLOC), which depends only on the element
    subtype;
  * the prefix-to-set construction (model loop, loop invariants and its
    postcondition, about 19 SLOC), as a generic ghost function over an
    array and a count, with uniqueness as a precondition.
* **Necessarily per instance:** the `Type_Invariant` in the user's private
  part, the `Refined_Post`, the one-line model body and the lemma call.

### The one experiment that resolves it

**Next-task candidate (not started):** move the generic support into a
hand-written reusable SPARK generic ghost package (for example
`Prefix_Sets`, providing `Unique_Prefix`, `Prefix_Set` and
`Lemma_Universe_Bound`). Then re-prove this exact benchmark (same spec,
client proof, tests and fixtures, same toolchain and switches) and measure
the residual per-instance mechanical SLOC `R`:

* `R ≤ 10` (about `M`): the generic value is a **library**, not a
  generator → PIVOT (library + diagnostics).
* `R ≥ 25`: per-instance glue dominates, for example because GNATprove
  does not carry generic postconditions through the instance → the
  generator case stands.

This separates *generic*, which Task 003 establishes, from *needs
generation*, which it does not.

The following evidence stands whatever the outcome, and supports the
diagnostics direction:

* invariant masking reproduced (P1, P5);
* the single-prover fragility of the one real lemma;
* the client-contract insufficiency found by the client proof (problem 5).

## 14. Trust boundary

* **0** of each of the following in `src/`, `proof/`, `tests/`,
  `fixed_pool.gpr` and every `negative/*/fault.toml` (gate: `trust-scan`):
  `pragma Assume`, `Assume` aspects,
  `False_Positive`/`Intentional` justifications, `Skip_Proof`,
  `pragma Suppress`, `-gnatp`, `pragma Warnings`, `-gnatws`,
  `--warnings=off`, imports, `External_Axiomatization`, Why3 axioms.
* **One exemption:** the test driver is `SPARK_Mode => Off`. It is not
  proof material.
* External foundation is unchanged from Tasks 001/002: GNATprove 16.1.0,
  SPARKlib 16.1.0 (trusted library contracts for `Functional.Sets` and
  `Big_Integers`) and the Ada runtime.
* **One allow-listed foundation result**, the same as for the ring buffer:
  `a-nbnbin.ads` "function Is_Valid is assumed to return True" (SPARKlib
  `Big_Integers`, reached through `Functional.Sets.Length`). It is matched
  by exact rule, file and message prefix. No other warning is permitted.
* **No new trusted foundation.** The pigeonhole lemma is proved, not
  assumed.

## 15. Assertion-enabled runtime behaviour

`-XFIXED_POOL_ASSERTIONS=on` (`-gnata`) builds and links without
section-garbage-collection flags. The runtime tests pass (138 646 checks)
with every package contract executed, including:

* the ghost `Free_Model` construction;
* the `Functional.Sets` equalities in the `Allocate`/`Release`
  postconditions;
* the uniqueness `Type_Invariant`.

This is a valid runtime gate for this benchmark. To confirm the contracts
really execute, a duplicate-creating `Release` fault was seeded into a
scratch copy. It is analogous to P5 but pushes `Free_Stack (1)`. The
`-gnata` build then raised `ASSERTION_ERROR: failed precondition from
spark-containers-functional-sets.ads:273` (SPARKlib `Add`,
`SPARKlib_Defensive` level). That is the executed ghost model trying to
add the duplicated identity a second time.
