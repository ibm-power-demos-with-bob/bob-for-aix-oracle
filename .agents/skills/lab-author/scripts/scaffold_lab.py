#!/usr/bin/env python3
"""Scaffold a new lab in recipes/ that already satisfies the structure tests.

Every free-text field is a TODO that must be replaced. The generated file passes
`python evals/run_evals.py` as is (so the structure is right from the start), and
`grep -n TODO recipes/NN-*.md` must print nothing before the lab is delivered.

Usage:
    python .agents/skills/lab-author/scripts/scaffold_lab.py --title "Correlate an incident" \
        --slug correlate-oracle-and-errpt --mode oracle-aix [--steps 4] [--number 06] [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RECIPES = ROOT / "recipes"

MODES = {
    "oracle-aix": "🗄️ Oracle on AIX/Power",
    "aix-review": "🔍 AIX/Oracle Review",
    "ansible-aix": "⚙️ Ansible AIX",
}
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

STEP = """## Step {n}: TODO step title (5 minutes)

**Goal:** TODO one sentence describing what the reader gets from this step.

**Prompt:**

```text
TODO write the copy-and-paste prompt for this step in at least nine words here.
```

<!-- eval
mode: {mode}
must_include: ["TODO"]
must_not_include: []
-->

TODO explain every <placeholder> used in the prompt.

**What to observe:**

- TODO what a good answer from Bob contains (commands, questions, warnings, source file).

**If it goes differently:** TODO what to do when Bob's answer is not what you expected.

---

"""

TEMPLATE = """# Lab {number}: {title}

## Overview

TODO a short paragraph: the task, what Bob does, and what the reader learns.

**Duration**: TODO 30 minutes
**Difficulty**: TODO Beginner
**Mode**: {mode_name}
**Target**: TODO an AIX LPAR running Oracle Database
**Output**: `work/lab{number}/TODO.md`

> ✅ **TODO say whether the lab changes the system.** Anything that changes it needs a
> preview, a rollback and your explicit confirmation.

---

## Prerequisites

- Bob open on this repository, mode **{mode_name}**.
- TODO the accounts needed (`root` for the AIX layer, `oracle` or `grid` for Oracle tools).

---

{steps}## ✅ Success criteria

- [ ] TODO a checkable outcome.

---

## Key takeaways

- TODO one lesson per bullet.

---

## Next steps

TODO link the next lab, for example [Lab 01](01-prepare-oracle-install.md).
"""


def next_number() -> int:
    numbers = [int(p.name[:2]) for p in RECIPES.glob("[0-9][0-9]-*.md")]
    return max(numbers, default=0) + 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--title", required=True, help="lab title, without the 'Lab NN:' prefix")
    parser.add_argument("--slug", required=True, help="file slug, lowercase words joined by dashes")
    parser.add_argument("--mode", required=True, choices=sorted(MODES), help="mode of the steps")
    parser.add_argument("--steps", type=int, default=4, help="number of steps (minimum 4)")
    parser.add_argument("--number", help="two-digit lab number (default: next free)")
    parser.add_argument("--dry-run", action="store_true", help="print the file, write nothing")
    args = parser.parse_args(argv)

    if not SLUG_RE.match(args.slug):
        parser.error("--slug must be lowercase words joined by single dashes")
    if args.steps < 4:
        parser.error("--steps must be at least 4 (the tests require 4 steps per lab)")
    number = args.number or f"{next_number():02d}"
    if not re.fullmatch(r"\d{2}", number):
        parser.error("--number must be two digits")
    existing = sorted(RECIPES.glob(f"{number}-*.md"))
    if existing:
        parser.error(f"lab {number} already exists: {existing[0].name}")

    steps = "".join(STEP.format(n=n, mode=args.mode) for n in range(1, args.steps + 1))
    text = TEMPLATE.format(number=number, title=args.title, mode_name=MODES[args.mode], steps=steps)
    target = RECIPES / f"{number}-{args.slug}.md"
    if args.dry_run:
        sys.stdout.write(text)
        return 0
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"created {target.relative_to(ROOT).as_posix()}")
    print("next: replace every TODO, add the row to recipes/README.md, then run "
          "python scripts/validate.py and python evals/run_evals.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
