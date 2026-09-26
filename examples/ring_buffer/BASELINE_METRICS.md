# Task 001 — Manual Ring-Buffer Proof Baseline: Measurements

This file records what it actually cost to prove, by hand, that a fixed-array
`Content + First + Length` circular buffer implements a mathematical sequence.
It is the evidence base for Task 002. All numbers are reproducible with the
commands in [Reproduction](#reproduction).

## 1. Toolchain

| Item | Value |
|---|---|
| Alire | `alr 2.1.1` (CI: `alire-project/setup-alire@v6.0.0`, `version: 2.1.1`) |
| Compiler | `gnat_native 16.1.0` (GNAT 16.1.0, FSF) |
| GNATprove | `gnatprove 16.1.0` (`FSF 16.1.0`, Why3 1.8.2+git) |
| SPARKlib | `sparklib 16.1.0` (AdaCore/SPARKlib `6d13c714`), `SPARKLIB_MODE=full` |
| gprbuild | `gprbuild 26.0.1` |
| Provers shipped | CVC5 1.3.2, Z3 4.15.4, Alt-Ergo 2.6.1 |
| Host | Linux x86_64 (local: 32 cores; CI: `ubuntu-latest`) |

All four crates are pinned with `=` constraints in
[`alire.toml`](alire.toml). Alire 2.x writes the solved lockfile to
`alire/alire.lock` (the `alire/` directory is ignored repository-wide); with
every dependency exact-pinned the solution is fully determined by
`alire.toml`. The pair `gnat_native 16.1.0` / `gnatprove 16.1.0` resolved
cleanly locally and is what `sparklib 16.1.0` requires (`gnat >= 16`,
forbids `gnatprove < 16`). The host's system GNAT 14.2 is not used.

## 2. Proof configuration

Set once in `ring_buffer.gpr` (`package Prove`) so interactive and gated runs
are identical:

```text
-U --mode=all --level=2 --no-loop-unrolling --report=statistics
--checks-as-errors=on --warnings=error            (+ -j0 on the command line)
```

`--level=2` in GNATprove 16.1.0 expands to (observed with `-d`):
`--prover cvc5,z3,altergo --timeout 5 --steps 0 --memlimit 1000
--proof per_check`. No timeout or step value was set explicitly and no
prover resources were raised.

`--no-loop-unrolling` is deliberate: with the static `Max_Size = 16` the
model-construction loop can otherwise be unrolled, which makes the proof
succeed **without** the loop invariants. That is an artefact of the small
constant (with `Max_Size = 1024` the invariants are required again, see §7),
and would under-report the proof cost of any realistic capacity. The
baseline therefore measures the invariant-based proof.

## 3. Positive proof result

Extracted from `obj/baseline/gnatprove/gnatprove.sarif` and cross-checked
against the `.spark` files by `scripts/check_proof_results.py positive`
(written to `obj/baseline/proof_summary.json`):

| Metric | Value |
|---|---|
| Units analysed | `Ring_Buffer`, `Ring_Buffer_Client_Proof` (+ SPARKlib instantiation checks) |
| Total checks | **116** |
| Proved | **116** (flow 40, provers 76) |
| Unproved | **0** |
| Justified | **0** |
| `pragma Assume` analysed | 0 |
| Flow errors / warnings | 0 / 0 |
| Max prover steps for any check | 73 |
| Checks taking > 1 s | none |
| Wall time (`-j0`, 32 cores, clean) | ≈ 2.0 s (≈ 1.6 s at `--level=0`) |

Break-down (`gnatprove.out`): data dependencies 11, initialization 8,
run-time checks 9, assertions 10, functional contracts 57, termination 21.

The same baseline also proves at `--level=0`, `1` and `3` (checked
separately); level 2 is the configured gate.

### Allowed foundation warnings (not unproved checks)

GNATprove emits 6 identical informational warnings
`function Is_Valid is assumed to return True` located in the GNAT runtime
file `a-nbnbin.ads` (`Ada.Numerics.Big_Numbers.Big_Integers`), reached via
SPARKlib's `Functional.Vectors.Length`/`Big`. This is part of the accepted
external proof foundation (see §9). The gate allow-lists exactly this
(rule, file, message) triple; any other warning fails the gate.

## 4. Code classification

SLOC = non-blank, non-comment source lines. Produced by
`python3 scripts/proof_inventory.py` from the anchored line ranges in
[`proof_inventory.toml`](proof_inventory.toml); the script fails if a range
drifts, overlaps, or the three groups stop partitioning the package.

| Group | SLOC | Contents |
|---|---:|---|
| Production implementation | **54** | package/record/type declarations, `Physical_Index`, `Is_Empty`, `Is_Full`, `Initialize`, `Clear`, `Push`, `Pop`, `Peek` (specs + bodies) |
| Authoritative abstract specification | **19** | `with SPARK...Functional.Vectors`, `Sequences` instantiation, public ghost `Model` + capacity bound, all public `Pre`/`Post` |
| Mechanical proof/refinement support | **19** | `Model` body, its `Refined_Post`, its 2 loop invariants (the operations themselves need no `Refined_Post`) |
| **Package total** (`ring_buffer.ads` + `.adb`) | **92** | |
| Client abstraction proof (`proof/`) | 36 | not counted above; a test, not support |
| Runtime tests (`tests/`) | 175 | not counted above |

### Production implementation (54 SLOC)

Includes `Physical_Index`. It is **not** proof-only: `Push` and `Pop` call it
to compute the physical slot, and a hand-written ring buffer would have the
same modulo expression inline. The model reuses it, which is why no separate
proof-only index mapping exists.

### Authoritative abstract specification (19 SLOC)

Developer-owned requirement, **not** a generator target:

| Entity | SLOC | Note |
|---|---:|---|
| `with SPARK.Containers.Functional.Vectors` | 1 | model foundation |
| `Sequences` instantiation + `use type` | 4 | abstract sequence type |
| `Model` (ghost) + `Post => Last (Model'Result) <= Max_Size` | 3 | public abstraction; the bound is part of the requirement "bounded queue" |
| `Is_Empty` / `Is_Full` `Post` | 2 | `Is_Empty = (Last (Model) = 0)`, `Is_Full = (Last (Model) = Max_Size)` |
| `Initialize` / `Clear` `Post` | 2 | `Model (B) = Empty_Sequence` (exact equality) |
| `Push` `Pre`/`Post` | 2 | `Model (B) = Add (Model (B)'Old, E)` |
| `Pop` `Pre`/`Post` | 3 | `E = Get (Model'Old, 1) and Model = Remove (Model'Old, 1)` |
| `Peek` `Pre`/`Post` | 2 | `E = Get (Model, 1)`; `B` is mode `in` |

`Remove (S, 1)` from SPARKlib **is** the tail operation; no custom `Tail`
helper was needed.

### Mechanical proof/refinement support (19 SLOC) — the automation target

| Category | SLOC | Decls / pragmas | Entities | Why needed | Generic to circular buffers? | App-specific? |
|---|---:|---:|---|---|---|---|
| model construction | 9 | 1 function body | `Ring_Buffer.Model` (body) | A derived ghost model must be computed from the representation. | **yes** – `for J in 1 .. Length: R := Add (R, Content (Map (First, J-1)))` | no |
| auxiliary operation-refinement contract (abstraction relation) | 5 | 1 aspect | `Model'Refined_Post` | Exposes `Last (Model) = Length` and `Get (Model, K) = Content (Physical_Index (First, K-1))` to the operation bodies. Without it all 7 operation postconditions fail (§7). | **yes** | no |
| loop invariant | 5 | 2 `Loop_Invariant` | in `Model` | `Last (R) = J` (length) and the element-wise prefix property; each is necessary (§7). | **yes** | no |
| representation predicate | **0** | 0 | — | Not needed: the Ada subtypes `Storage_Index` and `Buffer_Length` already carry every range fact, and `Physical_Index` returns `Storage_Index`. | — | — |
| logical/physical index mapping used only for proof | **0** | 0 | — | `Physical_Index` is production code. | — | — |
| helper lemma | **0** | 0 | — | No lemma was required; not even for wraparound (§6). | — | — |
| proof-only state update | **0** | 0 | — | Derived model; no ghost field to update. | — | — |
| other | **0** | 0 | — | — | — | — |
| **Total** | **19** | | | | | |

### Structural counts

| Metric | Count |
|---|---:|
| Ghost declarations written by hand | 1 (`Model`) |
| Ghost package instantiations | 1 (`Sequences`, used only from ghost/contract context; GNAT 16 rejects `Ghost` on an instantiation) |
| Lemmas | 0 |
| Explicit loop invariants | 2 |
| Loop variants | 0 |
| Refined postconditions | 1 |
| Type invariants / predicates | 0 |
| Assertions in the package | 0 |
| Public behavioural contracts | 3 `Pre` + 8 `Post` on 8 public subprograms |
| Proof-only helper functions | 0 (the one ghost function is the model itself) |
| Client-proof assertions | 6 (in 2 client procedures) |
| VC/check count | 116 |
| Proof wall time | ≈ 2.0 s |

## 5. The three obligations that needed the most human reasoning

There was little prover difficulty. The maximum was 73 steps, nothing took
more than 1 s, and every check proved at level 0. The effort that did exist
was in **deciding what to state**. In decreasing order:

### D1. Connecting operation bodies to the derived model (`Model'Refined_Post`)

* **Property:** the postconditions of `Push`, `Pop`, `Peek`, `Clear`,
  `Initialize`, `Is_Empty` and `Is_Full` (e.g.
  `Model (B) = Add (Model (B)'Old, E)`).
* **Why the prover could not establish it:** `Model` is a function with a
  loop body. Outside that body the prover only knows its contract. With no
  contract relating the sequence to `Content/First/Length`, all 7 operation
  postconditions are unprovable (ablation `no_refined_post`, §7).
* **Manual artifact:** the element-wise abstraction relation, stated once as
  `Refined_Post` on `Model`:
  `Last (Model) = Length and (for all K in 1 .. Length => Get (Model, K) = Content (Physical_Index (First, K - 1)))`.
  After this, `Push` and `Pop` proved **with no further help**, including
  wraparound and the `Remove (S, 1)` shift.
* **Reusable/generic?** Yes. The formula is fully determined by the manifest
  roles `storage`, `first`, `length` and `capacity` plus the index origin.
* **Should spark-refine generate it?** **Yes.** This is the most valuable
  single artifact: 5 SLOC that unlock every refinement proof.

### D2. Proving the derived model construction (`Model` loop invariants)

* **Property:** `Model` satisfies its own `Refined_Post`, and each
  `Sequences.Add` call satisfies its precondition.
* **Why the prover could not establish it:** it is a loop. Without
  unrolling, it needs an inductive statement of what `R` holds after `J`
  iterations. Removing `Last (R) = J` loses the `Add` precondition and the
  element invariant cannot be preserved. Removing the element invariant
  loses the `Refined_Post` (§7).
* **Manual artifact:** 2 `Loop_Invariant`s. They are exactly D1 restricted
  to the prefix `1 .. J`.
* **Reusable/generic?** Yes. They are mechanically derivable from D1 by
  replacing `Length` with the loop variable.
* **Should spark-refine generate it?** **Yes, together with D1**, as one
  unit: model body + `Refined_Post` + prefix invariants.

### D3. Making the public abstraction usable by clients

* **Property:** the client proofs. `Push_Push_Pop` must show `not Is_Full`
  before the second `Push`. `Rotate` must show that `Push` is allowed after
  `Pop` on an *arbitrary* non-empty queue.
* **Why the prover could not establish it:** the first draft gave
  `Is_Empty`/`Is_Full` no contract; they were expression functions over
  private fields, invisible to clients, so no client could prove any
  operation precondition (`no_is_empty_post` / `no_is_full_post`, §7). A
  second gap: without a public statement that the model never exceeds
  `Max_Size`, a client cannot conclude `not Is_Full` after `Pop`
  (`no_public_model_bound`).
* **Manual artifact:** `Post` on `Is_Empty`/`Is_Full` relating them to
  `Last (Model)`, and `Post => Last (Model'Result) <= Max_Size` on `Model`.
* **Reusable/generic?** These are **specification**, counted as
  authoritative spec rather than support. They state what "empty", "full"
  and "bounded" mean. The reasoning needed to find them is generic, though:
  every bounded-sequence pattern needs them.
* **Should spark-refine generate it?** **No, it should check for them.** The
  requirement belongs to the developer, but a future `validate` could warn
  when a `circular_sequence` refinement's empty/full predicates have no
  model-level postcondition, or no public capacity bound exists.

### What did **not** require reasoning, contrary to expectation

* **Wraparound:** no lemma, assertion or case split. The SMT solvers
  discharged the `mod` arithmetic of `Physical_Index` directly, covering the
  range, append-slot and `First`-advance obligations.
* **`Pop`'s tail/shift property:** SPARKlib characterises
  `Remove (Model'Old, 1)` via `Range_Shifted`. With D1 in place it proved
  automatically in ≤ 73 steps, the most expensive check in the baseline.
* **Range safety:** carried entirely by Ada subtypes; no representation
  predicate was needed.

## 6. Answers to the Task 001 questions

| Question | Evidence-based answer |
|---|---|
| Did `Functional.Vectors` work well as the abstract model? | **Yes.** `Add`, `Get`, `Last`, `Remove` and `Empty_Sequence` expressed every contract directly. `Remove (S, 1)` is the tail, so no custom helper was needed. Everything proves at level 0. Minor friction: `Length` returns `Big_Natural`, so contracts use `Last` (an index; `Last (S) = 0` means empty with index origin 1). It also brings 6 allowed `Is_Valid` foundation warnings (§9). No custom ghost sequence was tried, because none was needed. |
| Was a representation predicate needed? | **No.** Subtype constraints on `First` (`1 .. Max_Size`) and `Length` (`0 .. Max_Size`) suffice; this representation has no cross-field invariant. That may change for `Head + Tail + Count` (A3), where fields are redundant. |
| Which circular-index facts needed explicit proof? | **None** needed a lemma or assertion. The only index artifact is the production `Physical_Index` expression; all range and modulo facts proved automatically. |
| Was the derived model expensive or awkward? | **Neither.** 9 SLOC body + 5 SLOC `Refined_Post` + 5 SLOC invariants, with negligible proof time. The one subtlety is that loop unrolling hides the invariants at small capacities (§2, §7). |
| Were intermediate model layers necessary? | **No.** One layer (array → sequence) was enough. |
| Did proving wraparound dominate the effort? | **No.** It needed zero manual artifacts. The effort was D1 and D3. |
| How much proof-support code is generic? | **All of it: 19/19 SLOC.** Every mechanical artifact is determined by the manifest roles. None is application-specific. |

## 7. Ablation: each artifact is necessary

`python3 scripts/ablate_proof_support.py` removes one artifact at a time and
re-proves with the gate configuration. Results (`obj/ablation_summary.json`):

| Artifact removed | Proved | Unproved obligations (rule @ entity) |
|---|---:|---|
| none (baseline) | 116 | — |
| loop invariant `Last (R) = J` | 110 | `VC_LOOP_INVARIANT_PRESERV`, `VC_PRECONDITION` (`Add`), `VC_REFINED_POST` @ `Model` |
| loop invariant (elements) | 111 | `VC_REFINED_POST` @ `Model` |
| both loop invariants | 108 | `VC_PRECONDITION`, `VC_REFINED_POST` @ `Model` |
| `Model'Refined_Post` | 106 | `VC_POSTCONDITION` @ `Clear`, `Initialize`, `Is_Empty`, `Is_Full`, `Peek`, `Pop`, `Push` |
| public `Model` capacity bound | 114 | `VC_PRECONDITION` @ `Ring_Buffer_Client_Proof.Rotate` |
| `Is_Empty` `Post` | 109 | `VC_ASSERT`, `VC_PRECONDITION` @ `Push_Push_Pop`; `VC_PRECONDITION` @ `Rotate` |
| `Is_Full` `Post` | 111 | `VC_ASSERT`, `VC_PRECONDITION` @ `Push_Push_Pop`; `VC_PRECONDITION` @ `Rotate` |

The results are identical with `--extra-switch=--level=0`
(`obj/ablation_summary_level0.json`).

Loop-unrolling sensitivity, measured during development with the same
toolchain:

| Configuration | Invariants present | Result |
|---|---|---|
| `Max_Size = 16`, unrolling allowed | no | proves (loop unrolled) |
| `Max_Size = 16`, `--no-loop-unrolling` | no | fails (`Refined_Post`, `Add` precondition) |
| `Max_Size = 16`, `--no-loop-unrolling` | yes | proves (**gate**) |
| `Max_Size = 1024`, unrolling allowed | no | fails |
| `Max_Size = 1024`, unrolling allowed | yes | proves |

## 8. Negative fixtures

Each fixture is a single find/replace patch (`negative/<name>/fault.toml`)
applied to a scratch copy of `src/`. The gate
(`scripts/check_proof_results.py negative`) requires every listed
`(rule, entity)` to appear **unproved** in SARIF. A fixture that proves, or
fails elsewhere only, fails the gate. Observed (`obj/negative_summary.json`):

| ID | Fixture | Fault | Expected & observed unproved obligations |
|---|---|---|---|
| N1 | `wrong_append_slot` | `Push` writes to offset 0 instead of `Length` | `VC_POSTCONDITION @ Ring_Buffer.Push` (append relation) |
| N2 | `wraparound_off_by_one` | `mod (Max_Size + 1)` in `Physical_Index` | `VC_RANGE_CHECK @ Ring_Buffer.Physical_Index` |
| N3 | `capacity_overflow` | `Buffer_Length` widened to `0 .. Max_Size + 1` | `VC_RANGE_CHECK @ Ring_Buffer.Push` and `VC_POSTCONDITION @ Ring_Buffer.Model` (public capacity bound) |
| N4 | `wrong_pop` | `Pop` returns the last element (LIFO) | `VC_POSTCONDITION @ Ring_Buffer.Pop` |
| N5 | `wrong_model_order` | model built in physical order from slot 1 (reorders wrapped elements); `Refined_Post` and invariants changed consistently so `Model` itself proves | `VC_POSTCONDITION` @ `Ring_Buffer.Push`, `Ring_Buffer.Pop`, `Ring_Buffer.Peek` |

No fixture uses `pragma Assume` (checked by the trust scan). Each negative
run still proves 113–116 other checks, so the failures are localised.

Independent confirmation: building N4 with `-XRING_BUFFER_ASSERTIONS=on`
makes the runtime tests raise
`ASSERTION_ERROR : failed postcondition from ring_buffer.ads:42`.

## 9. Trust boundary

`scripts/check_proof_results.py trust-scan` searches `src/`, `proof/`,
`tests/` and every negative patch for `pragma Assume`, `Assume =>`,
`Annotate (GNATprove, False_Positive | Intentional)`, `Import`,
`pragma Warnings`, `pragma Suppress`, `SPARK_Mode => Off`,
`Skip_Proof`/`Skip_Flow_And_Proof`, Why3 `axiom` and `spark-refine: trust-me`.
**Result: 0 forbidden constructs.** The single exemption is
`SPARK_Mode => Off` on the executable test driver, which is not a proof
artifact. The positive gate also requires 0 justified checks and 0 analysed
`pragma Assume`.

Accepted external proof foundation (explicit, not hidden):

1. **SPARKlib `SPARK.Containers.Functional.Vectors` 16.1.0.** Its body is
   `SPARK_Mode => Off`. Its specification contracts (`Add`, `Get`, `Last`,
   `Remove`, `"="`, `Range_Shifted`, …) are the trusted axiomatisation of
   the mathematical sequence. GNATprove proves the instantiation checks
   (`Eq_Reflexive` etc.) as part of the 116.
2. **`Ada.Numerics.Big_Numbers.Big_Integers.Is_Valid`** (GNAT runtime,
   `Convention => Intrinsic`), which GNATprove assumes is `True`. It is
   reported as 6 warnings and allow-listed by exact match.
3. GNAT / GNATprove / Why3 / CVC5 / Z3 / Alt-Ergo, as for any SPARK proof.

## 10. Hypothesis assessment

**Hypothesis (docs/MVP.md):** a small refinement declaration can generate
enough correct proof scaffolding to *materially* reduce human-authored proof
support for a conventional bounded circular buffer, without adding trust.

**Classification: WEAKER.**

The evidence cuts both ways, but the net effect on the hypothesis as stated
is negative:

* **For:** 100% of the mechanical support (19/19 SLOC, 4 declarations or
  pragmas) is generic and fully determined by the existing manifest roles.
  Generation is clearly feasible and could reach 100% removal, above the
  50% target in `docs/METRICS.md`.
* **Against:** the absolute amount is tiny. 19 SLOC is 21% of a 92-SLOC
  package: one function body, one `Refined_Post`, two loop invariants.
  There are **no** lemmas, representation predicate, index-mapping helpers,
  wraparound proofs or intermediate model layers. SPARKlib
  `Functional.Vectors` plus current SMT solvers eliminate most of the
  machinery `docs/PROOF_PATTERNS.md` planned to generate (9 candidate
  lemmas → 0 needed). The existing manifest, `spark-refine.toml`, has
  **30 non-blank lines, more than the 19 SLOC it would replace**. Much of it
  is `emit_*` flags and operation mappings that this baseline shows are
  unnecessary. Even a minimal manifest (roles + pattern, ≈ 12 lines) would
  save only ≈ 7 lines. That is close to a stop criterion in
  `docs/BENCHMARKS.md` ("source annotations/configuration become more
  verbose than the proof machinery they replace"). Line counts understate
  the difficulty of *designing* D1/D2 for a non-expert, though (§5).
* **Where the effort actually was:** D1 and D2 are generatable. D3 was about
  making the *public* specification usable by clients, which is
  developer-owned; checking it may be more valuable than generating code.

The hypothesis is not refuted, but the case for `spark-refine` must now come
from what this baseline could not exercise:

* **representation refactor (A3):** does `Head + Tail + Count` need a
  representation predicate and lemmas? Redundant fields are the classic
  source of them;
* **larger or generic capacity**, where unrolling cannot help;
* **structures whose model does not map onto SPARKlib primitives**
  (pools/bitmaps, Benchmark B);
* **stored (shadow) ghost models**, which need proof-only updates.

## 11. Task 002 generation candidates

Generate as **one unit**, for `pattern = "circular_sequence"`,
`backend = "derived"`:

1. `Model` body: loop over `1 .. <length>` appending
   `<storage> (<index map> (<first>, J - 1))`.
2. `Model'Refined_Post`: `Last = <length>` and element-wise
   `Get (Model, K) = <storage> (<index map> (<first>, K - 1))`.
3. The two prefix loop invariants derived from (2).

Validation-only candidates, which should **not** be generated:

4. Warn if empty/full predicates have no model-level postcondition.
5. Warn if the public `Model` lacks a capacity bound.

Candidates that looked generic but should **not** be generated for this
representation (no evidence of need):

* a representation predicate (the manifest's
  `emit_representation_predicate = true` is unjustified here);
* the lemmas `Logical_To_Physical_In_Range`, `Advance_First_In_Range`,
  `Append_No_Wrap`, `Append_With_Wrap`, `Append_Preserves_Prefix`,
  `Remove_First_Preserves_Suffix`, `Model_Length_Equals_Concrete_Length`,
  `Empty_Equivalent`, `Full_Equivalent` (`emit_lemmas = true` is
  unjustified here);
* a proof-only logical→physical mapping: the production one is reused;
* operation `Refined_Post`s (`emit_refined_contracts`): the public contract
  proved directly.

No artifact turned out to be application-specific. The genuinely
application-specific content is the public contract (spec, 19 SLOC), which
stays developer-owned.

## Reproduction

From `examples/ring_buffer/` with Alire 2.1.1 on `PATH`:

```bash
alr -n update                                   # resolve pinned toolchain
alr -n build                                    # production build
./bin/ring_buffer_runtime_tests                 # runtime tests
alr -n build -- -XRING_BUFFER_ASSERTIONS=on     # contracts executed
./bin/assertions/ring_buffer_runtime_tests
python3 scripts/check_proof_results.py trust-scan
python3 scripts/check_proof_results.py positive # runs: alr -n exec -- gnatprove -P ring_buffer.gpr -j0 ...
python3 scripts/check_proof_results.py negative
python3 scripts/proof_inventory.py              # §4 numbers
python3 scripts/ablate_proof_support.py         # §7 numbers
```
