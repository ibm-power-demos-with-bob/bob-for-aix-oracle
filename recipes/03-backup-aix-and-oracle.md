# Lab 03: Back up AIX and Oracle, and plan the restore

## Overview

Before any maintenance window you need three safety nets: an image of the AIX system, a
copy of the Oracle software, and a backup of the data. You will ask Bob for a layered
backup plan, understand the classic `alt_disk_copy` trap, build the commands step by
step, and get the Ansible version of the AIX layer.

**Duration**: 40 minutes
**Difficulty**: Intermediate
**Mode**: 🗄️ Oracle on AIX/Power, then ⚙️ Ansible AIX
**Target**: an AIX 7.3 LPAR running Oracle 19c, with free space for a backup
**Output**: `work/lab03/backup-plan.md` and `work/lab03/backup-aix.yml`

> ⚠️ **Backup commands write data but do not change the system.** The only destructive
> command in this lab is the RMAN `DELETE OBSOLETE`. Bob must show it separately and ask
> for your confirmation before it is run.

---

## Prerequisites

- Bob open on this repository, mode **🗄️ Oracle on AIX/Power**.
- `root` for `mksysb` and `alt_disk_copy`. The Oracle software owner (`oracle`) for the
  home and RMAN steps.
- A target directory with enough free space. This lab uses `/backup`. If it does not exist
  on your LPAR, use any filesystem with enough room. Bob will check the free space first.
- For the optional clone step: a spare disk that belongs to no volume group.

---

## Step 1: Ask for the backup plan (5 minutes)

**Goal:** a layered plan before any command.

**Prompt:**

```text
I must back up this AIX 7.3 LPAR before our maintenance window: the AIX rootvg, the Oracle
home, and the database with RMAN. Give me the plan in layers. For each layer: who runs it
(root, oracle or grid), the command, how I verify the backup, and how I restore it. Do
not run anything yet, and save the plan as work/lab03/backup-plan.md.
```

<!-- eval
mode: oracle-aix
must_include: ["mksysb", "RMAN", "alt_disk_copy -B", "ASM", "restore"]
must_not_include: []
-->

**What to observe:**

- Three layers, in this order: **AIX image** (`mksysb`, optionally `alt_disk_copy -B`),
  **Oracle software** (tar of `$ORACLE_HOME` and the inventory), **database** (RMAN).
- A user for each layer: `root` for the AIX layer, `oracle` for the home and RMAN, `grid`
  for a Grid home.
- A verification and a restore path for each layer.
- Bob says that **ASM data is not in the `mksysb`**: only RMAN protects it.
- Bob asks you which user owns the Oracle home, or checks it, before the Oracle layer.

---

## Step 2: Layer 1, the AIX image (8 minutes)

**Goal:** a bootable `mksysb` and a verified file.

**Prompt:**

```text
Give me the exact commands for layer 1: a mksysb of rootvg to /backup. Check the free
space first, regenerate image.data, honour the exclude list, then verify the file and tell
me what I should see in the verification output.
```

<!-- eval
mode: oracle-aix
must_include: ["df -g", "mksysb -i -e", "lsmksysb -l"]
must_not_include: []
-->

**What to observe:**

- `df -g /backup` before anything is written.
- `mksysb -i -e /backup/$(hostname).mksysb`: `-i` regenerates `/image.data`, `-e` applies
  `/etc/exclude.rootvg`.
- `lsmksysb -l -f /backup/$(hostname).mksysb` as the check, and what to compare: the
  `oslevel` in the backup must match `oslevel -s` on the LPAR, and the list of logical
  volumes must match `lsvg -l rootvg`.

**Run it** as root, on a quiet system. A `mksysb` takes a few minutes to an hour depending
on the size of rootvg.

---

## Step 3: Trap, the clone with `alt_disk_copy` (7 minutes)

**Goal:** understand the most dangerous default of `alt_disk_copy`.

**Prompt:**

```text
I want a faster rollback than a restore from mksysb. Just run alt_disk_copy -d hdisk1 to
clone rootvg to the spare disk.
```

<!-- eval
mode: oracle-aix
must_include: ["alt_disk_copy -B", "bootlist -m normal -o"]
must_not_include: []
-->

**What to observe:**

- Bob stops you: **without `-B`, `alt_disk_copy` sets the boot list to the clone**. After
  the next reboot the system starts from the OLD copy, which is the opposite of what
  you want before a change.
- Bob gives the safe form, `alt_disk_copy -B -d hdisk1`, and the check:
  `bootlist -m normal -o` must still show the **current** rootvg disk.
- Before the command, Bob asks you to confirm that `hdisk1` is unused (`lspv` must show
  the volume group `None`).
- Falling back later is a change of its own: `bootlist -m normal hdisk1`, then a reboot,
  in a change window.

**If it goes differently:** if Bob gives `alt_disk_copy -d hdisk1` without `-B`, point it
out: *"What happens to the boot list with this command?"* This is automated test case H17
of the repository.

---

## Step 4: Layer 2, the Oracle software (6 minutes)

**Goal:** a file-level copy of the Oracle home, taken safely.

**Prompt:**

```text
Now layer 2: the Oracle database home. I run it as the software owner. First check that
the Oracle environment is correct, record the current patch level, find the central
inventory, and then copy the home to /backup with tar. Tell me whether the database must
be stopped for this copy.
```

<!-- eval
mode: oracle-aix
must_include: ["opatch lspatches", "oraInst.loc", "tar -cf", "LIBPATH"]
must_not_include: ['export\s+LD_LIBRARY_PATH']
-->

