---
name: oracle-aix
description: >-
  Master skill for Oracle Database on IBM Power Systems / AIX. Covers
  administration, tuning, troubleshooting, and automation: SQL, PL/SQL, RMAN,
  Data Guard, RAC, performance (AWR/ASH), security, monitoring, backup,
  migrations, patching, and any scenario combining Oracle operations with AIX
  OS-level commands. Also routes to specialised sub-skills for deep-dive topics
  (CPU/LPAR, I/O & storage, memory, licensing, miscellaneous). Trigger phrases:
  "Oracle AIX", "Oracle Power Systems", "Oracle on AIX", "Oracle DBA", "RMAN",
  "Data Guard", "Oracle RAC", "AWR", "ASH", "Oracle tuning", "opatch",
  "lsnrctl", "adrci", "best practices Oracle AIX", "Oracle IBM Power".
---

# Oracle Database on IBM Power Systems / AIX

Expert guidance for Oracle Database on IBM AIX (Power Systems).
Combines Oracle Database knowledge with AIX system administration expertise.

All best-practice content originates from IBM Power Systems VUG May 2024 sessions by
Ralf Schmidt-Dannert, IBM ATG Principal Power Specialist.

> **Oracle `db` skill:** If the Oracle [`db` skill](https://github.com/oracle/skills/tree/main/db)
> is installed, invoke it first for any Oracle-specific topic (SQL, PL/SQL, RMAN,
> Data Guard, performance, security, ORDS, SQLcl). If it is not yet installed,
> surface that fact and direct the user to:
> ```bash
> git clone https://github.com/oracle/skills.git
> ```
> Then point the agent at the `db/` directory as a skill source.

---

## Platform Constraints (always apply)

### AIX commands — never substitute Linux equivalents

| Task | AIX command | Never use |
|---|---|---|
| Error log | `errpt` | `dmesg`, `journalctl` |
| Device listing | `lsdev`, `lsattr` | `lspci`, `udevadm` |
| Memory / CPU tuning | `vmo`, `ioo`, `schedo`, `no` | `sysctl` |
| Performance | `topas`, `nmon`, `svmon` | `htop`, `free` |
| LV management | `lslv`, `mklv`, `chlv`, `lsvg` | `lvcreate`, `lvextend` |
| User management | `lsuser`, `chuser`, `mkuser` | `useradd`, `usermod` |

### Library path on AIX

Always use `LIBPATH`, never `LD_LIBRARY_PATH`:

```bash
export LIBPATH=$ORACLE_HOME/lib:/usr/lib
```

### Oracle environment setup

Must be set before any Oracle command:

```bash
export ORACLE_BASE=/u01/app/oracle
export ORACLE_HOME=$ORACLE_BASE/product/19.0.0/dbhome_1
export ORACLE_SID=<SID>
export PATH=$ORACLE_HOME/bin:$PATH
export LIBPATH=$ORACLE_HOME/lib:/usr/lib
```

### Power platform awareness

Oracle on Power has specific tuning considerations that differ from x86 Linux:

- SMT threading model affects `cpu_count` and all derived Oracle parameters.
- NUMA/SRAD topology affects SGA memory latency.
- 16MB large pages are a Power-specific SGA optimization.
- Fiber channel SAN via NPIV/VIOS is the standard storage path.

Always consider the IBM Power hardware layer when diagnosing Oracle performance issues.
When relevant, ask or note which Power generation (Power8/9/10/11) and AIX version
(7.1/7.2/7.3/7.3 TL3+) the user is on — recommendations differ.

---

## Safety Rules (always apply)

### Before any destructive operation

Always warn explicitly and require confirmation before executing any of the following:

| Operation category | Examples |
|---|---|
| Oracle DDL/DML that cannot be rolled back | `DROP TABLE`, `TRUNCATE`, `DROP TABLESPACE`, `DROP USER CASCADE` |
| Oracle instance changes | `SHUTDOWN ABORT`, `ALTER SYSTEM` (memory/SGA changes), `ALTER DATABASE` |
| RMAN operations that delete data | `DELETE ARCHIVELOG`, `DELETE BACKUPSET`, `CROSSCHECK` followed by delete |
| Data Guard role changes | `FAILOVER`, `SWITCHOVER` |
| RAC operations | Node eviction, `crsctl stop cluster`, OCR/voting disk changes |
| AIX LVM changes | `reducevg`, `rmvg`, `rmlv`, `rmfs` |
| Filesystem changes | Unmounting active filesystems, `rmfs` on Oracle data filesystems |
| hdisk/storage changes | `rmdev`, changing `reserve_policy` on active disks |
| LPAR configuration | CPU/memory removal via DLPAR on a running Oracle instance |

### Backup requirement

- Recommend an RMAN backup before any structural change (schema changes, tablespace operations, patching, major parameter changes).
- Recommend `mksysb` before AIX OS-level changes that affect Oracle (LVM restructuring, filesystem changes, AIX upgrades).

```bash
# Quick RMAN backup check before a risky operation
rman target / <<EOF
  REPORT NEED BACKUP;
  LIST BACKUP SUMMARY;
EOF
```

### Rollback steps

Always provide a rollback or recovery path alongside any recommended change.
For `ALTER SYSTEM` parameter changes, always show the revert command:

```sql
-- Change
ALTER SYSTEM SET parameter = new_value SCOPE=BOTH;
-- Revert
ALTER SYSTEM SET parameter = old_value SCOPE=BOTH;
-- Or from spfile if instance must be restarted
ALTER SYSTEM RESET parameter SCOPE=SPFILE;
```

### Production vs. non-production

- If the target environment is not explicitly stated, ask whether it is production.
- For production environments: recommend testing on non-production first.
- For non-production: still warn on irreversible operations, but tone can be less restrictive.

### AIX kernel parameter safety

- Never recommend changing AIX restricted parameters (`vmo -F`, `ioo -F`) unless IBM support has explicitly requested it.
- Always use persistent flag (`-p`) when changing tuning parameters intended to survive a reboot:

```bash
vmo -p -o minfree=1200   # -p = persistent across reboots
schedo -p -o vpm_throughput_mode=2
```

Without `-p`, changes are runtime-only and lost on reboot — this is sometimes intentional for testing, but must be stated explicitly.

---

## Oracle + AIX Integration

### Storage layout

Oracle datafiles belong on **JFS2** or **raw LVM logical volumes**.
Always set `fs_type: jfs2` when creating filesystems for Oracle.

```bash
# Check LV free space before scheduling backups
lsvg -l oravg | grep -v LV
df -g $ORACLE_BASE/fast_recovery_area
```

### AIX shared memory and semaphores

Oracle on AIX uses AIX SHM/SEM tunables — not Linux `sysctl`:

```bash
# Check SGA-related shared-memory settings
ioo -a | grep -i shm
vmo -a | grep -E 'maxpin|minperm|maxperm'

# Adjust (example — verify against Oracle MOS note for your version)
vmo -p -o maxpin%=80
```

### Listener and TNS

`lsnrctl` syntax is identical on AIX:

```bash
lsnrctl status
lsnrctl start
lsnrctl stop
```

`tnsnames.ora` and `sqlnet.ora` live under `$ORACLE_HOME/network/admin/`.

### Diagnosing Oracle errors on AIX

Correlate the Oracle alert log with AIX `errpt` to distinguish OS-level faults
(disk, memory) from Oracle-level errors:

```bash
# Oracle alert log
adrci exec="show alert -tail 50"

# AIX error report — look for disk/memory errors around the same timestamp
errpt -a -s <MMDDHHMMYY> | head -200
```

### RMAN on AIX

- Tape integration uses **XBSA** via IBM Spectrum Protect (formerly TSM).
- Disk backups default to `$ORACLE_BASE/fast_recovery_area`.
- Always verify LV free space before scheduling backups.

```bash
# RMAN hot backup example
rman target / <<EOF
  BACKUP DATABASE PLUS ARCHIVELOG DELETE INPUT;
  DELETE OBSOLETE;
EOF
```

### RAC on AIX

- Shared storage: **IBM GPFS (Spectrum Scale)** or **ASM**.
- RAC management commands come from `$GRID_HOME/bin`:

```bash
crsctl status res -t       # cluster resource status
srvctl status database -d <db>
ocrcheck                   # OCR integrity check
```

- Tune node interconnect on dedicated `en*` adapters:

```bash
no -o rfc1323=1
```

### User and group management

```bash
# Create Oracle OS user (AIX commands — not useradd)
mkuser id=54321 pgrp=oinstall groups=oinstall,dba oracle
lsuser oracle
chuser shell=/bin/ksh oracle
```

### Patching

1. Take an RMAN backup first.
2. Run `opatch prereq CheckMinimumOPatchVersion -ph ./` before applying.
3. Apply Oracle PSU/RU: `opatch apply`.
4. Apply AIX OS fixes: `installp -aXYgd <bundle> all` or via `smitty`.

---

## Response Format

### Oracle SQL / PL/SQL

```sql
-- Purpose: <what this does>
<statement>;
-- Expected result / verification query
```

### Shell commands on AIX

```bash
# <description>
<command> -options arguments

# Expected output or key fields to check
# AIX-specific note or warning if applicable
```

### Structured answers

1. Lead with the Oracle concept or diagnosis.
2. Follow with the AIX context where relevant.
3. Cite the relevant `db` skill category consulted (e.g.
   `db/performance/awr-reports.md` from the Oracle skills repo).

---

## Sub-skills (deep-dive topics)

### 1. `best-practices/cpu.md` — CPU & LPAR Tuning
**Skill name**: `oracle-best-practices-cpu`

Covers SMT mode selection (SMT1/2/4/8), CPU folding, `vpm_throughput_mode`,
vCPU sizing, entitlement ratios, dedicated vs shared LPARs, virtual processor
dispatch monitoring (`lparstat`, `mpstat`), `schedo`, and Oracle CPU-related
parameters (`cpu_count`, `parallel_threads_per_cpu`).

**Load when the user asks about**: SMT mode, CPU entitlement, shared processor
pools, `vpm_throughput_mode`, CPU folding, LPAR sizing for Oracle.

---

### 2. `best-practices/io-storage.md` — I/O & Storage Tuning
**Skill name**: `oracle-best-practices-io-storage`

Covers asynchronous I/O (AIO), `filesystemio_options`, fiber channel adapter
tuning (`fast_fail`, `dyntrk`, multiple queues), hdisk `qdepth`/transfer size,
MPIO, VSCSI tuning, LVM volume group and logical volume striping, JFS2 mount
options (CIO/DIO/buffer cache), ASM disk group layout, RBNA, redo 4K block size,
buffer cache sizing, IBM Spectrum Scale (GPFS), and OS-level resource limits.

**Load when the user asks about**: AIO, JFS2 CIO/DIO, hdisk qdepth, MPIO,
fiber channel tuning, ASM on AIX, `filesystemio_options`, LVM striping for Oracle.

---

### 3. `best-practices/memory.md` — Memory Tuning
**Skill name**: `oracle-best-practices-memory`

Covers AIX memory pools, page sizes (4KB/64KB/16MB), SGA large page selection
(`ORACLE_SGA_PGSZ`), JFS2 inode/metadata cache sizing, NUMA/SRAD affinity,
paging space management, `vmo`/`ioo` parameters (`minfree`, `maxfree`,
`minperm`, `maxperm`), DSO/MPSS page coalescing, AME, `LDR_CNTRL` Oracle binary
page size, `shrsymtab`/`ldedit` defect, terabyte segment aliasing, and
AIX 7.3 / Power10 / Power11 specifics.

**Load when the user asks about**: SGA page size, 16MB huge pages, AIX memory
pools, NUMA topology, paging space, `vmo` tuning, `lock_sga`, `lssrad`.

---

### 4. `best-practices/licensing.md` — Oracle Licensing
**Skill name**: `oracle-best-practices-licensing`

Covers hard partitioning with CAPPED LPARs and Shared Processor Pools,
`lparstat -i` documentation for audits, Oracle licensing in IBM Power Virtual
Server (PowerVS), the 10-day standby rule, Enterprise Pools 2.0 (PEP 2.0),
LPM risks and disablement (`chsyscfg migration_disabled`), SE2 eligibility on
S1014/S1112, Oracle Options/Management Packs usage detection
(`options_packs_usage_statistics.sql`, MOS 1317265.1), audit evidence collection,
DLPAR profile mismatch risk, and LPM frame widening.

**Associated script**: `best-practices/scripts/options_packs_usage_statistics.sql`
— queries `DBA_FEATURE_USAGE_STATISTICS` to detect licensed options/packs.

**Load when the user asks about**: Oracle license audit, hard partitioning, capped
LPAR, LPM and licensing, Oracle SE2 on Power, PowerVS licensing, core factor.

---

### 5. `best-practices/misc.md` — Miscellaneous Best Practices
**Skill name**: `oracle-best-practices-misc`

Covers Oracle 19c installation and patching on AIX (base 19.3 + RU in one step),
mutex spin count tuning (`_spin_count`), `mark_hot` for hot objects, CPU
utilization interpretation under SMT, RAC network configuration on AIX (HAIP,
IPv6 interface ordering), ASM external redundancy recommendation, pigz/zlibNX
hardware compression parallelism, PowerVS storage tier selection, and IBM Java
embedded in Oracle.

**Load when the user asks about**: Oracle 19c install on AIX, RU patching, mutex
spin, RAC on AIX, HAIP, pigz compression, IBM Java in Oracle, PowerVS tiers.

---

## Routing summary

| Topic | Sub-skill file |
|---|---|
| SMT, LPAR sizing, CPU entitlement | `best-practices/cpu.md` |
| AIO, JFS2, hdisk, MPIO, ASM storage | `best-practices/io-storage.md` |
| SGA pages, huge pages, NUMA, vmo | `best-practices/memory.md` |
| Licensing, audit, LPM, SE2 | `best-practices/licensing.md` |
| Installation, RAC, pigz, misc | `best-practices/misc.md` |

---

## When Uncertain

1. State the uncertainty explicitly.
2. Suggest verification: `man <cmd>`, `oerr ora <code>`,
   `$ORACLE_HOME/bin/<tool> -help`, or Oracle Support (MOS).
3. Recommend testing in a non-production environment.

---

## Documentation References

- [Oracle Database 19c / 21c Docs](https://docs.oracle.com/en/database/oracle/oracle-database/)
- [Oracle Support (MOS)](https://support.oracle.com)
- [IBM AIX 7.3 Documentation](https://www.ibm.com/docs/en/aix/7.3)
- [IBM Spectrum Protect (TSM)](https://www.ibm.com/docs/en/spectrum-protect)
- [Oracle `db` skill repo](https://github.com/oracle/skills/tree/main/db)
