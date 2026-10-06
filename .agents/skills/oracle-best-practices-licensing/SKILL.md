---
name: oracle-best-practices-licensing
description: >-
  Use when discussing or auditing Oracle Database licensing on IBM Power Systems / AIX. Covers
  hard partitioning with CAPPED LPARs and Shared Processor Pools, lparstat -i documentation,
  Oracle licensing in IBM Power Virtual Server (PowerVS), the 10-day standby rule, Enterprise
  Pools 2.0 (PEP 2.0), common licensing pitfalls with LPM, LPM disable from HMC, LPM contractual
  negotiation, SE2 eligibility, Oracle Options/Management Packs usage detection, audit evidence
  collection, DLPAR profile mismatch risk, and LPM frame widening. Trigger phrases:
  "Oracle licensing Power", "hard partition AIX Oracle", "Oracle license audit Power",
  "capped lpar Oracle license", "shared processor pool Oracle license", "lparstat -i Oracle",
  "Oracle license PowerVS", "Oracle SE2 Power", "Oracle SE2 S1014", "Oracle SE2 S1112",
  "power virtual server Oracle license", "10-day Oracle standby rule", "LPM Oracle licensing",
  "LPM disable Oracle LPAR", "disable LPM Oracle HMC", "migration_disabled Oracle",
  "LPM contract Oracle", "LPM exemption Oracle", "Oracle LPM written agreement",
  "chsyscfg migration_disabled", "LPM frame widening Oracle",
  "enterprise pools Oracle license", "Oracle core factor Power", "Oracle processor factor IBM",
  "Oracle options packs usage", "options_packs_usage_statistics", "MOS 1317265",
  "Oracle audit detection", "Oracle management packs licensed", "dba_feature_usage_statistics",
  "Oracle partitioning policy", "Oracle data recovery licensing", "Oracle audit IBM Power",
  "lshwres oracle", "lssyscfg oracle profile", "Oracle DLPAR max proc", "saved profile mismatch",
  "Oracle Power11 core factor", "uncapped lpar Oracle cost".
---

# Oracle Licensing on IBM Power Systems

Technical insights for Oracle Database deployments on IBM Power Systems, to support licensing reviews.
Source: IBM Power Systems VUG May 2024 sessions by Ralf Schmidt-Dannert, IBM ATG Principal Power Specialist.

---

## ⚠ Important Disclaimer — Read Before Using This Skill

> **This skill does NOT provide Oracle licensing compliance advice and does NOT constitute a definitive answer on Oracle licensing obligations.**
>
> - **Governing document**: The terms and conditions that apply are those defined and signed in the **contract between Oracle and your organization**. That contract is the authoritative reference for all licensing questions.
> - **Purpose of this skill**: To provide **technical insights** about your current Oracle deployment on IBM Power Systems (LPAR configuration, partition mode, entitlement, options usage). These technical details can be used as **input data** for an Oracle licensing review conducted by your legal and Oracle licensing teams.
> - **Always engage**: Your Oracle License Management Services (LMS) contact, your Oracle account team, or a qualified Oracle licensing specialist for any compliance determination.
>
> **Oracle policy reference documents** (educational purpose):
> - Partitioning Policy: https://www.oracle.com/a/ocom/docs/it-infrastructure/partitioning-070609.pdf
> - Data Recovery (DR/Standby) Licensing: https://www.oracle.com/a/ocom/docs/data-recovery-licensing-070587.pdf
> - Oracle Processor Core Factor Table: https://www.oracle.com/contracts/docs/processor-core-factor-table-070634.pdf
> - MOS 1317265.1 — Database Options/Management Packs Usage Detection: https://support.oracle.com/support/?anchorId=&kmContentId=1317265&page=sptemplate&sptemplate=km-article *(requires Oracle Support login)*

---

## 1. Core Concept: Hard Partitioning

Oracle recognizes **hard partitioning** as the mechanism to limit license requirements to a subset of physical cores in a server. On IBM Power Systems, two technologies qualify:

