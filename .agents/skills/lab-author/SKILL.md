---
name: lab-author
description: >-
  Use when the user wants to create, add, extend, or review a recipe, lab, or demo in
  recipes/ for the AIX, Ansible AIX, or Oracle on AIX/Power Bob modes, so that it also
  enriches the automated evals (each step is a test case with an eval block). Covers the
  next lab number, topic and mode choice, the exact lab format, AIX command verification,
  registration in the indexes, and validation with validate.py and run_evals.py. Trigger
  phrases: "new recipe", "new lab", "create a lab", "add a demo", "recipes on demand",
  "extend recipes/", "add an eval step", "lab 06", "generate a Bob demo for AIX".
---

# Lab author: add a recipe (lab) to `recipes/`

A lab is a guided Bob session for an AIX or Oracle administrator, and **every step is also an
automated test case**. A lab that passes `python evals/run_evals.py` enriches the evals at the
same time. Follow the steps in order. Do not skip the verification step: a lab with an invented
flag is worse than no lab.

Read these two files from this skill before writing anything:

- `lab-format.md`: the exact lab template, the eval-block syntax, and every rule the tests enforce.
- `verified-facts.md`: AIX and Ansible facts already checked on a real LPAR (do not rediscover them).

## Step 1: Scope the lab

Use `ask_followup_question` (one question per turn) to settle:

1. **Topic.** Propose 3 topics from the table below when the user has none. Never build a lab
   on a skill or topic that is not finished (for example the Oracle licensing work in `WIP/`).
2. **Mode** of the lab: `oracle-aix`, `aix-review`, `ansible-aix` (or `aix` for a step, but the
   lab must name at least one of the three display names in `lab-format.md`).
3. **Does it change the system?** Default is no: read-only, or "plan and previews only". Any
   change needs a preview, a rollback, and an explicit "yes" from the user.
4. **The Linux-reflex trap**: the one prompt a Linux administrator would answer with a Linux command.

| Candidate topic | Source to read first | Typical trap |
|---|---|---|
| Correlate an Oracle incident with the AIX error log | `.agents/skills/oracle-aix/best-practices/diagnostics.md` | `dmesg` or `journalctl` |
| Add and validate ASM or JFS2 storage | `.agents/skills/oracle-aix/best-practices/io-storage.md` | `mkvg` on an ASM `rhdisk` |
| RAC network and interconnect | `.agents/skills/oracle-aix/best-practices/network-rac.md` | `sysctl -w` |
| Automate an AIX task with Ansible | `.agents/skills/ansible-aix/SKILL.md` and its `examples/` | `ansible.builtin.systemd`, `ansible.builtin.user` |
| NIM and VIOS basics | `.agents/skills/aix/SKILL.md` | `yum`, `apt-get` |

## Step 2: Investigate before writing

1. List `recipes/` and take the **next free number** (the tests require a contiguous numbering
   from 01). Read `recipes/README.md` and one existing lab of the same mode as the template.
2. Read the skill and best-practice files for the topic (see the table). Cite the source file
   and section for every recommendation in "What to observe".
3. Read `evals/hallucination_cases.yaml` so no code line of the lab matches a known wrong form.

## Step 3: Verify every command, flag, tunable, and module parameter

Never invent one. For each command that appears in a step:

- Check the IBM documentation with `search_ibm_docs` (AIX 7.3) or the `ibm-docs-search` MCP tools.
- For Ansible: `ansible-doc -t module ibm.power_aix.<module> --json` lists the real parameters.
  Only modules and roles of the `ibm.power_aix` collection are allowed.
- Check `verified-facts.md` first. If a fact is not there and not in the docs, write "verify" in
  the lab instead of guessing.
- A live check on an LPAR is optional, **read-only only**, and only with the user's explicit
  agreement. Never run a change-making command on a shared system without that agreement.
- If you find a wrong command line that an assistant would plausibly produce **and** its
  correct form is documented, add a case to `evals/hallucination_cases.yaml` (next free `H##`,
  with `wrong`, `example`, `fix`, `why`, `source`). The `fix` string must appear in a skill or lab.

## Step 4: Scaffold, then fill

Generate a skeleton that already satisfies the structure tests:

```bash
python .agents/skills/lab-author/scripts/scaffold_lab.py --title "<title>" --slug <slug> --mode oracle-aix
```

Options: `--number NN` (default: next free), `--steps N` (default 4, minimum 4), `--dry-run`.
Then replace every `TODO` of the generated file, applying the rules of `lab-format.md`:

- English only, generic wording (no cloud-provider-specific or version-specific claims).
- Each step: Goal, a copy-and-paste `text` prompt of more than 8 words, the eval block right
  after it, "What to observe", "If it goes differently". Explain each `<placeholder>` under the prompt.
- At least one step marked **Trap**, and a confirmation gate for anything that changes a system.
- `must_include` strings are literals the step text really contains. `must_not_include` holds
  regexes for the wrong forms (for example `'\bdmesg\b'`).
- Keep generated files of the lab under `work/labNN/` (git-ignored).

Do not leave any `TODO`: `grep -n TODO recipes/NN-*.md` must print nothing.

## Step 5: Register the lab

- Add a row to the labs table of `recipes/README.md` (link as `(NN-slug.md)`, mode, duration,
  level, "Changes the system?"). Mention any new dependency in the suggested path.
- The root `README.md` and `evals/README.md` describe the recipes without a fixed count. Update
  them only if they would become wrong.
- If you changed a skill's frontmatter, run `python scripts/sync_bob_skills.py`.

## Step 6: Validate (mandatory before reporting done)

```bash
python scripts/validate.py
python evals/run_evals.py
python evals/scenario_evals.py --recipe-prompts
```

Both checks must pass with no new warning. Then grade one new step with a sample answer:

```bash
python evals/scenario_evals.py --grade-recipe NN:2 answer.txt
```

For Ansible snippets, also run `ansible-lint --profile production` on the playbook (on Windows,
run it in WSL: it does not run natively).

## Step 7: Report

Summarise in the user's language: the lab number and title, the steps and their modes, the
trap, the commands verified (and how), any new hallucination case, and the validation results.
Commit and push only when the user asks, with a conventional message such as
`feat(recipes): add lab NN <topic>`.
