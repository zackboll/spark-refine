# Task 004 — Reusable Prefix-Set Proof Library: Metrics

Same fixed pool as Task 003 (`BASELINE_METRICS.md`): same public
specification (token-identical), same production representation
(`Free_Stack`, `Top`) and algorithm, same client proof, same runtime tests,
same toolchain pins and proof switches. The only difference is that the
mechanical proof support now comes from a hand-written, reusable SPARK
generic library, `SPARK_Refine_Prefix_Sets` (`proof_patterns/src/`).

| Path | Contents |
|---|---|
| `variants/library_backed/fixed_pool.ad[sb]` | library-backed variant |
| `../../proof_patterns/src/` | reusable library (`L`) |
| `../../proof_patterns/validation/` | 3 independent proof-only validation instances |
| `proof_inventory_library_backed.toml` | line-exact classification (`R`) |
| `variants/library_backed/negative/L*/` | fault fixtures L1–L6 (equivalents of P1–P6) |

All numbers come from committed scripts:

```bash
cd examples/fixed_pool
python3 scripts/check_public_api_equivalence.py
python3 scripts/proof_inventory.py --all                  # P, R, L, A
python3 scripts/check_proof_results.py trust-scan
python3 scripts/check_proof_results.py positive --variant library_backed
python3 scripts/check_proof_results.py negative --variant library_backed
python3 scripts/check_proof_results.py library-validation
python3 scripts/ablate_library_backed.py                  # measurement only
python3 scripts/prover_matrix.py --variant library_backed # measurement only
alr -n build -- -XFIXED_POOL_SRC=variants/library_backed -XFIXED_POOL_VARIANT=library_backed
./bin/fixed_pool_runtime_tests
```

## 1. Main comparison

| Metric | Manual Task 003 | Library-backed Task 004 |
|---|---:|---:|
| Production SLOC | 41 | 41 |
| Authoritative specification SLOC | 26 | 26 |
| Mechanical per-instance SLOC | 36 (`P`) | **10 (`R`)** |
| Reusable library SLOC | 0 | **98 (`L`)** |
| Generic actual concepts | 0 | **4 (`A`)** |
| Local helper lemma SLOC (incl. call) | 12 | 0 |
| Local model construction SLOC | 9 | 2 (one-call adapter) |
| Local `Refined_Post` SLOC | 5 | 0 |
| Local loop invariant SLOC | 5 | 0 |
| Local representation invariant SLOC | 5 | 2 (1 `Is_Unique` + 1 `Top := 0`) |
| Local library configuration SLOC | 0 | 6 (1 `private with` + 5 instantiation) |
| Local assertion SLOC | 0 | 0 |
| Local library-lemma call SLOC | 0 | 0 |
| Proof checks | 136 | 161 |
| — located in application sources | 68 | 47 |
| — located in reusable library sources | 0 | 46 |
| — client proof | 28 | 28 |
| — SPARKlib instance checks | 40 | 40 |
| Proof wall time (`--level=2 -j0`, 3 runs) | 1.83–1.88 s | 2.15–2.17 s |
| Max prover steps (racing portfolio) | 7 553 (Alt-Ergo, lemma assert) | 294 (Alt-Ergo, library `Model` post) |
| Unproved | 0 | 0 |
| Justified | 0 | 0 |
| `pragma Assume` | 0 | 0 |
| Runtime tests (production / `-gnata`) | PASS 138 646 / PASS 138 646 | PASS 138 646 / PASS 138 646 |

```text
absolute local reduction   = 36 - R = 36 - 10 = 26 SLOC
percentage local reduction = 26 / 36 = 72.2 %
R / M                      = 10 / 5 = 2.0
A vs M                     = 4 semantic actuals vs 5 estimated metadata SLOC
```

### Composition of `R = 10`

