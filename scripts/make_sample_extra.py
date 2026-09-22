#!/usr/bin/env python3
"""Draw extra Defects4J bugs after the frozen seed=42 sample of 10.

Protocol:
  unique = first-seen order of experimental_setups/batches/{0..4} (864 lines)
  random.seed(42)
  first10 = random.sample(unique, 10)          # same SET as demos/sample10.txt
  remaining = [b for b in unique if b not in first10]
  extra = random.sample(remaining, N)          # continues the same RNG
  extra is then sorted by (project, index) for the file; the SET is what matters.

Not Table III. Chart-1 is never in these lists.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATCHES = ROOT / "vendor" / "RepairAgent" / "repair_agent" / "experimental_setups" / "batches"
SAMPLE10 = ROOT / "demos" / "sample10.txt"
EXTRA = ROOT / "demos" / "sample_extra.txt"
ALL = ROOT / "demos" / "sample_all.txt"
N_EXTRA_DEFAULT = 15


def unique_from_batches() -> list[str]:
    bugs: list[str] = []
    for i in range(5):
        text = (BATCHES / str(i)).read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                bugs.append(line)
    return list(dict.fromkeys(bugs))


def load_sample10() -> list[str]:
    return [ln.strip() for ln in SAMPLE10.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


def sort_bugs(bugs: list[str]) -> list[str]:
    def key(b: str) -> tuple[str, int]:
        proj, idx = b.split()
        return proj, int(idx)

    return sorted(bugs, key=key)


def draw(n_extra: int) -> tuple[list[str], list[str]]:
    unique = unique_from_batches()
    frozen = load_sample10()
    rng = random.Random(42)
    first = rng.sample(unique, 10)
    if set(first) != set(frozen):
        raise SystemExit(f"seed=42 first-10 SET drifted: {sorted(first)} vs {sorted(frozen)}")
    remaining = [b for b in unique if b not in set(first)]
    extra = rng.sample(remaining, n_extra)
    return frozen, sort_bugs(extra)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-extra", type=int, default=N_EXTRA_DEFAULT)
    args = parser.parse_args()
    frozen, extra = draw(args.n_extra)
    EXTRA.write_text("\n".join(extra) + "\n", encoding="utf-8")
    ALL.write_text("\n".join(frozen + extra) + "\n", encoding="utf-8")
    print(f"unique-from-batches verified; wrote {EXTRA} ({len(extra)}) and {ALL} ({len(frozen)+len(extra)})")
    for b in extra:
        print(f"  extra {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