| Technology | Qualifies for Hard Partitioning? |
|---|---|
| CAPPED LPAR | ✅ Yes |
| Shared Processor Pool (SPP) with capacity limit | ✅ Yes |
| Uncapped LPAR (no pool limit) | ❌ No — licenses the entire physical server |
| Dedicated LPAR (donating) | ✅ Yes |
| Live Partition Mobility (LPM) | ❌ Moves Oracle to unlicensed physical CPUs |

**Capped LPAR**: The LPAR's entitlement is the maximum it can consume. The hypervisor enforces this cap. Oracle licenses the **physical core equivalent** of the cap (applying Oracle's core factor table for Power processors).

**Shared Processor Pool**: A pool of physical cores shared by multiple LPARs. If the pool has a capacity limit, Oracle licenses are based on that limit, not the total server capacity.

```bash
# Document LPAR configuration for Oracle licensing audit
lparstat -i

# Key fields Oracle licensing team reviews:
# - "Type"                       → Shared-SMT-8 (shared) or Dedicated
# - "Mode"                       → Capped or Uncapped
# - "Entitled Capacity"          → CPU entitlement (licenses based on this if capped)
# - "Maximum Virtual CPUs"       → Max vCPU count
# - "Shared Pool ID"             → Which SPP this LPAR belongs to
# - "Maximum Capacity"           → For the SPP (pool max capacity)
# - "Pool Capacity"              → Current pool size
```

> Run `lparstat -i` **in every LPAR that runs Oracle software** on the server. Provide this output to Oracle's licensing team.

---

## 2. Shared Processor Pool (SPP) Licensing

When multiple Oracle LPARs share an SPP with a defined maximum capacity:

```
Oracle licenses required = SPP max_pool_capacity (in physical cores)
                           × Oracle Core Factor for Power
```

Oracle's core factor for IBM Power processors (January 2026 table):

| Generation | Oracle Core Factor | Status |
|---|---|---|
| Power6, Power6+ | 1.0 | Listed |
| Power7, Power7+ | 1.0 | Listed |
| Power8 | 1.0 | Listed |
| Power9 | 1.0 | Listed |
| Power10 | 1.0 | Listed |
| Power11 | ⚠ Not listed | **Confirm with Oracle in writing before sizing** |

> IBM POWER6 through POWER10 processors all carry a core factor of **1.0** per Oracle's published January 2026 table.
> **Power11 is NOT listed** in the January 2026 Oracle Processor Core Factor Table. Before finalizing any Power11 Oracle deployment, obtain confirmation of the applicable core factor directly from Oracle in writing.
> Source: https://www.oracle.com/contracts/docs/processor-core-factor-table-070634.pdf
> Always verify against the current published table before finalising a license agreement — Oracle updates this document periodically.

```bash
# Check SPP configuration
lparstat -i | grep -E "Shared Pool|Pool Capacity|Mode|Capped"

# All LPARs running Oracle in the same SPP must be accounted for
# The SPP maximum is the license boundary — not the sum of individual LPAR entitlements
```

### Enterprise Pools 2.0 (PEP 2.0 / Power Private Cloud)
- Allows sharing of CPU and memory **across physical servers** in a pool, even across data centers.
- **Licensing clarification**: PEP 2.0 is **not** a method to reduce Oracle licensing. Standard Oracle hard partitioning rules still apply.
- LPARs in PEP 2.0 must still be CAPPED or in an SPP with a defined capacity limit.
- Dynamic capacity borrowed from the pool is metered by the minute (OpEx model).

---

## 3. Key Pitfall: Live Partition Mobility (LPM)

**LPM moves an LPAR from one physical server to another without downtime.**

### Oracle Licensing Rule for LPM

Oracle's position is that when an Oracle LPAR is migrated via LPM — even temporarily, even for maintenance — Oracle must be licensed on **both the source server and the destination server**: all physical cores on both frames (or their SPP capacity limits) become licensable for the duration of the migration. This applies regardless of whether the migration was planned or triggered by an automated maintenance event.