| Artifact | File:line | SLOC | Category |
|---|---|---:|---|
| `private with SPARK_Refine_Prefix_Sets;` | `fixed_pool.ads:3` | 1 | library configuration |
| `package Free_Prefix is new SPARK_Refine_Prefix_Sets (…4 actuals…)` | `fixed_pool.ads:61-65` | 5 | library configuration |
| `Top : Pool_Count := 0;` (invariant on default value) | `fixed_pool.ads:69` | 1 | representation invariant (conservative, as Task 003) |
| `with Type_Invariant => Free_Prefix.Is_Unique (Pool.Free_Stack, Pool.Top);` | `fixed_pool.ads:71` | 1 | representation invariant |
| `function Free_Model … is (Free_Prefix.Model (P.Free_Stack, P.Top));` | `fixed_pool.adb:9-10` | 2 | model adapter |

Counting conventions are identical to Task 003 (non-blank, non-comment
lines; `end record` stays production; the `Top := 0` line is counted
conservatively). Sensitivity, stated so the result is not over-read:

* `R` sits **exactly on** the pre-registered PIVOT boundary (`R ≤ 10`).
* 4 of the 10 lines are layout: the instantiation is written one actual per
  line (GNAT style, as `Id_Sets` is). On two lines, `R = 7`.
* Excluding the `Top := 0` default, as Task 003 also discussed, gives `R = 9`.
* No configuration was relabelled as production or specification. The only
  exclusion from the API gate is the `private with` clause, which is
  invisible to clients. It is **counted in `R`**.

## 2. What moved (artifact disposition)

| Task 003 artifact | SLOC | Task 004 disposition |
|---|---:|---|
| uniqueness quantifier (`Type_Invariant` body) | 4 → 1 | **library** (`Is_Unique`); the local one-line aspect remains in `R` |
| `Top := 0` default | 1 → 1 | **local** (unchanged) |
| model body (loop) | 9 → 2 | **library** (`Model`); 2-line adapter remains local |
| membership `Refined_Post` | 3 → 0 | **library** (`Model` postcondition, `In_Prefix`) |
| cardinality `Refined_Post` | 2 → 0 | **library** (`Model` postcondition) |
| loop invariant 1 (length) | 1 → 0 | **library** |
| loop invariant 2 (membership) | 4 → 0 | **library** |
| pigeonhole lemma | 11 → 0 | **library** (`Lemma_Universe_Bound`, private to the body) |
| lemma call in `Release` | 1 → 0 | **eliminated**: the library's `Model` postcondition carries the finite-universe consequence (`Count < Universe_Size or else` every identity is in the prefix), so `Release` needs no proof statement. `Lemma_Can_Add` is still exported for sets not built from a prefix. The ablation `residual_with_explicit_lemma_call` shows that adding the call back changes nothing. |

## 3. Reusable library `L = 98`

| Metric | Value |
|---|---:|
| Library SLOC `L` | 98 |
| Specification SLOC | 51 (of which generic formal part: 8) |
| Body SLOC | 47 |
| Proof-only SLOC | 98 (every entity is Ghost) |
| Public ghost API entities | 7: `Count_Type`, `Prefix_Last`, `In_Prefix`, `Is_Unique`, `Universe_Size`, `Model`, `Lemma_Can_Add` |
| Helper lemmas | 2 (`Lemma_Universe_Bound` private, `Lemma_Can_Add` public) |
| Loop invariants | 4 (2 in `Model`, 2 in universe construction) |
| Assertions | 1 (`Num_Overlaps` step) |
| Validation instances (not in `L`) | 131 SLOC, 3 instance units + 1 generic obligations package |

98 library lines replace 36 transparent lines in one instance. The library
is nonetheless small and readable. Its 7 public entities each have
a one-line meaning, and its two proofs (model loop, pigeonhole) are the
Task 003 proofs, generalised over index/identity types.

### Generic actuals `A = 4`

