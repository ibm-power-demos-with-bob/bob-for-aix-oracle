# Oracle on Power: Memory Tuning

> **Read this file for:** AIX memory pools, page sizes, SGA page size
> (`ORACLE_SGA_PGSZ`, `LOCK_SGA`, 16 MB pages), `vmo` parameters
> (`minfree`/`maxfree`/`minperm%`), paging space, JFS2 inode and metadata caches,
> NUMA/SRAD, DSO/MPSS, AME, `LDR_CNTRL`, and the `shrsymtab`/`ldedit` defect.
> **Source:** IBM Power Systems VUG May 2024 (Ralf Schmidt-Dannert, IBM ATG), for
> Power9, Power10, and Power11.
> **Before changing any `vmo`, `ioo`, or `asoo` tunable**, check that it exists
> and show its default and type with `vmo -L <tunable>`.

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

# Verify an Oracle process is using 64KB pages (pgrep is not part of base AIX)
ps -Z -p $(ps -e -o pid,comm | awk '$2=="oracle"{print $1; exit}')
# DPGSZ / SPGSZ / TPGSZ columns (data / stack / text) show 4K, 64K or 16M
```

> **`pgz_*` vmo tunables:** these control page zeroing. Check what they mean at
> your level with `vmo -h pgz_mode`, and keep the defaults unless IBM Support
> advises otherwise.

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
| `minperm%` | 3 | 3 | Minimum file cache %. While the file cache is above this, LRUD steals file pages before computational pages. Lowering it to 2 is a measured emergency option against paging (see Quick Actions below). |
| `maxperm%` | 90 | 90 | Maximum file cache %. Reduce if 64KB page starvation occurs. |
| `maxclient%` | 90 | 90 | Maximum client file cache %. |
| `strict_maxclient` | 1 | 1 | |
| `strict_maxperm` | 0 | 0 | Keep at default 0. |
| `lru_file_repage` | 0 | N/A (AIX 7.x) | AIX 6.1 only; leave at 0 on AIX 7.x. |
| `minfree` | `max(960, 120 × logical_CPUs / num_pools)` | 960 | Per pool. Increase if the `vmstat` `fre` column approaches zero. |
| `maxfree` | `minfree + min(1024, max(maxpgahead, j2_maxPageReadAhead) × logical_CPUs / num_pools)` | 1088 | Must always be greater than `minfree`. Change both in one command. |
| `maxpin%` | Leave at default | 90% (AIX 7.x) | **Do not modify.** Changing this can interfere with 16MB page allocation. AIX 6.1 default is 80%. |
| `vmm_klock_mode` | 2 | 2 (AIX 7.x) | Kernel memory locking. `0`=disabled; `1`=AME-only; `2`=all kernel memory types (recommended for Oracle RAC and any pinned SGA); `3`=kernel stacks only. AIX 6.1 prerequisite: TL6 SP5+ and APAR IZ95744. |
| `v_pinshm` | 1 (when using 16MB pages) | 0 | Must be set to `1` when allocating 16MB pages for Oracle SGA. Leave at `0` if not using 16MB pages. |
| `lgpg_regions` | 0 (unless explicitly allocating 16MB pages) | 0 | |
| `lgpg_size` | 0 | 0 | |
| `memory_affinity` | 1 | 1 | Enables NUMA memory affinity. Keep enabled. |
| `page_steal_method` | 1 | 1 | |
| `enhanced_affinity_private` | 40% (AIX 6.1 TL6+ / AIX 7.x default) | 40% | % of app private data allocated locally. Restricted parameter -- do not change unless guided by IBM support. AIX 6.1 TL5 default was 20%. |

```bash
# Example: 10 cores at SMT2 = 20 logical CPUs, 2 memory pools,
#          maxpgahead=8, j2_maxPageReadAhead=128
# minfree = max(960, 120 x 20 / 2)               = max(960, 1200) = 1200
# maxfree = 1200 + min(1024, 128 x 20 / 2)       = 1200 + min(1024, 1280) = 2224
vmo -L minfree; vmo -L maxfree                   # record the current values first
vmo -p -o minfree=1200 -o maxfree=2224           # change both together (maxfree > minfree)
# Revert: vmo -p -o minfree=<old> -o maxfree=<old>   (or: vmo -p -d minfree -d maxfree for the defaults)

