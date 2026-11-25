# bob-for-aix-oracle

**Quick install (global):** paste this into your IBM Bob:

```text
Install the skills in .agents/skills/ from https://github.com/ibm-power-demos-with-bob/bob-for-aix-oracle globally for yourself (your user-level skills directory), then run the .bob/commands/oracle-aix-setup.md workflow to clone and install the Oracle skills.
```

AI agent skills and modes for IBM AIX system administration, Ansible automation on AIX,
and Oracle Database administration on AIX / IBM Power Systems.

Built for **IBM Bob**. The skills also work with other agents that read
`.agents/skills/`.

---

## Repository Layout

```
.agents/skills/                     # canonical skills (shared by all agents)
  aix/SKILL.md                      # AIX administration
  lab-author/                       # create a new recipe (lab) that also enriches the evals
    SKILL.md                        # procedure: scope, verify, scaffold, register, validate
    lab-format.md, verified-facts.md
    scripts/scaffold_lab.py         # skeleton generator for recipes/NN-slug.md
  ansible-aix/
    SKILL.md                        # Ansible with ibm.power_aix
    examples/*.yml                  # complete playbooks, ansible-lint production-clean
  oracle-aix/
    SKILL.md                        # Oracle on AIX/Power: always-on rules + routing table
    best-practices/
      diagnostics.md                # diagnosis flows (I/O, CPU, paging, ORA errors, RAC)
      cpu.md                        # SMT, CPU folding, vCPU/entitlement, Power11 migration
      memory.md                     # SGA page sizes, 16 MB pages, NUMA, vmo, DSO, AME
      io-storage.md                 # AIO, hdisk/FC/MPIO, LUN layout, flash tiers, ASM on AIX, JFS2, LVM, redo
      network-rac.md                # no/ISNO, RAC interconnect, interface naming, HAIP
      os-prereqs.md                 # filesets, IOCP, users/limits, 19c install + patching
      misc.md                       # mutex spin, MARKHOT, SMT CPU %, PowerVS tiers, pigz
    operations/                     # (git-ignored) Oracle community db skill, via /oracle-aix-setup
.bob/
  custom_modes.yaml                 # Bob modes: aix, ansible-aix, oracle-aix, aix-review
  rules-<mode>/                     # always-on rules loaded for each mode
  skills/<name>/SKILL.md            # generated pointers to .agents/skills (Bob discovery)
  commands/oracle-aix-setup.md      # /oracle-aix-setup slash command
recipes/                            # step-by-step recipes for AIX + Oracle administrators (01-05), also automated tests
  README.md                         # prerequisites, recipe list, how a recipe works, how it is tested
  0N-*.md                           # one recipe per task, with copy-and-paste prompts and <!-- eval --> test blocks
evals/
  run_evals.py                      # runs every eval (skills + scenarios + recipes + hallucination cases)
  scenario_evals.py                 # scenario/recipe checks and answer graders (--prompts, --grade, --recipe-prompts, --grade-recipe)
  hallucination_cases.yaml          # known wrong AIX command lines and their fixes
  scenarios/                        # technical eval scenarios (S00-S05) with reference answers
    README.md                       # scenario format and how to grade an answer
scripts/
  validate.py                       # static checks (run in CI)
  sync_bob_skills.py                # regenerate .bob/skills pointers
.github/workflows/validate.yml      # CI: validate.py + ansible-lint on the examples
```

### How the pieces fit together

- **Skills** (`.agents/skills/<name>/SKILL.md`) hold the actual guidance. Their frontmatter
  `description` decides when an agent activates them.
- The `oracle-aix` skill keeps `SKILL.md` short. Detailed topics live in companion files
  that the agent reads **on demand**, following the routing table in `SKILL.md`.
- **Bob discovery:** Bob's documentation lists `.bob/skills/` and `~/.bob/skills/` as
  skill locations. `.bob/skills/` therefore holds small generated pointer skills with the
  same frontmatter, which tell Bob to read the canonical file. Check Bob's *Settings → Skills*
  tab. If Bob also lists the `.agents/skills/` copies (duplicates), delete `.bob/skills/`.
- **Modes** (`.bob/custom_modes.yaml`) set the persona, the tool groups, and file-type edit
  restrictions. Their `customInstructions` load the matching skill, or read its
  `SKILL.md` directly as a fallback.
- **Rules** (`.bob/rules-<slug>/`) hold the non-negotiable rules, applied on every turn of
  that mode even if a skill doesn't load.

