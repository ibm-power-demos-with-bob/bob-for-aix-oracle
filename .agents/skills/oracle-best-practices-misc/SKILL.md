---
name: oracle-best-practices-misc
description: >-
  Use for miscellaneous Oracle Database best practices on IBM Power Systems / AIX that span multiple
  domains: Oracle 19c installation and patching on AIX, mutex spin count tuning, mark_hot for hot
  objects, CPU utilization interpretation under SMT, RAC network configuration on AIX (HAIP,
  IPv6 interface ordering), ASM external redundancy recommendation, pigz/zlibNX hardware compression
  parallelism, PowerVS storage tier selection, and IBM Java embedded in Oracle. Trigger phrases:
  "Oracle 19c install AIX", "Oracle 19c patch AIX", "_spin_count Oracle AIX", "cursor mutex X AIX",
  "mark_hot Oracle", "Oracle CPU percent SMT", "RAC interconnect AIX", "HAIP AIX", "IPv6 RAC AIX",
  "Oracle IBM Java update", "ASM redundancy AIX", "pigz parallelism", "zlibNX oracle aix",
  "PowerVS Oracle storage tier",
  "extended statistics Oracle AIX", "Oracle 19c RU apply AIX", "LMS processes RAC Power".
---

# Oracle Power — Miscellaneous Best Practices

Supplementary guidance for Oracle Database on IBM Power Systems / AIX, covering topics not addressed
by the CPU, memory, I/O, or licensing skills. Source: IBM Power Systems VUG May 2024 sessions by
Ralf Schmidt-Dannert, IBM ATG Principal Power Specialist.

---

## 1. Oracle 19c Installation on AIX — Base Release + RU in One Step

### The Problem

Oracle Database 19c on AIX **must be installed from the base 19.3 release first** — you cannot
install directly from a later Release Update (RU). However, production deployments should always
run a recent RU (e.g., 19.22+). Installing 19.3 and then patching separately is error-prone.

A common failure when attempting a combined install/patch approach:

```
delete action destination file not writable
```

This error occurs when using a naive single-installer approach that tries to apply a RU without
the correct pre-steps.

### Recommended Approach: `gridSetup` / `runInstaller` + `-applyRU` Flag

Run the 19.3 base installer with the `-applyRU` flag pointing to the RU patch directory. This
applies the Release Update **during** the installation, before the full install completes:

```bash
# Example: install Oracle Grid 19.3 with RU 19.22 applied in one step
./gridSetup.sh \
  -applyRU /stage/patches/34340533 \
  -silent \
  -responseFile /stage/grid_install.rsp

# Same approach for the database home installer
./runInstaller \
  -applyRU /stage/patches/34340533 \
  -silent \
  -responseFile /stage/db_install.rsp
```

> This avoids a separate post-install patching step and ensures the home is already at the
> current RU level before any configuration utilities (DBCA, netca) are run.

### What RU to Target

As of May 2024 (VUG session), **19.22** was the recommended current release. Always verify the
latest available RU on Oracle Support (My Oracle Support) before a new deployment.

---

## 2. Oracle Mutex and Spin Count Tuning for High-Throughput OLTP

### Background

Oracle uses mutexes (lightweight locks) to protect shared cursor and library cache structures.
The mutex algorithm has a **spin phase** — a process will actively spin (loop on a CPU) for a
configurable number of cycles before going to sleep and releasing the CPU.

The default spin count (`_spin_count`) is **255** — a value set many CPU generations ago and
intentionally very short. On modern Power processors (Power9/10/11) with their high clock
speeds and deep caches, this value is frequently too low for high-concurrency OLTP workloads.

### Symptoms of Insufficient Spin Count

In AWR or `v$system_event`, a dominant wait event of:

```
cursor: mutex X
```

...combined with high **CPU "idle" time** (processes sleeping unnecessarily after short spins)
and low actual TPS despite available CPU capacity.

**Test observation (VUG May 2024, Ralf Schmidt-Dannert, IBM ATG):**

| Configuration | TPS (Swingbench OLTP) |
|---|---|
| Default (`_spin_count=255`) | ~12,000 |
| `_spin_count=4000` only | ~22,000 (+83%) |
| `_spin_count=4000` + `mark_hot` on hot objects | ~38,000 (+217%) |

### Recommended Approach

