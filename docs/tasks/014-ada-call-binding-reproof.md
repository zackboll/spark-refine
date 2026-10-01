# Task 014 — Ada call-binding conjunct re-proof experiment

Status: pre-registered. This section was committed before any Task 014
probe code was written and before any Task 014 functional GNATprove proof
run. Base: `origin/main` `768d7f6836d519d58d31b8f478be338fea92b86e`, which
contains the reviewed Task 013 head
`80c47d4ce59e1ffc92a8cfedc3c0438dd818ebdf`. This is an **experiment**. It
is not a product feature. It adds no CLI, no SRD rule and no change to
`failed_conjunct`.

Before this commit, only feasibility gates were run on the Task 014
corpus: Ada legality (`gcc -c -gnatc`), GNATprove `--mode=check_all`
(SPARK-subset legality), GNATprove `--mode=flow` (data flow), and
Libadalang parsing and name resolution. None of them discharges or
reports a functional `Pre`/`Post` or run-time-check VC (P0). P0 also
records the protocol clarification that allowed the two non-proof
GNATprove modes.

## Pre-registration

This section is frozen at the preregistration commit. Results are
appended below under "Observed results". Nothing in this section is
edited after the experiment has run.

### P1. Question

Task 012 validated selected-conjunct scratch re-proofs for independent,
total conjuncts. Task 013 validated cumulative source-prefix re-proofs for
`and then` guards (access, index, nested `Pre`), with verdict
`PREFIX_METHOD_VALIDATED_ON_GUARDED_CORPUS`.

Task 014 asks:

> Does the prefix re-proof method continue to produce the pre-registered
> per-occurrence GNATprove evidence when Ada itself is doing non-trivial
> actual/formal binding and callee selection?

Cases covered: positional, named and reordered named actuals; defaulted
formals; explicit numeric conversion; an `in out` formal; package state
read by `Pre`; overload resolution; a generic instance; and a dispatching
call with `Pre'Class`.

### P2. Trust model and vocabulary

GNATprove is the only proof authority. Each scratch run proves, or fails
to prove, only the scratch program. The result is **new scratch proof
evidence**. It is not read out of the original GNATprove result, and it
does not prove the original program.

Libadalang decides which source call is present, which declaration it
resolves to, and where that declaration's explicit contract lives.
Libadalang does not decide proof status.

The experiment never substitutes actuals for formals. For
`Map_Op (C => Z, A => X, B => Y)` it does not derive `A := X`, `B := Y`,
`C := Z` and prove a rewritten expression. It changes only the resolved
callee's scratch contract source and leaves every caller byte-identical.
Ada/GNATprove performs the binding. A static test (P6) forbids an
association-list parser, text substitution into contracts, and
`eval`/`exec` in the experiment code.

Allowed vocabulary: *prefix transition*, *newly unproved at conjunct i*,
*blocked by earlier prefix*, *scratch evidence*, *auxiliary obligation*.
The experiment does not speak of a failed conjunct, a culprit or a root
cause. Normal Task 009 reports keep `failed_conjunct: null` and
`attribution: not_provided_by_gnatprove`.

### P3. Corpus (new, experimental input only)

`diagnostics/tests/experiments/task014_call_binding/` is new in this
commit and is not product code. The Task 012 and Task 013 corpora are not
modified. Committed sha256 of every corpus file:

| file | sha256 |
|---|---|
| `call_binding.gpr` | `eae698e45051e8471b61ce39c8c49ccb99c693fbb88b30159e81a981638cab94` |
| `resolution_manifest.json` | `e3c67f1a38b20ec32fd3c70ae8907f1235554a39793918e23fb6b7a2f57d3b90` |
| `src/binding_client.adb` | `9ff3f3cbf3c39969396d378bb91a2daa47643a2ab54e76bd270b752497556292` |
| `src/binding_client.ads` | `0cef4392124819daa5280e25634897473d7ca1dc9262d232e0974f4a858510a2` |
| `src/binding_generic.adb` | `55a198ec310788b4aa8c8d18e7e66805f6bf1c851dce7cf219a115037bda4302` |
| `src/binding_generic.ads` | `4f3f23d5de39c2c037a88de7fd83f4db39e995340a908b9f3ef0b0fdd9979db4` |
| `src/binding_int_ops.ads` | `ae94ebb225a95e166f794971cff2d21a1409b3a7cd07e0af573a55825a2475c1` |
| `src/binding_ops.adb` | `098d479b3ff93d09fa9c2fc924ad4e5a002c58f39359da34e8a23e5412e4ee4d` |
| `src/binding_ops.ads` | `924f0bbeca65b4884d254f0718c4d52c2dcd6be37c33f62b54c91b24d2653df0` |
| `src/binding_shapes.adb` | `9ecc62448438b1041578ef19979bd411c05b30859905b8ca46cd9c932ab00c5d` |
| `src/binding_shapes.ads` | `2a5f765b4d7cb7451b68f7cb57481df95aee1167e92316dd15fbcf8067fd4c90` |

All files are ASCII, LF-only and tab-free. `resolution_manifest.json` is
the frozen Libadalang resolution manifest (P4). It is corpus metadata. It
is not copied into scratch programs. The project's proof switches are
`-U --mode=all --level=2 --report=statistics`.

Callee contracts (layout abbreviated; exact bytes in the files, exact
prefix texts in P5):