> **Technical validation from this skill covers how to disable LPM. Whether your contract permits LPM use without licensing both frames is a legal question — see the negotiation note below.**

### Contractual Negotiation Option

Some organizations negotiate a **written addendum to their Oracle contract** that explicitly permits LPM use without requiring both source and destination servers to be licensed simultaneously. Key requirements for such an agreement:

- Must be **in writing** and **incorporated into the Oracle contract** (not a verbal or email commitment from an account rep).
- Typically specifies the mobility group (which servers are in scope), the maximum migration frequency, and the logging/audit obligations.
- Must be obtained **before** LPM is used on Oracle LPARs — retroactive agreements are not guaranteed.
- Engage Oracle License Management Services (LMS) or your Oracle account team to initiate this.

> ⚠ Without a written contractual exemption, treat any LPM usage on Oracle LPARs as requiring both source and destination frames to be licensed.

### Technical Recommendation: Disable LPM on Oracle LPARs from the HMC

The safest technical control — absent a contractual LPM exemption — is to **disable LPM at the LPAR level** in the HMC partition profile. This setting is applied via the HMC GUI or CLI and is valid for **Power9, Power10, and Power11** systems.

IBM documentation: https://www.ibm.com/docs/en/power10/0000-REF?topic=POWER10_REF/p10jak/p10jak_lpar_general_lpmdisable.html

```bash
# On the HMC — disable LPM for a specific LPAR (CLI method)
# Set migration_disabled=1 in the partition profile

chsyscfg -r lpar \
  -m <frame_name> \
  -i "lpar_name=<lpar_name>,migration_disabled=1"

# Verify the change
lssyscfg -r lpar -m <frame_name> -F lpar_name,migration_disabled
# Expected output: <lpar_name>,1

# Also verify the saved profile reflects the setting
lssyscfg -r prof -m <frame_name> \
  -F lpar_name,migration_disabled
```

> This setting prevents the HMC from initiating a Live Partition Mobility operation for this LPAR. It does not affect normal LPAR operations, PowerHA failover, or DLPAR resource changes.

### IBM Power Virtual Server (PowerVS) and LPM

PowerVS uses LPM internally for server maintenance (evacuating LPARs before maintenance). **This must be disabled for Oracle LPARs**:

```bash
# Oracle LPARs in PowerVS MUST be hard-pinned
# Hard pinning prevents LPM
# Contact your PowerVS admin or IBM to configure hard pinning on the LPAR

# Verify hard-pinning status
lparstat -i | grep "Memory Mode"   # Also check pin status via HMC
```

> **Consequence**: Disabling LPM on Oracle LPARs means the PowerVS SLA (which assumes LPM capability for availability) does not apply. You must implement alternative HA:
> - PowerHA SystemMirror
> - Oracle Data Guard
> - Oracle RAC

---

## 4. Oracle Licensing in IBM Power Virtual Server (PowerVS)

PowerVS is IBM's cloud offering where IBM manages the physical infrastructure and you own the OS.

| Aspect | Detail |
|---|---|
| Infrastructure | Same hardware/software as on-premises Power |
| Storage | Fiber Channel SAN, VIO servers — same as on-prem |
| Supports | Oracle RAC and non-RAC |
| Hard partitioning | **Required** — CAPPED LPARs with hard pinning |
| LPM | **Disabled** for Oracle LPARs |
| SLA | PowerVS standard SLA does not apply when LPM is disabled — implement your own HA |
| Licensing rules | Same as on-premises — no special cloud exemptions |

### PowerHA Resource Optimization in PowerVS
PowerHA can dynamically grow/shrink CPU and memory for Oracle LPARs:
- **Standby node**: runs at minimal resources (saves cost).
- **Active node**: at full resource allocation.
- **On failover**: PowerHA uses PowerVS CLI/API to grow standby to full allocation.

