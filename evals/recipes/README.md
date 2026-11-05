# Eval recipes: technical test cases for the AIX / Oracle Bob modes

Each eval recipe is a **test case** for one Bob mode on a realistic task: its front
matter holds the prompt and the patterns a correct answer must (and must not) contain,
and its body is the reference answer. `evals/recipe_evals.py` reads these files, so a
reference answer and its test never drift apart.

These files are written for automated checks, not for people. The step-by-step,
copy-and-paste labs for administrators are in [`../../recipes/`](../../recipes/README.md).

| ID | Recipe | Mode | Skills it exercises |
|---|---|---|---|
| R00 | [AIX command accuracy](00-aix-command-accuracy.md) | `aix` | `aix` |
| R01 | [Oracle install preparation](01-oracle-install-prereqs.md) | `oracle-aix` | `oracle-aix` |
| R02 | [Assessment / best practices](02-assessment-best-practices.md) | `oracle-aix`, `aix-review` | `oracle-aix` |
| R03 | [Backup](03-backup.md) | `oracle-aix` | `aix`, `oracle-aix`, `ansible-aix` |
| R04 | [Patching AIX + Oracle + Live Kernel Update](04-patching-and-live-kernel-update.md) | `oracle-aix` | `aix`, `oracle-aix`, `ansible-aix` |
| R05 | [Performance and monitoring](05-performance-monitoring.md) | `oracle-aix` | `aix`, `oracle-aix` |

## How to run a demo

1. Open the repository in IBM Bob and select the mode named in the recipe.
2. Paste the `prompt` from the recipe front matter, or print it:

   ```bash
   python evals/recipe_evals.py --prompts
   ```

3. Follow the "Demo script" section of the recipe. The "Reference answer" section is
   what a correct answer looks like.
4. Optional: grade Bob's real answer against the recipe's patterns:

   ```bash
   python evals/recipe_evals.py --grade R04 answer.txt
   ```

   The grader fails the answer if a required item is missing or a forbidden pattern
   (a Linux-ism, an invented flag) is present.

## Recipe file format

```yaml
---
id: R04                       # unique, R + two digits
title: ...
mode: oracle-aix              # a slug from .bob/custom_modes.yaml
skills: [aix, oracle-aix]     # skills under .agents/skills/
reads: [path, ...]            # repository files the answer must be grounded in
prompt: >-                    # the text to paste into Bob
  ...
must_include: ["literal", ...]    # case-insensitive literal strings
must_not_include: ['regex', ...]  # regular expressions (single-quoted YAML)
---
```

Rules for writing a recipe:

- English only, as for every file in this repository.
- Every command must be AIX-native and bash compatible. `scripts/validate.py` and the
  evals scan the shell blocks for Linux-isms.
- The reference answer must satisfy its own `must_include` and `must_not_include`
  lists. The evals check this, so a recipe cannot ship with a contradictory reference.
- Never invent a flag, tunable, or module parameter. Check it in the IBM
  documentation and cite the companion file the answer comes from.
- Destructive steps are previewed, confirmed, and shown with their revert.

## Relation to the evals

- [`evals/hallucination_cases.yaml`](../hallucination_cases.yaml): one case per
  known wrong command (Linux-ism or invented flag) with the right AIX replacement.
  Recipe R00 and R05 are the live demos of these cases.
- [`evals/recipe_evals.py`](../recipe_evals.py): structure, grounding, reference
  answer consistency, hallucination coverage, and the answer grader.
- [`evals/run_evals.py`](../run_evals.py): the existing skill checks. It also runs
  the recipe evals, so one command covers everything.