| label | declaration | contract | operators |
|---|---|---|---|
| `map_op` | `procedure Map_Op (A : Integer; B : Integer := 1; C : Integer := 1)` | `Pre => A > 0 and then B > 0 and then C > 0` | `and then`, `and then` |
| `mutate` | `procedure Mutate (X : in out Integer; Limit : Integer)` | `Pre => X > 0 and then Limit > X` | `and then` |
| `above` | `procedure Above (X : Integer)`, `Global => (Proof_In => Threshold)` | `Pre => Threshold > 0 and X > Threshold` | `and` |
| `check_int` | `procedure Check (X : Integer; N : Integer)` | `Pre => X > 0 and N > X` | `and` |
| `check_bool` | `procedure Check (X : Boolean; N : Integer)` | `Pre => X and then N > 0` | `and then` |
| `generic_check` | `Binding_Generic.Check (X : T)` in the template, reached as `Binding_Int_Ops.Check` | `Pre => X > 0 and then X < 100` | `and then` |
| `resize` | primitive `procedure Resize (S : Shape; N : Integer)` | `Pre'Class => N > 0 and then N < 100` | `and then` |

`Threshold : Integer := 10` is a package-level variable in
`Binding_Ops`. `Binding_Int_Ops` is the only instance:
`package Binding_Int_Ops is new Binding_Generic (Integer);`. `Square` is
derived from `Shape`. Its `overriding procedure Resize (S : Square; ...)`
has only `Global => null`: no `Pre` and no `Pre'Class`. Callee bodies are
`null`, except `Mutate`, which is `X := X - 1`.

Every caller body in `src/binding_client.adb` is a single call. The
caller's own `Pre` in `src/binding_client.ads` sets up the caller state
(P11). A caller never changes between runs.

**Mixed `and` / `and then`.** The preferred Family A chain
`A > 0 and then B > 0 and C > 0` is illegal Ada (`gcc -gnatc`:
`mixed logical operators in expression`). Ada forbids mixing `and` and
`and then` at one level without parentheses. With parentheses, the
parenthesised group becomes ONE top-level conjunct, so no legal Ada
expression has three top-level conjuncts with mixed operators. So:

* Family A proof-tests three top-level conjuncts joined by
  `and then`, `and then`.
* Plain `and` is proof-tested by `above` and `check_int`, and `and then`
  by the others. The planner must keep each operator exactly as written.
* A mixed operator list (`and then`, `and`) is tested only by planner unit
  tests on synthetic byte ranges, not by proof runs.

This decision was made before any GNATprove run.

### P0. Feasibility gates (not proof observations)

Protocol clarification (from the task owner, before this commit): before
preregistration, GNATprove may run ONLY in the non-proof feasibility modes
`--mode=check_all` and `--mode=flow`, and only on temporary copies. No
`--mode=prove`, `--mode=all`, `--level`, silver or gold run is allowed,
and no functional VC may be inspected. None was.

Toolchain: the pinned Alire environment of `examples/ring_buffer`.
`gnatprove --version` prints `FSF 16.1.0`, `Why3 for gnatprove version
1.8.2+git` and `Alt-Ergo version 2.6.1`. Libadalang `26.0.0` (crate
marker `SPARK_REFINE_CRATE_VERSION`).

Final gates on the committed corpus bytes (P3), run from
`examples/ring_buffer`:

```text
# Ada legality, every unit
rm -rf /tmp/t014legal && mkdir -p /tmp/t014legal
cp ../../diagnostics/tests/experiments/task014_call_binding/src/* /tmp/t014legal/
alr -n exec -- sh -c 'cd /tmp/t014legal && for f in *.ads *.adb; do
  gcc -c -gnatc -gnat2022 $f; done'

# SPARK-subset legality (fresh temporary copy)
rm -rf /tmp/t014gate && mkdir -p /tmp/t014gate
cp -r ../../diagnostics/tests/experiments/task014_call_binding/. /tmp/t014gate/
alr -n exec -- gnatprove -P /tmp/t014gate/call_binding.gpr --mode=check_all -j0

# data flow (fresh temporary copy)
rm -rf /tmp/t014gate && mkdir -p /tmp/t014gate
cp -r ../../diagnostics/tests/experiments/task014_call_binding/. /tmp/t014gate/
alr -n exec -- gnatprove -P /tmp/t014gate/call_binding.gpr --mode=flow -j0
```

Results:

| gate | result |
|---|---|
| `gcc -c -gnatc -gnat2022`, all 9 units | exit 0, no diagnostics |
| `--mode=check_all` | exit 0; phases: data representation, Global contracts, full SPARK legality; no error or warning |
| `--mode=flow` | exit 0; 34 flow checks, all `Data Dependencies`, all flow-proved; SARIF has 34 results, all `GLOBAL_WRONG` / `pass`; 38 entities `flow analyzed (0 errors, 0 checks, 0 warnings and 0 pragma Assume statements)`; `binding_generic`: "generic unit is not analyzed" (analysed through the instance) |

The `.spark` files of the flow run have 0 proof entries. The flow summary
table reports 0 `Run-time Checks`, 0 `Assertions` and 0 `Functional
Contracts`. No functional VC exists in any feasibility output.

Corrections made while drafting, all before any functional proof:

