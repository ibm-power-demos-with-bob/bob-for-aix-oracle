---
name: oracle-aix
description: >-
  Use for Oracle Database running on IBM AIX / IBM Power Systems (including
  PowerVS): administration, installation and patching on AIX, performance tuning
  of the AIX/Power layer (CPU/SMT/LPAR, memory/large pages/NUMA, I/O/ASM/JFS2/FC,
  RAC network), and diagnosis that correlates Oracle with AIX (alert log + errpt).
  Do NOT use for Oracle on Linux, Windows, or Exadata. Trigger phrases: "Oracle on
  AIX", "Oracle AIX", "Oracle Power Systems", "Oracle IBM Power", "Oracle PowerVS",
  "RAC on AIX", "ASM on AIX", "Oracle LPAR", "ORACLE_SGA_PGSZ", "opatch AIX",
  "LIBPATH Oracle".
---

# Oracle Database on IBM Power Systems / AIX

Expert guidance for Oracle Database on IBM AIX. It combines Oracle DBA knowledge
with AIX and Power platform expertise. The best-practice files are based on the
IBM Power Systems VUG May 2024 sessions by Ralf Schmidt-Dannert (IBM ATG), plus
later IBM and Oracle documents cited in each file.

---

## Step 1: Load Only What You Need

This file holds the rules that always apply. Detailed guidance lives in companion
files. **Read the matching file before answering** a question in its domain, and
read only the files you need.

| Topic | Read |
|---|---|
| Diagnosis flows (slow I/O, CPU, paging, ORA errors, RAC network) | [`best-practices/diagnostics.md`](best-practices/diagnostics.md) |
| SMT, CPU folding, vCPU/entitlement, LPAR sizing, Power11 migration | [`best-practices/cpu.md`](best-practices/cpu.md) |
| SGA page size, 16 MB pages, NUMA/SRAD, vmo, paging space, DSO, AME | [`best-practices/memory.md`](best-practices/memory.md) |
| AIO, hdisk/FC/MPIO tuning, ASM on AIX, JFS2 mount options, LVM striping, redo | [`best-practices/io-storage.md`](best-practices/io-storage.md) |
| RAC/public network, `no` tunables, interface naming, HAIP, jumbo frames | [`best-practices/network-rac.md`](best-practices/network-rac.md) |
| Install/patch 19c on AIX, filesets, users/capabilities/limits, IOCP, OS prerequisites | [`best-practices/os-prereqs.md`](best-practices/os-prereqs.md) |
| Mutex spin, MARKHOT, CPU % under SMT, PowerVS tiers, pigz/zlibNX, embedded JDK, known 19c issues | [`best-practices/misc.md`](best-practices/misc.md) |

**Pure Oracle topics** (SQL, PL/SQL, RMAN, Data Guard, AWR/ASH, security, ORDS,
SQLcl) are platform-neutral:

- If `operations/` exists next to this file, read the matching topic file there.
  It holds the Oracle community `db` skill, installed by `/oracle-aix-setup`.
- If it does not exist, mention once that the user can install it with the Bob
  command `/oracle-aix-setup` (defined in `.bob/commands/oracle-aix-setup.md`),
  then answer from general Oracle knowledge.

---

## Step 2: Capture Context

Recommendations differ by Oracle release/RU, AIX level, and Power generation. If the
user hasn't given these, ask for them or include the commands to collect them:

```bash
oslevel -s                                  # AIX level, e.g. 7300-02-02-2420
prtconf | grep -E "System Model|Processor Type|Processor Implementation Mode"
lparstat -i | grep -E "^Type|^Mode|^Entitled Capacity|^Online Virtual CPUs|^Shared Pool ID"
smtctl | head -5
$ORACLE_HOME/OPatch/opatch lspatches        # Oracle RU / one-offs (as oracle)
```

Also confirm whether the environment is **production**. If it isn't stated, ask.

---

## Platform Constraints (always apply)

### AIX commands: never substitute Linux equivalents

