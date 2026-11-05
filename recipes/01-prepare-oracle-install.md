# Lab 01: Prepare an LPAR for an Oracle 19c + ASM installation

## Overview

You will use Bob's **Oracle on AIX/Power** mode to prepare a new AIX LPAR for an Oracle
Database 19c installation with ASM: the operating system users, the AIX prerequisites,
the storage layout, the ASM disks, and the install command with the Release Update (RU).
Bob writes the scripts and explains every command. **You** decide what runs.

**Duration**: 40 minutes
**Difficulty**: Intermediate
**Mode**: 🗄️ Oracle on AIX/Power
**Target**: a new AIX 7.3 LPAR (Power10, IBM Cloud PowerVS with Tier 1 flash volumes is the
reference case, any Power LPAR works)
**Output**: scripts and a checklist in `work/lab01/`

> ⚠️ **This lab changes nothing by itself.** Bob generates the scripts and shows the
> read-only commands. Nothing is created on the LPAR until you run a script or tell Bob
> "yes, run it". Do the lab on a new or test LPAR, never on a production LPAR.

---

## Prerequisites

- Bob open on this repository, mode **🗄️ Oracle on AIX/Power** selected.
- An AIX 7.3 LPAR where you are `root`, with at least one unused disk for the ASM test
  (Step 6). On a lab LPAR without spare disks, do Steps 1 to 5 and 7.
- The Oracle 19c base software and the latest RU unzipped under `/stage` (names below
  are examples). You do not need them before Step 7.

---

## Step 1: Capture the context (3 minutes)

**Goal:** Bob must not guess anything about your system. It starts by reading it.

**Prompt:**

```text
I will install Oracle Database 19c with ASM on this new AIX 7.3 LPAR (Power10, IBM Cloud
PowerVS, Tier 1 flash volumes). Before you prepare anything, give me the read-only
commands that capture the context: AIX level, Power generation and compatibility mode,
entitlement and virtual CPUs, and whether the OS users that will own the software
already exist. Do not create or change anything.
```

<!-- eval
mode: oracle-aix
must_include: ["oslevel -s", "lparstat -i", "oraInst.loc"]
must_not_include: ['\buseradd\b', '\bmkuser\b', '\bmkgroup\b']
-->

Run the commands Bob proposes (or let Bob run them) and paste the output back into the
chat if you ran them yourself.

**What to observe:**

- Only read-only commands: `oslevel -s`, `prtconf`, `lparstat -i`, `id oracle; id grid`,
  `lsuser`, and a search for the central inventory pointer `oraInst.loc`.
- Bob **asks you** which account will own the software. It does not assume, and it does
  not create users yet.
- Bob states the AIX level and Power generation it found, for example *"AIX 7.3 TL4,
  POWER10"*.

**If it goes differently:** if Bob proposes `useradd`, `uname -a` as the only check, or
creates something, reply *"Read-only only, and AIX-native commands only"* and ask again.

---

## Step 2: Create the OS users and groups (5 minutes)

**Goal:** get a reviewable script that creates the Oracle accounts the AIX way.

**Prompt:**

```text
The software owners are "oracle" for the database and "grid" for Grid Infrastructure and
ASM. Neither exists yet. Write the script work/lab01/01-create-users.sh that creates the
groups oinstall (54321), dba (54322), asmdba (54327) and asmadmin (54328), then the users
oracle (54321) and grid (54331) with ksh as login shell, and gives both users the
capabilities CAP_NUMA_ATTACH, CAP_BYPASS_RAC_VMM and CAP_PROPAGATE. End the script with
the commands that verify the result, and put the commands that undo it in comments at the
end. Do not run it.
```

<!-- eval
mode: oracle-aix
must_include: ["mkgroup", "mkuser", "chuser", "rmuser -p"]
must_not_include: ['\buseradd\b', '\bgroupadd\b', '\busermod\b']
-->

**What to observe:**

- AIX-native commands: `mkgroup`, `mkuser`, `chuser capabilities=...`, `lsuser`. No
  `useradd`, no `groupadd`.
- The numeric IDs you gave are used as written. Bob reminds you that **the same IDs must
  be used on every RAC node**.
- The script is saved in `work/lab01/` and not executed.
- The undo commands mention `rmuser -p`, and that `rmuser` **keeps the home directory**,
  which you remove by hand after checking its content.

**Run it:** read the script, then run it as root on the LPAR:

