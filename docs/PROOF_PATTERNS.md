# Proof Pattern Library

## Purpose

Patterns are the reusable intellectual property of the project. The generator is infrastructure; patterns encode proof-engineering knowledge.

A pattern is not simply a code template. It defines a relation among:

- a family of concrete representations;
- an abstract mathematical model;
- validity conditions;
- operation semantics;
- standard proof obligations;
- reusable lemmas.

## Pattern 001: circular sequence

### Abstract meaning

A finite ordered sequence of elements with maximum capacity `N`.

### Candidate concrete representation A

```text
Content : array [Index] of Element
First   : Index
Length  : 0 .. N
```

Logical element `J`, where `0 <= J < Length`, maps to a physical index equivalent to:

```text
First + J modulo N
```

with an index-origin adjustment for Ada array bounds.

### Representation properties

The pattern should generate/prove facts equivalent to:

```text
Length <= Capacity
Every logical position maps into Content'Range
Model'Length = Length
For each logical position J:
    Model(J) = Content(Logical_To_Physical(J))
Empty(concrete) <=> Model'Length = 0
Full(concrete)  <=> Model'Length = Capacity
```

### Operation schemas

`append(E)`:

```text
Pre:  not full
Post: Model' = Model_old & E
```

`remove_first`:

```text
Pre:  not empty
Post: returned = First(Model_old)
      Model' = Tail(Model_old)
```

`replace(J,E)`:

```text
Pre:  J in model range
Post: same length
      Model'(J)=E
      all K /= J unchanged
```

### Standard lemmas

Candidate library:

```text
Logical_To_Physical_In_Range
Advance_First_In_Range
Append_No_Wrap
Append_With_Wrap
Append_Preserves_Prefix
Remove_First_Preserves_Suffix
Model_Length_Equals_Concrete_Length
Empty_Equivalent
Full_Equivalent
```

The actual implementation should seek the smallest useful lemma set. Too many lemmas can slow proof and make generated output harder to understand.

#### Evidence from the Task 001 manual baseline (representation A)

With SPARKlib `Functional.Vectors` as the model and GNATprove FSF 16.1.0 at
level 2, **none of the candidate lemmas above was needed**. Neither were a
representation predicate, a proof-only index mapping, or operation
`Refined_Post`s. The complete manual proof support was:

```ada
function Model (B : Buffer) return Sequences.Sequence
with Refined_Post =>                                      -- abstraction relation
  Sequences.Last (Model'Result) = B.Length
  and then (for all K in 1 .. B.Length =>
              Sequences.Get (Model'Result, K)
              = B.Content (Physical_Index (B.First, K - 1)))
is
   R : Sequences.Sequence;
begin
   for J in 1 .. B.Length loop                            -- derived model
      R := Sequences.Add (R, B.Content (Physical_Index (B.First, J - 1)));
      pragma Loop_Invariant (Sequences.Last (R) = J);     -- prefix length
      pragma Loop_Invariant                               -- prefix elements
        (for all K in 1 .. J =>
           Sequences.Get (R, K) = B.Content (Physical_Index (B.First, K - 1)));
   end loop;
   return R;
end Model;
```

`Physical_Index` is production code (`Push`/`Pop` use it), so the mapping
comes for free. The facts that actually had to be stated were therefore:

```text
Model'Length = Length                          (Refined_Post + invariant)
Model(K) = Content(Logical_To_Physical(K-1))    (Refined_Post + invariant)
```

The following were discharged automatically by the provers from the Ada
subtypes and SPARKlib's `Add`/`Remove`/`Range_Shifted` contracts:

```text
Length <= Capacity                              (subtype)
Every logical position maps into Content'Range  (Physical_Index returns Storage_Index)
Append with/without wrap                        (no lemma)
Remove-first shift                              (SPARKlib Remove, no lemma)
```

`Empty(concrete) <=> Model'Length = 0` and the matching `Full` relation still
matter, but as **public postconditions** on `Is_Empty`/`Is_Full`, written by
the developer. Clients cannot call `Push`/`Pop` without them. Similarly the
public `Last (Model) <= Capacity` bound is needed for clients, not for the
implementation proof.

