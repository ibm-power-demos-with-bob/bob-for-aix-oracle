# Oracle Licensing on IBM Power Systems

> **Read this file for:** hard partitioning (capped LPARs, shared processor
> pools), `lparstat -i` and HMC evidence, LPM and how to disable it, PowerVS,
> the 10-day failover rule, Enterprise Pools 2.0, SE2 eligibility,
> options/packs usage detection, audit evidence, and profile-mismatch risks.
> **Sources:** IBM Power Systems VUG May 2024 (Ralf Schmidt-Dannert, IBM ATG), the
> Oracle policy documents linked below, and one third-party analysis (§10, marked
> as such).

Technical information about Oracle deployments on IBM Power Systems, to feed a
licensing review.

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
| Capped shared LPAR | ✅ Yes |
| Shared processor pool (SPP) with a maximum capacity | ✅ Yes (the pool maximum is the boundary) |
| Dedicated-processor LPAR | ✅ Yes |
| Dedicated-donating LPAR | Confirm with your Oracle licensing contact |
| Uncapped LPAR in the default pool (no pool limit) | ❌ No: may license every core in the server |
| Live Partition Mobility (LPM) | ❌ Moves Oracle onto other servers' cores |

**Capped LPAR**: the hypervisor never lets the LPAR use more than its entitled
capacity.

> **How a capped shared LPAR is counted** (rounded-up entitled capacity, or online
> virtual processors) is a matter of interpretation and of your contract. Record
> both values and let the licensing team decide. The conservative assumption is
> the larger of the rounded-up EC and the online VPs.

**Shared processor pool**: a pool of physical cores shared by several LPARs. When
the pool has a maximum capacity, that maximum caps what all its LPARs together can
use.

```bash
lparstat -i

# Fields the licensing review needs:
# - "Type"                         Shared-SMT-8 (shared) or Dedicated
# - "Mode"                         Capped / Uncapped (Donating for dedicated-donating)
# - "Entitled Capacity"            the LPAR's current entitlement (processing units)
# - "Online Virtual CPUs"          current virtual processors
# - "Maximum Virtual CPUs"         profile maximum for virtual processors
# - "Maximum Capacity"             the LPAR's MAXIMUM entitled capacity (profile max), not the pool
# - "Shared Pool ID"               0 = default pool (no limit beyond the server's shared cores)
# - "Maximum Capacity of Pool"     the pool's maximum capacity (the SPP licensing boundary)
# - "Active CPUs in Pool"          physical cores currently in the shared pool
```

> Run `lparstat -i` **in every LPAR that runs Oracle software** on the server. Provide this output to Oracle's licensing team.

---

## 2. Shared Processor Pool (SPP) Licensing

When multiple Oracle LPARs share an SPP with a defined maximum capacity:

```
Oracle processor licenses ≈ SPP maximum capacity (in physical cores)
                            × Oracle core factor for the processor
(provided the pool's capacity is below the sum of the LPARs' possible consumption)
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
# Check the SPP configuration from inside the LPAR
lparstat -i | grep -E "^Mode|^Shared Pool ID|^Maximum Capacity of Pool|^Active CPUs in Pool"

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
# On the HMC: disable LPM for one LPAR (a partition-level attribute; -r lpar uses name=)
chsyscfg -r lpar -m <frame_name> -i "name=<lpar_name>,migration_disabled=1"

# Verify
lssyscfg -r lpar -m <frame_name> -F name,migration_disabled
# Expected: <lpar_name>,1

# Check that no migration is in progress
lslparmigr -r lpar -m <frame_name>
```

> This stops the HMC from starting an LPM operation for the LPAR. It doesn't
> affect normal operation, PowerHA failover, or DLPAR changes. Check the attribute
> name and support at your HMC level in the IBM document linked above
> (`lssyscfg -r lpar -F` shows the attributes available).

### IBM Power Virtual Server (PowerVS) and LPM

PowerVS uses LPM internally for server maintenance (evacuating LPARs before maintenance). **This must be disabled for Oracle LPARs**:

