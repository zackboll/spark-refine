# Task 019 manual baseline

**GREEN — minimized and measured manual baseline**

The initial audit below was recorded as **WORKING — manual baseline not yet
complete** before proof engineering. No metric was treated as final then.

Structural audit of the original configured run (SARIF locations, cross-check
with `bitmap_allocator.spark`; locations relative to variants/manual):

| Rule | Entity (Bitmap_Allocator.) | Location | Category |
|---|---|---|---|
| VC_POSTCONDITION | Free_Count | bitmap_allocator.ads:19:17 | public postcondition |
| VC_POSTCONDITION | Is_Exhausted | bitmap_allocator.ads:21:17 | public postcondition |
| VC_POSTCONDITION | Is_Free | bitmap_allocator.ads:17:17 | public postcondition |
| VC_PRECONDITION | Free_Model | bitmap_allocator.adb:18:30 | model construction |
| VC_POSTCONDITION | Initialize | bitmap_allocator.ads:24:38 | public postcondition |
| VC_RANGE_CHECK | Release | bitmap_allocator.adb:50:26 | range/overflow |
| VC_POSTCONDITION | Release | bitmap_allocator.ads:31:17 | operation preservation |
| VC_PRECONDITION | Allocate | bitmap_allocator.ads:28:37 | public Remove precondition |
| VC_POSTCONDITION | Allocate | bitmap_allocator.ads:27:17 | operation preservation |

All nine original obligations are proved. Dispositions:

| Original obligation | Proof chain |
|---|---|
| Free_Count post | Count invariant = raw model length; Free_Model adapter |
| Is_Exhausted post | Same invariant and adapter |
| Is_Free post | Raw model's membership contract |
| Free_Model Add pre | Processed-prefix membership excludes the current ID |
| Initialize post | Raw membership plus full-model cardinality equivalence |
| Release range | Absent ID implies not all bits set; full equivalence implies length != 70; invariant and Count subtype give Count < 70 |
| Release post | Raw set-bit membership assertion and extensional Add semantics |
| Allocate Remove pre | Selected set bit, raw membership, and nonempty scan-prefix reasoning |
| Allocate post | Raw clear-bit membership assertion and extensional Remove semantics |

## Final architecture

Production remains three Unsigned_32 words, valid IDs 0 .. 69, Count 0 .. 70.
Visible API and all authoritative contracts are unchanged. Runtime mapping
uses Id/32 and Id mod 32 (equivalent to ordinal offset for this zero-origin
Natural subtype); mask is Shift_Left(1, bit). Mapping bounds, boundary masks
and canonical padding preservation prove without separate mapping lemmas.

Raw `Bitmap_Model (Words)` has no Pool parameter/precondition and visits only
valid IDs. Its contract proves membership equivalence, full iff every valid
bit is set, and empty iff no valid bit is set. Its three loop invariants are
prefix membership, length <= processed IDs, and full-prefix equivalence.
No duplicate popcount function/state is introduced: canonical cardinality
is Length(Bitmap_Model). The invariant is canonical padding AND
Count = Length(Bitmap_Model(Words)), with Free_Model a raw-model adapter.
This is the equivalent-through-model architecture allowed in the mission.

Set/clear membership assertions prove selected-ID change and preservation of
every other valid ID. The proved local `Equal_Length` lemma uses SPARKlib's
Num_Overlaps contract to bridge extensional equality to equal lengths; two
calls then transfer Add +1 and Remove -1 cardinality to the mutated bitmap.
Ghost snapshots/assertions/calls do not determine production values.
No Refined_Post, bodyless theorem, mutation helper, assumption or axiom added.

## Validation and measurements

Frozen preregistration: `a3265d455d2420daf435a02127455af1ee07a9d0` unchanged.
Alire 2.1.1, GNAT/GNATprove 16.1.0, SPARKlib 16.1.0 full. gprbuild package
pin 26.0.1 reports executable version 26.0.0 (2026-04-15); recorded rather
than silently treated as an exact executable match. CVC5 1.3.2, Z3 4.15.4,
Alt-Ergo 2.6.1. Standard level-2 racing profile, no resource escalation.

Three clean proofs, same final source:

| Run | Wall seconds | Application results | SPARKlib results | Total | Unproved | Justified | Max steps |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4.485 | 78 | 40 | 118 | 0 | 0 | 47,169 |
| 2 | 4.290 | 78 | 40 | 118 | 0 | 0 | 47,169 |
| 3 | 4.360 | 78 | 40 | 118 | 0 | 0 | 47,169 |

No reusable-library checks exist. Totals include 27 flow/termination results
and 91 prover results. Runtime-check 41, assertion 11, functional-contract 39,
termination 19, data-dependency 5, initialization 3 (GNATprove summary).
Detailed structural rule counts are in `evidence/manual_proof.json`.
The runtime driver is SPARK_Mode Off and is not a client proof.
Both production and -gnata builds pass **45,792 checks** with exit 0.
Trust scan passes. All ghost routines have checked bodies. The documented
external Big_Integers Is_Valid foundation is excluded from user assumptions;
no benchmark warnings control, unchecked import, suppression or justification.

