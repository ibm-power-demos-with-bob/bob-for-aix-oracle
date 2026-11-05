# Agent Evaluations for AIX and Oracle Skills

This directory contains automated evaluation suites to verify the accuracy, portability, and practical utility of the `aix`, `ansible-aix`, and `oracle-aix` skills on IBM Power Systems (including live IBM Cloud PowerVS LPARs such as `aix-oracle01`).

## Test Suite Structure

- `run_evals.py`: entry point. Runs the skill evals below plus everything in `recipe_evals.py`:
  1. **AIX System Administration & Diagnostics**: Correct command generation (`lparstat`, `vmstat`, `svmon`, `errpt`, `vmo`, `ioo`, `no`, `schedo`, `lsvg`, `lsmpio`).
  2. **Ansible AIX Playbook Standards**: `ibm.power_aix` modules, YAML syntax, `ansible-lint` compliance, and lack of Linux-isms (`systemctl`, `date -d`, `useradd`, etc.).
  3. **Oracle on AIX / Power Systems Layout**:
     - Pre-flight environment check enforcement (`ORACLE_HOME`, `ORACLE_SID`, `PATH`, `LIBPATH`, etc.).
     - OS user verification defaults (`oracle` for DB, `grid` for ASM/RAC, prompt if missing).
     - Standardized shell execution (bash compatibility with AIX native ksh93 support).
     - Storage layout best practices: minimum 8 data LUNs, 8 redo LUNs, 2-4 backup LUNs, bflash/Tier 1 Flash tiering, `queue_depth` (64-256), `AU_SIZE=4M/8M`.
     - CPU & memory sizing: Power10 SMT-8 entitlement, large pages (`ORACLE_SGA_PGSZ=16m`, `vmo_lgpg_regions`), memory affinity (`AIXTHREAD_SCOPE=S`).
  4. **PowerVS Live Compatibility**: Scenario checks tailored for IBM Cloud PowerVS instance `aix-oracle01` (Power10, AIX 7.3 TL04, General-Flash-96 storage pool).
- `recipes/`: the technical **eval recipes** R00 to R05 (front matter with the prompt and the
  required / forbidden patterns, then the reference answer). See [`recipes/README.md`](recipes/README.md).
  They were moved here from the top-level `recipes/` directory, which now holds the
  human-oriented labs (see [`../recipes/`](../recipes/README.md)).
- `recipe_evals.py`: evals for the eval recipes in `recipes/` and for the labs in [`../recipes/`](../recipes/README.md):
  1. **Recipe structure**: required front matter, unique `R##` ids, known Bob mode, existing skills and `reads` files.
  2. **Reference answers**: each recipe's reference answer satisfies its own `must_include` / `must_not_include` rules.
  3. **AIX accuracy**: shell blocks in eval recipes, labs and skills contain no Linux-only command and none of the known wrong forms.
  4. **Hallucination cases**: every case in `hallucination_cases.yaml` has a regex that matches its example, a documented fix, and is rejected by the grader.
  5. **Labs**: five numbered labs linked from the index, each with the same sections, a copy-and-paste `text` prompt and a goal in every step, a trap or a confirmation, English text.
- `hallucination_cases.yaml`: known wrong AIX command lines (`free -m`, `iostat -x`, `mpstat -P`, `alt_disk_copy` without `-B`, ...) with the AIX-native fix and its source. Add a case only when the correct form is documented.

## Running Evaluations

To run the complete evaluation suite:

```bash
python evals/run_evals.py
```

These evals are static: they need no LLM and no AIX host. To test a real Bob answer,
run a recipe prompt in the matching mode, save the answer to a file, and grade it:

```bash
python evals/recipe_evals.py --prompts               # list recipe ids, modes and prompts
python evals/recipe_evals.py --grade R04 answer.txt  # exit code 1 if the answer fails
```

The grader checks the recipe's `must_include` strings (case-insensitive), its
`must_not_include` patterns and every hallucination case. Only code lines are scanned for
wrong forms, so an answer may mention `systemctl` in prose to explain that AIX has none.

## Live validation on PowerVS (2026-11-05)

Inventory of `aix-oracle01` (AIX 7.3 TL4 SP2, POWER10, S1022) with `ibmcloud pi instance get`
(workspace `lg`, eu-de-1), then the read-only commands of the recipes over SSH.

