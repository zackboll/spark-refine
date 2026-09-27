# Agent integration: using `spark-refine` output safely

This page is for AI coding agents (Cline, Devin, ...), CI and editor
integrations that consume `spark-refine explain --format json`.

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
* `spark-refine` is read-only and deterministic. It never runs GNATprove,
  edits sources, repairs proofs or changes contracts.
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

`spark-refine explain` analyzes the proof results you point it at. They
correspond to the current sources **only if GNATprove was just run**. An
agent must rerun GNATprove after every source change before calling
`spark-refine` again. Otherwise it is reading stale results.

## The loop

```text
1. run GNATprove                  gnatprove -P project.gpr
2. run spark-refine               spark-refine explain --format json > r.json
3. inspect code / category / action / confidence of each diagnostic
4. modify implementation or proof support as appropriate
5. do not weaken authoritative requirements automatically
6. rerun GNATprove (step 1), then spark-refine again
```

Exit status of `explain`:

* `0`: report produced (diagnostics are informational);
* `1`: a `--fail-on CODE` diagnostic was emitted;
* `2`: input problem, with nothing on stdout. Causes: no result set found,
  several result sets found (candidates listed on stderr, sorted; pass
  one explicitly), or malformed SARIF/.spark.

Stop and ask a human if step 2 exits 2 with multiple candidates. Also
stop if the only way forward seems to be changing an authoritative
contract.

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
true}`) appears only when the result set was auto-discovered.

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

SRD003 is **not** produced by `explain`. It comes from
`spark-refine compare-provers --run NAME=PATH --run ... --format json`,
run over separate single-prover GNATprove runs. In `explain` output,
`by_code.SRD003` is therefore always `0`.

Do **not** assume "one solver fails ⇒ the proof architecture is wrong".
Keep the working prover portfolio (`--prover=...` / project switches).
Strengthen the proof (extra assertions or lemmas) only if single-prover
portability is an actual requirement.

## What `spark-refine` does not do

It does not identify the exact callee or `Pre` conjunct (no Libadalang
yet). It does not suggest source edits, run GNATprove, or decide proof
status. Those remain with GNATprove, the agent and the human reviewer.

