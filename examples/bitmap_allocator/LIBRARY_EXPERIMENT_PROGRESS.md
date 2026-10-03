# Task 019 intermediate experiment — NOT an acceptance result

The frozen preregistration and historical manual benchmark are unchanged.
The manual checkpoint branch was pushed normally at
`029f2907c7993da3854ed72583c166de4b79faa5`.

## Manual artifact transfer inventory

Ranges refer to the committed manual files, not the candidate files.

| Manual artifact | Classification for experiment |
|---|---|
| ads:40–42 padding predicate | move_to_library |
| ads:43–50 model declaration/contracts | move_to_library; mapping adapter might remain local |
| ads:55–56 invariant header/padding | must_remain_instance_local; delegate padding predicate |
| ads:57 Count/model consistency | must_remain_instance_local |
| adb:2–8 Equal_Length | move_to_library |
| adb:16–17 Free_Model adapter | must_remain_instance_local |
| adb:19–35 model construction/invariants | move_to_library |
| adb:46–47 clear snapshots | possibly_eliminated_by_stronger_library_contract |
| adb:51–52 scan-prefix invariant | must_remain_instance_local |
| adb:58–61 clear assertion/length call | possibly_eliminated_by_stronger_library_contract |
| adb:68–69 set snapshots | possibly_eliminated_by_stronger_library_contract |
| adb:73–76 set assertion/length call | possibly_eliminated_by_stronger_library_contract |

The original 52 generic lines are transfer candidates, not a promise that
52 lines disappear. In particular Count consistency and application adapters
remain local despite being classified generic in the historical inventory.

## Candidate design

`SPARK_Refine_Bitmap_Sets` is experimental, not a second stable pattern.
Formals: discrete element type, modular word type, integer word-index type,
constrained storage-array type, caller's Functional.Sets instance, explicit
Bits_Per_Word. The sixth actual is honest representation configuration; no
final A measurement has been made.

Compile_Time_Error predicates check binary modulus and sufficient storage
extent. Only the allocator's 32-bit instance has been analyzed so far; rejection
fixtures for these predicates and other word widths have NOT been validated.
Logical bit width is not inferred from physical Size. Ordinal mapping uses
Pos relative to First and does not intentionally require zero origins.
Offset/extent arithmetic is restricted to values representable by Integer;
conversion/arithmetic checks are re-proved per instance.

Raw Model has no Pool-invariant precondition. Padding is quantified over
physical words/bits outside the valid identity universe. Mutation procedures
are Ghost lemmas relating old/new arrays; they never mutate production storage.
All theorem-like procedures have checked bodies.

## Intermediate runs

All invocations used the inherited frozen level-2 profile, -U, -j0,
--no-loop-unrolling, warnings/checks as errors, and --output-header.
Runs were sequential. These are development runs, NOT three clean stability
runs, minimized measurements, or single-prover results.

| Run | Result |
|---|---|
| first | compilation failure: arithmetic mixed formal index type with Integer |
| second | 151 analysis results; 150 passed, 1 unproved, 0 justified |
| third | snapshot/assertion attempt: 2 unproved public Allocate obligations |
| fourth | unchanged-word/model loop witnesses: 157 results, 156 passed, 1 unproved |
| fifth | local mutation assertions/Equal_Length: 155 results, 150 passed, 5 unproved |
| sixth | local raw-model adapter: 161 results, 158 passed, 3 unproved, 0 justified |

The generic body was analyzed through the allocator instantiation. The second
run proved the generic mutation relations but not the public Allocate Remove
postcondition. Its maximum successful proof steps were 82,275. The current
sixth candidate fails canonical-padding invariants at Allocate/Release exit
and the adapter's full-model equivalence postcondition (maximum successful
steps 87,985). No resource limits were increased.

Local logs are `/tmp/task019-library-{first,second,third,fourth,fifth,sixth}.log`.
Generated GNATprove outputs remain ignored under obj/library_backed. These
paths are operational hints, not canonical acceptance evidence.

## Scope remaining

