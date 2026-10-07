---
name: oracle-aix-best-practices-memory
description: >-
  Use when tuning AIX memory management for an Oracle database on IBM Power Systems. Covers AIX
  memory pools, page sizes (4KB/64KB/16MB), SGA page size selection, JFS2 inode/metadata cache
  sizing, NUMA/SRAD affinity, paging space management, and related vmo/ioo parameters. Also
  covers DSO/MPSS page coalescing, AME, LDR_CNTRL Oracle binary page size, shrsymtab/ldedit
  defect, terabyte segment aliasing, and AIX 7.3 / Power10 / Power11 specifics. Trigger phrases:
  "memory tuning Oracle AIX", "SGA page size", "16MB pages Oracle", "JFS2 inode cache",
  "NUMA Oracle Power", "lssrad", "memory pools AIX", "vmo Oracle", "paging space Oracle",
  "minfree maxfree", "lock_sga", "ORACLE_SGA_PGSZ", "minperm maxperm", "DSO Oracle AIX",
  "aso_active", "asoo Oracle", "LDR_CNTRL Oracle", "DATAPSIZE", "AME Oracle", "shrsymtab",
  "ldedit Oracle", "pgz vmo", "topas -M NUMA", "svmon large pages", "AIX 7.3 Oracle memory".
---

# Oracle Power Memory Tuning

Expert guidance for AIX memory tuning specific to Oracle Database on IBM Power Systems (Power9/Power10/Power11).
Source: IBM Power Systems VUG May 2024 sessions by Ralf Schmidt-Dannert, IBM ATG Principal Power Specialist.

---

## 1. AIX Memory Architecture Fundamentals

### Memory Pools
- Physical memory is divided into **memory pools** at boot time, based on logical CPU count and physical topology.
- Each pool maintains separate **free lists** and **used lists** for **4KB** and **64KB** pages.
- `vmo` parameters `minfree`/`maxfree` are enforced **per pool per page size** — not system-wide.
- The number of memory pools changes dynamically when SMT mode changes or CPUs/memory are added/removed (DLPAR).
- Highly uneven pool sizes can occur after dynamic SMT changes (e.g., SMT8→SMT1) — some pools may be very large, others tiny.
  - If one small pool exhausts its free list, AIX will steal pages even if other pools have abundant free memory.

```bash
# View memory pool summary
vmstat -v | grep pool

# Advanced: detailed pool breakdown (use cautiously — root only, potential perf impact)
echo "mempsum *" | kdb | sed -n '/mempsum/,$p'

# View SRAD/NUMA topology
lssrad -va
```

### Page Sizes and Their Roles
| Page Size | Used For | Notes |
|---|---|---|
| 4KB | JFS2 filesystem cache, process text/stack/data | Default; can be coalesced to 64KB by psmd |
| 64KB | Oracle SGA, PGA, kernel, Oracle process memory | Default for Oracle 11g+; 64KB default for Oracle binaries (12.1+); can be broken from 16MB |
| 16MB | Large SGA pinning (SGA ≥ 100GB) | Manual allocation required; never auto-recreated if split; DSO can create temporary ones |
| 16GB | Rarely used | Requires server power-off to allocate; not used in practice |

```bash
# Verify process page size
ps -Z -p <pid>

# Check 16MB page allocation
vmo -a | grep lgpg
nmon  # 'g' key: large page stats (count and free)
      # 'M' key: full memory breakdown including large pages (AIX 7.x)

# Check unused pre-allocated 16MB pages via svmon
svmon -G
# In the output, under PageSize section, 'L 16 MB' row:
#   PoolSize = total allocated 16MB pages
#   inuse    = currently used by Oracle SGA
#   PoolSize - inuse = unused/wasted 16MB pages
```

### Oracle Binary Page Size (LDR_CNTRL)
Oracle 12.1+ uses 64KB pages **by default** for Oracle binary text, data, and stack pages.
On older Oracle releases this must be set explicitly:

```bash
# For Oracle < 12.1: enable 64KB pages for Oracle binary (set in oracle user environment)
export LDR_CNTRL=DATAPSIZE=64K@TEXTPSIZE=64K@STACKPSIZE=64K

# Verify Oracle process is using 64KB pages
ps -Z -p $(pgrep -x oracle | head -1)
# 'K' in output = 64KB pages; 'k' = 4KB pages
```

