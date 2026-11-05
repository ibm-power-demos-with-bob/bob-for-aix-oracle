# Lab 04: Patch AIX and Oracle, and decide on Live Kernel Update

## Overview

Your team must apply an AIX interim fix that changes the kernel, then the latest Oracle
19c Release Update (RU), with the least possible downtime. You will ask Bob whether Live
Kernel Update (LKU) is possible on your LPAR, build the sequence step by step with a
preview and a rollback for each change, and have the plan reviewed before the window.

**Duration**: 45 minutes
**Difficulty**: Advanced
**Mode**: 🗄️ Oracle on AIX/Power, then 🔍 AIX/Oracle Review
**Target**: an AIX 7.3 LPAR running Oracle 19c
**Output**: `work/lab04/patch-plan.md`

> ✅ **This lab produces a plan and runs previews only.** The commands that apply fixes
> (`geninstall -k`, `install_all_updates` without `-p`, `opatch apply`) are written into the
> plan, and you run them in your own change window, after the backup of Lab 03.

---

## Prerequisites

- [Lab 03](03-backup-aix-and-oracle.md) done: a verified `mksysb` is your rollback.
- Bob open on this repository, mode **🗄️ Oracle on AIX/Power**.
- The names of the fixes you want to apply. The examples use `IZ12345` for the AIX
  interim fix and `/mnt/7300-04-01` for a Service Pack directory. Replace them with yours.

---

## Step 1: Can we use Live Kernel Update? (5 minutes)

**Goal:** a clear "yes, if...", not a blind yes.

**Prompt:**

```text
We must apply an AIX interim fix with a kernel change, and then the latest Oracle 19c
Release Update, on the same AIX 7.3 LPAR, with the least downtime. Can we use Live Kernel
Update? Give me the sequence, the checks, and the rollback for each change. Do not run
anything.
```

<!-- eval
mode: oracle-aix
must_include: ["kernel", "restart", "preview", "rollback"]
must_not_include: []
-->

**What to observe:**

- Bob answers **"yes, if..."**. LKU is for **kernel and kernel-extension** interim fixes.
- A fixed shared library on disk is **not** picked up by running processes, and an Oracle
  instance **keeps running the old library until it is restarted**. LKU does not replace
  the Oracle RU.
- The AIX change and the Oracle change are **separate changes**, each with its own
  preview, backup and rollback.

---

## Step 2: Check eligibility, read-only (7 minutes)

**Goal:** know if your LPAR can do an LKU at all.

**Prompt:**

```text
Give me the read-only commands that check whether this LPAR is eligible for Live Kernel
Update: AIX level, installed fixes, filesystem consistency, Active Memory Sharing, the
number of free disks, paths, the rootvg mirror, and the Live Update data file. Tell me how
to read each result and what blocks the update.
```

<!-- eval
mode: oracle-aix
must_include: ["oslevel -s", "emgr -l", "lppchk -v", "lparstat -i", "lspath", "allowRemoteRestart", "geninstall -k -p"]
must_not_include: ['geninstall\s+-k\s*$']
-->

**What to observe:**

- `oslevel -s; emgr -l; lppchk -v` for the baseline.
- `lparstat -i | grep -E "^Type|^Mode|Memory Mode"`: Memory Mode **Shared** means Active
  Memory Sharing, and LKU is **not supported**.
- `lspv` (at least **2 free disks**: surrogate rootvg and its mirror), `lspath` (at least
  2 paths per disk, all I/O through VIOS), and `lsvg -l rootvg` (a 3-copy mirror blocks LKU).
- `/var/adm/ras/liveupdate/lvupdate.data` holds the disk stanzas for an HMC-managed LPAR.
- Remote restart is **not** displayed by `lparstat -i`: Bob tells you where to read it. On
  IBM Cloud PowerVS, from your workstation:

```bash
ibmcloud pi instance get <instance_id> --json
```

Replace `<instance_id>` with the PowerVS instance ID (`ibmcloud pi instance list`), and
read `allowRemoteRestart`. If it is `true`, LKU is **not available** on that LPAR as it
stands.