| Task | AIX command | Never use |
|---|---|---|
| Error log | `errpt` | `dmesg`, `journalctl` |
| Device listing | `lsdev`, `lsattr`, `lscfg` | `lspci`, `udevadm` |
| Memory / CPU / network tuning | `vmo`, `ioo`, `schedo`, `no` | `sysctl` |
| Performance | `topas`, `nmon`, `svmon`, `vmstat`, `iostat` | `htop`, `free` |
| LV management | `lslv`, `mklv`, `extendlv`, `lsvg` | `lvcreate`, `lvextend` |
| User management | `mkuser`, `chuser`, `lsuser` | `useradd`, `usermod` |
| Services | `lssrc`, `startsrc`, `stopsrc` | `systemctl` |
| Date arithmetic | `perl -MPOSIX -e ...` | `date -d` (GNU only) |

### Library path and environment

On AIX, use `LIBPATH` rather than `LD_LIBRARY_PATH`:

```bash
export ORACLE_BASE=/u01/app/oracle
export ORACLE_HOME=$ORACLE_BASE/product/19.0.0/dbhome_1
export ORACLE_SID=<SID>
export PATH=$ORACLE_HOME/bin:$PATH
export LIBPATH=$ORACLE_HOME/lib:/usr/lib
```

For databases started by Clusterware or Oracle Restart, set environment variables
with `srvctl setenv`. Shell profile variables are **ignored** by `srvctl start`.

### Shared memory and semaphores

AIX sizes shared memory and semaphores dynamically. Unlike Linux, there are no
`shmmax`/`semmsl` kernel parameters to tune. The memory settings that matter for
Oracle are covered in `best-practices/memory.md`: page size, `v_pinshm` when you
pin the SGA, and `minfree`/`maxfree`.

### Power platform awareness

- SMT mode sets the logical CPU count, which drives `cpu_count` and every Oracle
  parameter derived from it.
- NUMA/SRAD placement affects SGA memory latency.
- 16 MB pages are the Power-specific option for large SGAs (≥ 100 GB).
- Storage is normally Fibre Channel SAN through NPIV and dual VIOS.

---

## Safety Rules (always apply)

### Confirm before destructive operations

Warn explicitly and get confirmation before running or recommending:

| Category | Examples |
|---|---|
| Irreversible SQL | `DROP TABLE`, `TRUNCATE`, `DROP TABLESPACE`, `DROP USER CASCADE`, `ALTER DATABASE DROP LOGFILE` |
| Instance changes | `SHUTDOWN ABORT`, memory/SGA `ALTER SYSTEM`, any underscore (`_`) parameter |
| RMAN deletes | `DELETE ARCHIVELOG`, `DELETE OBSOLETE`, `DELETE BACKUPSET`, `BACKUP ... DELETE INPUT` |
| Data Guard / RAC | `FAILOVER`, `SWITCHOVER`, `crsctl stop cluster`, OCR/voting disk changes |
| AIX LVM / filesystems | `reducevg`, `rmvg`, `rmlv`, `rmfs`, `varyoffvg`, unmounting active filesystems |
| Disks | `rmdev`, `chdev` on in-use disks (for example `reserve_policy`), `mkvg -f`, adding a disk that ASM owns to a VG |
| LPAR | DLPAR removal of CPU or memory from a running instance |

### Backup and rollback

- Recommend an RMAN backup before structural changes (schema, tablespaces,
  patching, major parameter changes), and `mksysb` or `alt_disk_copy` before AIX
  OS changes.
- For every `ALTER SYSTEM`, capture the current value first and show the revert:

```sql
SHOW PARAMETER <parameter>                                -- record the current value
ALTER SYSTEM SET <parameter> = <new_value> SCOPE=BOTH;    -- change
ALTER SYSTEM SET <parameter> = <old_value> SCOPE=BOTH;    -- revert
ALTER SYSTEM RESET <parameter> SCOPE=SPFILE;              -- or return to the default at next restart
```

- **Underscore (hidden) parameters and diagnostic events** must be set only with
  Oracle Support's agreement. Say this every time you mention one.

### Production vs non-production

- For production: test on non-production first and schedule a change window.
- For non-production: still warn about irreversible operations.

### AIX tunable safety

- Do not change **restricted** tunables (visible only with `vmo -F`, `ioo -F`, and
  so on) unless IBM Support has asked for it.
- Before recommending a tunable, check that it exists at the user's level and show
  its default: `vmo -L <tunable>` (or `-h`).
- Use `-p` for changes that should survive a reboot, and `-r` for reboot-type
  tunables (then `bosboot -a`). A change without `-p` is runtime-only, so say so.
- Dependent tunables must be changed together, for example
  `vmo -p -o minfree=<n> -o maxfree=<m>` with `maxfree > minfree`.

---

