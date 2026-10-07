# bob-for-aix-oracle

AI agent skills and modes for IBM AIX system administration, Ansible automation
on AIX, and Oracle Database administration on AIX / Power Systems.

---

## Repository Layout

```
.agents/
  skills/
    aix/
      SKILL.md          # AIX system administration & skill
    ansible-aix/
      SKILL.md          # Ansible ibm.power_aix skill
    oracle-dba-aix/
      SKILL.md          # Oracle DBA on AIX skill
.bob/
  custom_modes.yaml     # Bob custom modes (Bob / IBM only)
  mcp.json
```

### `.agents/skills/` — cross-agent skills

Skills placed under `.agents/skills/<name>/SKILL.md` are read natively by most
modern AI agents: **Bob (IBM)**, **OpenCoder**, **Claude Code**, **Cursor**,
**Windsurf**, **GitHub Copilot (agent mode)**, and others following the open
`.agents/` convention.

Each skill contains:
- A YAML frontmatter `description` that drives automatic activation.
- Step-by-step procedural guidance the agent follows when the skill triggers.

### `.bob/custom_modes.yaml` — Bob modes

Custom modes are Bob-specific. They define a named persona (role definition +
tool permissions) selectable from the Bob mode picker. Each mode references its
companion skill so the full reference material is loaded at activation time.

---

## Skills

### `aix`

**Activates when:** working on IBM AIX systems — administration, performance
tuning, troubleshooting, or automation.

Covers AIX-native commands (`lsdev`, `errpt`, `lsvg`, `topas`, `nmon`,
`smitty`), JFS2/LVM management, AIX networking, performance tools, and
automation-friendly output patterns. Enforces AIX-vs-Linux command distinctions.

### `ansible-aix`

**Activates when:** writing, reviewing, or refactoring Ansible playbooks and
roles targeting AIX with the `ibm.power_aix` collection.

Covers all `ibm.power_aix` modules (packages, users, LVM, filesystems, NFS,
network, security, services, NIM, VIOS), collection roles, playbook skeleton,
and production-lint rules (FQCN, idempotency, vault secrets, register+assert,
ansible-lint profile=production).

### `oracle-dba-aix`

**Activates when:** administering, tuning, troubleshooting, or automating Oracle
Database on IBM AIX / Power Systems.

Covers Oracle environment setup on AIX (`LIBPATH`, not `LD_LIBRARY_PATH`), AIX
shared memory / semaphore tuning (`ioo`, `vmo`), storage layout (JFS2 / raw
LVM), RMAN on AIX (Spectrum Protect / disk), RAC on AIX (GPFS / ASM), `errpt`
correlation, patching (`opatch` + `installp`), and safety/change management.

Delegates Oracle-specific topics (SQL, PL/SQL, RMAN, Data Guard, performance,
security) to the [Oracle `db` skill](https://github.com/oracle/skills/tree/main/db).

---

## Usage

### Bob (IBM)

Skills auto-activate based on conversation context. Custom modes appear in the
Bob mode picker immediately after cloning this repository and opening it as a
workspace.

### Other agents (OpenCoder, Claude Code, Cursor, …)

Clone this repository (or copy the `.agents/` folder) into your workspace.
Skills under `.agents/skills/` are discovered and activated automatically.

```bash
git clone https://github.com/<your-org>/bob-for-aix-oracle.git
# or add as a git submodule
git submodule add https://github.com/<your-org>/bob-for-aix-oracle.git .agents-aix
```

---

## Contributing

1. Fork this repository.
2. Add or update a skill under `.agents/skills/<skill-name>/SKILL.md`.
3. If adding a new Bob mode, append it to `.bob/custom_modes.yaml`.
4. Open a pull request.

---

## License

See [LICENSE](LICENSE).