```ada
package Free_Prefix is new SPARK_Refine_Prefix_Sets
  (Element_Type  => Object_Id,     --  identity universe (finite, discrete)
   Index_Type    => Object_Id,     --  storage positions
   Storage_Array => Free_Array,    --  array (Index_Type) of Element_Type
   Element_Sets  => Id_Sets);      --  the caller's existing Functional.Sets instance
```

Capacity and universe size are **not** actuals: they are derived from
`Index_Type` and `Element_Type`. The caller's public `Id_Sets` instance is
reused through a formal package, so no second set type exists and the public
abstraction is unchanged.

## 4. Ada / SPARK / GNATprove generic limitations encountered

| # | Attempt | Result | Workaround | Per-instance SLOC cost |
|---|---|---|---|---:|
| G1 | Library package declared `Ghost` (cleanest intent) | **Rejected:** `error: ghost package expected for actual` at `fixed_pool.ads:65:24` (`Element_Sets => Id_Sets`); `formal "Element_Sets" was declared as ghost at spark_refine_prefix_sets.ads:40`. A ghost generic makes its formal package ghost, and the caller's public `Id_Sets` instance is not ghost. | Non-ghost generic package whose every entity carries `Ghost` (7 aspects, library side). | **0** |
| G2 | Instance in the **private part** of `Fixed_Pool`, used by the `Type_Invariant` of the private type (section 17, first choice after the body, which cannot see the invariant) | **Works.** No diagnostic. The invariant expression is a call to a generic-instance expression function, which GNATprove inlines. | none | 0 |
| G3 | Formal package over the caller's own `SPARK.Containers.Functional.Sets` instance (section 11) | **Works**, with `Equivalent_Elements => "=", others => <>`. | Restriction: the caller's set must use predefined equality (all pools with discrete identities do). | 0 |
| G4 | Separate index and identity types (section 13) | **Works** (validation instances use `Slot /= Id`). | `Count_Type` is a subtype of `Index_Type'Base`. When index and count types differ, the caller's count must be of that type. The pool's `Pool_Count` (a `Natural` subtype) is compatible because its index type is a `Positive` subtype. | 0 here |
| G5 | A function's postcondition is only available where its precondition is proved | **Behavioural, not blocking.** Removing the invariant (`residual_no_invariant`) now fails 8 checks instead of the manual 2, because `Model`'s contract becomes unusable once `Is_Unique` is unknown. | none needed for the positive proof. Affects diagnostics (section 8). | 0 |
| G6 | Proof reuse | GNATprove re-proves the generic body **per instance** (46 library VCs in the pool; 32–35 per validation instance). Authoring is reused; proof execution is not. | inherent | 0 |

**No GNATprove limitation forced per-instance glue.** No `LIBRARY BLOCKED`
condition arose.

## 5. Independent validation instances (sections 22/23)

`proof_patterns/validation/` instantiates the library three times with
actuals different from the pool's. A generic obligations package then
proves, per instance: empty prefix → empty model; push of a fresh
identity preserves uniqueness and yields `Add` (with `Count < Universe_Size`
from `Model` alone); pop yields `Remove`; missing identity → short prefix;
`Lemma_Can_Add` on arbitrary sets.

| Instance | Identity universe | Storage index | Purpose |
|---|---|---|---|
| `Validate_Capacity_1` | `range 7 .. 7` (1 value, lower bound ≠ 1) | `range 1 .. 1` | extreme small |
| `Validate_Offset_Large` | `range -50 .. 149` (200 values, negative lower bound) | `range 0 .. 199` (distinct type) | larger, offset, index ≠ identity |
| `Validate_Enum_Overcapacity` | enumeration `(Red, Green, Blue)` | `range 10 .. 14` (5 > 3 positions) | non-integer identity; storage larger than universe, so the pigeonhole bound is the only capacity fact |

Result (`check_proof_results.py library-validation`): **356/356 proved,
0 unproved, 0 justified**, 5.6 s wall. Library VCs per instance: 34 / 35 / 32.