## Oracle + AIX Integration (quick reference)

### Storage layout

- Put database files on **ASM using raw hdisks** (`/dev/rhdiskN`, no PVID,
  `reserve_policy=no_reserve`, owned by `grid:asmadmin`, mode `660`) or on
  **JFS2**.
- Raw LVs are not supported for database files.

Details are in `best-practices/io-storage.md`.

```bash
lsvg -l oravg                               # LVs and filesystems in the Oracle VG
df -g /u01/app/oracle/fast_recovery_area    # free space in GB before backups
```

### Diagnosing Oracle errors on AIX

Correlate the Oracle alert log with the AIX error log to tell OS faults (disk,
adapter, memory) from Oracle-level errors:

```bash
adrci exec="show alert -tail 100"                   # as oracle
errpt | head -30                                    # as root: look near the same time
errpt -a -s <MMDDhhmmYY> | head -200                # detail from a start time
```

The full flow is in `best-practices/diagnostics.md`.

### RMAN on AIX

- Tape integration uses an MML such as IBM Storage Protect (formerly Spectrum
  Protect / TSM) for Databases.
- Before scheduling backups, check free space in the FRA filesystem or disk group.

```bash
# Hot backup. The deletes are destructive: confirm the retention policy first
# (RMAN> SHOW RETENTION POLICY;) and that backups of the archived logs exist.
rman target / <<EOF
  BACKUP DATABASE PLUS ARCHIVELOG;
  DELETE NOPROMPT OBSOLETE;
EOF
```

### RAC on AIX

- Shared storage is ASM on raw hdisks, or IBM Storage Scale (GPFS).
- Run cluster commands from `$GRID_HOME/bin`:

```bash
crsctl stat res -t                 # cluster resource status
srvctl status database -d <db>
ocrcheck                           # OCR integrity (as root)
oifcfg getif                       # public / cluster_interconnect assignment
```

Interconnect and `no`/ISNO settings are in `best-practices/network-rac.md`.

### Patching (summary)

The full procedure is in `best-practices/os-prereqs.md`.

1. Take an RMAN backup and back up the Oracle home (tar).
2. Update OPatch in each home, then run the conflict check:
   `opatch prereq CheckConflictAgainstOHWithDetail -ph ./`.
3. Stop the home's processes. As root, run `/usr/sbin/slibclean` to unload
   cached shared libraries (this avoids "text file busy" errors).
4. Apply the patch: `opatch apply` for DB homes, or `opatchauto apply` as root for
   Grid. Then run `datapatch -verbose`.
5. AIX OS fixes go in a separate change: preview with
   `install_all_updates -d <dir> -p -Y`, then apply.

---

## Response Format

### SQL / PL/SQL

```sql
-- Purpose: <what this does>
<statement>;
-- Verification query / expected result
-- Revert: <statement> (for changes)
```

### Shell commands on AIX

```bash
# Purpose: <description>
<command> -options arguments

# Expected output or key fields to check
# AIX-level / Power-generation caveat, rollback
```

### Structure of answers

1. Lead with the diagnosis or Oracle concept.
2. Add the AIX/Power context, including the commands to verify the current state.
3. Give the change, its revert, and the safety notes.
4. Name the companion file you used, for example
   `best-practices/memory.md §5`.

---

## When Uncertain

1. Say so explicitly. Many facts here depend on the AIX TL/SP, the Oracle RU, and
   the Power generation.
2. Suggest how to verify: `man <cmd>`, `vmo -h <tunable>`, `oerr ora <code>`,
   `<tool> -help`, My Oracle Support, or IBM Support note
   [6825029](https://www.ibm.com/support/pages/node/6825029).
3. Recommend testing in a non-production environment.

---

## Documentation References

- [IBM: AIX with Oracle Database on IBM Power, considerations for performance and stability](https://www.ibm.com/support/pages/node/6825029)
- [Oracle Database 19c documentation](https://docs.oracle.com/en/database/oracle/oracle-database/19/)
- [Oracle Database installation guide for AIX (19c)](https://docs.oracle.com/en/database/oracle/oracle-database/19/axdbi/)
- [My Oracle Support](https://support.oracle.com) (certification matrix: Certifications tab)
- [IBM AIX 7.3 documentation](https://www.ibm.com/docs/en/aix/7.3)
- [Oracle `db` skill repository](https://github.com/oracle/skills/tree/main/db)
