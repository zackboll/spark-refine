# Trust Model and Soundness Policy

## 1. Objective

`spark-refine` must save proof-engineering effort without weakening the meaning of “proved by SPARK.”

The safest architecture treats the generator as an **untrusted convenience tool** whose generated claims are independently checked by GNATprove.

## 2. Intended trust boundary

```text
Trusted/accepted for a normal SPARK proof
-----------------------------------------
Ada/SPARK language semantics
GNAT compiler/frontend assumptions required by GNATprove
GNATprove / Why3 / selected automated provers
Explicit project-level trusted foundations already accepted by the user

Not trusted for correctness
---------------------------
spark-refine parser
spark-refine pattern implementation
source generator
future AI suggestions
future IDE integration
```

If `spark-refine` emits a wrong lemma, the desired result is a failed proof.

## 3. The central rule: no generated axioms

The default generator must not create a path where a false pattern theorem becomes accepted merely because the generator emitted it.

Disallowed by default:

- `pragma Assume` generated to close an obligation;
- bodyless ghost routines treated as arbitrary mathematical truth;
- imported proof functions used as axioms without a separately documented trusted implementation/model;
- unchecked Why3 axioms;
- turning off a required run-time check merely to make a VC disappear;
- changing a user postcondition to a weaker one automatically.

## 4. Lemmas

A generated lemma should normally be an ordinary ghost procedure/function with a body or specification structure whose required property GNATprove verifies.

If a lemma is reused from SPARKlib or another reviewed library, the generated code should reference the library rather than copying a trusted assertion.

## 5. Pattern verification

Patterns need two forms of testing.

### Generator tests

Check that expected SPARK is emitted for known inputs.

### Proof tests

Compile/prove generated fixtures with GNATprove and verify that:

- expected obligations are proved;
- negative fixtures fail where intended;
- no forbidden assumptions appear;
- all generated units are compatible with the declared SPARK profile.

Proof tests are more important than golden text tests.

## 6. Trust report

A future command should print the proof-affecting trust configuration:

```text
$ spark_refine trust-report
Generated assumptions: 0
External axioms: 0
Pattern foundations:
  SPARK functional sequences: project dependency
Unproved generated obligations: 0
Experimental suggestions accepted: 0
```

If advanced modes eventually permit user-trusted assumptions, the report must make them impossible to overlook.

## 7. AI policy

AI-generated proof changes are suggestions, not evidence.

An AI integration must classify edits:

```text
requirement change
representation mapping change
lemma/invariant addition
implementation change
assumption/trust change
```

Changes in the first or last categories require especially prominent review. The system must never silently weaken an authoritative contract.

## 8. Reproducibility

Proof results depend on toolchain versions and solver behavior. Benchmarks and CI should pin or record:

- GNAT/GNATprove version;
- project configuration;
- prover set and timeout/steps where relevant;
- generator version;
- pattern version;
- generated-source digest.

The project should distinguish “source generation reproducibility” from “solver timing reproducibility.” Byte-stable generated code is realistic; identical prover runtime is not.

## 9. Security handling

A bug that can cause `spark-refine` to emit an unchecked trusted assertion or silently weaken user requirements is a security/soundness issue, even if it is not a conventional memory-safety vulnerability.

See `SECURITY.md`.