The claim is limited to these 3 validation instances plus the pool's 1.
The library is **not** claimed to be proved for all possible instances.

## 6. Prover matrix (single prover, `--level=2` limits, nothing raised)

| Prover | Manual Task 003 | Library-backed Task 004 |
|---|---|---|
| CVC5 only | 130/136: lemma `VC_ASSERT`, `VC_INVARIANT_CHECK` Allocate/Release, `VC_POSTCONDITION` Allocate/Initialize, `VC_PRECONDITION@Free_Model`; 1.6 s | 156/161: `VC_INVARIANT_CHECK` Allocate/Release, `VC_POSTCONDITION@Allocate` (app); `VC_POSTCONDITION@Free_Prefix.Model` (`spark_refine_prefix_sets.ads:91`, room clause), `VC_PRECONDITION@Free_Prefix.Model` (`…adb:47`, `Add`) (library); 1.8 s |
| Z3 only | 135/136: lemma `VC_ASSERT` (`fixed_pool.adb:45`); 6.6 s | 160/161: `VC_POSTCONDITION@Free_Prefix.Model` (`spark_refine_prefix_sets.ads:91`, room clause); 6.8 s |
| Alt-Ergo only | **136/136**, max 7 553 steps (lemma assert); 1.7 s | **161/161**, max 917 steps (`Allocate` post); 1.8 s |
| Validation instances | n/a | CVC5 344/356 (12, all library `Model`); Z3 **356/356**; Alt-Ergo **356/356** |

Encapsulating the proof in a library does **not** remove prover
fragility. The pool still needs Alt-Ergo, and the one Z3-unproved VC is now
the library's finite-universe consequence. What changes:

* the fragile VC is in library source, written and tuned **once** by the
  library author;
* the application developer never writes, sees or chooses a prover for it
  (Z3 proves the same library VC in all 3 validation instances, so the
  fragility is instance-dependent);
* the racing-portfolio peak drops from 7 553 to 294 steps. The pigeonhole
  proof builds its universe with a loop instead of through `Free_Model`.

## 7. Negative fixtures: diagnostic comparison (section 28)

L1–L5 apply **byte-identical** edits to P1–P5. L6 is the adapter
equivalent of P6 (see `fault.toml`).

| Fault | Manual (rule @ entity, location) | Library-backed (rule @ entity, location) |
|---|---|---|
| duplicate active identity | P1: `VC_INVARIANT_CHECK@Initialize` (`fixed_pool.ads:38`) | L1: same (`fixed_pool.ads:39`) |
| Allocate keeps Top | P2: `VC_POSTCONDITION@Allocate` (`ads:46`) | L2: same (`ads:47`) |
| Allocate wrong identity | P3: `VC_POSTCONDITION@Allocate` (`ads:46`) | L3: same (`ads:47`) |
| Release wrong identity | P4: `VC_INVARIANT_CHECK@Release` + `VC_POSTCONDITION@Release` | L4: same |
| Release duplicate | P5: `VC_INVARIANT_CHECK@Release` (`ads:50`) | L5: same (`ads:51`) |
| wrong model mapping | P6: `Free_Count`, `Initialize`, `Is_Exhausted`, `Is_Free` posts **+ `VC_ASSERT@Lemma_Universe_Bound` (`fixed_pool.adb:46`)** | L6: `Free_Count`, `Initialize`, `Is_Exhausted`, `Is_Free` posts, all in `fixed_pool.ads` |

(Line numbers differ by one because of the `private with` line.)

* **Easier or harder to understand?** Same or easier. Every application
  fault is reported at the same `(rule, entity)` in the application's own
  spec. **No application fault moved into generic source.** L6 is cleaner
  than P6: the manual lemma used `Free_Model` as its universe witness, so a
  wrong model also broke the unrelated lemma. The library lemma is
  independent of the application model.