```sql
-- Step 1: Identify if cursor mutex X is a top wait event
SELECT event, total_waits, time_waited
FROM   v$system_event
WHERE  event LIKE '%mutex%'
ORDER  BY time_waited DESC;

-- Step 2: Check current spin count (hidden parameter)
SELECT name, value, description
FROM   v$parameter
WHERE  name = '_spin_count';

-- Step 3: Increase spin count (requires instance restart for spfile scope)
-- Start conservatively; 4000 is a well-tested starting point on Power9/10
ALTER SYSTEM SET "_spin_count" = 4000 SCOPE=SPFILE;
-- Restart required for hidden parameters
```

> **Note**: `_spin_count` is a hidden (underscore) parameter. Changes require thorough testing
> on a non-production instance first. The optimal value varies with workload concurrency and
> hardware. Values between 2000 and 8000 have been used successfully on Power9/10 systems.

---

## 3. Oracle `DBMS_SHARED_POOL.MARKHOT` — Hot Object Copies

For very high-concurrency access to the same library cache object (cursor, package, package body,
type), Oracle can create **multiple copies** of the object in the shared pool, distributing
the mutex contention across copies.

### When to Use

- AWR shows `cursor: mutex X` or `library cache: mutex X` as top waits.
- Hot objects are **pinned and highly executed** (confirmed via the query below).
- `_spin_count` increase alone does not eliminate the wait event.

### Identifying Hot Objects

```sql
-- Objects that are good candidates for mark_hot
-- Look for: pinned=YES, execute_count very high
SELECT object_name, object_type, kept, loads, executions, invalidations
FROM   v$db_object_cache
WHERE  kept = 'YES'
  AND  executions > 100000
ORDER  BY executions DESC;

-- Generate the mark_hot commands for top candidates
SELECT 'EXECUTE DBMS_SHARED_POOL.MARKHOT(''' || name || ''', ' ||
       CASE type
         WHEN 'PACKAGE'      THEN '1'
         WHEN 'PACKAGE BODY' THEN '2'
         WHEN 'TRIGGER'      THEN '3'
         WHEN 'TYPE'         THEN '4'
         ELSE '1'
       END || ');' AS cmd
FROM   v$db_object_cache
WHERE  kept = 'YES'
  AND  executions > 500000
  AND  type IN ('PACKAGE','PACKAGE BODY','TRIGGER','TYPE')
ORDER  BY executions DESC
FETCH FIRST 10 ROWS ONLY;
```

### Applying MARKHOT

```sql
-- Mark a specific package as hot (creates multiple copies in shared pool)
EXECUTE DBMS_SHARED_POOL.MARKHOT('SYS.DBMS_SQL', 1);   -- 1 = PACKAGE
EXECUTE DBMS_SHARED_POOL.MARKHOT('SYS.DBMS_SQL', 2);   -- 2 = PACKAGE BODY

-- Unmark (remove extra copies)
EXECUTE DBMS_SHARED_POOL.UNMARKHOT('SYS.DBMS_SQL', 1);
```

### ⚠️ Caution: Do Not Over-apply MARKHOT

Marking too many objects as hot can cause Oracle Enterprise Manager and internal dictionary
queries to run for **minutes** because the object list in `v$db_object_cache` becomes
excessively large. Apply only to the 3–10 most contended objects, not to every hot object.

> **Sequences cannot be marked hot.** Only packages, package bodies, triggers, and types
> are supported.

---

## 4. CPU Utilization Interpretation Under SMT on Power

### The Problem

When using `topas` or `nmon` (the `t` key or process CPU view) on an AIX Power system,
the percentage shown for a single Oracle process is **relative to the total logical CPU count**,
not to a single physical core or thread.

On an SMT8 system with 4 physical cores (= 32 logical CPUs):
- A **fully CPU-bound** process running at maximum speed on one logical CPU appears as
  approximately **3.1%** (1/32 × 100%) in `topas`/`nmon`.
- The same process on SMT1 would show **~99.8%**.

### Consequence for Oracle Tuning

If you see an Oracle process at "32%" CPU, it is likely **fully CPU-bound** on one thread on
an SMT8 system — not merely moderately busy. Misreading this leads to wrong conclusions.

**The ratio differs between Power generations** — test and document the expected "100% CPU"
value for your specific platform:

```bash
# Test script: run a single-threaded CPU loop and observe the topas/nmon %CPU
# The % reported when the process is clearly CPU-bound = your "100% reference" for this LPAR

# Simple CPU spin test (run in background, observe with topas)
perl -e 'while(1) {}' &
SPIN_PID=$!
topas    # Observe % CPU for the perl process — this is your "1 logical CPU = X%" reference
kill $SPIN_PID

# Document the result:
# Power9 SMT8  (4 cores, 32 threads):  ~3.1% per fully loaded thread in topas
# Power10 SMT8 (4 cores, 32 threads):  value differs — re-measure
# Power11 SMT8 (4 cores, 32 threads):  re-measure after migration
```

