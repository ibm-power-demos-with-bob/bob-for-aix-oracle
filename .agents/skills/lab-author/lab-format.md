# Lab format and test rules

Read by `SKILL.md`. Everything here is enforced by `evals/scenario_evals.py`
(`TestRecipes`, `TestRecipeSteps`) and `validate.py` (in the repo `scripts` directory). The reference implementation
is `recipes/02-assess-best-practices.md`.

## File and title

- File: `recipes/NN-slug.md`. `NN` is the next free number, contiguous from `01`.
  The two digits are the key of the tests (`--grade-recipe NN:STEP`).
- First line: `# Lab NN: <title>`.

## Required sections, in this order

`## Overview`, `## Prerequisites`, one or more `## Step N: <title> (X minutes)`,
`## ✅ Success criteria`, `## Key takeaways`, `## Next steps`.

The overview has a short paragraph, then these bold fields, one per line:

```text
**Duration**: 30 minutes
**Difficulty**: Beginner | Intermediate | Advanced
**Mode**: 🗄️ Oracle on AIX/Power, then 🔍 AIX/Oracle Review
**Target**: an AIX LPAR running Oracle Database
**Output**: `work/labNN/<file>`
```

Followed by one admonition saying whether the lab changes the system:

```text
> ✅ **Nothing is changed in this lab.** ...
> ⚠️ **Only <the step> changes the system, after your explicit "yes".** ...
```

The `**Mode**` line must contain at least one of these display names:

| Slug (eval block) | Display name |
|---|---|
| `oracle-aix` | 🗄️ Oracle on AIX/Power |
| `aix-review` | 🔍 AIX/Oracle Review |
| `ansible-aix` | ⚙️ Ansible AIX |
| `aix` | 🖥️ AIX (not enough alone: add one of the three above) |

## Step block

````text
## Step N: <title> (X minutes)

**Goal:** <one sentence>

**Prompt:**

```text
<copy-and-paste prompt, more than 8 words. Replaceable values go in <angle brackets>>
```

<!-- eval
mode: oracle-aix
must_include: ["literal one", "literal two"]
must_not_include: ['\bdmesg\b']
-->

Explain every <placeholder> here (for example: Replace `<db>` with the database unique name).

**What to observe:**

- ...

**If it goes differently:** ...
````

Rules:

- At least **4 steps** per lab. All labs together must keep at least 20 steps.
- Each step has `**Goal:**` and a ```` ```text ```` prompt block.
- **Exactly one** `<!-- eval ... -->` block per step, placed directly after the prompt block.
  The last ```` ```text ```` block before it is the prompt, and it needs more than 8 words.
- A trap step is marked `**Trap**` in its title or text. A trap is a prompt a Linux
  administrator would answer with a Linux command. Bob must refuse it and give the AIX form.
- The lab must contain `**Trap` or the word `confirm` (case-insensitive). Any change needs
  a preview, a rollback, and an explicit "yes".

## Eval block

| Field | Rule |
|---|---|
| `mode` | A slug of `.bob/custom_modes.yaml`: `aix`, `ansible-aix`, `oracle-aix`, `aix-review` |
| `must_include` | Non-empty list of literals. Matching is case-insensitive. **Each literal must appear in the visible step text** (the text without the eval comment), so the lab and its test cannot drift |
| `must_not_include` | List of valid regexes (may be `[]`). Scanned in the code lines of an answer. **No code line of the step itself may match them** |

Good `must_include` values are the commands and words a correct answer cannot do without
(`"mksysb -i -e"`, `"lsmpio -q"`, `"PASS"`). Avoid sentences. Good `must_not_include` values
are the Linux forms of the trap (`'\bsystemctl\b'`, `'\buseradd\b'`, `'\bdmesg\b'`).

The grader accepts an answer made of all `must_include` strings and rejects "I do not know."
It also rejects every regex of `evals/hallucination_cases.yaml` found in a code line.

## Content rules

- English only. The tests flag the words `les des pour avec vous est une dans cette`.
- Shell code blocks (`bash`, `sh`, `ksh`, `shell`, `sql`) must contain no Linux-only command:
  `date -d`, `pgrep`, `systemctl`, `useradd`/`usermod`, `sysctl`, `journalctl`, `dmesg`,
  `lspci`, `free -m`, `sed -i`, `grep -P`, `export LD_LIBRARY_PATH`. Comment lines
  (`#`, `--`, `:`) and trailing ` # comments` are ignored.
- Prose may quote a wrong command to warn against it, but put it in a `text` block or in
  backticks outside a shell block.
- Ansible content uses only `ibm.power_aix.<module>` names listed in `validate.py` (in the repo `scripts` directory).
- Link other labs with a relative Markdown link to the lab file name. Broken links fail `validate.py`.
- Keep wording generic: no cloud-provider-specific and no version-specific claims.
- Safety wording to reuse: read first; Bob proposes and the user confirms; test system first;
  backup before change; check the Oracle environment before Oracle tools; Bob never uses
  `root` for Oracle tools; generated files go in `work/` (git-ignored).

## Register the lab

Add a row to the table of `recipes/README.md`. The test `test_recipes_are_listed_in_the_index`
requires the link `(NN-slug.md)` in that file.