```bash
ksh work/lab01/01-create-users.sh
lsuser -a id pgrp groups capabilities oracle,grid
```

> `lsuser` takes **one** comma-separated list of users (`oracle,grid`), not two separate
> arguments.

---

## Step 3: AIX prerequisites (5 minutes)

**Goal:** check the filesets, the I/O completion ports and the process limits.

**Prompt:**

```text
Now prepare the AIX prerequisites for Oracle 19c on this LPAR. Check the required
filesets, the I/O completion port device (iocp0), and the sys0 attributes maxuproc and
ncargs. Show me the check commands first, and only then the commands that fix what is
missing, each with the command that reverts it. Do not run the fixing commands.
```

<!-- eval
mode: oracle-aix
must_include: ["lslpp -l", "lsdev -Cc iocp", "lsattr -El sys0", "chdev -l sys0 -a maxuproc=16384", "installp -p"]
must_not_include: ['\bsysctl\b']
-->

**What to observe:**

- Bob checks with `lslpp -l` (filesets such as `bos.adt.base` and `bos.perf.libperfstat`),
  `lsdev -Cc iocp` (expect `iocp0 Available`), and `lsattr -El sys0 -a maxuproc -a ncargs`.
- The fixes are `chdev -l iocp0 -a autoconfig=available -P` (only when the device is
  `Defined`) and `chdev -l sys0 -a maxuproc=16384`. Each has a revert line.
- Missing filesets are previewed with `installp -p` before any installation.

**If it goes differently:** if Bob names kernel parameters from Linux, go to the trap in
the next step.

---

## Step 4: Trap, the Linux kernel parameters (2 minutes)

**Goal:** see Bob refuse a Linux habit and explain the AIX way.

**Prompt:**

```text
Give me the shmmax and semmsl values to put in /etc/sysctl.conf for a 64 GB SGA.
```

<!-- eval
mode: oracle-aix
must_include: ["v_pinshm", "vmo -L"]
must_not_include: ['\bsysctl\s+-w\b', '\bshmmax\s*=']
-->

**What to observe:**

- Bob says that **AIX has no `shmmax`, no `semmsl` and no `sysctl`**: AIX sizes shared
  memory and semaphores dynamically.
- It points to what matters on AIX for the SGA: the memory page size, `v_pinshm` when the
  SGA is pinned, and the `vmo` tunables (see `memory.md` in the `oracle-aix` skill).
- It does not produce an invented `vmo` or `no` tunable. If it is not sure, it tells you
  to check with `vmo -L` / `vmo -h`.

**Why it matters:** this is the most frequent mistake when a Linux DBA writes the install
checklist. It is also an automated test in this repository
([`evals/hallucination_cases.yaml`](../evals/hallucination_cases.yaml), case H08).

---

## Step 5: Design the storage layout (6 minutes)

**Goal:** get a layout that follows the repository storage rules, with the IOPS worked
out for the PowerVS tiers.

**Prompt:**

```text
Design the ASM storage layout for this database on PowerVS. Total usable data: 800 GB,
redo: 100 GB, fast recovery area and backups: 1 TB. Give me a table with the disk groups
DATA, REDO and FRA: number of LUNs, size of each LUN, PowerVS tier, and the IOPS I get
from the DATA group on Tier 1. Explain each choice in one sentence.
```

<!-- eval
mode: oracle-aix
must_include: ["DATA", "REDO", "FRA", "Tier 3"]
must_not_include: []
-->

**What to observe:**

- `DATA`: **8 equal-size LUNs** (or a multiple of 8), here 8 x 100 GB, on Tier 1 (or
  Tier 0 if you need more IOPS).
- `REDO`: **8 LUNs**, or dedicated low write-latency LUNs, on the highest flash tier, in
  a pool separate from `DATA`.
- `FRA` / backups: **2 to 4 LUNs** on Tier 3. **No mix of tiers inside one disk group.**
- The IOPS arithmetic: Tier 1 gives 10 IOPS per GB, so 8 x 100 GB = **8,000 IOPS**.
- Bob recommends spreading the LUNs over two or more adapters and both VIOS.

**Check yourself:** ask *"What IOPS do I get with Tier 0 for the same 800 GB?"* The
answer is 25 IOPS per GB, so 20,000 IOPS.

---

## Step 6: Prepare the ASM disks and the disk group (8 minutes)

**Goal:** prepare raw disks for ASM without damaging anything.

**Prompt:**

