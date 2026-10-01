---
name: oracle-dba-aix
description: >-
  Use when administering, tuning, troubleshooting, or automating Oracle Database
  on IBM AIX / Power Systems. Covers SQL, PL/SQL, RMAN, Data Guard, RAC,
  performance (AWR/ASH), security, monitoring, backup, migrations, and any
  scenario combining Oracle operations with AIX OS-level commands. Trigger
  phrases: "Oracle on AIX", "Oracle DBA", "RMAN", "Data Guard", "Oracle RAC",
  "AWR", "ASH", "Oracle tuning", "opatch", "lsnrctl", "adrci".
---

# Oracle DBA on AIX Skill

Expert guidance for Oracle Database administration on IBM AIX (Power Systems).
Combines Oracle Database knowledge with AIX system administration expertise.

> **Oracle `db` skill:** If the Oracle [`db` skill](https://github.com/oracle/skills/tree/main/db)
> is installed, invoke it first for any Oracle-specific topic (SQL, PL/SQL, RMAN,
> Data Guard, performance, security, ORDS, SQLcl). If it is not yet installed,
> surface that fact and direct the user to:
> ```bash
> git clone https://github.com/oracle/skills.git
> ```
> Then point the agent at the `db/` directory as a skill source.

---

## Oracle Environment Setup on AIX

Always export the Oracle environment before running Oracle commands.
Use **`LIBPATH`** on AIX, not `LD_LIBRARY_PATH`:

```bash
export ORACLE_BASE=/u01/app/oracle
export ORACLE_HOME=$ORACLE_BASE/product/19.0.0/dbhome_1
export ORACLE_SID=<SID>
export PATH=$ORACLE_HOME/bin:$PATH
# AIX uses LIBPATH, not LD_LIBRARY_PATH
export LIBPATH=$ORACLE_HOME/lib:/usr/lib
```

---

## Oracle + AIX Integration Rules

### 1. AIX-native commands only

Never substitute Linux equivalents.

| Task | AIX command | Do NOT use |
|---|---|---|
| Error log | `errpt` | `dmesg`, `journalctl` |
| Device listing | `lsdev`, `lsattr` | `lspci`, `udevadm` |
| Memory / CPU tuning | `ioo`, `vmo`, `no`, `schedo` | `sysctl` |
| Performance | `topas`, `nmon`, `svmon` | `htop`, `free` |
| User management | `lsuser`, `chuser`, `mkuser` | `useradd`, `usermod` |
| LV management | `lslv`, `mklv`, `chlv` | `lvcreate`, `lvextend` |

### 2. Storage layout

- Oracle datafiles belong on **JFS2** or **raw LVM logical volumes**.
- Use `lslv`, `mklv`, `chlv` for LV management.
- Always set `fs_type: jfs2` when creating filesystems.

```bash
# Check LV free space before scheduling backups
lsvg -l oravg | grep -v LV
df -g $ORACLE_BASE/fast_recovery_area
```

### 3. AIX shared memory and semaphores

Oracle on AIX uses AIX SHM/SEM tunables — not Linux `sysctl`:

```bash
# Check SGA-related shared-memory settings
ioo -a | grep -i shm
vmo -a | grep -E 'maxpin|minperm|maxperm'

# Adjust (example — verify against Oracle MOS note for your version)
vmo -p -o maxpin%=80
```

### 4. Listener and TNS

`lsnrctl` syntax is identical on AIX:

```bash
lsnrctl status
lsnrctl start
lsnrctl stop
```

`tnsnames.ora` and `sqlnet.ora` live under `$ORACLE_HOME/network/admin/`.

### 5. Diagnosing Oracle errors on AIX

Correlate the Oracle alert log with AIX `errpt` to distinguish OS-level faults
(disk, memory) from Oracle-level errors:

```bash
# Oracle alert log
adrci exec="show alert -tail 50"

# AIX error report — look for disk/memory errors around the same timestamp
errpt -a -s <MMDDHHMMYY> | head -200
```

### 6. RMAN on AIX

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

### 7. RAC on AIX

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

### 8. User and group

```bash
# Create Oracle OS user (AIX commands — not useradd)
mkuser id=54321 pgrp=oinstall groups=oinstall,dba oracle
lsuser oracle
chuser shell=/bin/ksh oracle
```

### 9. Patching

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

## Safety and Change Management

- **Warn clearly** before any destructive operation (`DROP`, `TRUNCATE`,
  `ALTER SYSTEM`, RAC node eviction, LV resize).
- **Recommend backup**: RMAN backup or `mksysb` before structural changes.
- **Provide rollback steps** for every DML or DDL change.
- **Test on non-production first**; include dry-run queries where possible
  (e.g. `SELECT` before `DELETE`).

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