Tail is expressed as `Remove (Model, 1)`; no custom `Tail` is needed.

Loop unrolling caveat: with a small static capacity, GNATprove may unroll
the model loop and prove it without invariants. Proof fixtures should use
`--no-loop-unrolling` so that measurements reflect realistic capacities.

### Representation B

```text
Content
Head
Tail
Count
```

The same abstract pattern can have a separate adapter. This is the first representation-refactor benchmark.

#### Evidence from Task 002 (representation B)

`Head`/`Count` play exactly the *first*/*length* roles of representation
A, so the model body, its `Refined_Post` and the two loop invariants carry
over with the fields renamed. `Tail` is redundant state: the *next insert*
slot. The complete additional proof support was one private invariant over
the production index function:

```ada
type Buffer is record
   Content : Storage_Array;
   Head, Tail : Storage_Index;
   Count   : Buffer_Length;
end record
with Type_Invariant =>
  Buffer.Tail = Physical_Index (Buffer.Head, Buffer.Count);
```

* It is needed **only because production `Push` writes `Content (Tail)`**.
  Without it the append postcondition is unprovable. If `Push` ignored
  `Tail`, no invariant would be needed.
* Re-establishing it in `Push` (`Tail` advanced) and in `Pop` (`Head`
  advanced, `Tail` unchanged, i.e. two composed `mod`s) proved
  automatically. Again **none** of the candidate lemmas above was needed.
* Use `Type_Invariant`, not `Dynamic_Predicate`. A predicate is checked
  after each component assignment, so ordinary field-by-field updates of
  `Head`/`Tail`/`Count` fail predicate checks unless every mutator is
  rewritten as a whole-record update.
* Negative-test caveat: when a fault breaks both the invariant and a
  functional postcondition, GNATprove reports only the invariant. The
  postcondition is proved under the assumed (failed) invariant.

Pattern rule suggested by A and B: each redundant role (such as `next`, or
a *last* index) contributes exactly one invariant conjunct
`role = index (first, offset)`. Everything else in the pattern is
unchanged. Measurements: `examples/ring_buffer/REFACTOR_METRICS.md`.

## Pattern 002 candidate: fixed object pool

### Abstract meaning

A finite universe of object identities partitioned into `Free` and `Allocated`, with optional object values.

### Concrete implementations

- free-list array;
- bitmap;
- stack of free indices.

### Useful properties

```text
Free ∩ Allocated = {}
Free ∪ Allocated = Universe
Allocate removes exactly one identity from Free
Release returns exactly one identity to Free
No allocated identity is returned twice without release
```

This is a strong second pattern because its abstract model is set-oriented, unlike the sequence-oriented first pattern.

After Task 002 this is the deciding benchmark for generation. Circular
sequences needed only 19–21 SLOC of generic support, because they map
directly onto SPARKlib sequence primitives. The open question is whether a
free-index stack refined to a `Functional.Sets` free/allocated set needs
substantial generic lemmas, for example about no duplicates in
`Free_Stack (1 .. Top)`, membership, or `Length (Free_Set) = Top` across
push and pop.

#### Evidence from Task 003 (free-index stack → `Functional.Sets` free set)

The model is one derived set, `Free_Model`; "allocated" is defined as its
complement. The minimal proof support was **36 SLOC, all generic**:

```text
Type_Invariant   Free_Stack (1 .. Top) has no duplicates      (+ Top := 0)
Refined_Post     Length (Model) = Top
                 Contains (Model, Id) = (exists I in 1 .. Top : Free_Stack (I) = Id)
Model body       R := Add (R, Free_Stack (I)) for I in 1 .. Top
                 + 2 loop invariants (length, membership)
Lemma            any set of Object_Id has Length <= Max_Objects
                 (pigeonhole; called once in Release for Top + 1)
```

**Not needed:** separate no-duplicate, popped-element or
`not Contains` → not-in-prefix lemmas; operation-specific contracts or
assertions; intermediate models; initialization invariants.
`Allocate` = `Remove` and `Release` = `Add` follow from SPARKlib contracts.

**Pattern-level lessons:**

* A set model over a prefix requires **injectivity** of the prefix.
* A pool whose release takes an arbitrary identity requires a
  **finite-universe cardinality** fact that SPARKlib `Functional.Sets`
  does not provide.
* That lemma is the only artifact that needs a particular prover
  (Alt-Ergo).

Decision under the pre-registered rule: **REVIEW** (P = 36, G = 100 %,
M = 5). Measurements: `examples/fixed_pool/BASELINE_METRICS.md`.

#### Evidence from Task 004: the pattern as a reusable library

The Task 003 support now lives in a hand-written generic,
`proof_patterns/src/spark_refine_prefix_sets.ad[sb]` (`L = 98` SLOC, all
Ghost). It is the first entry of the proof-pattern library.

```text
generic  Element_Type (<>), Index_Type range <>, Storage_Array,
         with package Element_Sets is new Functional.Sets (Element_Type, "=", others => <>)
Is_Unique (Storage, Count)            no identity twice in the active prefix
In_Prefix (Storage, Count, E)
Model     (Storage, Count) -> Set     Pre  Is_Unique
                                      Post Length = Count
                                           Contains (Model, E) = In_Prefix (...)
                                           Count < Universe_Size or else every E in prefix
Lemma_Can_Add (S, E)                  not Contains (S, E) => Length (S) < Universe_Size
```

**Per-instance residual: `R = 10` SLOC, `A = 4` actuals.**

* **Adoption** needs one instantiation (in the private part, next to the
  representation), `Type_Invariant => X.Is_Unique (...)` and a one-call
  model adapter. That is all.
* **Finite-universe consequence:** putting it into `Model`'s postcondition
  removed the only lemma call an application needed.

**Version-1 restrictions:**

* the prefix starts at `Index_Type'First`;
* the count is its length (`Index_Type'Base`);
* the identity is discrete, and the set uses predefined `=`.

**Ada restriction found:** the package cannot itself be `Ghost`. A ghost
generic's formal package rejects a non-ghost public set instance as
actual. Each entity is `Ghost` instead.

**Proving:** GNATprove proves it per instance. CI proves the pool plus
three validation instances (`proof_patterns/validation/`):

* a 1-value universe with lower bound 7;
* 200 values with a negative lower bound and a distinct 0-based index;
* an enumeration in 5 slots.

Decision: **PIVOT** (library + diagnostics). See
`examples/fixed_pool/LIBRARY_METRICS.md`.

## Pattern 003 candidate: bitmap set/allocator

### Abstract meaning

A finite set of indices.

### Concrete representation

Packed words/bits.

### Proof value

This exercises bit arithmetic and mapping from mathematical membership to representation bits. It is relevant to kernels, embedded allocators, permissions, and hardware state.

## Pattern 004 candidate: state machine

### Abstract meaning

A finite state plus permitted transition relation and optional abstract event trace.

### Concrete representation

Enums, flags, counters, or packed protocol state.

### Long-term leverage

This pattern could become a bridge to temporal/specification tools without requiring that bridge in the core generator.

## Pattern 005 candidate: descriptor ring

This should **not** be an MVP pattern. It combines circular structure with ownership, volatility, memory ordering, hardware interaction, and sometimes concurrency.

It is a high-value long-term target precisely because it demonstrates the real-time systems use case, but the project should establish proof-generation soundness on simpler structures first.

## Pattern acceptance criteria

A new pattern should not enter the stable library until it has:

1. a written mathematical meaning;
2. at least one realistic implementation fixture;
3. complete GNATprove proof under the project's supported profile;
4. negative tests showing important invalid implementations fail;
5. measured reduction in developer-authored proof support;
6. deterministic generated output;
7. documentation of unsupported representation variants;
8. no default generated assumptions.

## Pattern evolution

Patterns require semantic versioning because proof behavior matters.

A change is potentially breaking if it:

- strengthens generated preconditions;
- weakens generated obligations;
- changes abstract indexing semantics;
- changes the meaning of a role;
- changes required trust foundations;
- causes previously accepted mappings to resolve differently.

Pure formatting changes need not bump the pattern major version.