1. The mixed `and then ... and` Family A chain failed Ada legality (P3).
2. The first `binding_shapes` draft failed Ada legality on the body with
   SPARK elaboration error E0003 ("first freezing point of type Square
   must appear within early call region of primitive body"). The fix
   was `pragma Elaborate_Body;` in the spec.
3. Family C first used `Global => (Input => Threshold)` and
   `Threshold > 0 and then X > Threshold`. That draft **passed** Ada
   legality, `--mode=check_all` and `--mode=flow` (34 flow checks, all
   proved). It was not rejected. It was changed on purpose, by design and
   not because of a tool result:
   * `Proof_In`: `Threshold` is read only in assertions (the `Pre`), and
     `Proof_In` is the SPARK mode for such globals;
   * plain `and`: so that proof runs cover plain `and` in a
     package-state contract.
   The final form was re-gated above.

An earlier local preregistration attempt (commit `31597f5`, never pushed)
was discarded before this commit. It had been created outside the
supervised workflow. Its document wrongly said `--mode=check_all` rejected
`Input`, and it had no resolution manifest. An audit found no Task 014
functional proof output anywhere on the machine. The only GNATprove
output for this corpus is the `--mode=flow` directory above: SARIF command
line `--mode=flow`, 34 `GLOBAL_WRONG` pass results, 0 proof entries. This
commit replaces that attempt. The corpus bytes are identical.

### P4. Libadalang resolution manifest (before proof)

`resolution_manifest.json` (P3 sha256) holds, for every target call, the
resolution Libadalang 26.0.0 reported on the committed corpus. Method:
the project context from `call_binding.gpr`; each `CallStmt` in
`binding_client.adb`; the call anchor and the one-call-per-anchor rule of
Task 009 (`semantic_lal.LalBackend._anchor` / `calls_at`: the start of
the called name, or the `.` before the selector of a dotted name); then
`p_referenced_decl`, `p_unique_identifying_name`,
`p_is_dispatching_call`, `p_get_aspect`, `p_get_uninstantiated_node`,
`p_generic_instantiations` and `p_find_all_overrides`. Spans are 1-based.
End columns are exclusive. It was generated twice and the two outputs
were byte-identical.

Target calls (26). All anchors are in `src/binding_client.adb`:

| case | client entity | call | source call text | callee |
|---|---|---|---|---|
| A1 | `Binding_Client.A1_Positional` | 7:7 | `Map_Op (X, Y, Z)` | map_op |
| A2 | `Binding_Client.A2_Named` | 12:7 | `Map_Op (A => X, B => Y, C => Z)` | map_op |
| A3 | `Binding_Client.A3_Reordered` | 17:7 | `Map_Op (C => Z, A => X, B => Y)` | map_op |
| A4 | `Binding_Client.A4_Reordered_Reversed` | 22:7 | `Map_Op (C => Z, B => Y, A => X)` | map_op |
| A5 | `Binding_Client.A5_Defaulted` | 27:7 | `Map_Op (A => X)` | map_op |
| A6 | `Binding_Client.A6_Explicit_And_Default` | 32:7 | `Map_Op (X, C => Z)` | map_op |
| A7 | `Binding_Client.A7_Conversion` | 37:7 | `Map_Op (A => Integer (S), B => Y, C => Z)` | map_op |
| A8 | `Binding_Client.A8_Conversion_Unbounded` | 43:7 | `Map_Op (A => Integer (S), B => Y, C => Z)` | map_op |
| B1 | `Binding_Client.B1_In_Out` | 48:7 | `Mutate (V, L)` | mutate |
| B2 | `Binding_Client.B2_In_Out_Named` | 53:7 | `Mutate (Limit => L, X => V)` | mutate |
| B3 | `Binding_Client.B3_In_Out_Unconstrained` | 58:7 | `Mutate (X => V, Limit => L)` | mutate |
| C1 | `Binding_Client.C1_Global` | 63:7 | `Above (X)` | above |
| C2 | `Binding_Client.C2_Global_Threshold_Only` | 68:7 | `Above (X => X)` | above |
| C3 | `Binding_Client.C3_Global_Unconstrained` | 73:7 | `Above (X)` | above |
| D1 | `Binding_Client.D1_Int_Check` | 78:7 | `Check (X, N)` | check_int |
| D2 | `Binding_Client.D2_Int_Check` | 83:7 | `Check (N => N, X => X)` | check_int |
| D3 | `Binding_Client.D3_Int_Check` | 88:7 | `Check (X, N)` | check_int |
| D4 | `Binding_Client.D4_Bool_Check` | 93:7 | `Check (B, N)` | check_bool |
| D5 | `Binding_Client.D5_Bool_Check` | 98:7 | `Check (N => N, X => B)` | check_bool |
| D6 | `Binding_Client.D6_Bool_Check` | 103:7 | `Check (B, N)` | check_bool |
| E1 | `Binding_Client.E1_Generic` | 108:22 | `Binding_Int_Ops.Check (X)` | generic_check |
| E2 | `Binding_Client.E2_Generic` | 113:22 | `Binding_Int_Ops.Check (X)` | generic_check |
| E3 | `Binding_Client.E3_Generic` | 118:22 | `Binding_Int_Ops.Check (X)` | generic_check |
| F1 | `Binding_Client.F1_Dispatch` | 123:7 | `Resize (S, N)` | resize |
| F2 | `Binding_Client.F2_Dispatch` | 128:7 | `Resize (S, N)` | resize |
| F3 | `Binding_Client.F3_Dispatch` | 133:7 | `Resize (S, N)` | resize |

Every anchor has exactly one call and no name-resolution error.

Resolved callees (kind `procedure` for all; declaration and contract
spans as `file:line:col-line:col`):

| label | fully qualified name | unique identifying name | declaration | aspect | contract span |
|---|---|---|---|---|---|
| map_op | `Binding_Ops.Map_Op` | `binding_ops.map_op(standard.integer, standard.integer, standard.integer)` | `binding_ops.ads:6:4-13:24` | `Pre` | `10:19-12:33` |
| mutate | `Binding_Ops.Mutate` | `binding_ops.mutate(standard.integer, standard.integer)` | `binding_ops.ads:16:4-21:24` | `Pre` | `19:19-20:37` |
| above | `Binding_Ops.Above` | `binding_ops.above(standard.integer)` | `binding_ops.ads:26:4-29:43` | `Pre` | `27:19-28:36` |
| check_int | `Binding_Ops.Check` | `binding_ops.check(standard.integer, standard.integer)` | `binding_ops.ads:32:4-35:24` | `Pre` | `33:19-34:28` |
| check_bool | `Binding_Ops.Check` | `binding_ops.check(standard.boolean, standard.integer)` | `binding_ops.ads:37:4-40:24` | `Pre` | `38:19-39:33` |
| generic_check | `Binding_Int_Ops.Check` | `binding_int_ops.check(standard.integer)` | `binding_generic.ads:7:4-10:24` | `Pre` | `binding_generic.ads:8:19-9:35` |
| resize | `Binding_Shapes.Resize` | `binding_shapes.resize(binding_shapes.shape, standard.integer)` | `binding_shapes.ads:10:4-13:27` | `Pre'Class` | `binding_shapes.ads:11:22-12:38` |

Family D (overloads). The two `Binding_Ops.Check` declarations have the
same fully qualified name. They differ in unique identifying name,
declaration span and `Pre` span. D1-D3 resolve to the Integer overload
(`binding_ops.ads:32:4-35:24`, `Pre` `33:19-34:28`, `X > 0 and N > X`).
D4-D6 resolve to the Boolean overload (`binding_ops.ads:37:4-40:24`,
`Pre` `38:19-39:33`, `X and then N > 0`). The mutation target is the
resolved declaration's span, never the name `Check`.

Family E (generic). What Libadalang reports for
`Binding_Int_Ops.Check (X)`:

* `p_referenced_decl` is a `SubpDecl` whose fully qualified name is the
  INSTANCE name `Binding_Int_Ops.Check`
  (`binding_int_ops.check(standard.integer)`). Its source span is the
  TEMPLATE declaration, `binding_generic.ads:7:4-10:24`.
* `p_get_uninstantiated_node` is a different node: the template
  declaration `Binding_Generic.Check`, with the same span
  `binding_generic.ads:7:4-10:24`.
* `p_generic_instantiations` has exactly one element, the
  `GenericPackageInstantiation` at `binding_int_ops.ads:4:1-4:58`.
* `p_get_aspect("Pre")` on the resolved declaration gives the expression
  at `binding_generic.ads:8:19-9:35`, which is written once, in the
  template.

So Libadalang establishes structurally, without name matching, that the
`Pre` of the called instance subprogram is the template source range
`binding_generic.ads:8:19-9:35`. That is the only range mutated for
`generic_check`. The instance unit `binding_int_ops.ads` is never
mutated. Family E status: **supported** (not
`semantic_target_unresolved`).

Family F (dispatching). What Libadalang reports for `Resize (S, N)` with
`S : Shape'Class`:

* `p_is_dispatching_call` is `True`.
* `p_referenced_decl` is the root primitive `Binding_Shapes.Resize`
  (`binding_shapes.resize(binding_shapes.shape, standard.integer)`,
  `binding_shapes.ads:10:4-13:27`).
* `p_get_aspect("Pre")` does not exist. `p_get_aspect("Pre'Class")`
  exists and is not inherited; its expression is at
  `binding_shapes.ads:11:22-12:38`.
* `p_find_all_overrides` reports one override,
  `Binding_Shapes.Resize` for `Square`, at
  `binding_shapes.ads:17:4-18:24`. Its only aspect is `Global`: no `Pre`
  and no `Pre'Class`.

The applicable contract for the class-wide call is therefore the root
`Pre'Class` range. That is the only range mutated for `resize`. The
override's declaration is never changed. Family F status: **supported**.
The pre-proof feasibility gates (P0) accepted the hierarchy (with
`pragma Elaborate_Body`) in `check_all` and `flow`.

Before any proof run, the experiment re-derives the manifest from the
committed corpus with the same Libadalang properties and compares it
with `resolution_manifest.json`, field by field. It also requires
`resolution_manifest.json`'s own sha256 to equal P3. On a mismatch it
stops (exit 2) with no verdict.

### P5. Prefix construction (planner)

The Task 013 planner is reused unchanged in meaning. The Task 013 module's
`plan_prefixes` / `request_probe` / `prefix_source` are called directly.
Its input is the ordered top-level conjuncts of the resolved contract
(text + byte range from Libadalang `BinOp` nodes, cross-checked against
Task 009's `LalBackend.conjuncts`) and the original operators. Every
`prefix_text` is the exact original source slice from the start of `C0`
to the end of `Ci`. Nothing is rebuilt from normalized strings, and `and`
and `and then` are never exchanged. A selected-only probe of conjunct
`i > 0` is refused.

Pre-registered exact prefixes (JSON strings; `\n` is a newline):

| callee | i | exact prefix text |
|---|---|---|
| map_op | 0 | `"A > 0"` |
| map_op | 1 | `"A > 0\n                  and then B > 0"` |
| map_op | 2 | `"A > 0\n                  and then B > 0\n                  and then C > 0"` |
| mutate | 0 | `"X > 0"` |
| mutate | 1 | `"X > 0\n                  and then Limit > X"` |
| above | 0 | `"Threshold > 0"` |
| above | 1 | `"Threshold > 0\n                  and X > Threshold"` |
| check_int | 0 | `"X > 0"` |
| check_int | 1 | `"X > 0\n                  and N > X"` |
| check_bool | 0 | `"X"` |
| check_bool | 1 | `"X\n                  and then N > 0"` |
| generic_check | 0 | `"X > 0"` |
| generic_check | 1 | `"X > 0\n                  and then X < 100"` |
| resize | 0 | `"N > 0"` |
| resize | 1 | `"N > 0\n                     and then N < 100"` |

The last prefix of each callee is the full original contract. The
per-prefix operator lists are the first `i` original operators. For
`map_op` these are `[]`, `["and then"]` and `["and then", "and then"]`.
If the planned prefix text differs, the experiment stops.

### P6. Scratch transformation, isolation and no substitution

Each run gets a real-file copy (bytes only, no symlinks) of
`call_binding.gpr` and all nine `src/*.ad[sb]` files. The copy goes in its
own directory below the gitignored
`diagnostics/obj/task014-call-binding-reproof/<run>/`.
`resolution_manifest.json` is not copied.

For prefix `i` of callee `K`, only `K`'s mutable file changes
(`binding_ops.ads`, or `binding_generic.ads` for `generic_check`, or
`binding_shapes.ads` for `resize`). The contract bytes from the end of `Ci`
to the end of `K`'s contract expression are overwritten with spaces,
keeping newline bytes. The prefix keeps its original bytes. The Task 012
helpers (`overlay`, `mutation_inventory`) are reused unchanged.

Gates, machine-checked for every run:

* non-final prefix: exactly one changed file (`K`'s mutable file) and
  exactly one changed allowed range. No changed byte outside it. File
  length and newline positions preserved. Therefore:
  * `binding_client.ads` / `binding_client.adb` are byte-identical in
    every run (the named, reordered, defaulted, converted, `in out` and
    `Proof_In` callers are never touched);
  * for an overload, only that overload's range changes, so the other
    `Check` is byte-identical;
  * for `generic_check`, only the template `Pre` range changes, and
    `binding_int_ops.ads` is byte-identical;
  * for `resize`, only the root `Pre'Class` range changes, and the
    `Square` override is byte-identical.
* final prefix and baseline: the copy is byte-identical to the corpus.
* reparse (Libadalang, scratch copy): zero diagnostics in every unit. The
  resolved contract of `K` has text exactly `prefix_text`, conjuncts
  exactly `C0..Ci` and operators exactly the first `i` original
  operators. Every other callee's contract text and span are unchanged.
* semantic identity (P9): in the scratch copy every one of the 26 call
  anchors re-resolves to its manifest callee.

All destructive operations resolve strictly below
`diagnostics/obj/task014-call-binding-reproof/` and use the Task 012
safety model unchanged. They refuse the root itself, parent paths,
paths outside the root, symlinked scratch directories and symlinked
corpus files.

No substitution: the experiment script
(`diagnostics/scripts/call_binding_reproof_experiment.py`, added after
this commit) must pass an AST test. The test forbids:

* reading association lists (`f_suffix`, `ParamAssoc`, `f_designator`,
  `f_r_expr`, `p_zip_with_params`);
* formal-to-actual maps;
* `str.replace` / `re.sub` on contract or conjunct text;
* `eval` / `exec` / `compile`.

The only source edit the experiment makes is the P6 blanking of the
resolved callee's contract suffix.

### P7. Forbidden-trust gate

The Task 012 Libadalang structural scan (with its Axiom correction) runs
on the committed corpus and on every scratch copy. It covers
`pragma Assume`; `Annotate` with `False_Positive`, `Intentional`,
`Axiom`, `Skip_Proof` or `Skip_Flow_And_Proof`; `Suppress` /
`Suppress_All`; `SPARK_Mode => Off`; `Import` / `Interface` / `Axiom`
mechanisms; and bodyless Ghost subprograms. The committed corpus has zero
hits: checked before this commit over all nine units, 71 structural
records. No scratch copy may introduce a hit.

### P8. Runs

Each run is a fresh GNATprove FSF 16.1.0 from the pinned Alire
environment of `examples/ring_buffer`. It uses the project switches
`-U --mode=all --level=2 --report=statistics` plus `-j0`. The process
exit code is never used. There are 16 runs:

| run | scratch change |
|---|---|
| `baseline` | none |
| `map_op_p0`, `map_op_p1`, `map_op_p2` | `Map_Op` Pre := P0, P1, P2 (= original) |
| `mutate_p0`, `mutate_p1` | `Mutate` Pre := P0, P1 (= original) |
| `above_p0`, `above_p1` | `Above` Pre := P0, P1 (= original) |
| `check_int_p0`, `check_int_p1` | Integer `Check` Pre := P0, P1 (= original) |
| `check_bool_p0`, `check_bool_p1` | Boolean `Check` Pre := P0, P1 (= original) |
| `generic_check_p0`, `generic_check_p1` | template `Check` Pre := P0, P1 (= original) |
| `resize_p0`, `resize_p1` | root `Resize` Pre'Class := P0, P1 (= original) |

One scratch program serves every call occurrence of its callee. Every
occurrence is still read on its own, by its own structural target. No
result is transferred between occurrences. In a run for callee `K`, the
call sites of every other callee are untouched targets and must keep
their baseline status. This is the cross-mutation evidence for the two
`Check` overloads.

### P9. Structural result identity and callee-semantic identity

A target is one `VC_PRECONDITION` matched by rule, client entity, file,
line and column (P4 table). It is read from the loader's structural SARIF
status and checked against the `.spark` files (`disputed`). Message text
is never read. Invalid target: zero matches, more than one match, a
disputed check, or a JUSTIFIED status.

A target is also accepted only if, in the SAME scratch copy that was
proved, its call anchor still resolves (Libadalang) to the manifest
callee. The comparison uses unique identifying name, declaration span,
contract aspect and dispatching flag. The contract span is also compared,
except for the mutated callee, whose end changes by design. The mutated
callee's contract text is checked by the P6 reparse gate instead. A call
that resolves differently makes every observation in that run
`invalid_probe`.

### P10. Auxiliary obligations (recorded separately)

Every non-target check in every run is inventoried with rule, entity,
file, line, column, status and disputed flag. It is never folded into a
target. Categories:

* **Conversion (A7, A8).** Every check with rule `VC_RANGE_CHECK` or
  `VC_OVERFLOW_CHECK`, entity `Binding_Client.A7_Conversion` (line 37)
  or `Binding_Client.A8_Conversion_Unbounded` (line 43), in
  `binding_client.adb`, with a column inside the actual `Integer (S)`
  (columns 20..30). Expected in every run:
  * A7: at least one such check, and all of them PROVED
    (`S in 1 .. 1000`).
  * A8: at least one such check, and at least one UNPROVED
    (`S > 0` does not bound `S` by `Integer'Last`).
  The count is recorded.
* **Other.** Every other non-target check (flow, `Mutate` body overflow,
  generic instance, dispatch/LSP, run-time checks) must be PROVED and
  undisputed in every run. No UNPROVED and no JUSTIFIED is allowed.

SARIF results at warning/note level (the loader's `ToolWarning`s) are not
proof checks. They are recorded as a count and are not a condition.

If an auxiliary check for an occurrence is UNPROVED, JUSTIFIED or disputed
in a run, that occurrence's observation in that run is
`auxiliary_obligation_unproved`. It is never `newly_unproved`. This
experiment-only classification separates "cannot establish that the
converted actual is valid" from "cannot establish the callee `Pre`
prefix". It is not added to product diagnostics.

### P11. Baseline control

The baseline is the unmodified copy with every original full contract.
Required target statuses:

| case | caller Pre (state) | required |
|---|---|---|
| A1 | `X > 0 and then Y > 0 and then Z > 0` | PROVED |
| A2 | `X > 0` | UNPROVED |
| A3 | `X > 0 and then Y > 0` | UNPROVED |
| A4 | `Y > 0 and then Z > 0` | UNPROVED |
| A5 | `X > 0` (B, C defaulted to 1) | PROVED |
| A6 | `X > 0` (B defaulted, C => Z) | UNPROVED |
| A7 | `S in 1 .. 1000 and then Y > 0` | UNPROVED |
| A8 | `S > 0 and then Y > 0 and then Z > 0` | PROVED (conversion UNPROVED) |
| B1 | `V > 0 and then L > V` | PROVED |
| B2 | `V > 0` | UNPROVED |
| B3 | none | UNPROVED |
| C1 | `Threshold > 0 and then X > Threshold` | PROVED |
| C2 | `Threshold > 0` | UNPROVED |
| C3 | none | UNPROVED |
| D1 | `X > 0 and then N > X` | PROVED |
| D2 | `X > 0` | UNPROVED |
| D3 | none | UNPROVED |
| D4 | `B and then N > 0` | PROVED |
| D5 | `B` | UNPROVED |
| D6 | none | UNPROVED |
| E1 | `X in 1 .. 99` | PROVED |
| E2 | `X > 0` | UNPROVED |
| E3 | none | UNPROVED |
| F1 | `N > 0 and then N < 100` | PROVED |
| F2 | `N > 0` | UNPROVED |
| F3 | none | UNPROVED |

A8 is PROVED because GNATprove assumes a checked conversion once it has
been checked, and `S > 0` makes `Integer (S) > 0`. A8 is still not clean
evidence (P10).

The reordered calls test that binding follows the formal association,
not the textual order. In A3 (`C => Z, A => X, B => Y`), the first
textual actual `Z` is unconstrained, yet prefixes 0 and 1 are expected
PROVED. In A4 (`C => Z, B => Y, A => X`), the first two textual actuals
are constrained positive, yet prefix 0 is expected UNPROVED, because
`A => X` is unconstrained. B2, D2 and D5 also reorder named actuals.

### P12. Classification (per call occurrence, per conjunct index)

`status(i)` is the structural status of the occurrence's target in the
run for prefix `i` of its callee. For `i = 0` the predecessor is
conceptually `TRUE` (PROVED). The rules apply in this order:

1. The run failed a gate (P6, P7, P9), the current target is invalid
   (P9), or the predecessor status is missing, invalid or JUSTIFIED:
   `invalid_probe`.
2. An auxiliary check of THIS occurrence (P10) in the current run is
   UNPROVED, JUSTIFIED or disputed: `auxiliary_obligation_unproved`.
3. Predecessor UNPROVED:
   * current UNPROVED: `blocked_by_earlier_prefix`. No claim is made
     about conjunct i.
   * current PROVED: `invalid_probe` (not monotone).
4. Predecessor PROVED, current PROVED: `prefix_proved`.
5. Predecessor PROVED, current UNPROVED: `newly_unproved`.

These are the Task 013 rules, unchanged, with rule 2 in place of Task
013's nested-precondition rule. `failed`, `culprit` and `root_cause` are
never classification values.

Pre-registered case outcomes (P22 vocabulary: `supported`,
`semantic_target_unresolved`, `proof_tool_unsupported`,
`invalid_auxiliary_obligation`): every case is `supported` except A8. A8
is `invalid_auxiliary_obligation` by design: it is the conversion control
whose call-prefix result must NOT count as clean evidence.

### P13. Pre-registered result matrix (60 observations)

Signatures list the prefix statuses `[status(0), status(1), ...]`
(P = PROVED, U = UNPROVED). Classifications: `pp` `prefix_proved`,
`nu` `newly_unproved`, `bl` `blocked_by_earlier_prefix`, `aux`
`auxiliary_obligation_unproved`.

| case | client entity | call | callee | p0 | p1 | p2 | classifications |
|---|---|---|---|---|---|---|---|
| A1 | `Binding_Client.A1_Positional` | binding_client.adb:7:7 | `Binding_Ops.Map_Op` | P | P | P | pp pp pp |
| A2 | `Binding_Client.A2_Named` | binding_client.adb:12:7 | `Binding_Ops.Map_Op` | P | U | U | pp nu bl |
| A3 | `Binding_Client.A3_Reordered` | binding_client.adb:17:7 | `Binding_Ops.Map_Op` | P | P | U | pp pp nu |
| A4 | `Binding_Client.A4_Reordered_Reversed` | binding_client.adb:22:7 | `Binding_Ops.Map_Op` | U | U | U | nu bl bl |
| A5 | `Binding_Client.A5_Defaulted` | binding_client.adb:27:7 | `Binding_Ops.Map_Op` | P | P | P | pp pp pp |
| A6 | `Binding_Client.A6_Explicit_And_Default` | binding_client.adb:32:7 | `Binding_Ops.Map_Op` | P | P | U | pp pp nu |
| A7 | `Binding_Client.A7_Conversion` | binding_client.adb:37:7 | `Binding_Ops.Map_Op` | P | P | U | pp pp nu |
| A8 | `Binding_Client.A8_Conversion_Unbounded` | binding_client.adb:43:7 | `Binding_Ops.Map_Op` | P | P | P | aux aux aux |
| B1 | `Binding_Client.B1_In_Out` | binding_client.adb:48:7 | `Binding_Ops.Mutate` | P | P | - | pp pp |
| B2 | `Binding_Client.B2_In_Out_Named` | binding_client.adb:53:7 | `Binding_Ops.Mutate` | P | U | - | pp nu |
| B3 | `Binding_Client.B3_In_Out_Unconstrained` | binding_client.adb:58:7 | `Binding_Ops.Mutate` | U | U | - | nu bl |
| C1 | `Binding_Client.C1_Global` | binding_client.adb:63:7 | `Binding_Ops.Above` | P | P | - | pp pp |
| C2 | `Binding_Client.C2_Global_Threshold_Only` | binding_client.adb:68:7 | `Binding_Ops.Above` | P | U | - | pp nu |
| C3 | `Binding_Client.C3_Global_Unconstrained` | binding_client.adb:73:7 | `Binding_Ops.Above` | U | U | - | nu bl |
| D1 | `Binding_Client.D1_Int_Check` | binding_client.adb:78:7 | `Binding_Ops.Check` (Integer) | P | P | - | pp pp |
| D2 | `Binding_Client.D2_Int_Check` | binding_client.adb:83:7 | `Binding_Ops.Check` (Integer) | P | U | - | pp nu |
| D3 | `Binding_Client.D3_Int_Check` | binding_client.adb:88:7 | `Binding_Ops.Check` (Integer) | U | U | - | nu bl |
| D4 | `Binding_Client.D4_Bool_Check` | binding_client.adb:93:7 | `Binding_Ops.Check` (Boolean) | P | P | - | pp pp |
| D5 | `Binding_Client.D5_Bool_Check` | binding_client.adb:98:7 | `Binding_Ops.Check` (Boolean) | P | U | - | pp nu |
| D6 | `Binding_Client.D6_Bool_Check` | binding_client.adb:103:7 | `Binding_Ops.Check` (Boolean) | U | U | - | nu bl |
| E1 | `Binding_Client.E1_Generic` | binding_client.adb:108:22 | `Binding_Int_Ops.Check` | P | P | - | pp pp |
| E2 | `Binding_Client.E2_Generic` | binding_client.adb:113:22 | `Binding_Int_Ops.Check` | P | U | - | pp nu |
| E3 | `Binding_Client.E3_Generic` | binding_client.adb:118:22 | `Binding_Int_Ops.Check` | U | U | - | nu bl |
| F1 | `Binding_Client.F1_Dispatch` | binding_client.adb:123:7 | `Binding_Shapes.Resize` (dispatching) | P | P | - | pp pp |
| F2 | `Binding_Client.F2_Dispatch` | binding_client.adb:128:7 | `Binding_Shapes.Resize` (dispatching) | P | U | - | pp nu |
| F3 | `Binding_Client.F3_Dispatch` | binding_client.adb:133:7 | `Binding_Shapes.Resize` (dispatching) | U | U | - | nu bl |

Totals: 60 observations (Family A 24, B 6, C 6, D 12, E 6, F 6).
Statuses: 34 PROVED, 26 UNPROVED, 0 JUSTIFIED. Classifications:
`prefix_proved` 31, `newly_unproved` 17, `blocked_by_earlier_prefix` 9,
`auxiliary_obligation_unproved` 3, `invalid_probe` 0. Family A shows
`[P,P,P]`, `[P,U,U]`, `[P,P,U]` and `[U,U,U]`. Every other family shows
`[P,P]`, `[P,U]` and `[U,U]` (both overloads separately). The last
prefix of every callee is its full contract, so `status(last)` must also
equal the P11 baseline.

### P14. Frozen decision rule

**Per-family verdict.** Families: A (`map_op`), B (`mutate`), C (`above`),
D (`check_int` + `check_bool`), E (`generic_check`) and F (`resize`). All
six are pre-registered as **supported**. A family is:

* `VALIDATED` if every run for its callee(s) passes every gate, and every
  observation, baseline status, untouched-target status and auxiliary
  expectation for its cases matches P10, P11 and P13;
* `UNSUPPORTED` only if its semantic target cannot be established
  (manifest mismatch or unresolvable contract), or GNATprove produces no
  structural result for its targets (zero matching `VC_PRECONDITION` in
  the baseline for every one of its cases);
* `NOT_VALIDATED` otherwise.

A family pre-registered as supported that ends up `UNSUPPORTED` fails the
overall rule. It is not excused.

**Overall verdict.** It is
**`CALL_BINDING_METHOD_VALIDATED_ON_PREREGISTERED_SUPPORTED_CASES`** only
if ALL of the following hold. Otherwise it is
**`CALL_BINDING_METHOD_NOT_VALIDATED`**.

1. All six families are `VALIDATED`. None silently became unsupported.
2. All 26 baseline targets match P11.
3. All 60 prefix statuses match P13.
4. All 60 classifications match P13.
5. No target result (baseline, observed or untouched) is JUSTIFIED.
6. Every target query matches exactly one structural `VC_PRECONDITION`.
7. No target is disputed (SARIF vs `.spark`).
8. The P4 manifest matches on the corpus and on every scratch copy,
   including overload spans, the Family E template/`Pre` relation and the
   Family F dispatching `Pre'Class` relation.
9. No P6 source-isolation or reparse violation. The Integer and Boolean
   `Check` contracts never cross-mutate.
10. No forbidden trust construct in the corpus, and none introduced (P7).
11. P10 holds in every run: A7 conversion checks present and all PROVED,
    A8 conversion checks present with at least one UNPROVED, and no other
    non-target check UNPROVED, JUSTIFIED or disputed.
12. Every scratch contract re-extracts to a planned prefix. The planner
    refuses a selected-only probe of every conjunct `i > 0`.
13. In every prefix run, every untouched target has its baseline status.
14. The committed corpus, including `resolution_manifest.json`, is
    unchanged by the experiment.
15. The static no-substitution test (P6) passes.

A missing field counts as a failure. This rule is not changed after
results are seen. The per-family verdicts report a partial result; they
do not relax the overall rule.

### P15. Evidence and determinism

`diagnostics/obj/task014-call-binding-reproof/evidence.json` is canonical
JSON: sorted keys, pre-registered case and run order, and no timestamps,
absolute paths or prover messages. It holds the corpus identity, the
resolution manifest comparison, the extraction, the prefix plans, the
baseline, the runs, the target results, the auxiliary inventory, the
family summaries and the overall summary. Timing goes only into
`timing.json`. The experiment is run twice locally, and `evidence.json`
must be byte-identical. Runtime is measured but is not a correctness
condition.

Run-count accounting (descriptive only, not an optimization benchmark):

* `target_occurrence_count` = 26;
* `naive_occurrence_prefix_runs` = 60 (one program per occurrence and
  prefix);
* `unique_callee_prefix_runs` = 15 executed prefix programs, plus 1
  baseline;
* `per_occurrence_observations` = 60;
* observed sharing factor = 60 / 15 = 4.0.

Every observation is still read from its own structural target. No
result is transferred between occurrences.

### P16. Permitted interpretation

If validated, the ONLY permitted conclusion is:

> On the controlled call-binding corpus, cumulative source-prefix
> re-proofs that mutated only the Libadalang-resolved callee contract
> produced the pre-registered per-occurrence structural GNATprove
> evidence for positional, named, reordered, defaulted and converted
> actuals, an `in out` formal, `Proof_In` package state, overload
> resolution, a generic instance and a dispatching `Pre'Class` call,
> without a local actual/formal substitution engine.

This does NOT imply any of the following:

* arbitrary contracts, binding forms or generic/dispatch shapes are
  supported. In particular it says nothing about overriding `Pre`,
  inherited-and-strengthened `Pre'Class`, formal subprograms or
  generic-formal-dependent contracts;
* a later conjunct can be assessed after an unproved prefix;
* a `newly_unproved` transition is a root cause;
* `failed_conjunct` may be populated;
* production contracts should change;
* A8's callee prefix was established independently of its unproved
  conversion;
* anything about `Post` or `in out` state after the call;
* the method is cheap enough for interactive use.

If not validated, no other method is tried in this task. The exact
mismatch is recorded, and the next research question is recommended.

### P17. Product boundary and non-goals

No user CLI. No new SRD. No production `failed_conjunct`. No change to
`semantic.py`, `semantic_lal.py`, `semantic_groups.py`,
`semantic_shape.py`, `render.py` or `cli.py`. No change to the Task 012 or
Task 013 corpora, scripts or verdicts. No editor UI. No GNATprove
session-reuse optimization. No external corpus. No automatic contract
editing. The experiment script, its tests and the CI step are added only
in the post-preregistration commit.

If the supported families validate, Task 015 should stop adding synthetic
language cases and measure the tool on a SPARK codebase that was not
written for these diagnostics. Task 015 is not started here.

## Observed results

Local run (post-preregistration): `CALL_BINDING_METHOD_VALIDATED_ON_PREREGISTERED_SUPPORTED_CASES`.
All six families validated. The 26 baseline targets, 60 prefix statuses and
60 classifications matched P11/P13. The 16 programs (one control and 15
unique callee prefixes) passed resolution, source-isolation, reparse,
trust and auxiliary gates. A7's conversion was proved and A8's conversion
unproved in every run; A8's three call-prefix classifications were
`auxiliary_obligation_unproved`, not clean call-prefix evidence. All
untouched targets retained baseline status. No target was justified or
SARIF/.spark disputed. These are scratch-program observations only.

Canonical evidence: `diagnostics/obj/task014-call-binding-reproof/evidence.json`
(gitignored). Timing: `diagnostics/obj/task014-call-binding-reproof/timing.json`
(measurement only). The two local runs produced byte-identical evidence.
