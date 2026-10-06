# Oracle DB on AIX/Power -- Safety Rules

These safety rules are always active in the `oracle-power` mode.

## Before Any Destructive Operation

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

## Backup Requirement

- Recommend an RMAN backup before any structural change (schema changes, tablespace operations, patching, major parameter changes).
- Recommend `mksysb` before AIX OS-level changes that affect Oracle (LVM restructuring, filesystem changes, AIX upgrades).

```bash
# Quick RMAN backup check before a risky operation
rman target / <<EOF
  REPORT NEED BACKUP;
  LIST BACKUP SUMMARY;
EOF
```

## Rollback Steps

- Always provide a rollback or recovery path alongside any recommended change.
- For `ALTER SYSTEM` parameter changes, always show the revert command:
  ```sql
  -- Change
  ALTER SYSTEM SET parameter = new_value SCOPE=BOTH;
  -- Revert
  ALTER SYSTEM SET parameter = old_value SCOPE=BOTH;
  -- Or from spfile if instance must be restarted
  ALTER SYSTEM RESET parameter SCOPE=SPFILE;
  ```

## Production vs. Non-Production

- If the target environment is not explicitly stated, ask whether it is production.
- For production environments: recommend testing on non-production first.
- For non-production: still warn on irreversible operations, but tone can be less restrictive.

## AIX Kernel Parameter Safety

- Never recommend changing AIX restricted parameters (`vmo -F`, `ioo -F`) unless IBM support has explicitly requested it.
- Always use persistent flag (`-p`) when changing tuning parameters intended to survive a reboot:
  ```bash
  vmo -p -o minfree=1200   # -p = persistent across reboots
  schedo -p -o vpm_throughput_mode=2
  ```
- Without `-p`, changes are runtime-only and lost on reboot -- this is sometimes intentional for testing, but must be stated explicitly.
