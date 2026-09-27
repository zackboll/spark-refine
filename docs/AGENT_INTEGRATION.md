# Agent integration: using `spark-refine` output safely

This page is for AI coding agents (Cline, Devin, ...), CI and editor
integrations that consume `spark-refine prove --format json` (preferred,
Task 008) or `spark-refine explain --format json`.

## Trust boundary

```text
GNATprove determines proof status.

spark-refine interprets proof-result patterns.

An AI agent may consume spark-refine output,
but neither spark-refine nor the AI is a proof authority.
```

* A check is proved only if **GNATprove** says it is proved. A clean
  `spark-refine` report is **not** a proof, and a diagnostic is **not**
  a verdict that something is false.
* `spark-refine` never edits sources, repairs proofs or changes
  contracts, and its analysis is deterministic. `spark-refine prove`
  runs GNATprove (the exact command is shown), but it does not prove
  anything itself. Its authority is exactly that of "run GNATprove, then
  `explain` the result". The only thing it adds is **fresh-result
  provenance**. `explain` never runs GNATprove.

```text
GNATprove       proof authority
spark-refine    orchestration + interpretation
human / agent   decides changes
```
* **Recommended workflow policy:** changes to *authoritative*
  specifications deserve explicit human review. These include public
  `Pre`/`Post`, type invariants, ghost models, and anything that states
  a requirement. An agent may freely change implementation code and
  proof support (assertions, lemmas, loop invariants, ghost helpers),
  but it should propose, not silently apply, changes that weaken or
  re-state a requirement. `spark-refine` does not enforce source
  ownership mechanically; this is a policy for the agent's operator.
* The three kinds of source (implementation, authoritative
  specification, mechanical proof support) are defined in
  `docs/ARCHITECTURE.md` §3. There, representation invariants and ghost
  model *adapters* count as mechanical proof support, and the abstract
  model's *meaning* is authoritative. Because a type invariant is also
  something GNATprove assumes, a change to it can alter what "proved"
  means (see SRD001). This page therefore asks for review of invariant
  changes, which is stricter than the category alone would require.

## Freshness

* `spark-refine prove` **guarantees** that the analyzed result set was
  created or changed by the GNATprove command it just launched. Stale
  result sets are ignored. Zero or several fresh result sets mean no
  report: it refuses instead of guessing.
* `spark-refine explain` analyzes an existing result set. The **caller**
  is responsible for freshness: the results correspond to the current
  sources only if GNATprove was just run.

`prove` substantially reduces stale-result mistakes, but it does not
remove every build/source synchronization risk. For example, it cannot
help if sources change while GNATprove runs, or if GNATprove writes
outside the current directory and `--results` is not given.

## The loop (preferred)

```text
1. spark-refine prove -P project.gpr --format json > r.json
2. inspect analysis.orchestration.gnatprove_exit_code, then
   code / category / action / confidence of each diagnostic
3. modify implementation or proof support as appropriate;
   do not weaken authoritative requirements automatically
4. repeat from step 1
```

GNATprove's own console output goes to **stderr**, so stdout (`r.json`)
is always the JSON report or empty. Pass extra GNATprove switches after
`--`, verbatim:
`spark-refine prove -P project.gpr --format json -- --level=2 -j0`. Use
`--dry-run` to see the command without running it. In an Alire crate:
`alr exec -- spark-refine prove -P project.gpr --format json`.

Exit status of `prove`:

* GNATprove's **nonzero** exit code, if it returned one. A report is
  still produced if GNATprove wrote a fresh result set. A failed proof is
  exactly when the diagnostics are most useful. Without a fresh result,
  there is no report, and stderr says so;
* otherwise `1` if a `--fail-on CODE` diagnostic was emitted;
* otherwise `0`;
* `2`: nothing on stdout. Causes: GNATprove could not be launched; or
  GNATprove exited 0 but no unique fresh result set exists (none, or
  several listed sorted on stderr); or `--results PATH` was not freshly
  written.

If GNATprove exits 0 although the result has unproved checks, which the
project configuration may permit, `prove` reports them in a note and
does **not** override the exit code. To make CI fail, configure
GNATprove itself (e.g. `--checks-as-errors=on`).

Manual two-step loop (still supported): `gnatprove -P project.gpr`, then
`spark-refine explain --format json`. Rerun GNATprove after every source
change.

Exit status of `explain`:

* `0`: report produced (diagnostics are informational);
* `1`: a `--fail-on CODE` diagnostic was emitted;
* `2`: input problem, with nothing on stdout. Causes: no result set found,
  several result sets found (candidates listed on stderr, sorted; pass
  one explicitly), or malformed SARIF/.spark.

Stop and ask a human if `prove` or `explain` exits 2 with multiple
candidates. Do not respond by deleting other result directories to
force a choice. Also stop if the only way forward seems to be changing
an authoritative contract.

## JSON fields an agent should read

`format_version` is `1`. The Task 006 fields are additive, and every
Task 005 field is unchanged.