> **`pgz_*` vmo parameters** (AIX 7.2 TL2+): A set of page granularity zone parameters (`pgz_*`) was introduced in AIX 7.2 TL2 for controlling fine-grained page size zones. Review `vmo -a | grep pgz` on your system. IBM ATG recommends keeping defaults unless specifically guided by IBM support.

### The PSMD and LRUD Processes
- **PSMD** (`psmd` process): converts between 4KB ↔ 64KB pages on free/used lists. Active PSMD = conflicting page-size demand (file cache vs. Oracle SGA). Consider reducing `maxperm%` to give 64KB pages more room.
- **LRUD** (`lrud` process, one per memory pool): steals pages when `free < minfree`. Steals from file cache first; from computational pages only when file cache is below `minperm%`.
- High LRUD activity = AIX struggling to maintain free lists. Review memory layout, reduce `maxperm%`.

---

## 2. AIX VMO Memory Parameters for Oracle

### Key Parameters and Recommended Values

| Parameter | Recommended | AIX 7.x Default | Notes |
|---|---|---|---|
| `esid_allocator` | 1 | 1 | Enhanced segment ID allocator. Keep at default. |
| `minperm%` | 3 | 3 | Minimum file cache %. When file cache drops below this, computational pages can be stolen. Do not reduce below default in Oracle environments. |
| `maxperm%` | 90 | 90 | Maximum file cache %. Reduce if 64KB page starvation occurs. |
| `maxclient%` | 90 | 90 | Maximum client file cache %. |
| `strict_maxclient` | 1 | 1 | |
| `strict_maxperm` | 0 | 0 | Keep at default 0. |
| `lru_file_repage` | 0 | N/A (AIX 7.x) | AIX 6.1 only; leave at 0 on AIX 7.x. |
| `minfree` | `max(960, 120 × logical_CPUs) / num_pools` | 960 | Per pool. Increase if `vmstat` `fre` column approaches zero. |
| `maxfree` | `minfree + min(1024, (max(maxpgahead, j2_maxPageReadAhead) × logical_CPUs / num_pools))` | 1088 | Do not reduce below default. |
| `maxpin%` | Leave at default | 90% (AIX 7.x) | **Do not modify.** Changing this can interfere with 16MB page allocation. AIX 6.1 default is 80%. |
| `vmm_klock_mode` | 2 | 2 (AIX 7.x) | Kernel memory locking. `0`=disabled; `1`=AME-only; `2`=all kernel memory types (recommended for Oracle RAC and any pinned SGA); `3`=kernel stacks only. AIX 6.1 prerequisite: TL6 SP5+ and APAR IZ95744. |
| `v_pinshm` | 1 (when using 16MB pages) | 0 | Must be set to `1` when allocating 16MB pages for Oracle SGA. Leave at `0` if not using 16MB pages. |
| `lgpg_regions` | 0 (unless explicitly allocating 16MB pages) | 0 | |
| `lgpg_size` | 0 | 0 | |
| `memory_affinity` | 1 | 1 | Enables NUMA memory affinity. Keep enabled. |
| `page_steal_method` | 1 | 1 | |
| `enhanced_affinity_private` | 40% (AIX 6.1 TL6+ / AIX 7.x default) | 40% | % of app private data allocated locally. Restricted parameter -- do not change unless guided by IBM support. AIX 6.1 TL5 default was 20%. |

```bash
# Apply minfree/maxfree (example: 10 logical CPUs, SMT2, 2 pools, maxpgahead=8, j2_maxPageReadAhead=128)
# minfree = max(960, 120x10x2/2) = 1200
# maxfree = 1200 + min(1024, (128x10x2/2)) = 2024
vmo -p -o minfree=1200 -o maxfree=2024

# Check perm page usage
vmstat -v | grep -E 'perm|free'
```

### Addressing Paging Space Issues (Quick Actions)
1. Reduce `minperm%` from 3 to 2 (`vmo -p -o minperm%=2`) — frees more memory for computational pages.
2. Reduce Oracle `sga_target` or `pga_aggregate_target` temporarily.
3. Free unused 16MB pages if over-allocated (`vmo -p -o lgpg_regions=<N>`).
4. DLPAR: dynamically add memory to the LPAR.

