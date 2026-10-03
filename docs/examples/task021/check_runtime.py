#!/usr/bin/env python3
"""Check saved exact inputs and chunkings against independent hashlib oracles."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    cases = json.loads(Path(__file__).with_name("runtime_cases.json").read_text())
    executable = Path(sys.argv[1]).resolve()
    for case in cases:
        data = bytes.fromhex(case["hex"])
        expected = hashlib.sha256(data).hexdigest()
        assert expected == case["expected"], case["id"]
        assert sum(case["chunks"]) == len(data), case["id"]
        result = subprocess.run(
            [str(executable), case["hex"], str(case["origin"]),
             ",".join(map(str, case["chunks"]))],
            text=True, capture_output=True, check=True,
        )
        if result.stdout.splitlines() != [expected, expected]:
            raise AssertionError((case["id"], result.stdout, result.stderr))
    print(f"PASS: {len(cases)} cases, one-shot and streaming for each; hashlib oracle")


if __name__ == "__main__":
    main()