No first green proof, clean-run stability, independent validation instances,
residual/library minimization, final R/L/A, M1–M8 campaign, masking experiments,
single-prover matrix, performance comparison, canonical final evidence, CI
integration, final experiment commits, or PR has been completed.
There is therefore no ADOPT/REVIEW/DO_NOT_ADOPT decision yet. The candidate's
then-current proof failure was a blocker, not a measured final economic verdict.
Task 020 has not started.

## Boundary continuation: initial audit

An exact source/log/proof snapshot with SHA-256 manifest was preserved in an
ignored `obj/boundary-*` directory before any edits. Clean reproduction used
the unchanged inherited proof switches and a fresh proof-pattern object
variant. It produced **161 results, 156 passed, 5 unproved, 0 justified**;
SARIF and `.spark` agree on all five failures. Both analyzed `.spark` units
report PROGRESS_PROOF, STOP_REASON_NONE, and no assumptions/skipped proof.
Generic-body obligations are present through Bitmap_Allocator.Bitmap.

| Fact | Prover / exposed interface | Caller and preconditions | Initial gap classification |
|---|---|---|---|
| Production membership = generic membership | No named bridge; definitions differ syntactically | Raw-model adapter, raw Words; no Pool needed | not established explicitly; composition proof-search difficulty suspected, not diagnosed |
| Production mask/mapping = generic mask/mapping | Shift_Left versus modular exponent; division versus ordinal offset | Mutation-lemma physical-update preconditions | absent contract fact |
| Model membership | Generic Model body/post | Adapter, mutation lemmas; Model has no precondition | present, generic proof succeeds |
| Model full equivalence | Generic Model body/post, generic Universe_Size | Adapter needs Capacity and production-membership bridges | present; composed adapter postcondition unproved |
| Model empty equivalence | Generic Model body/post | Adapter, exhaustion reasoning; no precondition | present; adapter empty clause proves in reproduction |
| Clear-bit set relation | Lemma_Clear_Bit post/body | Not called in current allocator; requires present bit/exact delta update | absent at caller, not a failed call precondition |
| Set-bit set relation | Lemma_Set_Bit post/body | Not called in current allocator; requires absent bit/exact delta update | absent at caller; local assertion/public Release fail |
| Cardinality decrement/increment | Mutation posts and SPARKlib Add/Remove, Equal_Length bridge | Local Equal_Length calls require extensional equality | calls prove in reproduction; explicit Count assertions still needed to isolate exit conjuncts |
| Physical padding preservation | Mutation posts conditional on canonical old storage | Not called; exact physical update required, not just model relation | absent contract at caller; padding named in exit diagnostics |

Initial structural failures (application sources): VC_POSTCONDITION
Bitmap_Model ads:48:15; VC_ASSERT Release adb:48:36; VC_INVARIANT_CHECK
Release ads:30:14; VC_POSTCONDITION Release ads:32:17;
VC_INVARIANT_CHECK Allocate ads:26:14. Invariant diagnostics name canonical
padding, but isolated checked Count/padding assertions will test this directly.

Installed SPARKlib full 16.1.0 was inspected: set equality is extensional
mutual subset; Num_Overlaps equates its result to each included set's length;
Add/Remove expose length +/-1 and Included_Except with membership preconditions.
The existing checked Equal_Length bridge is therefore retained for this phase.

Configuration audit: Compile_Time_Error checks occur in the generic spec;
main-instance values reduce to modulus 2**32 and storage 96 >= universe 70.
Pos/extent arithmetic and Word_Index conversion checks are proved per instance.
The mask exponent is strictly below Bits_Per_Word, never a full-width power.
The padding predicate quantifies every storage word and every logical bit,
including entirely unused extra words. The application currently uses that
generic predicate directly, not the manual final-word mask predicate; no
equivalence between those predicates has yet been established explicitly.

## Boundary continuation: stable first green (32-bit instance only)

Verdict: **FIRST_GREEN_LIBRARY_INSTANCE_STABLE** for the current allocator
instance, not ADOPT_BITMAP_PATTERN or final Task 019 completion.