* **Failures inside generic source** appear only when the library itself
  is wrong (library ablations, section 9). GNATprove then reports
  `spark_refine_prefix_sets.adb:47 … in instantiation at fixed_pool.ads:61`
  with SARIF entity `Fixed_Pool.Free_Prefix.Model`. The chain is enough to
  trace the failure to the instance. It points at library internals that
  an application developer should not need to fix.
* **One confusing message:** without the invariant, GNATprove reports
  `precondition might fail` at the adapter (`fixed_pool.adb:10`) “in inlined
  expression function body at spark_refine_prefix_sets.ads:71, in
  instantiation at fixed_pool.ads:61”. It suggests “subprogram at
  fixed_pool.ads:20 should mention P in a precondition”. The real fix is the
  missing invariant, so the hint is misleading. This is a diagnostics
  opportunity, not a library defect.

## 8. Invariant masking (section 29)

| Fixture | Normal run (library-backed) | Invariant removed (`mask_l*`) | Masked functional failure? | Manual equivalent |
|---|---|---|---|---|
| L1 | `VC_INVARIANT_CHECK@Initialize` only | 9 failures incl. `VC_POSTCONDITION@Initialize` | **yes** (same as P1) | P1: yes |
| L4 | `VC_INVARIANT_CHECK@Release` + `VC_POSTCONDITION@Release` | 8 failures incl. `VC_POSTCONDITION@Release` | no (already visible) | P4: no |
| L5 | `VC_INVARIANT_CHECK@Release` only | 8 failures incl. `VC_POSTCONDITION@Release` | **yes** (same as P5) | P5: yes |

The library leaves masking exactly as it was: the same 2 of 3 invariant
faults hide a false functional postcondition. Masking is a property of
GNATprove's treatment of type invariants, not of how the invariant is
authored. The *location* is unchanged (application spec). The generic
source never appears in the normal masked diagnostics.

The secondary signal is **noisier**: the ablated baseline itself fails
8 checks instead of 2 (G5). The library contract of `Model` is guarded by
`Is_Unique`, so every model-dependent public post fails. This makes the
“remove the invariant to see what it hides” technique less useful by hand.
It strengthens the case for a tool that does this differential diagnosis
automatically.

## 9. Ablation

### Residual per-instance artifacts (section 36)

| Case | Result | Necessary? |
|---|---|---|
| `residual_no_invariant` | 8 unproved (`Free_Model` pre, `Free_Count`, `Is_Free`, `Is_Exhausted`, `Allocate` pre/post, `Release` post, `Release` range) | **yes** |
| `residual_no_top_default` | `VC_INVARIANT_CHECK_ON_DEFAULT_VALUE@Fixed_Pool` | **yes** |
| `residual_local_quantified_invariant` (manual 4-line quantifier instead of `Is_Unique`) | 0 unproved | equivalent: the library predicate saves 3 SLOC |
| `residual_with_explicit_lemma_call` (re-add `Lemma_Can_Add` in `Release`) | 0 unproved | **unnecessary**, so removed from `R` |
| instantiation, `private with`, adapter | required for compilation / are the model | yes |

### Library internals (section 37; pool **and** validation instances)

| Case | Pool unproved | Validation unproved | Necessary for |
|---|---:|---:|---|
| `lib_no_model_precondition` (`Pre => Is_Unique`) | 1 | 2 | uniqueness reasoning (`Add` pre in loop) |
| `lib_no_model_post_cardinality` | 2 | 0 | pool (`Free_Count`, public `Free_Model` bound) |
| `lib_no_model_post_membership` | 5 | 11 | both |
| `lib_no_model_post_room` (finite-universe clause) | 1 (`Release` range check) | 1 | both |
| `lib_no_model_loop_invariant_cardinality` | 1 | 2 | both |
| `lib_no_model_loop_invariant_membership` | 2 | 4 | both |
| `lib_no_universe_lemma_in_model` | 1 | 1 | both |
| `lib_no_num_overlaps_assert` | 1 | 1–3 | both (pigeonhole step) |
| `lib_no_universe_loop_invariants` | 3 | 7 | both |
| `lib_no_can_add_body` | 1 | 3 | `Lemma_Can_Add` contract (exported API) |