---

## Skills

| Skill | Activates for | Highlights |
|---|---|---|
| `aix` | AIX administration, troubleshooting, tuning, shell automation | AIX vs Linux command map, SRC, tunables (`-L`/`-p`/`-r`), performance triage, installp/emgr/TL-SP, mksysb/alt_disk, NIM, VIOS basics |
| `ansible-aix` | Playbooks and roles with `ibm.power_aix` | Real module and role catalogue, check-mode and idempotency rules, Python bootstrap, linted examples |
| `oracle-aix` | Oracle Database on AIX / Power, including PowerVS (not Linux) | Safety rules, diagnosis flows, CPU/memory/I-O/network best practices, install/patch |
| `lab-author` | Creating or extending a recipe in `recipes/` on demand | Next lab number, verified AIX facts, exact lab format, scaffold script, validation with `validate.py` and `run_evals.py` |

The `oracle-aix` skill hands platform-neutral Oracle topics (SQL, PL/SQL, RMAN, Data Guard,
AWR) to the [Oracle `db` skill](https://github.com/oracle/skills/tree/main/db) when it is
installed under `.agents/skills/oracle-aix/operations/`.

## Bob Modes

| Mode | Slug | Tools |
|---|---|---|
| 🖥️ AIX | `aix` | read, edit (shell/config/docs), execute, MCP, skills, todo, subagents, mode switch |
| ⚙️ Ansible AIX | `ansible-aix` | read, edit (YAML/Jinja/ini/docs), execute, MCP, skills, todo, subagents, mode switch |
| 🗄️ Oracle on AIX/Power | `oracle-aix` | read, edit (SQL/shell/rsp/ora/YAML/docs), execute, MCP, skills, todo, subagents, mode switch |
| 🔍 AIX/Oracle Review | `aix-review` | read-only: read, MCP, skills, todo |

---

## Usage

### Learn with the recipes

New to Bob on AIX and Oracle? Start with the [recipes](recipes/README.md): five guided
sessions (assessment, install preparation, backup, patching, performance) with prompts
you copy and paste into Bob. Each step of a recipe is also an automated test case: a
saved Bob answer can be graded with `python evals/scenario_evals.py --grade-recipe 03:2 answer.txt`.

### IBM Bob

1. Open the repository as a workspace. The modes appear in the mode picker, and as slash
   commands such as `/oracle-aix`.
2. Check *Settings → Skills* to see that the `aix`, `ansible-aix`, and `oracle-aix` skills
   are listed. Turn on skill auto-approval if you don't want an activation prompt each time.
3. Optional: run `/oracle-aix-setup` to install the Oracle community `db` skill content.

### Other agents (Claude Code, Cursor, Copilot agent mode, …)

Copy or clone `.agents/skills/` into your workspace, or point your agent's skill directory
at it. Each skill's `SKILL.md` is self-contained, and it references its companion files
with relative paths.

```bash
git clone https://github.com/ibm-power-demos-with-bob/bob-for-aix-oracle.git
# or add as a git submodule
git submodule add https://github.com/ibm-power-demos-with-bob/bob-for-aix-oracle.git .agents-aix
```

To install the Oracle `db` skill content without Bob, run the bash or PowerShell block in
[`.bob/commands/oracle-aix-setup.md`](.bob/commands/oracle-aix-setup.md) from inside the
repository.

---

## Contributing

1. Edit the canonical skill under `.agents/skills/<skill-name>/`.
   - Companion files (`best-practices/*.md`, …) have **no** frontmatter. Start them with a
     "Read this file for:" note, and add them to the routing table in `SKILL.md`.
   - Never invent commands, flags, tunables, or module parameters. Mark anything unverified,
     and give the command to check it (`<cmd> -L`, `-h`, `ansible-doc`).
2. If you changed a skill's frontmatter, regenerate the Bob pointers:
   `python scripts/sync_bob_skills.py`.
3. Add any new Bob mode to `.bob/custom_modes.yaml`, with a `.bob/rules-<slug>/` directory.
4. Run the checks locally before opening a pull request:

```bash
pip install pyyaml && python scripts/validate.py && python evals/run_evals.py
```

```bash
pip install ansible-lint && ansible-galaxy collection install ibm.power_aix && ansible-lint --profile production .agents/skills/ansible-aix/examples/
```

Do not commit Oracle Support (MOS) scripts or other content you are not allowed to
redistribute. Link to the MOS note instead.

---

## License

See [LICENSE](LICENSE).