```bash
# PowerVS: Oracle LPARs must use the "hard" pin policy, which prevents LPM.
# Set the pin policy when creating the instance (or change it in the console or CLI).
# Check it with the IBM Cloud CLI. lparstat inside the LPAR does not show it:
ibmcloud pi instance get <instance-id>      # look for the pin policy field: hard
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

## 5. Failover Clusters: the 10-Day Rule

According to Oracle's Data Recovery licensing document (linked above):

- **Failover environments** are clusters with shared storage where only one node
  runs the database at a time, such as PowerHA active/passive. Here the unlicensed
  spare node may run the database for **up to 10 separate days per calendar year**.
- The rule covers **failover only**. It does **not** cover:
  - Data Guard standby databases
  - remote mirroring or replicated copies
  - any configuration where the second copy runs or is kept up to date
  
  Those must be fully licensed.
- Whether the Oracle software may be installed on the spare node, and how
  "days" are counted, is defined in the document and your contract. Have the
  licensing team confirm the configuration.

### PowerHA active/passive design

```
[Active node]  runs the database. Licensed.
[Spare node]   takes over only on failover. The database files are on shared storage,
               accessible from one node at a time.
```

This applies to PowerHA with JFS2 (shared VGs) or with ASM (shared raw hdisks),
both on-premises and in PowerVS.

---

## 6. Documenting Your Configuration

Oracle's licensing team uses `lparstat -i` output to validate license requirements. **Best practice**: run and save this output quarterly or after any LPAR configuration change.

```bash
# Run in EVERY LPAR that has Oracle software installed
lparstat -i > /tmp/lparstat-$(hostname)-$(date +%Y%m%d).txt

