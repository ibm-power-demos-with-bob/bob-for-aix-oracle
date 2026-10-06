# Oracle Licensing Scripts

Scripts in this folder support Oracle licensing reviews on IBM Power Systems / AIX.

---

## options_packs_usage_statistics.sql

**Purpose**: Detects which Oracle Database options and management packs have been used in a database instance.
Queries `DBA_FEATURE_USAGE_STATISTICS`, `CDB_FEATURE_USAGE_STATISTICS` (for CDBs), `V$INSTANCE`, `V$DATABASE`, and `V$VERSION`.

**Source**: Oracle My Oracle Support (MOS) Note **1317265.1**
Title: *"Database Options/Management Packs Usage Detection"*
URL: https://support.oracle.com/support/?anchorId=&kmContentId=1317265&page=sptemplate&sptemplate=km-article
*(Requires Oracle Support login)*


**Version note**: This copy is the original script from MOS 1317265.1, last updated Oct-2021 per its header (covers Oracle 11.2 through 21c and later).
Oracle periodically updates the script as new options and management packs are added.
**Always check MOS 1317265.1 for the latest version before using in a formal audit.**

### How to use

```sql
-- Connect as SYSDBA (or a user with SELECT on DBA_FEATURE_USAGE_STATISTICS)
-- Run against each database instance to be reviewed

-- Optional: force a fresh usage sample before running
EXEC DBMS_FEATURE_USAGE_INTERNAL.exec_db_usage_sampling(SYSDATE);

-- Run the script
@options_packs_usage_statistics.sql
```

### Disclaimer

> The output of this script is **technical data only**.
> It does not constitute a licensing compliance determination.
> Oracle licensing obligations are governed by the contract signed between Oracle and your organization.
> Engage your Oracle License Management Services (LMS) contact or Oracle account team for any compliance assessment.

---

## How to obtain the script from MOS

1. Log in to https://support.oracle.com with your Oracle Support credentials.
2. Navigate to MOS Note 1317265.1 or search for "Database Options/Management Packs Usage Detection".
3. Download the attached `options_packs_usage_statistics.sql` file.
4. Replace the copy in this folder with the downloaded version.
5. Update the version note in this README with the download date.