**Paging Space Sizing Rule-of-Thumb:**
| Physical Memory | Max Paging Space |
|---|---|
| ≤ 128GB | 60GB |
| ≤ 256GB | 100GB |
| ≤ 512GB | 150GB |
| ≤ 1TB | 200GB |

> Paging space is a **fail-safe**, not a resource. Goal for Oracle: **zero paging space activity from the database**.
> Max size per paging device: 64GB — multiple devices may be required for large systems.

---

## 3. JFS2 Inode and Metadata Cache Sizing

JFS2 has two caches (inode cache, metadata cache) that grow until maximum size is reached — they do **not** auto-release unless forcibly reduced. **Default values are tuned for a file server, not an Oracle database.**

- On a 300GB system, defaults allow up to **21GB** for inode cache (~21 million files).
- AIX 7.2 + Oracle 19c Grid + DB installs only ~210,000 files — vastly over-configured.

```bash
# Check current JFS2 cache usage
cat /proc/sys/fs/jfs2/memory_usage
# Shows: metadata cache, inode cache, total bytes

# Controlled via ioo parameters:
ioo -a | grep -E 'j2_inodeCacheSize|j2_metadataCacheSize'
```

### Sizing Procedure

1. Count inodes currently on the server:
   ```bash
   df | awk '/jfs2/{sum+=$7} END{print sum}'   # Sum 'Iused' column for JFS2 filesystems
   # Or (slow but thorough): find / | wc -l
   ```
2. Add headroom for temp files (e.g., +50,000–100,000): `reqInode`
3. Calculate required MB: `reqMB = reqInode / 1000`
4. Calculate parameter value: `j2_inodeCacheSize = (((reqMB × 100) / physical_mem_MB) / 2.5) × 100`

```bash
# Example: 64GB system, 220,000 inodes + 50,000 headroom = 270,000
# reqMB = 270
# j2_inodeCacheSize = (((270*100)/(64*1024))/2.5)*100 ≈ 17

ioo -p -o j2_inodeCacheSize=17 -o j2_metadataCacheSize=17

# WARNING: Reduce cache size in small steps — large reductions can cause
# system unresponsiveness for tens of seconds while AIX frees memory!
```

---

## 4. NUMA / SRAD Memory Affinity

### Understanding NUMA on Power Systems
- **Local memory**: directly attached to the processor chip — lowest latency.
- **Near memory**: same CEC node, different chip.
- **Far memory**: different CEC drawer — significant latency penalty.
- Oracle SGA is striped across all LPAR memory by default. If the LPAR spans multiple nodes, SGA accesses will hit far memory frequently.
- Oracle PGA for a given process tends to be allocated near the processor that process was running on when the memory was allocated. This limits but does not eliminate NUMA impact for PGA.

### NUMA Topology by Model
| Model | Local | Near | Far |
|---|---|---|---|
| Power S924 (Power9) | Same chip | Other chip | N/A (single socket) |
| Power E850 (Power9) | Same chip | Other chip, same socket | Other socket |
| Power E950 (Power9) | Same chip | Other chip, same node | N/A |
| Power E880/E980 (Power9) | Same chip | Other chip, same node | Different node |
| Power S1014 (Power10) | Same chip | Other chip, same socket | N/A |
| Power E1050 (Power10) | Same chip | Other chip, same socket | Other socket |
| Power E1080 (Power10) | Same chip | Other chip, same node | Different node |
| Power E1150 (Power11) | ⚠ Topology not documented in May 2024 source. E1150 is a 4U rack server (up to 120 cores, 16TB) — expected multi-node similar to E1080. Confirm with `lssrad -va` on live system. | likely Same chip | likely Different node |
| Power E1180 (Power11) | ⚠ Topology not documented in May 2024 source. E1180 is a full-rack enterprise server — multi-node architecture confirmed by IBM product page ("scale-up"). Confirm with `lssrad -va` on live system. | likely Same chip | likely Different node |
| Power S1112 (Power11) | ⚠ Topology not documented in May 2024 source. S1112 is a 2U compact server (up to 512GB DDR5) — single-node architecture expected. Confirm with `lssrad -va`. | Same chip | N/A (expected) |