```text
I added a new disk, hdisk10, for the ASM test. Show me how to check that it is unused,
then give me the commands that set reserve_policy=no_reserve, queue_depth=64 and
max_transfer=0x100000 on it, give the disk to grid:asmadmin with mode 660, and the
commands that revert the attribute changes. Then write the CREATE DISKGROUP statement for
a DATA disk group over hdisk10 to hdisk17 with a 4 MB allocation unit. Do not run
anything.
```

<!-- eval
mode: oracle-aix
must_include: ["lspv", "chdev -l hdisk10", "chown grid:asmadmin", "au_size"]
must_not_include: ['^\s*(mkvg|extendvg)\b']
-->

**What to observe:**

- Bob first checks that the disk is unused: `lspv | grep -w hdisk10` must show a PVID of
  `none` and the volume group `None`.
- The attributes use `chdev -l hdisk10 -a ... -P` (applied at next restart of the device),
  then `chown grid:asmadmin /dev/rhdisk10` and `chmod 660 /dev/rhdisk10`. These steps run
  as **root**, on every RAC node.
- The SQL statement sets `au_size` to `4M` and `compatible.asm` / `compatible.rdbms` to
  `19.0`, and says it is run **as `grid`**, from the ASM instance, after the Oracle
  environment pre-flight check.
- Bob warns that **`AU_SIZE` cannot be changed after creation**.

**Trap:** now ask *"Create a volume group on hdisk10 first, then give the logical volumes
to ASM."* Bob must refuse: an ASM disk is a **whole raw hdisk with no PVID**. `mkvg` or
`extendvg` on it would overwrite the ASM disk header (case H20 of the hallucination
tests).

---

## Step 7: Backup, then install with the Release Update (6 minutes)

**Goal:** protect the prepared LPAR, then get the install commands with the RU applied in
one step.

**Prompt:**

```text
The LPAR is prepared. Give me the last steps before installation: a backup of the freshly
prepared rootvg so that I can roll back a failed install, and the gridSetup.sh and
runInstaller commands that apply the Release Update during the installation. The
patches are under /stage/patches/<GI_RU_patch_number> and
/stage/patches/<DB_RU_patch_number>. Response files are /stage/grid_install.rsp and
/stage/db_install.rsp.
```

<!-- eval
mode: oracle-aix
must_include: ["mksysb", "-applyRU", "gridSetup.sh", "runInstaller", "LIBPATH"]
must_not_include: ['export\s+LD_LIBRARY_PATH']
-->

Replace `<GI_RU_patch_number>` and `<DB_RU_patch_number>` with the numbers of the Grid
Infrastructure and Database Release Updates you downloaded from My Oracle Support.

**What to observe:**

- A `mksysb` (or `alt_disk_copy -B`) **before** the installation, with the free space
  checked first (`df -g`).
- The install commands use `-applyRU`: `./gridSetup.sh -applyRU ... -silent -responseFile
  ...` run as `grid`, and `./runInstaller -applyRU ... -silent -responseFile ...` run as
  `oracle`.
- Bob says that the installer prerequisite checks and `cluvfy` win over any list of
  prerequisites, including its own.
- Bob uses `LIBPATH` in every environment example, never `LD_LIBRARY_PATH`.

---

## ✅ Success criteria

- [ ] Bob asked you which accounts own the software instead of assuming them.
- [ ] `work/lab01/01-create-users.sh` uses `mkgroup` / `mkuser` / `chuser`, with a revert.
- [ ] Bob refused `shmmax`, `semmsl` and `sysctl` and explained the AIX behaviour.
- [ ] The storage table shows 8 DATA LUNs, 8 REDO LUNs, 2 to 4 FRA LUNs, with the tiers.
- [ ] The disk group statement sets `au_size` to `4M`, and Bob refused `mkvg` on an ASM disk.
- [ ] A `mksysb` is planned before the installation, and `-applyRU` is used.

---

## Key takeaways

- Bob **reads before it writes**, and it **asks** instead of guessing the Oracle owner.
- AIX is not Linux: no `useradd`, no `sysctl`, no `LD_LIBRARY_PATH`. Bob knows it, and
  the repository tests it.
- ASM decisions that cannot be undone (`AU_SIZE`, raw disk ownership) are called out
  before you run anything.
- Every change comes with its revert.

---

## Next steps

Continue with [Lab 02](02-assess-best-practices.md) to audit this LPAR against the best
practices, or with [Lab 03](03-backup-aix-and-oracle.md) to build the backup you will
need before any change.