```bash
# PowerHA controls LPAR resources via IBM Power Virtual Server CLI
# Active node: full CPU entitlement and memory
# Standby node: minimum CPU/memory until failover triggered
```

---

## 5. Oracle Standby — The 10-Day Calendar Rule

For Oracle licensing on standby/DR servers:
- Oracle allows a standby server to be unlicensed if the **Oracle software is not installed or accessible**.
- The standby server can run the Oracle workload for **up to 10 calendar days per year** without requiring a permanent license.

### PowerHA Active-Passive Architecture for License Optimization

```
[Active Node] — Oracle installed, licensed, running
[Standby Node] — Oracle software NOT installed; shared storage only
```

- Shared storage contains database files accessible by only one node at a time.
- The standby node has no Oracle software → no license required.
- Failover ≤ 10 days/year → no license required on standby.

This applies to:
- PowerHA with JFS2 file systems (shared LVs)
- PowerHA with ASM (shared raw LVs)
- Both on-premises and PowerVS deployments

---

## 6. Documenting Your Configuration

Oracle's licensing team uses `lparstat -i` output to validate license requirements. **Best practice**: run and save this output quarterly or after any LPAR configuration change.

```bash
# Run in EVERY LPAR that has Oracle software installed
lparstat -i > /tmp/lparstat-$(hostname)-$(date +%Y%m%d).txt

# Key fields to capture and review:
# - Node Name, Partition Name, Partition Number
# - Type (Shared vs. Dedicated)
# - Mode (Capped vs. Uncapped)
# - Entitled Capacity
# - Maximum Virtual CPUs
# - Minimum/Maximum Memory
# - Online Memory
# - Shared Pool ID
# - Maximum Capacity (pool)
# - Pool Capacity (pool current physical cores)
# - Hypervisor
# - Firmware version
```

### What Oracle Licensing Reviews
1. **`Mode: Capped`** — confirms hard partitioning is active.
2. **`Entitled Capacity`** — the licensed CPU allocation.
3. **`Pool Capacity` / `Maximum Capacity`** — if using SPP licensing, the pool cap = license boundary.
4. **`Maximum Virtual CPUs`** — should be reasonable relative to entitlement (no over-allocation that implies SPP bypass).

---

## 7. Common Licensing Pitfalls

| Pitfall | Risk | Mitigation |
|---|---|---|
| Uncapped LPAR with no SPP limit | Entire server licensed | Always use CAPPED or SPP |
| LPM used on Oracle LPAR | Destination server becomes licensed | Hard-pin Oracle LPARs |
| SPP max_pool_capacity set higher than needed | Higher license cost | Size SPP to actual peak need |
| Over-allocated `max_virtual_procs` | Hypervisor may spread LPAR across more physical nodes; also can raise licensing questions | Set realistic max vCPU |
| Assuming a fractional core factor for Power | Incorrect license calculation | All IBM POWER processors use factor 1.0 per Oracle's published table — licenses = physical cores × 1.0 |
| Standby with Oracle software installed | Must be licensed if operational > 10 days/year | Remove Oracle software from standby; use PowerHA shared storage |
| PEP 2.0 pools without SPP limits on Oracle LPARs | Potentially licenses the entire pool | Always use CAPPED LPARs + SPP in PEP 2.0 |

---

## 8. Oracle SE2 Licensing on Power

Oracle Standard Edition 2 (SE2) eligibility is **server-model specific**, not generation-wide. Only designated entry-level scale-out models qualify. Mid-range (S1022, S1024, S1042) and high-end enterprise (Exxxx) servers do **not** qualify for SE2 regardless of core count or configuration.

### Eligible Models

| Generation | Eligible Models | Not Eligible |
|---|---|---|
| Power9 | S9xx scale-out servers | E950, E980 and all Exxxx enterprise |
| Power10 | S1012, S1014 | S1022, S1022S, S1024, E1050, E1080 |
| Power11 | S1112 | S1024, S1042, E1150, E1180 and all other models |

### SE2 Licensing Constraints (all generations)