Starting branch: `feature/019-bitmap-set-proof-pattern`; committed HEAD:
`029f2907c7993da3854ed72583c166de4b79faa5`. Six candidate files were untracked;
all tracked files were unchanged. Frozen preregistration remains
`a3265d455d2420daf435a02127455af1ee07a9d0`.

### Controlled attempts and failure disposition

| Attempt | Observed outcome |
|---|---|
| clean reproduction | 161 results: 156 pass, 5 unproved, 0 justified; original three plus Release assertion/Add; Allocate Remove proved |
| mapping, unreferenced raw harness | warning-as-error; marking incomplete; not a proof result |
| mapping, called contractless harness | GNATprove inlining error involving From_Universal_Image; no complete SARIF |
| mapping, checked harness contract | 190 results: 189 pass, only Release padding exit unproved |
| exact physical delta assertions and mutation calls | 206 results, all passed |
| explicit frozen/manual padding equivalence | 209 results: 208 pass, Release membership assertion timed out; padding bridge proved |
| per-identity mapping composition at Release | 213 results, all passed; first green of final source |

VC counts differ because checked support adds obligations; counts were not
used as a progress proxy. All public Allocate Remove and Release Add clauses
prove on final source. The original adapter full clause and both padding exit
checks prove. Separate checked assertions for canonical padding and Count/model
cardinality prove at both operation exits; neither conjunct is being hidden.

### Final boundary proof chain

`Mapping_Bridge(Words,Id)` has no precondition and proves production Id/32
equals generic Word_Index, production Shift_Left mask equals generic Mask, and
physical membership agreement. `Model_Interface_Check` takes raw Word_Array,
not Pool, and independently checks generic full equivalence, universe size =
Capacity, and composed full equivalence. Its checked post exposes the latter
two facts. `Bitmap_Model` forwards Bitmap.Model with mapping witness loop,
the harness call, and universe-size assertion. It does not build another set.
The generic has no hard-coded 70; universe arithmetic is Last'Pos-First'Pos+1.

`Padding_Interface_Check` proves the quantified generic predicate equals the
manual `(Words(2) and not Unsigned_32(2**6-1))=0` predicate on arbitrary raw
storage. Generic padding still covers every bit in every storage word,
including entirely extra words. Physical preservation is NOT derived from
model equality: before each write checked assertions capture canonical old
storage and selected membership/absence; after the write an exact delta-array
assertion establishes the actual updated word/mask and every unchanged word.
Lemma_Clear_Bit/Lemma_Set_Bit then supply model equality, cardinality +/-1,
and conditional canonical-new-storage. Their checked bodies and ALL allocator
call-site preconditions prove. Id is a valid Object_Id throughout.

Old_Words/Old_Model snapshots precede mutation and match the operation entry
state. Release helpers between Words and Count updates accept raw arrays only,
not an inconsistent Pool. Local membership assertions remain, as do checked
Equal_Length calls whose extensional-equality preconditions prove; SPARKlib
Add/Remove cardinality and the generic equal-length bridge transfer length to
Count. The Allocate prefix scan invariant and production fallthrough are
unchanged, and public postcondition/exit checks cover both paths.

Final generic spec/body/API are byte-identical to the starting candidate:
all six actual concepts retained, existing Model full/empty/membership and
mutation equality/cardinality/padding contracts retained. No assumptions,
resource escalation, Assert_And_Cut, second popcount, or production mapper
rewrite was introduced. Retained local support includes Mapping_Bridge,
Model_Interface_Check, Padding_Interface_Check, forwarding Bitmap_Model and
Free_Model, two old model/raw snapshots per mutation, scan invariant, mapping
witness loops (including Release), focused assertions, mutation lemma calls,
and Equal_Length calls. These are not minimized; count them honestly later.

### Clean stability series

Each run moved only candidate-owned obj/library_backed into its own archived
run directory (fresh proof state) and selected a fresh proof-pattern object
variant. No simultaneous GNATprove invocations. Identical source hash maps
were verified for all three runs; no repair/retry within this series.

