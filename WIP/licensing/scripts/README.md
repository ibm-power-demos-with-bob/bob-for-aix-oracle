# Oracle Licensing Scripts

This folder is where the scripts used for Oracle licensing reviews on IBM Power Systems / AIX go.

---

## options_packs_usage_statistics.sql (download it yourself, not redistributed)

**Purpose**: detects which Oracle Database options and management packs have been used in a
database. It queries `DBA_FEATURE_USAGE_STATISTICS`, `CDB_FEATURE_USAGE_STATISTICS` (for
CDBs), `V$INSTANCE`, `V$DATABASE`, and `V$VERSION`.

**Source**: My Oracle Support (MOS) Note **1317265.1**, *"Database Options/Management Packs
Usage Detection"*:
https://support.oracle.com/support/?anchorId=&kmContentId=1317265&page=sptemplate&sptemplate=km-article
*(an Oracle Support login is required)*

The script is Oracle Support content, so this repository does **not** redistribute it. The
file name `options_packs_usage_statistics.sql` in this folder is git-ignored, so a downloaded
copy is never committed by accident.

### How to get it

1. Log in to https://support.oracle.com with your Oracle Support credentials.
2. Open MOS Note 1317265.1, or search for "Database Options/Management Packs Usage Detection".
3. Download the attached `options_packs_usage_statistics.sql`.
4. Save it in this folder. Oracle updates the script as new options and packs are added, so
   download it again before every formal review.

### How to use it

```sql
-- Connect as a user with SELECT ANY DICTIONARY (or as SYSDBA).
-- For a CDB, connect to CDB$ROOT so all open PDBs are reported.
-- Run it against every database in scope.

-- Optional: force a fresh usage sample first (usage data is otherwise refreshed about weekly)
EXEC DBMS_FEATURE_USAGE_INTERNAL.exec_db_usage_sampling(SYSDATE);

@options_packs_usage_statistics.sql
-- Output is spooled to options_packs_usage_statistics.txt in the current directory
```

### Disclaimer

> The script's output is **technical data only**. It is not a licensing compliance
> determination. Your organization's Oracle contract governs your licensing obligations.
> Ask your Oracle licensing team or Oracle account team for any compliance assessment.