- Maximum **16 physical cores** per server.
- Maximum **2 sockets** per server.
- Up to **3 RAC instances**.
- The physical server model must appear on Oracle's SE2 eligible hardware list — verify with Oracle before purchase.

> **Common pitfall**: Upgrading from an SE2-eligible model (e.g., S1014) to a larger scale-out server (e.g., S1024 or S1042) or any enterprise server (Exxxx) **disqualifies the deployment from SE2**. Plan hardware refreshes with this constraint in mind.

```bash
# Verify server model — must be an SE2-eligible model
lparstat -i | grep "Server Name"
prtconf | grep "System Model"
```

---

## 9. Oracle Options and Management Packs — Usage Detection

Certain Oracle Database options and management packs are **separately licensed** and may be activated without the DBA's explicit knowledge (e.g., the Diagnostics Pack starts automatically when `STATISTICS_LEVEL=TYPICAL` or higher). Using an option without a license is a compliance risk.

**Oracle MOS 1317265.1** — *"Database Options/Management Packs Usage Detection"* — provides a SQL script (`options_packs_usage_statistics.sql`) that queries `DBA_FEATURE_USAGE_STATISTICS` to report which options have been used and when.

> ⚠ **Disclaimer**: The output of this script is **technical data only**. What constitutes a licensing obligation is determined by your Oracle contract and must be assessed by your Oracle licensing team.

> **Script location**: The original script from MOS 1317265.1 is in this repository at:
> `.agents/skills/oracle-best-practices-licensing/scripts/options_packs_usage_statistics.sql`
> Script version in this repo: **Oct-2021** (covers Oracle 11.2 through 21c+).
> **Always check MOS 1317265.1 for the latest version** — Oracle updates the script as new options are added.

### Key Tables Queried

| View | Purpose |
|---|---|
| `DBA_FEATURE_USAGE_STATISTICS` | Tracks usage count, last usage date, and currently_used flag per feature (non-CDB) |
| `CDB_FEATURE_USAGE_STATISTICS` | Same, used automatically when connected to `CDB$ROOT` |
| `V$INSTANCE` / `V$DATABASE` / `V$VERSION` | DB name, version, host, role, open mode |
| `GV$PARAMETER` | Checks `control_management_pack_access` and `enable_ddl_logging` settings |
| `V$CONTAINERS` | Lists all PDBs (for Multitenant option detection) |

### How to Run

```sql
-- Connect as SYSDBA or a DBA with SELECT on DBA_FEATURE_USAGE_STATISTICS
-- Run in each database instance you want to audit

-- Step 1 (optional): refresh usage sampling before running the report
EXEC DBMS_FEATURE_USAGE_INTERNAL.exec_db_usage_sampling(SYSDATE);

-- Step 2: run the script
@options_packs_usage_statistics.sql
```

### Interpreting Results

The script reports for each option/pack:

| Column | Meaning |
|---|---|
| `CURRENTLY_USED` | `TRUE` = option was in use during the most recent sampling window |
| `DETECTED_USAGES` | Cumulative count of sampling intervals where usage was detected |
| `LAST_USAGE_DATE` | Most recent date the feature was observed as active |
| `FIRST_USAGE_DATE` | When the feature was first used in this database |

> **Important**: Even if `CURRENTLY_USED = FALSE`, Oracle may still require a license if `DETECTED_USAGES > 0` and the feature was used while the database was in production. This determination must be made by your Oracle licensing team based on your contract.

### Commonly Flagged Options on Power Systems Deployments

| Option / Pack | How it gets activated unintentionally |
|---|---|
| **Diagnostics Pack** | `STATISTICS_LEVEL = TYPICAL` (the default) enables AWR; AWR is a Diagnostics Pack feature |
| **Tuning Pack** | SQL Tuning Advisor, SQL Access Advisor — often called by EM or automated jobs |
| **Advanced Compression** | `ALTER TABLE ... COMPRESS FOR OLTP` or any compression clause |
| **Partitioning** | Any `PARTITION BY` clause in DDL |
| **Oracle RAC** | Cluster services installed even on single-instance |
| **Label Security / Database Vault** | Installed but never configured — check `V$OPTION` |
| **Real Application Testing** | STS capture or DB Replay sessions |
| **Multitenant** | Using PDB/CDB architecture (licensed per Oracle version/edition) |

