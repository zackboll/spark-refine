# Ring-buffer design fixture

This directory defines the first intended `spark-refine` benchmark shape. It is deliberately a **design fixture**, not yet a proved example.

The production type uses a fixed array plus `First` and `Length`. The public ghost model presents an ordinary logical sequence. The manifest describes which private representation fields implement the circular-sequence roles.

The first implementation task for this repository is to replace this design fixture with a complete hand-written SPARK/GNATprove baseline before generating any proof code.

That ordering is intentional: the generator should be based on measured manual proof needs rather than imagined boilerplate.
