# Security and Soundness Policy

This project treats **proof soundness regressions**, and anything that
misrepresents proof authority, as security-sensitive issues.

GNATprove is the proof authority. `spark-refine` consists of reusable
proof-pattern libraries and read-only diagnostics that interpret
GNATprove results. Neither may make something look proved that is not,
or push a user or AI agent toward weakening a requirement.

## Soundness-sensitive issues

Please report privately before public disclosure if a bug can cause any
of the following.

**Any component:**

- silently weakening a user-authored requirement or any other
  authoritative specification.

**Diagnostics (`spark-refine`):**

- reporting, summarizing or presenting an unproved obligation as proved,
  or a partial analysis as complete;
- claiming diagnostic certainty that the evidence does not support, in a
  way that could lead a user or agent to weaken an authoritative
  requirement. Examples: stating that a public contract *is* deficient,
  or that a postcondition *is* independent of a failed invariant;
- silently ignoring or resolving a disagreement between SARIF and
  `.spark`;
- unsafe dependency inference in SRD002: treating a client as having a
  fully proved dependency closure when dependency information is
  missing, partial, guessed or from an unsupported `.ali` version;
- modifying any file under a supposedly read-only command (`explain`,
  `analyze`, `compare-provers`, `rules`);
- executing untrusted project input unexpectedly during analysis.

**Proof-pattern libraries (`proof_patterns/`):**

- introducing unchecked assumptions or axioms: `pragma Assume`, bodyless
  or imported ghost functions used as axioms, justifications, disabled
  checks or suppressions;
- a library claim that is accepted without being proved per instance;
- documentation claiming support for representations that are not
  covered by proved instances, in a way that could mislead users about
  what is verified.

**Historical scope.** If generation is ever revived, the original
concerns apply again: emitting an unchecked assumption while claiming
assumption-free generation, omitting a required generated obligation, or
misreporting an unproved generated property as proved.

## Reporting

Until a dedicated private reporting channel exists, do not use this
bootstrap repository for sensitive vulnerability details. Establish a
security contact before public release.

## Ordinary bugs

Please keep these on the normal issue tracker:

- ordinary diagnostic bugs that make no claim of proof authority, e.g. a
  missed diagnostic, an unclear explanation, an overly conservative
  warning, or a rule skipped where it could have run;
- unsupported GNATprove versions or result layouts, when the tool
  degrades explicitly;
- discovery or packaging problems;
- unsupported language constructs;
- proof-performance regressions.

The dividing line: a bug is soundness-sensitive when it could make
something *look* proved, or *look* safe to weaken, when it is not.