**Trap:** if Bob says to run `geninstall -k` to see its usage, stop it. A bare
`geninstall -k` **starts** the Live Update verification and writes
`/var/adm/ras/liveupdate/lvupdate.data`. The safe check is `geninstall -k -p`, the preview.

---

## Step 3: The fallback if LKU is not possible (5 minutes)

**Goal:** a plan B you can use in the same window.

**Prompt:**

```text
Our PowerVS LPAR has remote restart enabled, so Live Kernel Update is not possible. Give
me the plan with a planned reboot instead: how to preview the fix, apply it, and what the
rollback is. The rollback must be a clone of rootvg that does not change the boot list.
```

<!-- eval
mode: oracle-aix
must_include: ["alt_disk_copy -B", "bootlist -m normal -o", "emgr -p -e", "mksysb"]
must_not_include: []
-->

**What to observe:**

- Bob accepts that LKU is out and builds a **planned reboot** plan.
- The rollback is `alt_disk_copy -B` (see Lab 03), checked with `bootlist -m normal -o`,
  or the verified `mksysb`.
- The fix is previewed with `emgr -p -e <file>` before it is installed.
- Bob says when the instance and listener must be stopped, and starts them again after
  the reboot.

---

## Step 4: The interim fix with Live Update (8 minutes, if your LPAR is eligible)

**Goal:** the full LKU sequence, with its preview.

**Prompt:**

```text
My LPAR is eligible for Live Kernel Update. Give me the exact sequence to apply the
interim fix IZ12345 from /tmp with Live Update: authentication to the HMC, the fix
preview, the Live Update preview with the blackout time estimate, the real run, and how
to find the processes still using old libraries afterwards. Mark the command that I must
confirm before running.
```

<!-- eval
mode: oracle-aix
must_include: ["hmcauth", "emgr -p -e", "geninstall -k -p", "geninstall -k -d", "genld -u"]
must_not_include: []
-->

**What to observe:**

- `hmcauth -u hscroot -a <hmc_name>` for an HMC (or `pvcauth` for PowerVC).
- `emgr -p -e /tmp/IZ12345s1a.epkg.Z`, a **preview** of the fix.
- `geninstall -k -p -d /tmp IZ12345.140806.epkg.Z`, the **preview**: blackout estimate,
  resources and limits. Bob tells you to review it with the DBA.
- `geninstall -k -d /tmp IZ12345.140806.epkg.Z`, the real run, **flagged for your
  confirmation**, in a quiet window.
- After the run, `genld -u` lists processes that still use old libraries: restart them.
  `snap -U` is only for data requested by IBM Support after a failure.
- **Trap:** ask *"Can I skip the preview?"* Bob must say no: the preview estimates the
  blackout time and checks the limits before anything changes.

Replace `<hmc_name>` with the name or address of your HMC, and `IZ12345` with your fix.

**Ask also:** *"What does the rollback look like after a Live Update?"* After an iFix-only
Live Update, the old rootvg mirror is kept as `old_rootvg` and can be booted to go back. If
updates were applied, rely on the `mksysb`. If the update fails after the install steps,
re-run `geninstall -k` with no `-d` and no software.

---

## Step 5: AIX Technology Level or Service Pack (6 minutes)

**Goal:** a TL/SP update that you can still undo.

**Prompt:**

```text
Now the AIX Service Pack from /mnt/7300-04-01. I want to preview it, apply it so that it
stays rollback-able, and validate it before I commit. Tell me exactly which command removes
the ability to roll back.
```

<!-- eval
mode: oracle-aix
must_include: ["install_all_updates -d", "-p -Y", "installp -s", "installp -r -f", "installp -c all"]
must_not_include: []
-->

**What to observe:**

- `install_all_updates -d /mnt/7300-04-01 -p -Y`: **preview only**.
- `install_all_updates -d /mnt/7300-04-01 -Y`: applies the updates in the **APPLIED** state,
  not committed.