Every library fact is necessary in at least one representative instance.
Cardinality is used only by the pool among these instances, which is
expected: it is part of the pattern's intended contract (`Length = Count`).

## 10. Performance (section 38)

| | Manual | Library-backed | Δ |
|---|---:|---:|---:|
| Total checks | 136 | 161 | +25 (+18 %) |
| Wall, gate (`--level=2 -j0`, 3 runs) | 1.83–1.88 s | 2.15–2.17 s | +0.3 s (+16 %) |
| Max prover steps (portfolio) | 7 553 | 294 | −96 % |
| Alt-Ergo-only wall | 1.7 s | 1.8 s | ≈ |
| Z3-only wall | 6.6 s | 6.8 s | ≈ |
| Validation instances (3, separate gate) | — | 356 checks, 5.6 s | new CI cost |

Memory was not measured separately; the host has no `/usr/bin/time`. There
is no proof-time explosion. The extra checks are the per-instance re-proof
of the library body (46 VCs) minus local model VCs no longer needed.

## 11. Developer experience (sections 41/42)

| Question | Manual | Library-backed |
|---|---|---|
| Proof concepts the developer must understand | prefix uniqueness, derived model, `Refined_Post` refinement, loop invariants for set construction, pigeonhole via `Num_Overlaps`, prover choice | “my active stack prefix is unique” and “the model is the prefix as a set” (2) |
| Ada generic syntax written | none | 1 `private with` + 1 instantiation with 4 named actuals |
| Must understand the pigeonhole proof? | **yes** (took 4 attempts in Task 003) | **no**: not even a lemma call is written |
| Must design model loop invariants? | yes (2) | **no** |
| Must write quantified prefix membership? | yes (`Refined_Post`, loop invariant, 4-line uniqueness invariant) | **no**: `Is_Unique` / `Model` contract |
| Needs to know only Alt-Ergo proves the hard VC? | yes | no; the library author does (and CI gates it) |
| Instantiation diagnostics understandable? | n/a | yes for application faults (never located in generic source); library-internal faults carry an `in instantiation at` chain |
| Experienced SPARK developer preference | — | likely library-backed: 10 lines of intent instead of 36 of proof engineering; full proof still visible and re-checked |
| Newer SPARK developer: fewer architecture mistakes? | — | yes: the two Task 003 traps (`Dynamic_Predicate` vs `Type_Invariant`, one-directional membership) collapse into choosing the documented `Type_Invariant => Is_Unique` line; the pigeonhole trap disappears |

What the library does **not** remove: choosing `Type_Invariant` (and the
`Top := 0` default), knowing that the model must be derived from
`(Storage, Count)`, and invariant masking in diagnostics.

## 12. Pre-registered decision

```text
PIVOT          needs R <= 10 and soundness/reuse gates pass : R = 10  -> yes
                 soundness: 0 assume/axiom/justification, 0 unproved   -> yes
                 reuse: 3 independent validation instances prove        -> yes
                 public API: 0 token changes, client proof unchanged    -> yes
GENERATOR CASE needs R >= 25 or library blocked            : false     -> no
REVIEW         needs 11 <= R <= 24                         : false     -> no
=> PIVOT (at the boundary; see sensitivity in section 1)
```

> For this pattern, a reusable SPARK proof library eliminates enough
> per-instance proof engineering that source generation is not justified.

The margin is zero, so the decision rests on the pre-registered rule, not
on a large gap. The qualitative evidence points the same way: the residual
10 lines contain no loop invariant, lemma, assertion, quantifier or
`Refined_Post`, and about half of them are configuration.