```sql
-- Quick check: which options are currently installed in the Oracle binary
SELECT parameter, value FROM v$option ORDER BY parameter;

-- Quick check: features with any detected usage
SELECT name, currently_used, detected_usages, last_usage_date, first_usage_date
FROM   dba_feature_usage_statistics
WHERE  detected_usages > 0
ORDER  BY last_usage_date DESC NULLS LAST;

-- AWR retention check (Diagnostics Pack)
SELECT retention FROM dba_hist_wr_control;
-- If AWR is collecting data and you don't have Diagnostics Pack licensed,
-- set STATISTICS_LEVEL = BASIC to disable AWR collection.
-- WARNING: STATISTICS_LEVEL = BASIC significantly impacts self-monitoring.
-- Engage Oracle licensing to find the right resolution.
```

---

## 10. IBM Power LPAR Licensing — Partition Configuration Risk Deep Dive

> **Source**: Redress Compliance, "Oracle IBM LPAR Licensing", August 2025 (updated September 2026).
> URL: https://redresscompliance.com/oracle-ibm-lpar-licensing

This section covers the most consequential configuration risks seen in Oracle audits on IBM Power Systems, including real cost worked examples, the DLPAR profile mismatch trap, and LPM frame widening.

### 10.1 Cost Reality: Capped vs. Uncapped on a Real Frame

A common misconception is that Oracle licensing is determined by how much CPU the LPAR *actually uses*. It is not — it is determined by how much CPU the LPAR *can use*, as enforced by the hypervisor.

**Worked example — 64-core Power10 server:**

| Scenario | Licensed cores | Oracle EE list price estimate | Exposure |
|---|---|---|---|
| Uncapped LPAR, no SPP limit | 64 physical cores | ~$3.04M | Maximum |
| Capped at 8 virtual processors | 8 physical core equiv. | ~$380K | Moderate |
| Capped at 4 physical cores | 4 physical cores | ~$190K | Minimum |
| **Difference (uncapped vs. 4-core capped)** | 60 cores | **~$2.85M** | — |

> Assumptions: Oracle EE list price ~$47,500/processor, core factor 1.0 for Power10, no volume discounts applied. For illustrative purposes only.

**The single most impactful action** to reduce Oracle license exposure on IBM Power is to **set partition mode to CAPPED** and size `entitled_proc_units` to the actual peak need.

```bash
# Verify capped status — run on every LPAR running Oracle software
lparstat -i | grep -E "^Mode|^Entitled Capacity|^Shared Pool|^Maximum Capacity"
# Expected:
# Mode                               : Capped
# Entitled Capacity                  : 4.00   ← this is the licensed quantity (× core factor)
# Shared Pool ID                     : 0
# Maximum Capacity                   : 4.00   ← pool cap reinforces the limit
```

---

### 10.2 DLPAR Profile Maximum Risk

**The hypervisor does not enforce a hard cap at the profile maximum** — it enforces the current active entitlement. However, Oracle auditors and Oracle License Management Services (LMS) **may argue that the profile maximum represents the reachable entitlement**, especially when:

- The LPAR has been in `Uncapped` mode at any point.
- The profile `max_proc_units` is significantly larger than the typical `desired_proc_units`.
- DLPAR commands have been used to expand CPU entitlement dynamically.

**Mitigation**: Keep the LPAR profile's `max_proc_units` close to the licensed entitlement. Do not leave a large gap between desired and maximum "just in case."

#### HMC Command — Read Partition Profile (live and saved)