| Item | Observed | Matches the skills |
|---|---|---|
| Machine / mode | POWER10, `Shared-SMT-8`, Uncapped, entitlement 1.0, 1 virtual CPU (max 8), 16 GB, Memory Mode Dedicated | yes |
| OS | AIX 7.3, 7300-04-02-2633 | yes |
| Storage pool | `General-Flash-96`, 4 volumes, all `tier3`; 3 VGs (`rootvg`, `orafsvg`, `oradatavg`) | pool yes; a small demo layout, not the 8 + 8 + 2 to 4 LUN target of R01 |
| Remote restart | `allowRemoteRestart: true` (PowerVS) | R04: Live Update is not supported on this LPAR |
| Disks | `no_reserve`, `queue_depth 32`, 2 to 4 MPIO paths per disk, `iocp0` Available | `queue_depth` is below the 64 to 256 advised in `io-storage.md` |
| Oracle | `ora_pmon_orcl` and a listener run as `oracle` from `/u01/19c/database/home`; user `grid` does not exist | consistent with a single-instance, non-RAC install |

Commands confirmed on the host: `svmon -G`, `vmstat -v`, `lsps -a`, `lssrc -s sshd`, `lsmpio`,
`lsmpio -q`, `lspath -F "name parent"`, `genld -u`, `smtctl`, `vmo -L lgpg_regions`,
`vmo -L v_pinshm`, `schedo -L vpm_throughput_mode`, `ioo -a`, `iostat -D`, `mpstat -s`,
`mpstat -v`, `lparstat`, `lparstat -i`, `vmstat`, `fcstat fcs0`, `lsattr -El hdisk2 -a queue_depth`,
`emgr -l`, `installp -s`, `lppchk -v`, `lsmksysb`, `odmget errnotify` (the stanza fields of
R05 exist), `nmon -m <dir>`. The `perl -MPOSIX` timestamp for `errpt -s` is accepted by `errpt`.
Confirmed as wrong on AIX: `date -d`, `free`, `iostat -x`, `mpstat -P`.

Findings fixed in the repository:

- `lsuser -a <attrs> oracle grid` fails ("Usage: lsuser"): AIX `lsuser` takes ONE comma-separated
  list (`oracle,grid`). Corrected in the skills and recipes.
- A bare `geninstall -k` is not a usage query: it starts the Live Update verification (and
  wrote `/var/adm/ras/liveupdate/lvupdate.data` on this LPAR). The `aix` skill now says so.
- Remote restart is not reported by `lparstat -i`; R04 now says where to read it.
- `/etc/oraInst.loc` does not exist here: the inventory pointer is `/u01/oraInventory/oraInst.loc`
  (installer run with `-invPtrLoc`). The skills and recipes now fall back to
  `find /u01 -maxdepth 3 -name oraInst.loc`.
- R03 uses `/backup`, which does not exist on this LPAR (`/u01` 50 GB, `orafsvg` has about
  10 GB free): the recipe's `df -g` check must come first. This is expected for a generic recipe.

Change-making commands replayed with the owner's agreement, each one cleaned up afterwards:

- R00 user flow: `mkuser pgrp=staff groups=staff home=/home/bobtest shell=/usr/bin/ksh bobtest`,
  `lsuser -f`, `pwdadm -f ADMCHG` all work as written; the temporary account was removed with
  `rmuser -p`. `rmuser` leaves the home directory (it kept the `.profile` created by `mkuser`),
  so a recipe that removes a user must say to remove the home directory by hand.
- R00 service flow: `stopsrc -s` / `startsrc -s` / `lssrc -s` were run on a throw-away SRC
  subsystem (`mkssys` / `rmssys`), not on `sshd`. `lssrc -s` shows `active` then `inoperative`
  as the recipe expects. `sshd` stayed `active` with the same PID throughout.
- Previews: `install_all_updates -d <dir> -p -Y` reports "Device ... could not be accessed" for a
  missing directory and changes nothing; `emgr -p -e <file>` starts an "EFIX MANAGER PREVIEW".

Not run on the host, because they change the system or need resources it lacks: `mksysb`
(no `/backup`), `alt_disk_copy` (no free disk), `geninstall -k -d`, `opatch`, tunable changes,
and a restart of the real `sshd`.

Ansible snippets of R03 and R04 were checked outside the LPAR: `ansible-lint --profile production`
passes on both, and every parameter used exists in `ansible-doc` for `ibm.power_aix.backup`,
`ibm.power_aix.alt_disk` and the `live_kernel_update` role (collection installed with
`ansible-galaxy` in a virtualenv on WSL).