**Observed ratios differ between Power8, Power9, and Power10** — always re-baseline after
a hardware migration.

> **Rule of thumb**: divide 100 by the logical CPU count of the LPAR to get the approximate
> `topas` % for a single fully CPU-bound process. But measure empirically — the actual ratio
> varies with hardware generation.

---

## 5. RAC Network Configuration on AIX

### HAIP vs. LACP/NIB for RAC Interconnect

| Option | When to Use | Notes |
|---|---|---|
| **HAIP** (Oracle High Availability IP) | Active-active interconnect HA | Oracle's native method; distributes I/O across interfaces; no switch-level LACP required |
| **LACP** (802.3ad Link Aggregation) | Bundling ports for higher throughput AND HA | Requires capable switch; switch and NIC must both support it |
| **EtherChannel/NIB** | Active-passive NIC bonding | Simpler; lower latency; failover only |

- For RAC interconnect with **active-active HA** requirements: prefer **HAIP**.
- For environments requiring higher aggregate throughput on the interconnect: LACP if supported.

```bash
# HAIP configuration is managed by Oracle Clusterware:
# Verify HAIP interfaces in Oracle GI:
srvctl config nodeapps -n $(hostname)

# In AIX, verify NIB (Network Interface Backup) or EtherChannel:
lsdev -Cc adapter | grep ent
entstat -d en0   # Shows adapter statistics including bond details
```

### IPv6 Interface Ordering Issue in PowerVS (RAC)

**Symptom**: Oracle RAC installation or cluster verification fails due to the installer detecting
IPv6-only interfaces (or interfaces with no IP) before the IPv4 interfaces configured for the
RAC public network and interconnect.

**Root cause**: PowerVS LPARs expose additional management interfaces (e.g., for NovaLink or
internal use) that may appear in the OS interface list before `en0/en1/en2`. Oracle RAC's
installation and detection code iterates interfaces in enumeration order and can select the
wrong interface even if explicitly told not to.

**Fix**: Use `rendev` to rename/reorder network interfaces so that the IPv4 interfaces intended
for RAC (public, private, VIP) appear **first** in the OS enumeration list (e.g., `en0`, `en1`,
`en2`) before any IPv6-only or unaddressed interfaces.

```bash
# List current network interfaces
lsdev -Cc adapter | grep ent
ifconfig -a | grep -E "^en|inet|inet6"

# Check interface enumeration order (affects Oracle RAC detection)
odmget CuAt | grep -A5 "name = \"en"

# Rename an interface (example: renumber en5 to en2 if en2 is free)
rendev -l en5 -n en2

# After renaming, verify:
ifconfig -a
lsdev -Cc adapter | grep ent
```

> **Workaround**: If renaming is not practical, during Oracle installation explicitly provide
> interface names for public, private, and VIP. However, even with explicit specification,
> Oracle RAC has been observed to still pick up unwanted interfaces — renaming is more reliable.

### TCP Loopback Optimization (Same-LPAR Client/Server)

For Oracle client processes connecting to a database in the **same LPAR** (e.g., batch jobs,
application server co-located with the database):

```bash
# Enable TCP fast loopback (shortcut for loopback-address connections within the LPAR)
no -p -o tcp_fastlo=1

# Verify
no -a | grep tcp_fastlo
```

### Cache Routes (DNS Lookup Optimization)

Slow DNS lookups (even for `localhost` or `/etc/hosts` entries) can add latency to every new
Oracle connection. The AIX `cacheroutes` feature caches IP routes:

```bash
# Verify cacheroutes status
no -a | grep routecache

# There have been known issues with cacheroutes in some AIX versions —
# review the APAR list for your AIX TL before enabling in production.
# Check: IBM Support for cacheroutes-related APARs on your AIX 7.2 TL5+ or 7.3 level
```

### Large Send Offload (Network)

For network-intensive Oracle workloads (Data Guard redo shipping, RMAN over network, RAC
interconnect) on Power Systems:

```bash
# Check Large Send Offload setting on ethernet adapter
entstat -d en0 | grep -i "large send"

# Review IBM documentation for LSO configuration specific to your adapter type
# (configuration varies: SEA, VNIC, physical ent)
```

---

## 6. ASM Redundancy — External Recommended for Enterprise Storage

When Oracle ASM is deployed on top of enterprise storage (IBM FlashSystem, Pure Storage, HPE
Primera, etc.):