# Check perm page usage
vmstat -v | grep -E 'perm|free'
```

### Addressing Paging Space Issues (Quick Actions)
1. Lower `minperm%` from 3 to 2 (`vmo -p -o minperm%=2`). This lets the file
   cache shrink further before computational pages are stolen. Measure before and
   after.
2. Reduce Oracle `sga_target` or `pga_aggregate_target` (or `pga_aggregate_limit`)
   temporarily. Record the old values for the revert.
3. Release unused, over-allocated 16 MB pages: dynamically with
   `vmo -p -o lgpg_regions=<N> -o lgpg_size=16777216`, or persistently from the
   next boot with `-r` and then `bosboot -a`. Only release pages the SGA doesn't
   use (check `svmon -G`).
4. DLPAR: add memory to the LPAR dynamically.

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
   # Sum the Iused column (5th column of AIX df) over all JFS2 filesystems
   for fs in $(lsfs -c -v jfs2 | awk -F: '!/^#/{print $1}'); do
     df "$fs" | awk 'NR==2{print $5}'
   done | awk '{s+=$1} END{print s}'
   # Or (slow but thorough): find / -xdev | wc -l   (run per filesystem)
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
| Power S924 (Power9, 2 sockets) | Same chip | Other socket | N/A |
| Power E950 (Power9, 4 sockets) | Same chip | Other chip, same node | N/A |
| Power E980 (Power9, multi-node) | Same chip | Other chip, same node | Different node |
| Power S1014 (Power10, 1 socket) | Same chip | Other chip in the module | N/A |
| Power E1050 (Power10) | Same chip | Other chip, same socket | Other socket |
| Power E1080 (Power10, multi-node) | Same chip | Other chip, same node | Different node |
| Power11 servers | The May 2024 source doesn't cover them. Enterprise models such as the E1180 are multi-node like the E1080. **Always confirm with `lssrad -va`** on the live LPAR | | |

> Scale-out Power9 uses single-chip modules (SCM). Power10 and Power11 come in SCM
> and dual-chip module (DCM) packaging, so one socket can hold two chips (two
> SRADs).

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

**Prerequisite: use ASMM, not AMM.** Automatic Memory Management
(`MEMORY_TARGET` / `MEMORY_MAX_TARGET`) can't be combined with `LOCK_SGA=TRUE`
(startup fails with ORA-00847), and the PGA never uses SGA large pages. With
16 MB pages, use `SGA_TARGET` / `SGA_MAX_SIZE` plus `PGA_AGGREGATE_TARGET` (and
`PGA_AGGREGATE_LIMIT`).

**Required 16 MB page count:**
```
lgpg_regions = ROUNDUP[(sga_max_size_MB - 1) / 16, 0] + 3
# i.e. lgpg_regions x 16 MB >= sga_max_size + 48 MB. Sum over all instances that use 16 MB pages in the LPAR.
```

```bash
# Step 1: reserve the pages from the next boot (-r is the most reliable; a dynamic
#         -p allocation can succeed only partly on a fragmented system)
vmo -r -o lgpg_regions=<calculated_count> -o lgpg_size=16777216

# Step 2: allow pinned shared memory (needed for LOCK_SGA with 16 MB pages)
vmo -p -o v_pinshm=1

# Step 3: the oracle and grid owners need CAP_NUMA_ATTACH,CAP_BYPASS_RAC_VMM,CAP_PROPAGATE
#         (see os-prereqs.md §4):  lsuser -a capabilities oracle grid

# Step 4: rebuild the boot image and reboot (required because -r was used)
bosboot -a
# then reboot the LPAR in the change window

# Step 5: verify after the reboot
vmo -L lgpg_regions                  # BOOT/CUR = the calculated count
svmon -G                             # "L 16 MB" row: PoolSize (allocated) vs inuse (used by the SGA)

# Per-instance check (find the ora_smon PID first)
SMON_PID=$(ps -e -o pid,args | awk -v s="ora_smon_${ORACLE_SID}" '$2==s{print $1}')
svmon -P "$SMON_PID" | grep -i shmat
# Segments with page size 'L' (16 MB) confirm the SGA uses large pages
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
| AIX 7.3 | Power11 | Not covered by the May 2024 source. Check `lssrc -s aso` and the AIX release notes for your TL (IBM Support note 7240644). |

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
- Oracle 11.2.0.3 also needs an Oracle-side bug fix. The source quotes bug
  "147645450", which looks mistyped, so take the bug number from MOS note
  1467807.1.
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
# Estimate the AME benefit and CPU overhead before enabling: monitor a
# representative workload for <minutes>
amepat <minutes>                      # e.g. amepat 60
amepat -e 1.2:2.0:0.2 <minutes>       # evaluate a range of expansion factors (check: man amepat)

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

# LRUD (page stealing) activity
vmstat 5          # 'fr' (pages freed) and 'sr' (pages scanned): sustained high sr/fr = LRUD busy
                  # 'pi'/'po' = paging-space page-ins/outs: goal is 0 for Oracle

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
- **Power11**: the May 2024 source predates the Power11 announcement (July 2025)
  and doesn't cover its NUMA topology or DSO/AME support.
  - Always check Power11 specifics in IBM Support note 7240644 (AIX on Power11
    supported levels) and note 7282898 (Power11 AIX compatibility modes).
- **`pgz_*` (page zeroing) tunables**: keep the defaults.
- **Oracle 19c on Power10/Power11**: IBM ATG noted increased NUMA sensitivity with 19c on Power10. Always run `lssrad -va` before deployment and after any DLPAR change.
- Always cross-check with the living document: IBM Support #6825029 -- "AIX with Oracle Database on IBM Power Systems Considerations for Performance and Stability".