> POWER9 is always Single Chip Module (SCM). POWER10 is available in SCM and DCM (Dual Chip Module) versions.

On a poorly configured large LPAR (e.g., E1080 with 3 CEC nodes assigned): `lssrad -va` may show SRADs with **0 local memory** — every process on those SRADs suffers far-memory latency on every access. This is a critical misconfiguration.

```bash
# Check LPAR SRAD/NUMA layout
lssrad -va
# Shows REF (CEC node), SRAD (chip), MEM (local GB), CPU (logical CPU range)
# ⚠ SRADs with MEM=0 = no local memory — severe NUMA latency guaranteed!

# Enhanced view with additional NUMA info
topas -M

# Monitor local/near/far thread dispatches
mpstat -d 1 60
# S3hrd = % local dispatches, S4hrd = % near, S5hrd = % far
# Goal: S3hrd > 95% for all CPUs

# Evaluate NUMA impact with CPI metric
hpmstat
```

### Corrective Actions
1. **Prevent at LPAR definition time**: Set realistic (smallest) `max_virtual_procs` — hypervisor uses max vCPU to determine physical spread. Over-allocating forces multi-CEC placement.
2. **Prevent**: Set realistic max memory — same issue with memory spreading across CECs.
3. **Reactive fix**: Use the **Dynamic Platform Optimizer (DPO)** via HMC to rebalance. Run during off-peak — DPO causes significant hypervisor activity while moving memory mappings. See: https://www.ibm.com/docs/en/power10?topic=dynamically-scheduling-dynamic-platform-optimizer-operations
4. Control LPAR **boot order** so high-priority LPARs boot first and get optimal placement.

### rsets (Resource Sets) for Fine-Grained Affinity
For very latency-sensitive workloads, `rsets` can bind Oracle processes to processors within a single CEC/chip. Use carefully — can cause CPU imbalance and dispatching delays in heavily loaded environments.

```bash
# Oracle memory affinity tuning (restricted parameter — do not change casually)
vmo -a | grep enhanced_affinity_private   # Default 40% in AIX 7.x / AIX 6.1 TL6+
```

---

## 5. SGA Page Size Configuration

### Decision Matrix
| SGA Size | Recommendation |
|---|---|
| < 100GB | Use default 64KB pages. Do not set `ORACLE_SGA_PGSZ`. |
| ≥ 100GB | Use 16MB pages with `ORACLE_SGA_PGSZ=16MB` + `LOCK_SGA=TRUE`. Also recommended for faster DB startup and reduced lock contention on large Power10/Power11 servers. |

### Allocating 16MB Pages — Full Procedure

**Formula for required 16MB page count:**
```
# Standard (ASMM / sga_max_size):
lgpg_regions = ROUNDUP[(sga_max_size_MB - 1) / 16, 0] + 3

# AMM (memory_max_target): use memory_max_target instead of sga_max_size
lgpg_regions = ROUNDUP[(memory_max_target_MB - 1) / 16, 0] + 3
```

> When AMM (`MEMORY_TARGET` / `MEMORY_MAX_TARGET`) is in use, large pages must cover **both SGA and PGA** combined — use `memory_max_target` not `sga_max_size` for the calculation.

```bash
# Step 1: allocate at boot time (use -r, not -p — requires reboot)
vmo -r -o lgpg_regions=<calculated_count> -o lgpg_size=16777216

# Step 2: enable SGA pinning for oracle user (both oracle and grid for RAC)
vmo -p -o v_pinshm=1

# Step 3: grant required AIX capabilities to oracle (and grid for RAC)
chuser capabilities=CAP_NUMA_ATTACH,CAP_BYPASS_RAC_VMM,CAP_PROPAGATE oracle
chuser capabilities=CAP_NUMA_ATTACH,CAP_BYPASS_RAC_VMM,CAP_PROPAGATE grid

# Step 4: regenerate boot image and reboot (required because -r was used)
bosboot -a
# then reboot the LPAR

# Step 5: verify after reboot
nmon   # press 'M' key: look for "Large Page" section
# Rule: sga_max_size + 3x16MB must be <= lgpg_regions (nmon will show this clearly)

# Alternative verification (find ora_smon PID first):
svmon -P $(ps -elf | grep "ora_smon_${ORACLE_SID}" | grep -v grep | awk '{print $4}') | grep shmat
# Output containing 'L' in the flags column confirms 16MB page usage
```