Per diagnostic:

| Field | Values | Use |
|---|---|---|
| `code` | `SRD001`, `SRD002`, `SRD003` | stable rule id |
| `category` | `proof_context`, `abstraction_boundary`, `prover_portfolio` | coarse semantic class |
| `action` | see below | workflow-level next step |
| `confidence` | `high`, `medium`, `low` | how much to trust the classification |
| `entity`, `primary_location`, `related[]` | | where to look |
| `explanation`, `recommendation`, `evidence` | prose | for humans; do not parse |

Top level:

```json
"summary": {
  "diagnostic_count": 3,
  "by_code":       {"SRD001": 1, "SRD002": 2, "SRD003": 0},
  "by_confidence": {"high": 1, "medium": 1, "low": 1},
  "by_category":   {"proof_context": 1, "abstraction_boundary": 2,
                    "prover_portfolio": 0},
  "by_action":     {"fix_invariant_then_reprove": 1, "...": 2}
}
```

The summary is computed from `diagnostics`. Every known key is present,
with value `0` when absent. There are no timestamps.

Also read `notes` and `analysis.rules`. For example,
`analysis.rules.SRD002.evaluated = false` means SRD002 was **not run**
because dependency (`.ali`) information was unavailable. That is not the
same as "no client-only gap". `analysis.input` (`{"path", "discovered":
true}`) appears only when `explain` auto-discovered the result set.

`analysis.orchestration` appears only in `prove` output. It was added in
Task 008 and keeps `format_version` 1:

```json
"orchestration": {
  "command": ["gnatprove", "-P", "project.gpr", "--level=2"],
  "gnatprove_exit_code": 1,
  "result_path": "obj/gnatprove",
  "result_selection": "fresh_discovery",
  "fresh": true,
  "stale_result_sets_ignored": ["obj/old/gnatprove"]
}
```

`command` is the exact argv that ran. `result_selection` is `explicit`
(from `--results`) or `fresh_discovery`. `stale_result_sets_ignored`
appears only for `fresh_discovery`. `gnatprove_raw_returncode` appears
only if GNATprove was killed by a signal; the exit code is then 128 + N.
There are no timestamps.

`spark-refine rules --format json` returns the catalogue with `category`,
`action` and `action_description` for each rule.

## Actions and what to do

Actions are **workflow-level**. They never name a line, a contract or an
edit.

### SRD001: `fix_invariant_then_reprove` (category `proof_context`)

A type invariant check failed in an entity whose postconditions GNATprove
reports as proved. Those postconditions were proved *assuming* the
invariant, so do not trust them yet.

The agent should generally:

1. inspect the **state update** in the operation (the implementation),
   and the **representation invariant** itself;
2. fix whichever is wrong. Usually it is the implementation. An
   invariant change is an authoritative change and needs review;
3. rerun GNATprove and re-read the postconditions.

Do **not** start by changing the behavioral postconditions. SRD001 is a
masking *risk*: it does not say the postcondition is false or depends on
the invariant.

### SRD002: `validate_client_goal_then_review_public_contracts` (category `abstraction_boundary`)

The implementation units are fully proved, but a client cannot prove a
precondition (`medium` confidence) or an assertion (`low`).

Before touching the public API, check:

1. **Is the client theorem actually true?** A false or too-strong client
   assertion produces exactly this pattern (see fixture
   `pool_false_client_assert`).
2. **Is the client's own `Pre` strong enough** to establish what it
   needs?
3. Would an intermediate client assertion help the provers?

Only then consider whether the public contracts expose too little.
Strengthening a public `Post` is an authoritative change: propose it for
review. SRD002 does not identify a callee or a specific contract.

### SRD003: `preserve_portfolio_or_strengthen_proof` (category `prover_portfolio`)

A check is proved by some single provers and not by others. The proof is
valid under the portfolio that proves it.

SRD003 is **not** produced by `prove` or `explain`. It comes from
`spark-refine compare-provers --run NAME=PATH --run ... --format json`,
run over separate single-prover GNATprove runs. In `prove` and
`explain` output, `by_code.SRD003` is therefore always `0`.

```text
spark-refine prove            -> SRD001 / SRD002 for ONE proof run
spark-refine compare-provers  -> SRD003 (several single-prover runs)
```

`prove` does not run a prover matrix. `prove -- --prover=z3` is just one
GNATprove run with that switch.

Do **not** assume "one solver fails ⇒ the proof architecture is wrong".
Keep the working prover portfolio (`--prover=...` / project switches).
Strengthen the proof (extra assertions or lemmas) only if single-prover
portability is an actual requirement.

## What `spark-refine` does not do

It does not identify the exact callee or `Pre` conjunct (no Libadalang
yet). It does not suggest source edits or decide proof status. Only
`prove` runs GNATprove, and it only relays GNATprove's verdict and exit
status. Those decisions remain with GNATprove, the agent and the human
reviewer.