```bash
# On the HMC (Hardware Management Console), not inside the LPAR:

# Live (current) resource allocation for all LPARs on a frame:
lshwres -r proc -m <frame_name> --level lpar \
  -F lpar_name,curr_proc_mode,curr_sharing_mode,curr_proc_units,curr_procs

# Saved profile configuration (what activates at next boot / next profile activation):
lssyscfg -r prof -m <frame_name> \
  -F lpar_name,proc_mode,sharing_mode,desired_proc_units,max_proc_units,desired_procs,max_procs

# Shared Processor Pool summary:
lshwres -r procpool -m <frame_name> \
  -F pool_name,max_pool_proc_units,curr_pool_proc_units

# Installed and activated processor counts (useful for CoD/CUoD tracking):
lscod -t cap -c cuod -r proc -m <frame_name>

# Activation history (CoD activations by date):
lscod -t hist -m <frame_name>

# LPM migration state:
lslparmigr -r lpar -m <frame_name>
```

> These commands are run from an HMC session (SSH to HMC or HMC CLI). They complement `lparstat -i` which runs inside the LPAR. Oracle LMS auditors request both.

---

### 10.3 Saved Profile Mismatch — The #2 Most Common Audit Finding

**The trap**: An administrator manually changes an LPAR from `Uncapped` to `Capped` via DLPAR without saving the profile. The LPAR runs correctly (capped) — but the saved profile still says `Uncapped`. On the next **partition activation** (reboot or profile activation), the LPAR returns to `Uncapped`, often unnoticed.

Oracle auditors compare the **saved profile** against the **live configuration**. A mismatch is treated as evidence that the LPAR is not reliably hard-partitioned.

**Detection**:

```bash
# On HMC — compare live vs. saved profile

# Step 1: Live (current) mode
lshwres -r proc -m <frame_name> --level lpar \
  -F lpar_name,curr_sharing_mode,curr_proc_units

# Step 2: Saved profile mode
lssyscfg -r prof -m <frame_name> \
  -F lpar_name,sharing_mode,desired_proc_units,max_proc_units

# If curr_sharing_mode=cap but profile sharing_mode=uncap → MISMATCH
```

**Remediation** — save the current (correct) configuration to the profile:

```bash
# On HMC — force-save the current live configuration as the partition profile
mksyscfg -r prof \
  -m <frame_name> \
  -o save \
  -p <partition_name> \
  -n <profile_name> \
  --force
```

> After saving, re-run `lssyscfg` to confirm the profile now reflects `sharing_mode=cap`.
> **Best practice**: Make this part of your quarterly Oracle licensing audit runbook.

---

### 10.4 LPM Frame Widening Risk

Oracle's licensing rule: LPM requires licenses for all physical cores on **both the source and destination servers** (or their SPP limits) for the duration of the migration. This applies even for maintenance-triggered migrations.

**Consequence**: If you have a mobility group of 3 servers and Oracle LPARs can roam freely:
- All cores across all 3 servers may need to be licensed.
- This applies even if the migration was done for maintenance purposes.
- Undocumented migrations are the highest-risk scenario in an audit — Oracle LMS will treat them as unlicensed use.

**Options**:

| Approach | Description | Risk Level |
|---|---|---|
| Disable LPM on Oracle LPARs (HMC) | Prevents any LPM — no frame widening possible | Lowest |
| Written contractual LPM exemption with Oracle | Negotiate addendum; requires all frames in scope to be documented | Low (if properly documented) |
| License all frames in mobility group | All servers in group remain fully licensed | Zero compliance risk, high cost |
| Undocumented LPM without exemption | Oracle licensing violation | Critical |

#### Disable LPM on Oracle LPARs (Recommended Technical Control)

Valid for **Power9, Power10, and Power11**.
IBM documentation: https://www.ibm.com/docs/en/power10/0000-REF?topic=POWER10_REF/p10jak/p10jak_lpar_general_lpmdisable.html