## Exact physical Ada SLOC inventory

`proof_inventory.toml` covers every nonblank/noncomment line exactly once;
`scripts/proof_inventory.py` was run twice with byte-identical output.
`evidence/manual_inventory.json` gives every span, active line, reason and hash.

| Class | SLOC |
|---|---:|
| Production | 42 |
| Authoritative specification | 31 |
| Mechanical P | **54** |
| Generic P | **52** |
| Application-specific P | **2** |
| G = 52/54 | **96.296296%** |
| Runtime test (excluded) | 54 |

Mechanical breakdown, paths under variants/manual:

| File:lines | Artifact | SLOC | Generic |
|---|---|---:|---|
| bitmap_allocator.ads:40–50 | Raw padding/model contracts | 11 | yes |
| bitmap_allocator.ads:55–57 | Representation invariant | 3 | yes |
| bitmap_allocator.adb:2–8 | Equal_Length lemma/body | 7 | yes |
| bitmap_allocator.adb:16–35 | Model adapter/body/prefix invariants | 19 | yes |
| bitmap_allocator.adb:46–47 | Clear snapshots | 2 | yes |
| bitmap_allocator.adb:51–52 | Scan-prefix invariant | 2 | no |
| bitmap_allocator.adb:58–61 | Clear assertion/length call | 4 | yes |
| bitmap_allocator.adb:68–69 | Set snapshots | 2 | yes |
| bitmap_allocator.adb:73–76 | Set assertion/length call | 4 | yes |

Application-specific lines: adb:51 starts the allocation-scan invariant;
adb:52 states no earlier Candidate is free. Both depend on this low-to-high
scan, although public semantics do not promise lowest-ID selection. All other
mechanical lines concern generic packed membership, canonical padding,
finite-universe cardinality, raw model construction or set mutation. Runtime
Mask/Bitmap_Contains mapping lines are production, not counted again in P.
Default fields are counted as production because they define valid default
runtime state; not separately counted as a proof-only initialization.

## Ablation/minimization

All runs were sequential clean proofs, restoring the source. Canonical
evidence records structural failures/locations for each pass.

| Artifact | First / reduced / final-reduced unproved VCs | Decision |
|---|---|---|
| Model membership contract | 4 / 6 / 6 | retain |
| Explicit capacity upper-bound contract | 1 / 0 / removed | remove |
| Full iff contract | 1 / 1 / 3 | retain |
| Empty iff contract | 4 / 4 / 3 | retain |
| Padding invariant | 1 / 0 / 0 | retain frozen canonical-storage requirement |
| Count invariant | 3 / 4 / 4 | retain |
| Model membership loop invariant | 2 / 3 / 3 | retain |
| Model bound loop invariant | 2 / 3 / 3 | retain |
| Model full-prefix loop invariant | 1 / 2 / 2 | retain |
| Scan model unchanged invariant | 0 / removed / removed | remove |
| Scan Count unchanged invariant | 0 / removed / removed | remove with unused Count snapshot |
| Scan prefix invariant | 2 / 2 / 2 | retain |
| Explicit clear set-equality assertion | 0 / removed / removed | remove |
| Clear Equal_Length call | 1 / 1 / 2 | retain |
| Set membership assertion | 1 / 2 / 3 | retain |
| Explicit set-equality assertion | 0 / removed / removed | remove |
| Set Equal_Length call | 1 / 2 / 2 | retain |
| Equal_Length proof assertion | 1 / 1 / 1 | retain |
| Equal_Length postcondition | 2 / 3 / 4 | retain |

After these reductions, a clean repeat failed Allocate's Equal_Length
precondition (VC_PRECONDITION, adb:57:13 before later line shifts). Added the
minimal clear membership assertion plus raw snapshot; three clean runs then
passed. Removing this assertion once can pass (0 VCs), but its earlier
absence failed a clean repeat under the same limits, so it is retained for
observed stability, not claimed universally logically indispensable.
Removing either mutation raw snapshot or the padding predicate alone causes
a compiler name-resolution error (not negative-fixture VC evidence).
The raw model body/adapter are essential definitions, not bodyless theorem
candidates. No decorative mapping helper/contract was introduced.

## Frozen gate and scope boundary

P >= 15 and G >= 50%: **PASS**. This is permission for a subsequent experiment,
not evidence of library value or adoption. No reusable library started.
No full M1–M8 campaign, single-prover comparison, CI integration, push or PR
is claimed here. These are later Task 019 experiment/finalization work.
Task 020 not started. GNATprove remains proof authority; no diagnostics rule,
Task 015–018 source/evidence or preregistration edit.