| Storage Type | Recommended ASM Redundancy | Reason |
|---|---|---|
| Enterprise SAN (FlashSystem, etc.) | **External** | Storage has built-in RAID and controller HA; ASM redundancy doubles I/O with no benefit |
| Internal disks (JBOD, no RAID) | Normal or High | No hardware redundancy below ASM |
| NVMe in server (no external HA) | Normal | Limited paths; hardware redundancy limited |

```sql
-- Create disk group with external redundancy (recommended for enterprise SAN)
CREATE DISKGROUP data
  EXTERNAL REDUNDANCY
  DISK '/dev/roradg_lv01','/dev/roradg_lv02','/dev/roradg_lv03','/dev/roradg_lv04',
       '/dev/roradg_lv05','/dev/roradg_lv06','/dev/roradg_lv07','/dev/roradg_lv08'
  ATTRIBUTE 'compatible.asm' = '19.0',
            'compatible.rdbms' = '19.0',
            'au_size' = '4M';    -- or 8M for large DW databases
```

> With external redundancy, ASM does not mirror data. All I/O goes to a single copy, maximizing
> throughput. The storage array's internal RAID protects against physical disk failure.

---

## 7. `pigz` Hardware Compression — Optimal Parallelism

Power9, Power10, and Power11 include **NX GZIP hardware acceleration** in each processor core.
The `pigz` command (parallel gzip, open source) uses the **`zlibNX`** library on AIX 7.2 TL4+
to leverage this hardware acceleration. `pigz` is part of AIX base media since AIX 7.2 TL5 SP2+.

> **Important correction (VUG slide 71)**: Use **`pigz`** (uses `zlibNX`), **not** `xgzip`
> (deprecated, single-threaded) and **not** `pixz` (parallel xz — different tool, does not use `zlibNX`).

### Parallelism Setting

The default parallelism `pigz` selects (based on logical CPU count) is often **not optimal**.
Testing shows that **parallelism = 8** provides the best throughput on Power systems:

```bash
# Optimal invocation for Power9/10/11 hardware-accelerated compression:
pigz -p 8 /path/to/backupfile.bkp

# -p 8 = 8 parallel compression threads (optimal for Power NX gzip engines)

# Do NOT use xgzip — it is single-threaded and deprecated
# Avoid the default parallelism (auto-detected from logical CPU count = too many threads)
```

### Throughput Reference (VUG May 2024 Test, IBM ATG — E980, 16 cores, ~230GB data)

| Config | Compression speed |
|---|---|
| `tar \| gzip` (single-threaded) | 3h 15m for ~230 GB |
| `tar \| pigz -p 8` | **4m 31s** — >43× faster |
| `xgzip` (deprecated, single-threaded) | Similar to `gzip`; deprecated |

```bash
# Must be in correct LPAR compatibility mode for hardware acceleration:
lparstat -i | grep -i "compat"
# Power9:  POWER9 compat mode (NOTE: POWER9_Base mode DISABLES the NX accelerator)
# Power10: POWER9, POWER9_Base, or POWER10 compat mode
# Power11: POWER9, POWER10, or POWER11 native mode (AIX 7300-03-01+)

# Verify the accelerator is actually available in this LPAR:
nxstat -S
# nx_accel_mask = 1  -> accelerator available
# nx_accel_mask = 0  -> NOT available — check compat mode

# Typical use cases:
# - Compress RMAN backup pieces after creation
# - Compress archive log files before shipping to tape/object storage
# - Data export compression
```

---

## 8. PowerVS Storage Tier Selection for Oracle

IBM Power Virtual Server (PowerVS) provides IOPS-tiered storage. Choosing the wrong tier is the
most common cause of unexpected I/O performance issues in PowerVS Oracle deployments.

### Recommended Starting Tiers

| Oracle File Type | PowerVS Storage Tier | Reason |
|---|---|---|
| Database data, indexes, temp | **Tier 1** (≥25,000 IOPS/LUN) | Random 8KB I/O; needs low latency and high IOPS |
| Oracle redo logs | **Tier 1** (≥25,000 IOPS/LUN) | Sequential small I/O; extremely latency-sensitive |
| Archive logs | **Tier 3** or **Tier 1** | Sequential write-once; Tier 3 acceptable if throughput is sufficient |
| Oracle binaries | **Tier 3** | Low IOPS, sequential reads at startup |
| RMAN backups | **Tier 3** | Bulk sequential I/O; IOPS density not critical |

```bash
# PowerVS CLI: create a storage volume with specific tier
# (IBM Power Virtual Server API v1.1.1+)
ibmcloud pi volume create data-lun-01 --size 100 --type tier1

# Verify volume tier assignment
ibmcloud pi volume list
ibmcloud pi volume get <volume-id>
```

