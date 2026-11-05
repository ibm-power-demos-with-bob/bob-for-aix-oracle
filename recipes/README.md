# Recipes: learn IBM Bob on AIX and Oracle, step by step

These recipes are written for **AIX and Oracle system administrators**. Each recipe (a
"lab") is a guided session with IBM Bob on a realistic task. You copy a prompt, paste it
into the Bob chat, look at what Bob does, and move to the next step. No scripting
knowledge is needed.

The same files are the support of the automated tests: every step is a test case (see
[Automated tests](#automated-tests)). The technical scenarios with reference answers are in
[`../evals/scenarios/`](../evals/scenarios/README.md).

## The labs

| Lab | Title | Mode | Duration | Level | Changes the system? |
|---|---|---|---|---|---|
| [Lab 01](01-prepare-oracle-install.md) | Prepare an LPAR for an Oracle + ASM install | 🗄️ Oracle on AIX/Power | 40 min | Intermediate | No: Bob writes scripts, you run them |
| [Lab 02](02-assess-best-practices.md) | Assess an Oracle LPAR against best practices | 🗄️ Oracle on AIX/Power, 🔍 AIX/Oracle Review | 30 min | Beginner | No: read-only |
| [Lab 03](03-backup-aix-and-oracle.md) | Back up AIX and Oracle, and plan the restore | 🗄️ Oracle on AIX/Power, ⚙️ Ansible AIX | 40 min | Intermediate | Only after your explicit "yes" |
| [Lab 04](04-patch-aix-oracle-lku.md) | Patch AIX and Oracle, and decide on Live Kernel Update | 🗄️ Oracle on AIX/Power, 🔍 AIX/Oracle Review | 45 min | Advanced | No: plan and previews only |
| [Lab 05](05-performance-and-monitoring.md) | Find a performance problem and set up monitoring | 🗄️ Oracle on AIX/Power | 40 min | Intermediate | Only the monitoring step, after your "yes" |

Suggested path: Lab 02 first if you want a quick win (read-only, 30 minutes), then
Lab 01, 03, 04 and 05 in any order. Lab 03 comes before Lab 04, because the patching
lab reuses the backup as its rollback path.

## What you need

- **IBM Bob** with this repository open as the workspace. The four modes appear in the
  mode picker (see the [main README](../README.md#bob-modes)). Check *Settings → Skills*:
  `aix`, `ansible-aix` and `oracle-aix` must be listed.
- **An AIX LPAR on IBM Power** with Oracle Database, ideally a test system. The labs work
  on any Power system, on premises or in the cloud.
- **A way for the commands to reach the LPAR.** Pick one:
  1. Bob has a shell on the LPAR (for example an SSH session in the Bob terminal). Bob
     runs the read-only commands itself and asks before any other command.
  2. Bob has no access. Bob prints the commands, you run them in your own SSH session,
     and you paste the output back into the chat. Every lab works this way too.
- **Root access** for the AIX steps, and the Oracle software owner (`oracle`, and `grid`
  with ASM or RAC) for the Oracle steps. Bob never uses `root` for Oracle tools.

## How a lab works

Every step has the same four parts:

1. **Goal** of the step in one sentence.
2. **Prompt**, in a `text` block. Copy it as is. Text between `<` and `>` is a value
   you replace, and every such value is explained right under the prompt.
3. **What to observe**: what a good answer from Bob looks like. Bob's wording varies from
   run to run. Check the *content* (the commands, the questions, the warnings), not the
   exact sentences.
4. **If it goes differently**: what to do when Bob's answer is not what you expected.

Some steps are marked **Trap**. A trap is a prompt that a Linux administrator, or a less
careful assistant, would answer with a Linux command. Bob must refuse the Linux form and
give the AIX one. Traps are the best moments for a live demonstration.

## Safety rules used in all labs

- **Read first, change later.** Every lab starts with read-only commands.
- **Bob proposes, you confirm.** Anything that changes the system, such as `chdev`,
  `mkuser`, `installp`, `opatch apply` or an RMAN `DELETE`, must come with its preview,
  its rollback and a question "may I run this?". If Bob runs one without asking, stop the
  session and report it.
- **Test system first.** Do the labs on a non-production LPAR. A lab that has an effect
  on the system says so in its overview.
- **Backup before change.** The labs that go further than reading start with a `mksysb`
  or an RMAN backup (see Lab 03).
- **Oracle commands need the Oracle environment.** Before `sqlplus`, `rman`, `opatch` or
  `srvctl`, Bob checks `ORACLE_HOME`, `ORACLE_SID`, `ORACLE_BASE`, `PATH` and `LIBPATH`
  (never `LD_LIBRARY_PATH` on AIX), and asks you which OS user owns the software if it
  cannot tell.

## Where the generated files go

Bob saves its documents and scripts in a `work/` directory of the workspace, for example
`work/lab01/prepare-os.sh`. Review every generated script before you run it on a system.
The directory is yours: delete it whenever you want to restart a lab.

## Automated tests

Each `## Step N:` section ends its prompt with a hidden `<!-- eval -->` block. A reader
does not see it, and `evals/scenario_evals.py` reads it:

```text
<!-- eval
mode: oracle-aix                  # a slug from .bob/custom_modes.yaml
must_include: ["mksysb", "..."]   # case-insensitive strings a correct answer contains
must_not_include: ['\buseradd\b'] # regular expressions a correct answer never matches in code
-->
```

`python evals/run_evals.py` (and the CI) checks, for every step of every recipe:

- there is exactly one eval block, with a known Bob mode and valid regular expressions;
- the prompt just above it is a real task;
- every `must_include` string is described in the step, so the recipe and its test do not drift;
- the commands shown in the step do not match its `must_not_include` patterns, nor any case
  of [`hallucination_cases.yaml`](../evals/hallucination_cases.yaml);
- the grader accepts a complete answer and rejects an incomplete or Linux-flavoured one.

To grade a real Bob session, save its answer to a file and run:

```bash
python evals/scenario_evals.py --recipe-prompts                 # list recipe steps, modes and prompts
python evals/scenario_evals.py --grade-recipe 03:3 answer.txt   # recipe 03, step 3; exit code 1 on failure
```

When you add or change a step, update its eval block in the same commit.

## Related material

- Skills: [`aix`](../.agents/skills/aix/SKILL.md),
  [`ansible-aix`](../.agents/skills/ansible-aix/SKILL.md),
  [`oracle-aix`](../.agents/skills/oracle-aix/SKILL.md).
- Technical eval scenarios and answer grader: [`../evals/scenarios/`](../evals/scenarios/README.md).
- Known wrong command lines that Bob must never produce:
  [`../evals/hallucination_cases.yaml`](../evals/hallucination_cases.yaml).
