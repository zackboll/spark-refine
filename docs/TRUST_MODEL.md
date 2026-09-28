# Trust Model and Soundness Policy

> **Status (Task 007).** The trust principles below were written for a
> generator. They apply unchanged to the current product
> ([ADR 0005](adr/0005-library-and-diagnostics-first.md)), where the
> "generator" is replaced by proof-pattern libraries and read-only
> diagnostics. Sections 1–2 were updated. Sections 3–6 and 8 carry a
> "current reading" note above their original generator wording, which
> is historical/deferred and kept as written.

## 1. Objective

`spark-refine` must save proof-engineering effort without weakening the meaning of “proved by SPARK.”

The safest architecture treats every `spark-refine` component as an
**untrusted convenience**:

* proof-pattern libraries are ordinary SPARK whose claims GNATprove
  checks at every instantiation;
* diagnostics only *interpret* GNATprove results, and never decide proof
  status.

(Originally: "treats the generator as an untrusted convenience tool
whose generated claims are independently checked by GNATprove".)

## 2. Intended trust boundary

```text
Trusted/accepted for a normal SPARK proof
-----------------------------------------
Ada/SPARK language semantics
GNAT compiler/frontend assumptions required by GNATprove
GNATprove / Why3 / selected automated provers
SPARKlib contracts (e.g. Functional.Sets, Big_Integers) the project uses
Explicit project-level trusted foundations already accepted by the user

Not trusted for correctness
---------------------------
spark-refine proof-pattern libraries   (re-proved per instance by GNATprove)
spark-refine diagnostics               (interpret results; never decide status)
spark-refine prove orchestration       (runs GNATprove, shows the exact command,
                                        relays its exit code; fresh-result
                                        provenance only, no proof authority)
spark-refine --semantic / Libadalang   (optional, descriptive source context
                                        for SRD002: call, callee, explicit Pre;
                                        used only if the source matches GNAT's
                                        .ali checksum + 1 s timestamp, which
                                        is NOT byte identity (same-second
                                        layout edits undetectable; reported
                                        as layout_exact=false); ambiguity or
                                        mismatch degrades, never guesses;
                                        Task 010 triage groups only collect
                                        identical callee+Pre, no causality)
AI agents consuming diagnostics
future IDE integration
(historical/deferred: spark-refine parser, source generator)
```

If a proof-pattern library contains a wrong lemma or contract, the
desired result is a failed proof. If a diagnostic is wrong, the proof
status reported by GNATprove is unaffected. The diagnostic may mislead,
which is why diagnostics are conservative and must never claim more
certainty than their evidence supports (see `SECURITY.md`).

The three kinds of source, and the change policy for each, are defined
in `docs/ARCHITECTURE.md` §3. Changes to authoritative specification are
the most trust-relevant, because GNATprove proves whatever it is given.

## 3. The central rule: no generated axioms

> **Current reading.** This rule applies today to proof-pattern libraries:
> no library may create a path where a false pattern theorem is
> accepted merely because the library states it. The list below is
> enforced by the CI trust scan over `proof_patterns/` and the
> benchmarks. The original generator wording follows.

The default generator must not create a path where a false pattern theorem becomes accepted merely because the generator emitted it.

Disallowed by default:

- `pragma Assume` generated to close an obligation;
- bodyless ghost routines treated as arbitrary mathematical truth;
- imported proof functions used as axioms without a separately documented trusted implementation/model;
- unchecked Why3 axioms;
- turning off a required run-time check merely to make a VC disappear;
- changing a user postcondition to a weaker one automatically.

## 4. Lemmas

> **Current reading.** Library lemmas, such as `Lemma_Can_Add` in
> `SPARK_Refine_Prefix_Sets`, are ordinary ghost subprograms with bodies
> that GNATprove proves. The generator wording below is historical.

A generated lemma should normally be an ordinary ghost procedure/function with a body or specification structure whose required property GNATprove verifies.

If a lemma is reused from SPARKlib or another reviewed library, the generated code should reference the library rather than copying a trusted assertion.

## 5. Pattern verification

> **Current reading.** Libraries use proof tests only: application and
> validation instances are proved, negative fixtures fail, and the trust
> scan is clean. "Generator tests" below are deferred with generation.

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

> **Current equivalent.** No `trust-report` command exists. Today, the
> CI trust scan (`examples/fixed_pool/scripts/check_proof_results.py
> trust-scan`) covers `proof_patterns/` and the benchmarks. Separately,
> `spark-refine explain` reports `pragma Assume` counts, justified checks
> and SARIF/.spark consistency notes found in GNATprove results. The
> sketch below is historical.

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

The operational form of this policy for agents consuming
`spark-refine prove --format json` or `spark-refine explain --format
json` is `docs/AGENT_INTEGRATION.md`.

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
- generator version (historical/deferred);
- pattern version;
- generated-source digest (historical/deferred).

The current diagnostics record the GNATprove version and command line of
each analyzed run in their JSON output (`runs[].gnatprove`,
`runs[].command_line`).

The project should distinguish “source generation reproducibility” from “solver timing reproducibility.” Byte-stable generated code is realistic; identical prover runtime is not.

## 9. Security handling

A bug that can cause `spark-refine` to emit an unchecked trusted assertion or silently weaken user requirements is a security/soundness issue, even if it is not a conventional memory-safety vulnerability.

See `SECURITY.md`.