> **IOPS tiers are dynamically adjustable** in PowerVS — you can upgrade a Tier 3 volume to
> Tier 1 without re-creating it. Monitor AWR average wait time for `db file sequential read`
> (target < 1ms for flash Tier 1) and adjust tier accordingly.

---

## 9. Oracle IBM Java Embedded — Keep Updated

Oracle Database embeds its own copy of **IBM Java** (used for XML, OJVM, and other internal
components). This embedded Java is a separate software stack from the OS Java — it has its own
security vulnerabilities and must be updated independently.

As of March 2024 (near time of VUG session), Oracle started bundling Java updates in patches:

```bash
# Identify Oracle-embedded IBM Java version
find $ORACLE_HOME -name "java" -type f 2>/dev/null | head -3
$ORACLE_HOME/jdk/bin/java -version 2>&1

# Oracle provides downloadable IBM Java updates for the Oracle Home separately from RUs
# Download from: My Oracle Support (MOS) — search for "IBM Java Oracle AIX"
# Apply to the Oracle Home and Grid Home separately

# After applying, verify:
$ORACLE_HOME/jdk/bin/java -version 2>&1
```

> Apply the latest available IBM Java update to every Oracle Home (DB home, Grid home) as part
> of your regular patching cycle — it is **not** included in standard Oracle PSUs/RUs.

---

## 10. Known Oracle 19c Issues on Power Systems (as of May 2024)

The following issues were highlighted by IBM ATG. Verify current patch status on My Oracle Support.

| Issue | Versions Affected | Impact | Resolution |
|---|---|---|---|
| Extended statistics locking (`spin lock` waits) | 19c < 19.13 | High CPU spin waits under high-concurrency OLTP | Apply patches; upgrade to 19.13+ or 19.22+ |
| Too many LMS processes in RAC on large systems | 19c, large Power10/Power11 configs | CPU overhead from excess GCS processes | Apply Oracle MOS Note (search "LMS processes RAC 19c large system") |
| `changevg` requirement for VG disk size rediscovery | AIX with Oracle | If not run after SAN disk expansion, AIX does not see new space | Run `chvg -g <vgname>` after any storage subsystem LUN resize |
| LVM / filesystem changes not honoring new LUN sizes | AIX 7.2/7.3 after SAN resize | VG commands return old size | `cfgmgr` then `chvg -g <vgname>` (see I/O skill, section 7) |
| AWR missing server detail metrics (>1031 logical CPUs) | 19c, 18c on large Power servers | AWR incomplete — missing OS-level metrics | Oracle one-off patch per release — request via Oracle Support |

```bash
# Verify current Oracle patch level
$ORACLE_HOME/OPatch/opatch lsinventory | grep -E "Oracle Database|Applied Patch"

# For RAC: check LMS process count
ps -ef | grep lms | grep -v grep | wc -l
# Expected: approximately 1 per 2 physical CPUs (check MOS for your specific config)
```

---

## 11. Key Reference Documents (from IBM ATG)

The following documents were highlighted as "must-check regularly" by Ralf Schmidt-Dannert (IBM ATG):

1. **"AIX with Oracle Database and IBM Power System Considerations for Performance Stability"**
   — IBM technical note; lists tuning parameters, known AIX APARs/PMRs affecting Oracle.
   Contains the authoritative list of all AIX parameters discussed in these VUG sessions.
   Search on IBM Support / developerWorks: _"AIX Oracle Database IBM Power System Performance Stability"_

2. **Oracle on Power Best Practices deck (this series)**
   — Full ~89 and ~116 slide decks available on IBM Power Systems VUG website.

3. **Oracle Certification Matrix for AIX on Power**
   — Oracle Support: verifies which Oracle versions are certified on which AIX/Power combinations.

4. **Oracle Proactive Patch Program (MOS)**
   — One-off patches and proactive recommendations specific to Oracle on AIX/Power.

---

## Source Reference

IBM Power Systems Virtual User Group, May 2024:
- Session 1: "Oracle on Power Best Practices — Memory and CPU" (Ralf Schmidt-Dannert, IBM ATG)
  - Deck: `OracleOnPowerTuningConsiderations_CPU_Memory_NEXT.pptx` (~89 slides)
- Session 2: "Oracle on Power Best Practices — I/O and Miscellaneous" (Ralf Schmidt-Dannert, IBM ATG)
  - Deck: `OracleOnPowerTuningConsiderations_AIX_IO_Misc_NEXT.pptx` (~116 slides)

Items marked ⚠️ require verification — no authoritative source available at time of writing.