> **Do not modify `maxpin%`** from its default (90% on AIX 7.x, 80% on AIX 6.1). Changing it can interfere with large page allocation.

### ORACLE_SGA_PGSZ Environment Variable
- Controls page size Oracle requests from AIX for SGA mapping.
- **Critical**: value depends on how the database is started:
  - `sqlplus startup` → value from `.profile` / `oraenv` shell environment.
  - `srvctl start database` → value from `srvctl setenv` **only** (shell env is ignored).
- Always set via `srvctl setenv` for consistency — this is also the only way to control the environment for automatic DB startup.

```bash
# Best practice: always use srvctl setenv for consistency
srvctl setenv database -db mydb -envs "ORACLE_SGA_PGSZ=16MB"
srvctl getenv database -db mydb
srvctl unsetenv database -db mydb -envs "ORACLE_SGA_PGSZ"
# Also set in oracle user .profile as a fallback for sqlplus-started DBs
```

> **⚠ ORACLE_SGA_PGSZ=64KB danger**: If 16MB pages are configured and you explicitly set `ORACLE_SGA_PGSZ=64KB`, Oracle will convert all 16MB pages to 64KB — permanently de-configuring them and potentially causing paging to paging space. Never use `64KB` when 16MB pages are intended.

### LOCK_SGA + ORACLE_SGA_PGSZ=16MB (Preferred for SGA ≥ 100GB)
- Oracle pre-allocates **all** memory up to `SGA_MAX_SIZE` and pins it.
- If insufficient 16MB pages → startup fails with `ORA-27126` / AIX Error 12. This is **intentional** — it prevents silent fallback to 64KB pages that may later cause paging.
- If DBA accidentally sets `SGA_MAX_SIZE` larger than available 16MB pages, startup fails cleanly. Fix: allocate more 16MB pages or reduce `SGA_MAX_SIZE`.
- Note: `LOCK_SGA` and `SGA_MAX_SIZE` can only be set at the **container DB level** — not for a pluggable DB.

### LOCK_SGA=TRUE without ORACLE_SGA_PGSZ — Strongly Discouraged
- Oracle tries 16MB pages first, then silently falls back to 64KB if insufficient.
- Can permanently reduce your 16MB page pool if 16MB→64KB conversion occurs.
- Converted 16MB pages are **never automatically recreated** — they are gone until you run `vmo -r -o lgpg_regions=N` + `bosboot -a` + reboot.

### LOCK_SGA=FALSE (Default, for SGA < 100GB)
- Oracle dynamically grows SGA up to `sga_target` as needed.
- 64KB pages used automatically; 4KB pages converted to 64KB by psmd as needed.
- At startup: if insufficient 64KB pages, existing 16MB pages on free list may be **converted and consumed permanently**.
- After startup: unused 16MB pages are NOT converted even if 64KB page shortage occurs → potential paging to paging space.

### PRE_PAGE_SGA
- Default `TRUE` in Oracle 12.1+. Every Oracle process maps all SGA pages at startup.
- **Downside**: High new connection rates cause contention in AIX VMM. Startup time proportional to `(SGA_SIZE / page_size)`.
- With 19c, this impact is reduced. Monitor if high connection rate is a concern.
- Required `TRUE` when using Oracle In-Memory option.

---

## 6. Dynamic System Optimizer (DSO) / MPSS

DSO transparently coalesces 64KB pages into temporary 16MB pages for shared memory (SGA).

### Platform Support Matrix
| AIX Release | Platform | Minimum Level |
|---|---|---|
| AIX 7.1 | Power8 | TL04 SP2+ |
| AIX 7.2 | Power8 | TL01 SP2+ |
| AIX 7.2 | Power9 | TL3+ |
| AIX 7.3 | Power10 | TL1+ |
| AIX 7.3 | Power11 | ⚠ Not explicitly confirmed in source. NX GZIP blog ("Power10 or later") implies the same NX unit is present; DSO expected to work in POWER11 native compat mode. Verify `lssrc -s aso` + IBM Support #7240644. |