# Key fields to capture and review:
# - Node Name, Partition Name, Partition Number
# - Type (Shared / Dedicated), Mode (Capped / Uncapped / Donating)
# - Entitled Capacity, Maximum Capacity (the LPAR's maximum entitlement)
# - Online / Maximum Virtual CPUs
# - Online / Maximum Memory
# - Shared Pool ID, Maximum Capacity of Pool, Active CPUs in Pool
```

### What the licensing review looks at

1. **`Mode: Capped`** confirms the LPAR is capped.
2. **`Entitled Capacity`** and **`Online Virtual CPUs`** are the inputs for
   counting a capped LPAR (§1).
3. **`Maximum Capacity of Pool`**: with a non-default pool, the pool maximum is
   the SPP boundary.
4. **`Maximum Capacity`** (LPAR maximum) and **`Maximum Virtual CPUs`** show what
   the LPAR could reach through DLPAR. Keep them close to the current values
   (§10.2).

---

## 7. Common Licensing Pitfalls

| Pitfall | Risk | Mitigation |
|---|---|---|
| Uncapped LPAR with no SPP limit | Entire server licensed | Always use CAPPED or SPP |
| LPM used on Oracle LPAR | Destination server becomes licensed | Hard-pin Oracle LPARs |
| SPP max_pool_capacity set higher than needed | Higher license cost | Size SPP to actual peak need |
| Over-allocated `max_virtual_procs` | Hypervisor may spread LPAR across more physical nodes; also can raise licensing questions | Set realistic max vCPU |
| Assuming a fractional core factor for Power | Wrong licence calculation | POWER6 to POWER10 have factor 1.0 in Oracle's table. Confirm Power11 in writing |
| Treating a Data Guard standby as covered by the 10-day rule | Unlicensed standby | The 10-day rule covers failover clusters only. License Data Guard standbys (§5) |
| Spare failover node used more than 10 days a year | Full licence needed | Track failover days. Fail back promptly |
| PEP 2.0 pools without SPP limits on Oracle LPARs | Potentially licenses the entire pool | Always use CAPPED LPARs + SPP in PEP 2.0 |

---

## 8. Oracle SE2 Licensing on Power

### The SE2 rules

- SE2 may only be licensed on servers with a **maximum capacity of 2 sockets**,
  and Oracle defines what a "socket" is.
- **On Power10 and Power11**, a dual-chip module can count as more than one
  socket. Eligibility therefore comes down to **specific server models**, not
  generations.
- An SE2 database instance is limited to **16 CPU threads** at any time. At SMT8
  that is only **2 cores' worth** of threads, so size the LPAR and SMT mode with
  this in mind.
- **RAC is not available with SE2 from 19c onwards.** Use a failover solution
  (PowerHA, or Oracle's SE2 high-availability option) instead.

### Models (confirm against Oracle's current SE2 statements before buying)

| Generation | Treated as eligible in the source | Not eligible |
|---|---|---|
| Power9 | 1–2 socket scale-out (S9xx) | E950, E980 |
| Power10 | S1012, S1014 | S1022, S1022s, S1024, E1050, E1080 |
| Power11 | Confirm with Oracle in writing (the source names S1112; check that this model exists and qualifies) | S1122, S1124, E1150, E1180 |

> **Common pitfall:** a hardware refresh from an eligible entry model (such as the
> S1014) to a larger scale-out or enterprise server **ends SE2 eligibility**.

```bash
prtconf | grep "System Model"     # server model (inside the LPAR)
uname -M
```

---

## 9. Oracle Options and Management Packs — Usage Detection

Some Oracle Database options and management packs are **licensed separately**,
and they can be used without the DBA noticing. For example, AWR snapshots are
collected by default, and querying AWR or running AWR/ADDM reports is Diagnostics
Pack usage. `CONTROL_MANAGEMENT_PACK_ACCESS` controls pack access, and its default
is `DIAGNOSTIC+TUNING`. Using an option without a license is a compliance risk.

**Oracle MOS 1317265.1** — *"Database Options/Management Packs Usage Detection"* — provides a SQL script (`options_packs_usage_statistics.sql`) that queries `DBA_FEATURE_USAGE_STATISTICS` to report which options have been used and when.

> ⚠ **Disclaimer**: The output of this script is **technical data only**. What constitutes a licensing obligation is determined by your Oracle contract and must be assessed by your Oracle licensing team.

> **Getting the script:** the script is Oracle Support content, so it is **not
> redistributed** in this repository. Download the current version from MOS
> 1317265.1 and save it in the `scripts/` folder next to this file as
> `options_packs_usage_statistics.sql` (that file name is git-ignored). The steps are in [`scripts/README.md`](scripts/README.md).
> If the file is missing, use the quick queries below and tell the user where to
> get the full script.

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
| **Diagnostics Pack** | Querying `DBA_HIST_*`, AWR/ADDM/ASH reports, or EM performance pages, while `CONTROL_MANAGEMENT_PACK_ACCESS` allows it (the default) |
| **Tuning Pack** | SQL Tuning Advisor, SQL Access Advisor, SQL profiles, often started by EM or automated jobs |
| **Advanced Compression** | `ROW STORE COMPRESS ADVANCED` (formerly `COMPRESS FOR OLTP`), SecureFiles compression or deduplication, compressed Data Pump or RMAN with non-BASIC algorithms. BASIC table compression is part of EE |
| **Partitioning** | Any `PARTITION BY` clause, including objects created by tools or applications |
| **Real Application Clusters** | A database opened by more than one instance (`cluster_database=TRUE`). Grid Infrastructure alone (Oracle Restart or Clusterware) does not mean RAC usage |
| **Label Security / Database Vault** | Configured and enabled. `V$OPTION` shows what is installed or enabled, not usage, so use `DBA_FEATURE_USAGE_STATISTICS` |
| **Real Application Testing** | Workload capture/replay, SQL Performance Analyzer |
| **Multitenant** | From 19c, more than **3 user PDBs** in a CDB (EE). Up to 3 are allowed without the option |

```sql
-- Installed / enabled options in the binary (not usage)
SELECT parameter, value FROM v$option ORDER BY parameter;

-- Features with any detected usage
SELECT name, currently_used, detected_usages, last_usage_date, first_usage_date
FROM   dba_feature_usage_statistics
WHERE  detected_usages > 0
ORDER  BY last_usage_date DESC NULLS LAST;