Invocation for N=1,2,3, from the bitmap example:
`alr -n exec -- gnatprove -P bitmap_allocator_library.gpr
-XPROOF_PATTERNS_VARIANT=boundary-stable-N -j0 --output-header --output=oneline`.
The invocation headers confirm inherited switches exactly:
`-U --mode=all --level=2 --no-loop-unrolling --report=statistics
--checks-as-errors=on --warnings=error`. No other resource/prover changes.

| Clean run | Analysis results | Passed | Unproved | Justified | Wall seconds |
|---|---:|---:|---:|---:|---:|
| stable-1 | 213 | 213 | 0 | 0 | 20.119 |
| stable-2 | 213 | 213 | 0 | 0 | 10.927 |
| stable-3 | 213 | 213 | 0 | 0 | 11.126 |

Each contains 43 flow results and 170 prover results; SARIF/.spark agree.
Both bitmap_allocator and bitmap_allocator_runtime_tests reach PROGRESS_PROOF
with STOP_REASON_NONE and no pragma_assume/skip flags. Runtime test code is
SPARK_Mode Off intentionally, not an application-proof coverage claim.
Generic-body analysis is through Bitmap_Allocator.Bitmap at ads:41: Model
16 checks, mutation lemmas 9 each, Equal_Length 6, mapping/arithmetic/padding
operations also analyzed. A standalone generic unit being skipped is expected.
SPARKlib implementation bodies are external trusted foundation, unchanged;
SARIF's existing a-nbnbin.ads Is_Valid messages are the same allowed foundation
messages as the manual gate, not candidate assumptions or justified checks.

Stable source SHA-256 (paths relative to repository):

```text
effd4de285beb37f6da817f312b6249607c3085277e84a72c09b0734e793a431 examples/bitmap_allocator/bitmap_allocator_library.gpr
a5f434fb2abd14f1e9454ce75467a6ea9b321015d0dc55a832e02861d0bbc8ac examples/bitmap_allocator/variants/library_backed/bitmap_allocator.adb
0b473195435dc51f3168799af23d6af3d8781aa9ed64e14db3e3bb11d01e34f6 examples/bitmap_allocator/variants/library_backed/bitmap_allocator.ads
8d049009ae08e2e737d82c27c7a055dbf5362462877890f25c7be603bb9c212c proof_patterns/src/spark_refine_bitmap_sets.adb
e49b72bd09dda59c64baff88ae98703c604628aa317465260e0f241e46e8b7a2 proof_patterns/src/spark_refine_bitmap_sets.ads
```

### Validation status

Production runtime: 45,792 checks passed. Forced `-XBITMAP_ASSERTIONS=on`
rebuild (inherited Compiler switch `-gnata`) and runtime: 45,792 checks passed,
exit 0. The forced-Ghost/assertion execution completed without an assertion
failure; it is not another proof stability run.
Public API/authoritative visible contracts pass the established tokenizer gate
(excluding private-with context only). Every inventoried production line is
byte-identical after removing indentation and remains in order: 10 ads and
32 adb lines. No production expression/statement changes.
Established forbidden-pattern scan passes for all five candidate Ada/GPR
files; existing repository/library trust scan passes (31 files, zero forbidden
constructs). Repository checks pass, root unit tests pass (4). Diagnostics:
467 tests, 34 skipped for unavailable Libadalang semantic support; these skips
are NOT semantic regression passes.

Clean frozen manual recheck: 118 analysis results, all pass (0 unproved).
Tracked diff against frozen HEAD is empty before adding the candidate; frozen
manual sources/project, BASELINE_METRICS/evidence, preregistration, Tasks
015–018/evidence, Prefix_Sets and production diagnostics remain unchanged.

Development snapshot and complete raw logs/SARIF/.spark/headers/manifest:
`/home/zboll/git/spark-refine/examples/bitmap_allocator/obj/boundary-2w4znj4t/`.
This is ignored local evidence, not a final deterministic evaluation bundle.
No final R/L/A, independent instances, M1–M8, adoption decision, final PR,
or Task 020 work has been undertaken. Stop for review after normal checkpoint.