> **AIX 7.3 default**: `aso_active=1` is the **default** in AIX 7.3. Explicit enable is only needed on AIX 7.2 and earlier.

### Behaviour Notes
- DSO 16MB pages are **temporary** — a DB shutdown destroys them and the process restarts from scratch.
- Conversion only begins after **≥1 hour** of sustained workload against the SGA memory.
- **AIX 7.3 TL2+**: DSO is significantly more selective — converts only "hot pages", not all pages in a 256MB segment. In practice, Ralf Schmidt-Dannert (IBM ATG, May 2024) noted: *"It takes a quite lengthy consistent runtime to trigger the conversion and it's quite selective and slow — in the past it had been significantly more aggressive."*
- DSO is **not** a substitute for manually pre-allocated 16MB pages when SGA ≥ 100GB.
- DSO 16MB pages are **not reported** as 16MB pages in `nmon` — they are "hidden" from the standard view.
- DSO requires ≥ 24GB of physical memory in the LPAR.
- **AME and DSO are mutually exclusive** — cannot use both simultaneously.
- **Pre-AIX 7.2**: DSO was a chargeable feature (`aso.dso` fileset). AIX 7.2+ includes it in `bos.aso`.

```bash
# Check DSO status
lssrc -s aso
asoo -a | grep aso_active
# AIX 7.3: default is 1; AIX 7.2: must set to 1 explicitly
asoo -p -o aso_active=1   # AIX 7.2 only — persists across reboot

# Control minimum CPU utilization threshold before DSO attempts conversion
asoo -a | grep large_page_utilization

# Verify DSO activity on an Oracle process
svmon -P <oracle_pid> -O mpss=on
# Look for 'L' flag in PSize column — indicates 16MB page usage
# 'm' (lowercase) = page created by DSO (temporary); 'L' (uppercase) = persistent pre-allocated

# Optional: per-process control via environment variable
export ASO_OPTIONS=LARGE_PAGE=ON
```

---

## 7. Shared Segment Aliasing (Terabyte Segment)

For large SGAs, Segment Lookaside Buffer (SLB) faults can consume up to 20% of execution time.
Large Segment Aliasing (1TB per SLB entry) eliminates this — each SLB entry addresses 1TB, supporting up to 12TB of shared memory addressability on Power8/9/10 without SLB faults.

- Enabled by default on AIX 7.1, 7.2, and 7.3.
- **`shm_1tb_unsh_enable=0`** is recommended for Oracle DB environments. This is already the default as of AIX 6.1 TL7 SP5+, AIX 7.1 TL1 SP5+, AIX 7.2, and AIX 7.3.
- **Oracle 11.2.0.3 specific issue**: An unshared memory bug exists documented in APAR IV23859 and Metalink note 1467807.1. Ensure `shm_1tb_unsh_enable=0` on any system running Oracle 11.2.0.3.
- Oracle 11.2.0.3 also requires an Oracle-side bug fix for bug #147645450.
- AIX 7.1 32-bit processes may need fix for APAR IV11261.

```bash
# Confirm shm_1tb_unsh_enable is 0 (expected on supported AIX releases)
vmo -a | grep shm_1tb_unsh_enable
# Expected output: shm_1tb_unsh_enable = 0
```

---

## 8. Active Memory Expansion (AME)

- Compresses less-frequently used pages to increase effective memory capacity using built-in hardware accelerator.
- Hardware accelerator: **built-in on Power8, Power9, Power10**. ⚠ Power11 AME hardware accelerator presence not confirmed — verify before planning AME deployments on Power11. (Note: AME is not recommended for Oracle production regardless.)
- **Not recommended for Oracle production databases** — carefully test performance impact. Use `amepat` planning tool first to estimate CPU overhead.
- When used with Oracle: requires Oracle 12.2+, AIX 7.2 TL1+ (or AIX 7.3), Firmware 860+, `ame_hw_accel=1`, and 64KB page AME support (`ame_mpsize_support=1`).
- AME by default uses only **4KB pages**. 64KB page support requires `ame_mpsize_support=1` and a POWER8-mode or POWER9/Power10 LPAR.
- AME is incompatible with 16MB or 16GB Oracle SGA pages.
- **AME and DSO (MPSS) are mutually exclusive** — enabling one disables the other.
- If AME is enabled: Oracle SGA will be mapped with 4KB pages (not 64KB) unless `ame_mpsize_support=1`. This significantly increases SLB fault risk for large SGAs.