-- Management pack access setting
SHOW PARAMETER control_management_pack_access
-- Without Diagnostics/Tuning Pack licences, the documented control is
-- CONTROL_MANAGEMENT_PACK_ACCESS = 'NONE' (not STATISTICS_LEVEL=BASIC, which disables much more).
-- Decide this with the licensing team. Revert: set it back to the recorded value.
```

---

## 10. IBM Power LPAR Licensing — Partition Configuration Risk Deep Dive

> **Third-party source** (not Oracle or IBM): Redress Compliance, "Oracle IBM LPAR
> Licensing", August 2025 (updated September 2026).
> https://redresscompliance.com/oracle-ibm-lpar-licensing
> Treat these examples as illustrations, not as Oracle policy.

This section covers the most consequential configuration risks seen in Oracle audits on IBM Power Systems, including real cost worked examples, the DLPAR profile mismatch trap, and LPM frame widening.

### 10.1 Cost Reality: Capped vs. Uncapped on a Real Frame

A common misconception is that Oracle licensing is determined by how much CPU the LPAR *actually uses*. It is not — it is determined by how much CPU the LPAR *can use*, as enforced by the hypervisor.

**Worked example — 64-core Power10 server:**

| Scenario | Licensed cores | Oracle EE list price estimate | Exposure |
|---|---|---|---|
| Uncapped LPAR, default pool | 64 physical cores | ~$3.04M | Maximum |
| Capped LPAR, EC 4.0 with 8 virtual processors | 4 (counted by EC) or 8 (counted by VPs), depending on interpretation (§1) | ~$190K–$380K | Moderate |
| Capped LPAR, EC 4.0 with 4 virtual processors | 4 | ~$190K | Minimum |
| **Difference (uncapped vs 4-core capped)** | 60 cores | **~$2.85M** | |

> Assumptions: Oracle EE list price ~$47,500 per processor, core factor 1.0 for
> Power10, no discounts. For illustration only.

**The single most effective action** is to **make Oracle LPARs capped**, with the
entitled capacity and virtual processors sized to the real peak. That also
removes the EC vs VP ambiguity.

```bash
lparstat -i | grep -E "^Mode|^Entitled Capacity|^Online Virtual CPUs|^Maximum Capacity|^Shared Pool ID"
# Example of a tightly capped LPAR:
# Mode                     : Capped
# Entitled Capacity        : 4.00
# Online Virtual CPUs      : 4
# Maximum Capacity         : 4.00     <- the LPAR's maximum entitlement (DLPAR headroom), not a pool value
# Shared Pool ID           : 0        <- default pool. For an SPP boundary, use a dedicated pool with a
#                                        "Maximum Capacity of Pool" sized to the licences
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

# Shared processor pools (all attributes, including the pool maximum):
lshwres -r procpool -m <frame_name>

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

The recommended technical control is to disable LPM on Oracle LPARs. The HMC
commands are in §3.

---

### 10.5 Audit Evidence Checklist

When preparing for an Oracle audit on IBM Power Systems, collect and retain:

| Evidence | Command | Where to run |
|---|---|---|
| LPAR configuration (live) | `lparstat -i` | Inside each Oracle LPAR |
| LPAR processor mode (HMC live) | `lshwres -r proc -m <frame> --level lpar` | HMC |
| Saved partition profile | `lssyscfg -r prof -m <frame>` | HMC |
| SPP configuration | `lshwres -r procpool -m <frame>` | HMC |
| LPM disabled flag | `lssyscfg -r lpar -m <frame> -F name,migration_disabled` | HMC |
| Installed/activated cores | `lscod -t cap -c cuod -r proc -m <frame>` | HMC |
| CoD activation history | `lscod -t hist -m <frame>` | HMC |
| Server model | `prtconf \| grep "System Model"` | Inside LPAR |
| Oracle options usage | `options_packs_usage_statistics.sql` (from MOS 1317265.1) | SQL*Plus as SYSDBA |
| Oracle software inventory | `$ORACLE_HOME/OPatch/opatch lsinventory` | Inside LPAR as oracle |
| Active Oracle processes | `ps -ef \| grep ora_` | Inside LPAR |
| LPM migration state | `lslparmigr -r lpar -m <frame>` | HMC |

> Run `lparstat -i` and save its output **before and after** any LPAR reconfiguration. Keep a dated history.

---

### 10.6 Summary: Hard Partitioning Compliance Checklist

```
[ ] LPAR Mode = Capped  (lparstat -i, lshwres live)
[ ] Saved profile also = Capped / cap sharing mode  (lssyscfg)
[ ] Online virtual CPUs close to entitled capacity (removes the EC vs VP ambiguity)
[ ] Dedicated SPP with maximum capacity sized to the licences, if pool licensing is used  (lshwres procpool)
[ ] Profile max_proc_units / max_procs close to desired values  (lssyscfg)
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