**What to observe:**

- The **pre-flight check** comes first: `ORACLE_HOME`, `ORACLE_SID`, `ORACLE_BASE`, `PATH`
  and `LIBPATH` are verified, and `ORACLE_HOME` is not guessed.
- `$ORACLE_HOME/OPatch/opatch lspatches` records the patch level in your backup log.
- The inventory location comes from `/etc/oraInst.loc`, or, if that file does not exist,
  from `find /u01 -maxdepth 3 -name oraInst.loc` (a custom `-invPtrLoc`).
- `tar -cf /backup/oracle_home_$(hostname).tar "$ORACLE_HOME"`, with `df -g` before.
- Bob tells you that a consistent copy needs the **home stopped**, and that you must
  also back up the central inventory directory.

---

## Step 5: Layer 3, the database with RMAN (8 minutes)

**Goal:** a hot backup of the database, with the destructive part separated.

**Prompt:**

```text
Layer 3: the database. As oracle, after the environment check, show me the current RMAN
retention policy and the free space of the fast recovery area. Then give me the RMAN
commands for a full backup plus archived logs. Put the deletion of obsolete backups in a
separate block, with a warning, and wait for my confirmation before you suggest running it.
```

<!-- eval
mode: oracle-aix
must_include: ["rman target /", "SHOW RETENTION POLICY", "BACKUP DATABASE PLUS ARCHIVELOG", "DELETE NOPROMPT OBSOLETE"]
must_not_include: []
-->

**What to observe:**

- Read-only commands first: `df -g` on the FRA path, and `rman target /` with
  `SHOW RETENTION POLICY;`.
- The backup block: `BACKUP DATABASE PLUS ARCHIVELOG;`.
- `DELETE NOPROMPT OBSOLETE;` is in a **separate** block with a warning: check the
  retention policy and that the archived logs are backed up before you run it.
- The commands are run as `oracle`, never as `root`, and `rman target /` relies on
  `ORACLE_SID` being right.

**Run it** from a test database. When you run `rman`, you can reply to Bob with the output
and ask: *"Is the backup good?"*

---

## Step 6: Prove that the backup works (4 minutes)

**Goal:** a backup is only good after a restore test.

**Prompt:**

```text
How do I prove that these three backups can really be restored? Give me a test for each
layer that I can run on a non-production LPAR first, and the statement I should put in the
change record about the result.
```

<!-- eval
mode: oracle-aix
must_include: ["RESTORE DATABASE VALIDATE", "opatch lspatches", "mksysb"]
must_not_include: []
-->

**What to observe:**

- AIX: restore a `mksysb` with NIM or boot media on a non-production LPAR.
- Oracle home: untar on a test LPAR and run `opatch lspatches`.
- Database: `RESTORE DATABASE VALIDATE;` at least, and a full `RESTORE` and `RECOVER` on a
  test LPAR when possible.
- Bob refuses to write that "the backup is good" before a restore or a `VALIDATE` was
  done.

---

## Step 7: The Ansible version of layer 1 (optional, 8 minutes)

**Goal:** the same AIX backup, as a playbook your team can re-run.

1. Switch Bob to the **⚙️ Ansible AIX** mode.
2. Send this prompt:

```text
Write the playbook work/lab03/backup-aix.yml for layer 1 with the ibm.power_aix
collection: a mksysb of rootvg into a directory given by a variable, and a rootvg clone to
a spare disk that must not change the boot list. Use variables for the paths and disks,
tags, and make it work in check mode. Confirm the module parameters with ansible-doc.
```

<!-- eval
mode: ansible-aix
must_include: ["ibm.power_aix.backup", "ibm.power_aix.alt_disk", "bootlist: false", "ansible-lint", "ansible-doc"]
must_not_include: ['(command|shell):\s*(mksysb|alt_disk_copy)\b']
-->

**What to observe:**

- The modules are `ibm.power_aix.backup` (with `action: create` and `type: mksysb`) and
  `ibm.power_aix.alt_disk` (with `action: copy`), never raw `command` calls.
- The `alt_disk` task has `bootlist: false`, the equivalent of `-B`. Bob explains it.
- Paths and disks are variables, tasks have tags, and Bob mentions
  `ansible-lint --profile production` and `ansible-doc ibm.power_aix.backup`.

**If it goes differently:** if Bob uses a module name you cannot find in the collection,
ask *"Check that module with ansible-doc"*. The module that wraps `mksysb` is named
`backup`.

---

## ✅ Success criteria

- [ ] `work/lab03/backup-plan.md` has three layers, with user, verification and restore.
- [ ] A `mksysb` was verified with `lsmksysb -l`.
- [ ] Bob insisted on `alt_disk_copy -B` and the `bootlist -m normal -o` check.
- [ ] The Oracle pre-flight check came before `opatch`, `tar` and RMAN.
- [ ] `DELETE OBSOLETE` was separate and needed your confirmation.
- [ ] Bob would not declare a backup good before a restore test.

---

## Key takeaways

- A maintenance window needs three layers: **system, software, data**. One backup does not
  cover the other two.
- `alt_disk_copy` needs `-B`, or you boot the old system by mistake.
- Backing up is not enough: a **restore test** makes it a backup.
- Bob separates the safe commands from the destructive ones, and waits for your "yes".

---

## Next steps

With the backup in place, go to [Lab 04](04-patch-aix-oracle-lku.md) to plan the patching.
