# Task 002 — Head/Tail/Count Representation Refactor: Measurements

This file compares two private representations of the same `Ring_Buffer`
public abstraction. Both are fully proved with the toolchain and switches
from Task 001.

| | Representation A (Task 001) | Representation B (Task 002) |
|---|---|---|
| Fields | `Content + First + Length` | `Content + Head + Tail + Count` |
| Location | `src/` | `variants/head_tail_count/` |
| Redundant state | none | `Tail` (always `Physical_Index (Head, Count)`) |

Controls held fixed:

* the public specification (checked token by token);
* the client proof (`proof/`, byte-identical to base `0f6da97`);
* the runtime tests (`tests/`, byte-identical);
* the abstract model (`SPARK.Containers.Functional.Vectors`, derived, not
  stored);
* the toolchain (Alire 2.1.1, gnat_native/gnatprove/sparklib 16.1.0,
  gprbuild 26.0.1) and proof switches
  (`-U --mode=all --level=2 --no-loop-unrolling --report=statistics
  --checks-as-errors=on --warnings=error`, plus `-j0`).

Every number is reproducible with the commands in
[Reproduction](#reproduction).

## 1. Headline comparison

| Metric | First + Length (A) | Head + Tail + Count (B) |
|---|---:|---:|
| Production SLOC | 54 | 58 |
| Authoritative specification SLOC | 19 | 19 (identical text) |
| **Mechanical proof-support SLOC** | **19** | **21** |
| &nbsp;&nbsp;model construction | 9 | 9 |
| &nbsp;&nbsp;representation invariant | 0 | **2** |
| &nbsp;&nbsp;helper lemma | 0 | 0 |
| &nbsp;&nbsp;loop invariant | 5 | 5 |
| &nbsp;&nbsp;refined contract (`Model'Refined_Post`) | 5 | 5 |
| &nbsp;&nbsp;operation-specific refined contracts | 0 | 0 |
| &nbsp;&nbsp;proof-only index mapping | 0 | 0 |
| &nbsp;&nbsp;proof-only state update | 0 | 0 |
| Explicit proof assertion SLOC (in package) | 0 | 0 |
| GNATprove total checks | 116 | 134 |
| Unproved | 0 | 0 |
| Justified | 0 | 0 |
| `pragma Assume` analysed | 0 | 0 |
| Proof wall time (`-j0`, 32 cores, clean) | ≈ 2.0–2.4 s | ≈ 2.1–2.8 s |
| Slowest single check | < 0.1 s | < 0.1 s (0.21 s Alt-Ergo-only) |
| Max prover steps, single prover (deterministic, §3) | CVC5 2 · Z3 2 · Alt-Ergo 1673 | CVC5 2 · Z3 714 · Alt-Ergo 3406 |
| Max prover steps, gate run (`--level=2`, racing) | nondeterministic: 2–73 observed | nondeterministic: 2–152 observed |

SLOC means non-blank, non-comment lines, as reported by
`python3 scripts/proof_inventory.py --all`. `Physical_Index` counts as
production code in both representations. It is the same expression
function, byte-identical. In B the production code calls it to advance
`Head` and `Tail`.

The 18 extra checks in B all come from the representation invariant:

* 17 `VC_INVARIANT_CHECK`, on exit from every public subprogram that takes
  a `Buffer`, including `in`-mode `Is_Empty`, `Is_Full` and `Peek`;
* 1 `VC_INVARIANT_CHECK_ON_DEFAULT_VALUE`, which confirms that the default
  components `Head = Tail = 1, Count = 0` satisfy the invariant.

All other per-rule counts are identical to A.

## 2. The representation invariant

```ada
type Buffer is record
   Content : Storage_Array := [others => 0];
   Head    : Storage_Index := Storage_Index'First;
   Tail    : Storage_Index := Storage_Index'First;
   Count   : Buffer_Length := 0;
end record
with Type_Invariant =>
  Buffer.Tail = Physical_Index (Buffer.Head, Buffer.Count);
```

This is exactly the relation from the task statement. It is stated once,
privately, over the production `Physical_Index`. Nothing else was needed:

* range facts (`Count <= Max_Size`, indices in `1 .. Max_Size`) still come
  from the subtypes, as in A;
* `Count` distinguishes empty from full. `Is_Empty` and `Is_Full` are
  still `Count = 0` and `Count = Max_Size`. No clause about `Head = Tail`
  was needed or added, because it follows from the relation:
  `Physical_Index (H, 0) = Physical_Index (H, Max_Size) = H`.

### Approaches attempted, in order

| # | Mechanism | Result |
|---|---|---|
| 0 | none (Task 001 support with fields renamed) | 115 proved, **1 unproved**: `VC_POSTCONDITION @ Ring_Buffer.Push` (the append relation). Every other operation proves, including `Pop`. |
| 1 | `Type_Invariant` on the private full view | **134/134 proved.** Kept. |
| 2 | `Dynamic_Predicate` on the same record, with the component-wise updates unchanged | 122 proved, 4 unproved: `VC_PREDICATE_CHECK` @ `Clear` (×2), `Push`, `Pop`. A predicate is checked after every component assignment, and updating `Head`, `Tail` and `Count` one field at a time passes through inconsistent intermediate states. |
| 3 | `Dynamic_Predicate` with whole-record updates (`B := (B with delta ...)`) in `Clear`, `Push`, `Pop` | 122/122 proved. Legal and the same size, but it reshapes production code around a proof mechanism. |

`Type_Invariant` was chosen because it:

* is legal SPARK;
* is private to the representation and checked only at the package
  boundary, which is where the relation belongs;
* states exactly one relation;
* leaves the production code with natural field-by-field updates.

Approach 3 is recorded because `Dynamic_Predicate` is the other standard
mechanism. It works, but it is less idiomatic here and more invasive.

A private ghost `Valid_Representation` function plus `Pre`/`Post` on every
operation was not tried. It encodes the same thing as a `Type_Invariant`
and would cost a ghost function and at least 8 contract clauses. The task
says not to choose the most verbose form.

## 3. Proof effort

Under the gate configuration, prover steps are **not a stable metric**.
`--level=2` races CVC5, Z3 and Alt-Ergo, records the winner's steps, and
the winner varies between identical runs. Three identical gate runs
reported a maximum of 2, 58 and 2 steps for A, and 143, 152 and 46 for B.
Task 001's recorded "73 steps" is one such sample.

The gate still records `max_prover_steps` and `most_expensive_checks` in
`proof_summary.json` as a measurement. The comparison below uses
single-prover runs instead, which are deterministic across repeats (each
configuration was run at least twice):

| Prover only | A: proved / max steps (check) | B: proved / max steps (check) |
|---|---|---|
| `--prover=cvc5` | 116/116, 2 | 134/134, 2 |
| `--prover=z3` | 116/116, 2 | 134/134, **714** (`Pop` postcondition) |
| `--prover=altergo` | 116/116, 1673 (`Pop` postcondition) | 134/134, **3406** (`Push` postcondition) |

Every check in both representations proves with **each prover on its
own**. B's `Push` and `Pop` postconditions are measurably harder for Z3
and Alt-Ergo, because the invariant adds a `mod` equation to the
hypotheses. They are still far from any limit: at most 0.21 s per check
with Alt-Ergo alone. For CVC5, neither representation needs any real
search.

The invariant checks themselves cost Alt-Ergo 135–653 steps each (at
`Initialize`, `Clear`, `Push`, `Pop`) and CVC5/Z3 one step.

The proof also succeeds at `--level=0`, `1`, `2` and `3`, and with
`Max_Size = 17` and `1000` (a non-power of two and a large capacity), with
no change to the proof support.

## 4. The two central proof questions

### Push: `Content (Tail)` vs the abstract append slot

Production `Push` writes `Content (Tail)`. The derived model's next slot is
`Physical_Index (Head, Count)`. Without the invariant the prover has no
link between the two, so `Model (B) = Add (Model (B)'Old, E)` is
**unprovable** (approach 0 above; ablation `no_type_invariant`).

**Needed: the representation invariant only.** Once
`Tail = Physical_Index (Head, Count)` is assumed on entry, the append
postcondition proves with no assertion, no lemma, no `Refined_Post` on
`Push` and no extra precondition. The exit check,
`Physical_Index (Tail, 1) = Physical_Index (Head, Count + 1)` across the
wrap, also proves automatically.

Control experiment (ablation `control_push_ignores_tail_no_invariant`):
when `Push` writes `Content (Physical_Index (Head, Count))` and ignores
`Tail`, which the task rules out for production code, everything proves
with **no invariant** (116/116). The invariant is therefore needed exactly
because production code *reads* the redundant field. Maintaining a
redundant field costs nothing; reading it costs the invariant.

### Pop: preserving the invariant while `Tail` stays unchanged

After `Pop`: `Head' = Physical_Index (Head, 1)`, `Count' = Count - 1`,
`Tail' = Tail`. GNATprove must show
`Tail = Physical_Index (Physical_Index (Head, 1), Count - 1)` given
`Tail = Physical_Index (Head, Count)` and `Count >= 1`. That is
`((h + 1) mod N + c - 1) mod N = (h + c) mod N`.

**Needed: nothing.** No lemma, no assertion, no `Refined_Post`. It proved
automatically on the first attempt. The `VC_INVARIANT_CHECK` at `Pop` costs
CVC5/Z3 one step and Alt-Ergo 494 steps. `Pop`'s functional postcondition
does not involve `Tail`, so it is the same proof as in A, with one extra
hypothesis.

Modulo arithmetic and wraparound therefore **still prove automatically** in
B. That includes composing two `mod` operations, which is exactly what the
candidate lemmas `Advance_First_In_Range`, `Append_With_Wrap` and
`Remove_First_Preserves_Suffix` were meant to cover.

## 5. Ablation: every B proof artifact

`python3 scripts/ablate_proof_support.py --variant head_tail_count`. The
results are identical with `--extra-switch=--level=0`.

| Case | Proved | Unproved obligations (rule @ entity) | Verdict |
|---|---:|---|---|
| none (B as committed) | 134 | — | |
| ***Mechanical support*** | | | |
| remove `Type_Invariant` | 115 | `VC_POSTCONDITION @ Push` | necessary |
| remove loop invariant `Last (R) = J` | 128 | `VC_LOOP_INVARIANT_PRESERV`, `VC_PRECONDITION` (`Add`), `VC_REFINED_POST` @ `Model` | necessary |
| remove loop invariant (elements) | 129 | `VC_REFINED_POST @ Model` | necessary |
| remove both loop invariants | 126 | `VC_PRECONDITION`, `VC_REFINED_POST @ Model` | necessary |
| remove `Model'Refined_Post` | 124 | `VC_POSTCONDITION` @ `Clear`, `Initialize`, `Is_Empty`, `Is_Full`, `Peek`, `Pop`, `Push` | necessary |
| ***Public specification** (developer-owned; for parity with A)* | | | |
| remove public `Model` capacity bound | 132 | `VC_PRECONDITION @ Ring_Buffer_Client_Proof.Rotate` | necessary |
| remove `Is_Empty` `Post` | 126 | `VC_ASSERT`, `VC_PRECONDITION @ Push_Push_Pop`; `VC_PRECONDITION @ Rotate` | necessary |
| remove `Is_Full` `Post` | 128 | `VC_ASSERT`, `VC_PRECONDITION @ Push_Push_Pop`; `VC_PRECONDITION @ Rotate` | necessary |
| ***Alternatives and controls*** | | | |
| `Type_Invariant` → `Dynamic_Predicate` | 122 | `VC_PREDICATE_CHECK` @ `Clear`, `Pop`, `Push` | not a drop-in replacement |
| … plus whole-record updates in `Clear`/`Push`/`Pop` | 122 | — | works; not chosen (§2) |
| no invariant, `Push` ignores `Tail` (not the production design) | 116 | — | control (§4) |

There are no `Push` or `Pop` assertions, lemmas or operation
`Refined_Post`s to ablate: none was ever needed, so none was written.
Every remaining artifact is necessary. The ablation profile matches Task 001
exactly, plus one new necessary artifact, the invariant. Removing it breaks
exactly one obligation.

## 6. Negative fixtures for representation B

`python3 scripts/check_proof_results.py negative --variant head_tail_count`
applies each `variants/head_tail_count/negative/<name>/fault.toml` to a
scratch copy of B. It requires every expected `(rule, entity)` to be
reported **unproved** in SARIF. A nonzero exit status alone does not pass.
Observed results (`obj/negative_summary_head_tail_count.json`):

| ID | Fixture | Fault | Expected = observed unproved | Other checks proved |
|---|---|---|---|---:|
| B1 | `tail_not_advanced` | `Push` writes `Content (Tail)` and increments `Count`, but leaves `Tail` | `VC_INVARIANT_CHECK @ Ring_Buffer.Push` | 133 |
| B2 | `tail_advances_twice` | `Push` sets `Tail := Physical_Index (Tail, 2)` | `VC_INVARIANT_CHECK @ Ring_Buffer.Push` | 133 |
| B3 | `head_advances_wrong` | `Pop` sets `Head := Physical_Index (Head, 2)`; `Count` is decremented correctly | `VC_INVARIANT_CHECK @ Ring_Buffer.Pop` | 133 |
| B4 | `count_not_incremented` | `Push` writes and advances `Tail` but leaves `Count` | `VC_INVARIANT_CHECK @ Ring_Buffer.Push` | 132 |
| B5 | `push_writes_head` | `Push` writes `Content (Head)`; `Tail` and `Count` are updated correctly | `VC_POSTCONDITION @ Ring_Buffer.Push` | 133 |
| B6 | `clear_keeps_tail` | `Clear` resets `Head` and `Count` but not `Tail` | `VC_INVARIANT_CHECK @ Ring_Buffer.Clear` | 133 |

B5 and B6 go beyond the four required faults. They cover the two remaining
single-field failure modes:

* B5 keeps the invariant but breaks refinement, so only the functional
  proof can catch it.
* B6 keeps refinement but breaks the invariant. The model is still empty,
  so the public contract holds.

### Observation: the invariant masks functional failures in B3 and B4

B3 genuinely violates `Model = Remove (Model'Old, 1)`, and B4 violates
`Model = Add (Model'Old, E)`.

* **Invariant removed:** GNATprove reports `VC_POSTCONDITION` at `Pop` and
  `Push` for B3, and at `Push` for B4 (verified by rerunning both).
* **Invariant present:** GNATprove reports **only** the
  `VC_INVARIANT_CHECK`, and shows the postcondition as *proved*.

The reason: after checking the invariant on exit, GNATprove assumes it.
The faulty state contradicts that relation, so the postcondition is
discharged under a contradictory hypothesis.

The fault is still detected, and each fixture requires the check that
actually detects it. However, the diagnostic points at the representation,
not at the broken abstract behaviour.

These faults are also caught at run time. With `-gnata`, the unchanged
runtime tests stop with `failed invariant from ring_buffer.ads:67`
(verified for B1).

The five Task 001 fixtures (N1–N5) still run against A, unchanged, and
report the same obligations as before.

## 7. Refactor churn (A → B)

Measured with `python3 scripts/refactor_churn.py`, which diffs the code
lines of B's two package files against A's and attributes each line to its
classification on each side.

| Controlled item | Lines changed |
|---|---:|
| Public API (visible part, token-level) | **0** |
| Public abstract contract lines | **0** |
| Client proof (`proof/`, vs base `0f6da97`) | **0** |
| Runtime tests (`tests/`, vs base `0f6da97`) | **0** |

| Classification | Removed (A) | Added (B) | Nature |
|---|---:|---:|---|
| production implementation | 15 | 19 | record fields, `Initialize`, `Clear`, `Push`, `Pop`, `Peek`, `Is_Empty`, `Is_Full` |
| mechanical: model construction | 2 | 2 | renames `First`→`Head`, `Length`→`Count` |
| mechanical: `Model'Refined_Post` | 3 | 3 | same renames |
| mechanical: loop invariants | 1 | 1 | same renames |
| mechanical: representation invariant | 0 | **2** | **new** |
| **Manual proof support changed** | 6 | 6 | pure field renames, no structural change |
| **Manual proof support newly required** | — | **2** | the `Type_Invariant` |

Apart from the 2 invariant lines, all proof-support churn is mechanical
field-name substitution. The *first* and *length* roles are played by
`First` and `Length` in A and by `Head` and `Count` in B. `Tail` plays a
role A does not have.

## 8. Minimum metadata a generator would need (estimate only; not implemented)

Derived from the finished proofs, not from `spark-refine.toml`. The
mechanical support is completely determined by the facts below. The
capacity, element type, sequence instantiation and index origin can all be
read from the declarations of the storage array and of `Physical_Index`,
and the model function is the public `Model`.

**Representation A** reproduces 19 SLOC:

```toml
pattern = "circular_sequence"
storage = "Content"
first   = "First"
count   = "Length"
index   = "Physical_Index"
```

**Representation B** reproduces 21 SLOC:

```toml
pattern = "circular_sequence"
storage = "Content"
first   = "Head"
count   = "Count"
index   = "Physical_Index"
next    = "Tail"            # redundant field: next = index (first, count)
```

Role assignment (which field is `first`, which is `count`, and what `Tail`
means) cannot be inferred reliably without semantic source analysis, so it
is genuine user input. `tail_role = next_insert` from the task sketch
folds into the role name `next`: a *last-occupied* tail would be a
different role with a different, partial formula
(`index (first, count - 1)`, undefined when empty).

Not needed:

* the `emit_*` flags and operation mappings in the existing
  `spark-refine.toml`: every operation proves from the abstraction relation
  plus the invariant, with no per-operation artifacts;
* a switch for the invariant: declaring a `next` role implies it.

| | A | B |
|---|---:|---:|
| Minimum metadata (non-blank TOML lines) | 5 | 6 |
| Realistic manifest (+ table header, target type, version) | ≈ 8 | ≈ 9 |
| Manual proof support it would replace | 19 | 21 |
| Net SLOC saved per structure (realistic manifest) | ≈ 11 | ≈ 12 |
| Existing `spark-refine.toml` | 30 | would grow to ≈ 31 |

Marginal cost of the refactor for a generator user: +1 metadata line
(`next`), versus +2 manual SLOC plus 6 renamed lines for a hand-writer.
The renames are a search-and-replace.

## 9. The three problems that needed the most human reasoning

As in Task 001, the prover was never the obstacle. All three problems were
about knowing *what* to state or how to read the result.

### R1. Why does only `Push` fail without an invariant?

* **Fact GNATprove was missing:** `Tail = Physical_Index (Head, Count)` on
  entry to `Push`.
* **Why it was not derivable:** the derived model depends only on
  `Content`, `Head` and `Count`. `Tail` appears in no contract, so the
  prover treats it as an arbitrary `Storage_Index`. Only an operation that
  *reads* `Tail` into abstract state can be affected, and that is `Push`
  alone (`Pop` and `Peek` read `Head`).
* **Artifact that solved it:** the 2-line `Type_Invariant`.
* **Specific or generic?** Generic to every Head/Tail/Count circular
  buffer. It is exactly the definition of the `next` role.
* **Could a tool derive it** from storage, head, tail, count, capacity and
  the physical-index function? **Yes**, once told that `Tail` is the
  next-insert slot.

### R2. Choosing the invariant mechanism

* **Fact GNATprove was missing:** none. This was a choice between SPARK
  mechanisms with different checking points.
* **Why it was not derivable:** `Dynamic_Predicate` looks like the natural
  "representation predicate", but it is checked after every component
  assignment, so ordinary field-by-field production code fails four
  predicate checks. The only fix under that mechanism is rewriting the
  mutators as whole-record `delta` aggregates. `Type_Invariant` is checked
  only at the package boundary. Knowing this, and that GNATprove also
  generates a default-value check and invariant checks for `in`-mode
  calls, is SPARK-specific knowledge.
* **Artifact that solved it:** choosing `Type_Invariant` on the private
  full view.
* **Specific or generic?** Generic.
* **Could a tool derive it?** Yes. A generator would always emit the same
  form.

### R3. Reading negative results where postconditions "prove" on faulty code

* **Fact GNATprove was missing:** none. This is an interpretation
  problem. In B3 and B4 the functional postcondition is reported *proved*
  on wrong code, because the failed invariant is assumed after its check.
* **Why it was not derivable:** GNATprove reports each check
  independently and does not say that a green `VC_POSTCONDITION` rests on
  a red `VC_INVARIANT_CHECK`.
* **Artifact that solved it:** none in the proof. The fixture expectations
  were set to the obligation that actually detects the fault, and the
  masking was confirmed by rerunning B3 and B4 without the invariant.
* **Specific or generic?** Generic to any use of type invariants or
  predicates.
* **Could a tool derive it?** A source generator cannot help here. A
  **diagnostic** tool could, for example by reporting "postcondition P of
  X is proved only under an invariant that fails at X".

## 10. Direct answers

| Question | Answer |
|---|---|
| Did modulo arithmetic still prove automatically? | **Yes**, including the two composed `mod`s in `Pop`'s invariant preservation. This holds at levels 0–3, at `Max_Size` 16, 17 and 1000, and with each prover on its own. |
| Did `Tail` preservation across `Pop` require a lemma? | **No.** It needed nothing at all. |
| Did the `Tail` update across `Push` require a lemma? | **No.** The invariant on entry was needed to prove the append; re-establishing it on exit proved automatically. |
| Was an explicit representation invariant necessary? | **Yes.** 2 SLOC (`Type_Invariant`). Removing it breaks exactly `VC_POSTCONDITION @ Push`. |
| Were operation-specific `Refined_Post`s necessary? | **No.** |
| Was an intermediate model layer necessary? | **No.** B uses the same one-layer derived model as A. |
| Were explicit proof assertions necessary? | **No.** There are none in the package. |
| Were helper lemmas necessary? | **No.** None of the 9 candidate lemmas in `docs/PROOF_PATTERNS.md`. |

## 11. Hypothesis assessment

**Hypothesis (`docs/MVP.md`):** a small refinement declaration can generate
enough correct proof scaffolding to *materially* reduce human-authored
proof support for a conventional bounded circular buffer, without adding
trust.

**Classification after Task 002: WEAKER.**

Task 002 was the experiment most likely to strengthen the hypothesis:
redundant state is the classic source of representation predicates and
arithmetic lemmas. It did not.

Measured against the task's own criteria for **WEAKER**:

| Criterion | Observed |
|---|---|
| B needs only a tiny invariant plus the same Model machinery | **Yes.** +2 SLOC `Type_Invariant`; the other 19 SLOC are A's support with fields renamed. |
| No lemmas needed | **Yes.** 0 lemmas, 0 assertions, 0 operation `Refined_Post`s. |
| SMT proves Head/Tail/Count arithmetic automatically | **Yes.** At every level and capacity tried, and with each prover alone. |
| Manual support comparable to metadata size | **Partly.** 21 SLOC vs ≈ 6–9 metadata lines: roughly 2.5×, but only ≈ 12 lines saved per structure. |

Measured against the criteria for **STRONGER**:

| Criterion | Observed |
|---|---|
| B requires meaningful invariant/preservation machinery | **No.** 2 lines; preservation is automatic. |
| Most of it is generic | Yes (100%), but there is very little of it. |
| Manual proof churn is significant | **No.** 6 renamed lines + 2 new lines. |
| Client abstraction remains stable | **Yes.** 0 lines changed. This validates the SPARK abstraction design, not generation. |
| Metadata materially smaller than proof support | Moderately: ≈ 9 vs 21. |

What the evidence does support:

1. **The refinement architecture holds.** A derived model plus one
   abstraction relation, with a representation invariant only where
   production code reads redundant state, is a clean, repeatable pattern.
   Both representations share the same public contract, client proof and
   tests.
2. **The generation target is tiny and stable:** model body,
   `Refined_Post`, two loop invariants, and optionally one invariant line
   per redundant role. It is 100% determined by 5–6 role declarations.
3. **The hard parts were not generatable.** In Task 001 the hard part was
   the public contract (D3). In Task 002 it was the choice between
   invariant mechanisms (R2) and interpreting masked failures (R3). Both
   are about understanding and diagnosing SPARK proof semantics, not about
   typing boilerplate.

## 12. Recommendation: MORE EVIDENCE

**Not GO.** Two circular-buffer representations show that generation would
save about 11–12 SLOC per structure, on proofs that already take about 2 s
and need no lemmas. That does not justify a Libadalang-based generator
(M1–M3). For the `circular_sequence` pattern alone, the answer is **no**.

**Not yet PIVOT.** Both benchmarks so far use a model (a sequence) that
maps one-to-one onto SPARKlib `Functional.Vectors` primitives (`Add`,
`Remove (S, 1)`, `Get`). That is the most favourable case for off-the-shelf
automation, so circular buffers are too easy to decide the general
question. A structure whose representation is related to its model by a
*quantified, non-functional* relation is the fair remaining test.

### Task 003: fixed object pool benchmark

* **Representation:** `Free_Stack : array (1 .. N) of Slot_Id` and
  `Top : 0 .. N` (a free-index stack), plus the per-slot object storage.
* **Abstract model:** `SPARK.Containers.Functional.Sets` of `Slot_Id`,
  `Free_Set` and/or `Allocated_Set` (one derived from the other), with
  public contracts `Allocate` (Pre: `Free_Set` non-empty; Post: result was
  in `Free_Set` and is now in `Allocated_Set`, everything else unchanged)
  and `Release` (Pre: `Id` in `Allocated_Set`; Post: `Id` moved back).
  Use the same derived-model, same toolchain/switches, same gates
  (positive, negative, ablation, inventory, trust scan) and the same
  client-proof-first discipline.
* **Question it must answer:** *When the representation-to-model relation
  needs uniqueness and membership (every free id appears exactly once in
  `Free_Stack (1 .. Top)`), with `Cardinality = Top`, does GNATprove still
  prove it with a small generic invariant? Or does it need lemmas
  (permutation, no-duplicates, cardinality after push/pop) that are
  (a) substantial and (b) generic to all free-stack pools?*
* **Pre-registered decision rule** (so Task 003 cannot be tuned toward an
  answer):
  * **GO** (generate for both patterns) only if the pool's mechanical
    support is ≥ 3× its minimum metadata **and** ≥ 50 SLOC, **and** at
    least 80% of it is generic to free-stack pools (would be reused
    unchanged by a second pool with different element types and capacity).
  * **PIVOT** to proof/specification diagnostics and abstraction-contract
    validation if the pool again needs < 30 SLOC of support, or if most of
    its support is application-specific.
  * Anything in between: report and decide with the reviewer.

A bitmap second representation (the original Benchmark B) is optional for
Task 003. The free-stack representation alone answers the question above.
The bitmap exercises bit arithmetic, which Tasks 001 and 002 suggest SMT
will handle.

### Evidence already pointing toward the pivot candidate

If Task 003 leads to a pivot, the candidate direction is
**proof/specification diagnostics and abstraction-contract validation**.
Concrete, evidence-backed features:

1. **Client-usability check of public contracts** (Task 001 D3): warn when
   a public predicate used in `Pre` (`Is_Full`, `Is_Empty`) has no
   model-level `Post`, or the model has no capacity bound. Removing any of
   these breaks the client proof in both representations (ablations).
2. **Invariant-masking diagnostic** (Task 002 R3): flag postconditions
   proved only because a failed type invariant or predicate is assumed.
3. **Invariant-mechanism advice** (Task 002 R2): when `Dynamic_Predicate`
   checks fail on consecutive component updates, suggest `Type_Invariant`
   or whole-record updates.
4. **Public-API equivalence and representation-independence gates**
   (built for this task as plain scripts): a reusable "refactor safety"
   check that the visible spec, client proofs and tests are unchanged.

## 13. Trust boundary

Unchanged from Task 001 (`BASELINE_METRICS.md` §9). The trust scan now also
covers `variants/*/*.ad[sb]` and `variants/*/negative/*/fault.toml`, and
finds 0 forbidden constructs.

B's positive proof has 0 justified checks and 0 `pragma Assume`. Its only
allowed warnings are the same 6 `Big_Integers.Is_Valid` foundation warnings
as A. `Type_Invariant` adds no trust: GNATprove proves every invariant
check, including the default-value check. No new external foundation was
introduced.

## Reproduction

From `examples/ring_buffer/` with Alire 2.1.1 on `PATH`:

```bash
alr -n update
python3 scripts/check_public_api_equivalence.py
python3 scripts/proof_inventory.py --all                              # §1 SLOC
python3 scripts/refactor_churn.py                                     # §7
python3 scripts/check_proof_results.py trust-scan
alr -n build -- -XRING_BUFFER_REPR=head_tail_count
./bin/head_tail_count/ring_buffer_runtime_tests
alr -n build -- -XRING_BUFFER_REPR=head_tail_count -XRING_BUFFER_ASSERTIONS=on
./bin/head_tail_count/assertions/ring_buffer_runtime_tests
python3 scripts/check_proof_results.py positive --variant head_tail_count  # §1
python3 scripts/check_proof_results.py negative --variant head_tail_count  # §6
python3 scripts/ablate_proof_support.py --variant head_tail_count          # §5
# §3 deterministic single-prover step counts (repeat with z3, cvc5):
alr -n exec -- gnatprove -P ring_buffer.gpr -j0 \
    -XRING_BUFFER_REPR=head_tail_count --prover=altergo
```