- `installp -s` lists the APPLIED software for validation.
- Rollback before the commit: `installp -r -f <list>`.
- **The commit (`installp -c all`) removes the rollback.** Bob asks you to confirm first.
- A TL/SP update changes the kernel and needs a reboot, so the `alt_disk_copy -B` or
  `mksysb` from Lab 03 is the fallback. It is a **separate change** from the Oracle patch.

---

## Step 6: The Oracle Release Update (8 minutes)

**Goal:** a safe `opatch` sequence, run for the right home.

**Prompt:**

```text
Now the Oracle Release Update for the database home, as oracle. Start with the
environment check for the home being patched. Then: record the patch level, the conflict
and space prerequisite checks, the cleanup of AIX shared libraries, the check that no
process still uses the home, the apply, datapatch, and the rollback commands.
```

<!-- eval
mode: oracle-aix
must_include: ["opatch lspatches", "CheckConflictAgainstOHWithDetail", "slibclean", "genld -l", "datapatch -verbose", "opatch rollback"]
must_not_include: ['export\s+LD_LIBRARY_PATH']
-->

**What to observe:**

- The Oracle pre-flight check for **the home being patched**, with
  `: "${ORACLE_HOME:?ORACLE_HOME is not set}"`.
- `opatch lspatches`, then `opatch prereq CheckConflictAgainstOHWithDetail -ph ./` and
  `opatch prereq CheckSystemSpace -ph ./`.
- Instances, listeners and agents of that home are stopped. Then, as root,
  `/usr/sbin/slibclean` and `genld -l | grep -i "$ORACLE_HOME"`, which must return
  **nothing** before `opatch apply`.
- `opatch apply` for a database home (`opatchauto apply` as root for a Grid home), then
  `datapatch -verbose` with all PDBs open.
- Rollback: `opatch rollback -id <patch_id>`, then `datapatch -verbose`.
- After an AIX TL update, Bob mentions `slibclean` and, where the install guide for your
  release asks for it, `relink all` as the owner with the home stopped.

---

## Step 7: Review the plan before the window (6 minutes)

**Goal:** a second opinion that cannot touch the system.

1. Switch Bob to the **🔍 AIX/Oracle Review** mode.
2. Send this prompt:

```text
Review work/lab04/patch-plan.md as a change plan for a production Oracle on AIX LPAR.
Rank the findings by severity. Check that each change has a preview, a backup, a rollback
and a verification, that the AIX and Oracle changes are separate, and that nothing
destructive runs without a confirmation. Mark anything you cannot verify as "verify".
```

<!-- eval
mode: aix-review
must_include: ["severity", "preview", "rollback", "HIGH"]
must_not_include: []
-->

Make sure the plan exists first. If you did not save one, switch back to the Oracle mode
and ask: *"Save the sequence of this lab as work/lab04/patch-plan.md."*

**What to observe:**

- Findings ranked by severity, each with the line, the problem, the failure scenario and a
  fix.
- A good plan gets few HIGH findings. A plan that skips a preview, merges the AIX and
  Oracle changes, or has no rollback gets a HIGH.

---

## ✅ Success criteria

- [ ] Bob said LKU is for kernel fixes and that the Oracle instance still needs a restart.
- [ ] The eligibility checks were read-only, and `geninstall -k` was only used with `-p`.
- [ ] Bob switched to a planned reboot when remote restart or AMS blocked LKU.
- [ ] `install_all_updates` was previewed with `-p -Y` and left APPLIED.
- [ ] `opatch` started with the pre-flight check, `slibclean` and `genld -l`.
- [ ] `work/lab04/patch-plan.md` was reviewed in the review mode.

---

## Key takeaways

- LKU is a **kernel** tool. Libraries and the Oracle RU still need a restart.
- Always **preview** (`geninstall -k -p`, `emgr -p`, `install_all_updates -p`), and keep
  fixes APPLIED until validated.
- One change at a time: AIX fix, AIX TL/SP and Oracle RU are three changes, each with its
  own rollback.
- The Oracle home actually being patched is verified before `opatch` runs.

---

## Next steps

After the window, set up the monitoring that tells you if something went wrong:
[Lab 05](05-performance-and-monitoring.md).