```bash
# On HMC — disable LPM for an LPAR
chsyscfg -r lpar \
  -m <frame_name> \
  -i "lpar_name=<lpar_name>,migration_disabled=1"

# Verify live LPAR setting
lssyscfg -r lpar -m <frame_name> -F lpar_name,migration_disabled
# Expected: <lpar_name>,1

# Verify saved profile also reflects the setting
lssyscfg -r prof -m <frame_name> \
  -F lpar_name,migration_disabled

# Check current migration state
lslparmigr -r lpar -m <frame_name>
```

> After disabling LPM, save the partition profile (`mksyscfg -r prof ... -o save --force`) so the setting persists across activations.

---

### 10.5 Audit Evidence Checklist

When preparing for an Oracle audit on IBM Power Systems, collect and retain:

| Evidence | Command | Where to run |
|---|---|---|
| LPAR configuration (live) | `lparstat -i` | Inside each Oracle LPAR |
| LPAR processor mode (HMC live) | `lshwres -r proc -m <frame> --level lpar` | HMC |
| Saved partition profile | `lssyscfg -r prof -m <frame>` | HMC |
| SPP configuration | `lshwres -r procpool -m <frame>` | HMC |
| Installed/activated cores | `lscod -t cap -c cuod -r proc -m <frame>` | HMC |
| CoD activation history | `lscod -t hist -m <frame>` | HMC |
| Server model | `prtconf \| grep "System Model"` | Inside LPAR |
| Oracle options usage | `options_packs_usage_statistics.sql` | SQL*Plus as SYSDBA |
| Oracle software inventory | `$ORACLE_HOME/OPatch/opatch lsinventory` | Inside LPAR as oracle |
| Active Oracle processes | `ps -ef \| grep ora_` | Inside LPAR |
| LPM migration state | `lslparmigr -r lpar -m <frame>` | HMC |

> Run `lparstat -i` and save its output **before and after** any LPAR reconfiguration. Keep a dated history.

---

### 10.6 Summary: Hard Partitioning Compliance Checklist

```
[ ] LPAR Mode = Capped  (lparstat -i, lshwres live)
[ ] Saved profile also = Capped / cap sharing mode  (lssyscfg)
[ ] SPP max_pool_proc_units sized to licensed entitlement  (lshwres procpool)
[ ] Profile max_proc_units close to desired_proc_units  (lssyscfg)
[ ] LPM disabled for all Oracle LPARs — or mobility group fully licensed
[ ] lparstat -i output saved quarterly and after every config change
[ ] HMC evidence (lshwres, lssyscfg, lscod) retained for audit readiness
[ ] Oracle options/packs audit run at least annually (options_packs_usage_statistics.sql)
[ ] Server model confirmed against SE2 eligible list (if using SE2)
[ ] Power11 deployments: Oracle core factor confirmed in writing with Oracle
```

---

## Source Reference
IBM Power Systems Virtual User Group, May 2024:
- Session 1: "Oracle on Power Best Practices — Memory and CPU" (Ralf Schmidt-Dannert, IBM ATG)
- Session 2: "Oracle on Power Best Practices — I/O and Miscellaneous" (Ralf Schmidt-Dannert, IBM ATG)
- Decks: `OracleOnPowerTuningConsiderations_CPU_Memory_NEXT.pptx`, `OracleOnPowerTuningConsiderations_AIX_IO_Misc_NEXT.pptx`

Oracle licensing reference documents:
- Oracle Processor Core Factor Table (January 2026): https://www.oracle.com/contracts/docs/processor-core-factor-table-070634.pdf
- Oracle Partitioning Policy: https://www.oracle.com/a/ocom/docs/it-infrastructure/partitioning-070609.pdf
- Oracle Data Recovery Licensing: https://www.oracle.com/a/ocom/docs/data-recovery-licensing-070587.pdf
- MOS 1317265.1 (Options/Packs usage): https://support.oracle.com/support/?anchorId=&kmContentId=1317265&page=sptemplate&sptemplate=km-article
- Redress Compliance — Oracle IBM LPAR Licensing (Aug 2025, updated Sep 2026): https://redresscompliance.com/oracle-ibm-lpar-licensing
