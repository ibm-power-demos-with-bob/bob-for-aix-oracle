---
id: S01
title: Oracle 19c install preparation on AIX / PowerVS
mode: oracle-aix
skills: [oracle-aix]
reads:
  - .agents/skills/oracle-aix/SKILL.md
  - .agents/skills/oracle-aix/best-practices/os-prereqs.md
  - .agents/skills/oracle-aix/best-practices/io-storage.md
  - .agents/skills/oracle-aix/best-practices/memory.md
prompt: >-
  I must install Oracle Database 19c with ASM on a new PowerVS LPAR
  (Power10, AIX 7.3 TL4, Tier 1 flash volumes). Prepare the AIX side and
  the storage layout. The users do not exist yet and I am not sure which
  account will own the software.
must_include:
  - "ask the user"
  - "oracle"
  - "grid"
  - "LIBPATH"
  - "ORACLE_HOME"
  - "iocp0"
  - "maxuproc"
  - "CAP_NUMA_ATTACH"
  - "queue_depth"
  - "AU_SIZE"
  - "-applyRU"
  - "reserve_policy=no_reserve"
  - "mksysb"
must_not_include:
  - '\bLD_LIBRARY_PATH\s*='
  - '\bshmmax\b'
  - '\bsemmsl\b'
  - '\bsysctl\b'
  - '\buseradd\b'
  - '\bmkvg\b.*rhdisk'
---

# Scenario S01: Oracle install preparation

**Goal:** a new LPAR ready for `gridSetup.sh` and `runInstaller`, following the
repository rules: ask for the OS users, verify the environment, 8/8/2-4 LUN
layout, flash tiers, and ASM `AU_SIZE` fixed at creation time.

## Demo script

1. Select the **Oracle on AIX/Power** mode and paste the prompt.
2. Bob must **ask for or confirm the OS user names** (`oracle` / `grid` by default)
   instead of creating or assuming them, then proceed after your answer.
3. Show that Bob refuses to give Linux kernel parameters (`shmmax`, `semmsl`):
   AIX sizes shared memory dynamically.
4. Show the storage checklist and the PowerVS IOPS arithmetic
   (Tier 1 = 10 IOPS/GB, so 8 x 100 GB = 8,000 IOPS).

## Reference answer

Step 0, context and users (read-only; do not create anything yet):

```bash
# Purpose: capture context and check whether the Oracle software owners exist
oslevel -s
prtconf | grep -E "System Model|Processor Type|Processor Implementation Mode"
lparstat -i | grep -E "^Type|^Mode|^Entitled Capacity|^Online Virtual CPUs"
id oracle; id grid
lsuser -a id pgrp groups home oracle,grid
cat /etc/oraInst.loc || find /u01 -maxdepth 3 -name oraInst.loc    # custom -invPtrLoc
# If a user is missing or the owner differs: ask the user for the correct username.
```

Step 1, OS prerequisites (as root, after the user agrees on the names):

```bash
# Purpose: required filesets (preview missing ones with installp -p before installing)
lslpp -l bos.adt.base bos.adt.lib bos.adt.libm bos.perf.libperfstat \
         bos.perf.perfstat bos.perf.proctools xlC.rte rsct.basic.rte 2>&1 | grep -E "not installed|COMMITTED|APPLIED"

lsdev -Cc iocp                                  # expect: iocp0 Available
chdev -l iocp0 -a autoconfig=available -P       # only if Defined: Available after reboot

lsattr -El sys0 -a maxuproc -a ncargs
chdev -l sys0 -a maxuproc=16384                 # revert: chdev -l sys0 -a maxuproc=<old>
chdev -l sys0 -a ncargs=256

# Users, groups, capabilities (names/IDs per site standard; same IDs on all RAC nodes)
mkgroup -A id=54321 oinstall
mkgroup -A id=54322 dba
mkgroup -A id=54327 asmdba
mkgroup -A id=54328 asmadmin
mkuser id=54321 pgrp=oinstall groups=oinstall,dba,asmdba home=/home/oracle shell=/usr/bin/ksh oracle
mkuser id=54331 pgrp=oinstall groups=oinstall,asmadmin,asmdba,dba home=/home/grid shell=/usr/bin/ksh grid
chuser capabilities=CAP_NUMA_ATTACH,CAP_BYPASS_RAC_VMM,CAP_PROPAGATE oracle
chuser capabilities=CAP_NUMA_ATTACH,CAP_BYPASS_RAC_VMM,CAP_PROPAGATE grid
lsuser -a capabilities oracle,grid
```

Step 2, storage layout (checklist from `io-storage.md` §7):

| Pool | LUNs | Tier (PowerVS) | Notes |
|---|---|---|---|
| `DATA` | 8 equal size (or a multiple of 8) | Tier 1 (Tier 0 if the IOPS target needs it) | spread over 2 or more NPIV adapters, dual VIOS |
| `REDO` | 8, or dedicated low write-latency LUNs | highest flash tier | separate pool from data |
| `FRA` / backups | 2 to 4 | Tier 3 | never mix tiers in one disk group |

```bash
# Purpose: prepare ASM disks on a new, unused hdisk (every RAC node)
lspv | grep -w hdisk10                      # must show PVID "none" and VG "None"
chdev -l hdisk10 -a reserve_policy=no_reserve -a queue_depth=64 -a max_transfer=0x100000 -P
chown grid:asmadmin /dev/rhdisk10
chmod 660 /dev/rhdisk10
ls -l /dev/rhdisk10                         # crw-rw---- grid asmadmin
# Revert queue_depth: chdev -l hdisk10 -a queue_depth=<old> -P
```

```sql
-- AU_SIZE cannot be changed later. Run as grid, from the ASM instance.
CREATE DISKGROUP data EXTERNAL REDUNDANCY
  DISK '/dev/rhdisk10','/dev/rhdisk11','/dev/rhdisk12','/dev/rhdisk13',
       '/dev/rhdisk14','/dev/rhdisk15','/dev/rhdisk16','/dev/rhdisk17'
  ATTRIBUTE 'compatible.asm'='19.0','compatible.rdbms'='19.0','au_size'='4M';
```

Step 3, installation with the Release Update in one step:

```bash
# Purpose: install 19c base + RU. Run as the software owner, with the latest OPatch in the home.
# Grid home, as grid
./gridSetup.sh -applyRU /stage/patches/<GI_RU_patch_number> -silent -responseFile /stage/grid_install.rsp
# Database home, as oracle
./runInstaller -applyRU /stage/patches/<DB_RU_patch_number> -silent -responseFile /stage/db_install.rsp
```

Required statements in the answer:

- Take an `mksysb` (or `alt_disk_copy -B`) of the freshly prepared LPAR before the
  installation, so a failed install can be rolled back.
- Use `LIBPATH`, never `LD_LIBRARY_PATH`. Run the Oracle environment pre-flight
  check (`ORACLE_HOME`, `ORACLE_SID`, `ORACLE_BASE`, `PATH`, `LIBPATH`) before
  every Oracle command.
- The installer prerequisite checks and `cluvfy` win over this list.

## What this scenario demonstrates

- OS user handling: default `oracle` / `grid`, ask when missing, never `root`.
- Storage rules: 8 data LUNs, 8 redo LUNs, 2 to 4 backup LUNs, flash tiers,
  `queue_depth`, `AU_SIZE`.
- No invented Linux kernel parameters.