```bash
# Estimate AME benefit and CPU overhead before enabling
amepat -m <expansion_factor>   # e.g. amepat -m 1.5 for 50% expansion

# Check AME settings
lparstat -i | grep -i AME
```

---

## 9. AIX 7.2 LDEDIT / shrsymtab Issue (Important Defect)

Affects: AIX 7.2 TL1–TL3 **without** APAR IJ17766/IJ17973. Resolved in AIX 7.2 TL4 and AIX 7.3.
- Oracle's `shrsymtab` feature reduces memory consumption by sharing symbol tables across processes.
- An AIX 7.2 change added new options to `ldedit` and changed the "no option" usage message. Oracle's parser fails to detect `shrsymtab` in the new output → Oracle binary is linked without the option → potential memory over-commitment.
- IBM Support: https://www.ibm.com/support/pages/apar/IJ17766

```bash
# Step 1: Diagnose — check the 2nd Flags section of the Oracle binary
dump -X64 -Hov $ORACLE_HOME/bin/oracle
# Look for: Flags 0x00/0x8000 Flags=( SHRSYMTAB )
# If SHRSYMTAB is absent, the workaround is needed.

# Step 2: Apply workaround (re-run after EVERY Oracle patch that re-links the binary)
ldedit -b shrsymtab $ORACLE_HOME/bin/oracle
# Output: ldedit: File oracle updated.

# Step 3: Restart the Oracle database after applying the workaround.

# Permanent fix: apply AIX APAR
#   AIX 7.2 TL4     -> APAR IJ17973
#   AIX 7.2 TL1 SP3 / TL3 SP2 -> APAR IJ17766
```

---

## 10. Monitoring Commands Reference

```bash
# Memory pool health
vmstat -v | grep -E 'pool|perm|free'

# PSMD activity (conversion between page sizes — should not be persistently high)
ps -ef | grep psmd

# LRUD activity
vmstat 5          # watch 'pi' (page-in) and 'po' (page-out) columns

# NUMA placement
lssrad -va
mpstat -d 1 60   # S3hrd/S4hrd/S5hrd

# 16MB page inventory
nmon             # 'g' key for large pages
vmo -a | grep lgpg

# JFS2 cache current usage
cat /proc/sys/fs/jfs2/memory_usage

# Overall memory picture
svmon -G         # System-wide memory summary
nmon             # 'm' key for memory

# DSO / MPSS activity
svmon -P <oracle_pid> -O mpss=on
```

---

## Source Reference
IBM Power Systems Virtual User Group, May 2024:
- Session 1: "Oracle on Power Best Practices — Memory and CPU" (Ralf Schmidt-Dannert, IBM ATG)
- Deck: `OracleOnPowerTuningConsiderations_CPU_Memory_NEXT.pptx` (~89 slides)

### AIX 7.3 / Power11 Coverage Notes
- **AIX 7.3 confirmed**: DSO `aso_active=1` default; TL2+ hot-page-only conversion behaviour.
- **Power11 (E1150, E1180, S1112)**: NUMA topology and DSO/AME support on Power11 are **not covered** in the May 2024 source (deck predates Power11 announcement Oct 2024).
  - Always verify Power11 specifics via IBM Support #7240644 (AIX on Power11 supported levels) and IBM Support #7282898 (Power11 AIX compatibility modes).
- **AIX 7.2 TL2+ `pgz_*`**: Page granularity zone parameters exist but are not elaborated in the source -- keep defaults.
- **Oracle 19c on Power10/Power11**: IBM ATG noted increased NUMA sensitivity with 19c on Power10. Always run `lssrad -va` before deployment and after any DLPAR change.
- Always cross-check with the living document: IBM Support #6825029 -- "AIX with Oracle Database on IBM Power Systems Considerations for Performance and Stability".
