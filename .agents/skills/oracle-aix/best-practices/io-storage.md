---
name: oracle-aix-best-practices-io-storage
description: >-
  Use when tuning I/O and storage configuration for Oracle Database on IBM Power Systems / AIX.
  Covers asynchronous I/O (AIO), filesystemio_options, fiber channel adapter tuning (fast_fail,
  dyntrk, multiple queues), hdisk qdepth/transfer size, multi-path I/O (MPIO), VSCSI tuning,
  LVM volume group and logical volume striping, JFS2 mount options (CIO/DIO/buffer cache),
  ASM disk group layout, RBNA, redo 4K block size, buffer cache sizing, IBM Spectrum Scale (GPFS),
  OS-level limits for Oracle, and storage best practices. Trigger phrases:
  "Oracle AIX IO tuning", "hdisk qdepth Oracle", "JFS2 concurrent IO Oracle", "ASM AIX storage",
  "fiber channel Oracle AIX", "volume group striping Oracle", "MPIO Oracle", "lv striping",
  "oracle storage AIX", "jfs2 mount options Oracle", "asm disk group AIX", "rdisk Oracle AIX",
  "npiv AIX Oracle", "fc adapter tuning AIX", "io_latency", "rbna jfs2",
  "filesystemio_options AIX", "aio Oracle AIX", "disk_asynch_io", "noatime oracle",
  "4k redo oracle aix", "buffer cache oracle aix", "db_cache_size oracle aix",
  "spectrum scale oracle", "gpfs oracle", "maxuproc oracle", "security limits oracle aix",
  "offload_iodone aix oracle", "asm storwize hbeatiowait", "vscsi oracle", "fc fast fail aix".
---

# Oracle Power I/O and Storage Tuning

Expert guidance for I/O and storage configuration for Oracle Database on IBM Power Systems / AIX.
Source: IBM Power Systems VUG May 2024 sessions by Ralf Schmidt-Dannert, IBM ATG Principal Power Specialist.
Slide deck: `OracleOnPowerTuningConsiderations_AIX_IO_Misc_NEXT.pptx` (~116 slides).

---

## 1. I/O Optimization Strategy

**Priority order** (highest ROI to lowest):

1. **Reduce the amount of I/O** (DBA responsibility):
   - Verify indexes exist and are used (not all indexes are beneficial — some hurt performance).
   - Use table/index **partitioning** to avoid full-table scans.
   - Tune parallel query to avoid re-reading the same data multiple times.
   - Maximize **buffer cache hit ratio** — see section 13 for tuning guidance.
   - Evaluate **Oracle In-Memory** for data warehouse workloads.

2. **Optimize I/O service time and throughput** (Sysadmin + Storage team):
   - Flash/SSD storage: target < 1ms for 8KB block reads.
   - Correct storage layout: spread I/O across maximum physical resources.
   - Tune fiber channel stack and hdisk parameters.
   - Use software striping (LV striping or ASM) to distribute I/O.
   - In PowerVS: ensure the correct I/O tier is selected (see `oracle-aix-best-practices-misc`).

> **Key principle**: The DBA, system administrator, and storage administrator must collaborate.
> Finger-pointing between teams is the most common cause of delayed problem resolution.

---

## 2. The AIX I/O Stack for Oracle

From top to bottom:

```
Oracle Database (buffer cache → ASM or JFS2)
    ↓
ASM (raw LVs) or JFS2 filesystem (with/without file cache)
    ↓
Logical Volume Manager (LVM) + disk driver (with cache/queue)
    ↓
Virtual Fiber Channel client adapter (vfclient) — in the LPAR
    ↓
Virtual I/O Server (VIOS) — physical adapter queue
    ↓
Fiber Channel SAN fabric
    ↓
Storage array (controllers + physical disks / NVMe / Flash)
```

Each layer has its own **queue depth** and **maximum transfer size** — these must be tuned in concert.

> **Note**: Raw LVs are **not** supported with Oracle 12c+ databases directly — only as devices
> used for ASM. Oracle data/redo/control files must use JFS2 or ASM.

---

## 3. Asynchronous I/O (AIO)

Asynchronous I/O allows multiple I/O requests to be sent without waiting for each to complete.
**Use of AIO is strongly advised** regardless of mount option (JFS2, CIO, DIO, or ASM).

### AIO for JFS2 Filesystems — `aio_fsfastpath`

```bash
# AIX 6.1+ default: aio_fsfastpath=1 (restricted parameter — do not change)
ioo -a | grep aio_fsfastpath   # Should show 1

# If CIO + AIX 7.x is in use, fsfast_path handles AIO automatically.
# No manual AIO server pool management is needed for JFS2+CIO with aio_fsfastpath=1.
```

### AIO for ASM / Raw Devices — `aio_fastpath`

```bash
# AIX 6.1+ default: aio_fastpath=1 (restricted — do not change)
ioo -a | grep aio_fastpath     # Should show 1

# For ASM environments, also verify:
ioo -Fa    # Lists all restricted parameters and their current values
```

### AIO Server Pool (Legacy — for JFS2 without fastpath)

These parameters matter when `aio_fsfastpath=0` or on older AIX levels:

```bash
# Check current AIO configuration
ioo -a | grep aio_

# Key parameters:
# aio_minservers = 3     (minimum AIO server processes per logical CPU)
# aio_maxservers = 30    (maximum AIO server processes per logical CPU)
# aio_maxreqs = 65536    (maximum concurrent AIO requests)

# Adjust if needed (example for high-concurrency system):
ioo -p -o aio_maxservers=60 -o aio_maxreqs=65536

# Monitor AIO server usage
pstat -a | grep aios   # Shows active AIO server processes
nmon -A                # AIO view (interactive or spreadsheet mode)
```

### Warning: `lio_listio EAGAIN` in Alert Log

```
Warning "lio_listio returned EAGAIN"
```
This message in the Oracle alert log or trace files indicates:
- `aio_maxservers` is set too low, **or**
- `aio_maxreqs` is too low, **or**
- The storage subsystem is overwhelmed and cannot keep up.

**Action**: Check AIX system error log first (`errpt`), then increase `aio_maxservers` and `aio_maxreqs`.

### Oracle AIO Parameters

| Parameter | Default on AIX | Recommended |
|---|---|---|
| `disk_asynch_io` | TRUE | Keep TRUE — disabling forces synchronous I/O |
| `filesystemio_options` | NONE | **SETALL** (see section 9) |

---

## 4. hdisk (LUN) Tuning

Each `hdisk` in AIX represents one LUN from the storage array.

### Key hdisk Parameters

```bash
# List all tunable attributes for an hdisk
lsattr -El hdisk0

# Identify which parameters can be changed live (AIX 7.3+)
# Look at the "user_settable" column in the output; additionally:
lsattr -El hdisk0 | grep True
# "True+"  = changeable while hdisk is ACTIVE (in a VG or ASM DG) — no unmount, no varyoff
# "True"   = changeable only when hdisk is NOT in a VG (varyoff first)
# "False"  = cannot be changed at runtime
```

| Parameter | Recommended Value | Notes |
|---|---|---|
| `queue_depth` | 32–64 (production) | **Max is 256**. In high-IOPS environments this limit is often a bottleneck. Use 8+ LUNs. |
| `max_transfer` | `0x100000` (1MB) | Match to Oracle's typical sequential I/O. Some storage supports up to `0x400000` (4MB). |
| `reserve_policy` | `no_reserve` | **Required** when using multi-path I/O. Without this, only one path is used. |
| `algorithm` | `shortest_queue` (default) | Use `round_robin` for CPU-constrained or uniform I/O size workloads (OLTP). |
| `rw_timeout` | leave default | Increasing rarely helps; may mask storage subsystem problems. |

```bash
# Change qdepth live (AIX 7.3+ with "True+" attribute)
chdev -l hdisk0 -a queue_depth=64 -U

# Change max_transfer (may require hdisk not in VG on older AIX)
chdev -l hdisk0 -a max_transfer=0x100000

# Set no_reserve on all hdisks in a VG
for d in $(lsvg -p oravg | awk 'NR>2{print $1}'); do chdev -l $d -a reserve_policy=no_reserve; done
```

### Diagnosing qdepth Saturation

```bash
iostat -D hdisk0 5
# "sqfull" column: non-zero = hdisk queue is filling up → increase queue_depth
# "serv" column: service time; if < 1ms but sqfull > 0 → storage is fine, queue is the bottleneck
```

### Critical: Maximum qdepth = 256

In high-IOPS environments, the 256 qdepth limit per hdisk is a hard bottleneck.
**Solution**: Use multiple hdisks (LUNs) — 8 per pool is the typical starting point.
Modern flash arrays can carve 8 × 100GB LUNs instead of 1 × 800GB with no physical impact.

### Storage Subsystem Overload Warning

Some SAN storage systems **silently drop** I/O requests when overloaded. AIX has no visibility
into dropped I/Os — it starts a **timeout (seconds)** before retrying. Increasing `queue_depth`
on an already-overloaded storage subsystem typically makes performance **worse**.

---

## 5. Fiber Channel Adapter Tuning

### NPIV (Virtual Fiber Channel) Architecture

- Physical FC adapters reside in the **Virtual I/O Server (VIOS)**.
- LPAR uses **virtual FC client adapters** (vfclient/fcs) mapped to VIOS physical ports.
- **Rule**: `num_cmd_elems` and `max_xfer_size` in the LPAR's FC adapter must be **≤** the
  corresponding values in the VIOS physical adapter port.

```bash
# Check FC adapter parameters in the LPAR
lsattr -El fcs0
lsattr -El fscsi0

# Key parameters:
# num_cmd_elems = max concurrent outstanding I/Os on this adapter port
# max_xfer_size = maximum I/O transfer size (typically 1MB–4MB)
```

### Recommended FC Adapter Settings

```bash
# Enable fast failover for multi-path I/O (critical — prevents long path failover times)
chdev -l fcs0 -a fc_err_recov=fast_fail

# Enable dynamic tracking (recovers automatically from N_Port ID changes — e.g., after fabric events)
chdev -l fcs0 -a dyntrk=yes

# Set max transfer size (must be >= value set at hdisk level; if default is higher, do NOT reduce)
chdev -l fcs0 -a max_xfer_size=0x100000   # 1MB

# Verify changes are persistent
lsattr -El fcs0 | grep -E "fc_err_recov|dyntrk|max_xfer_size"
```

### Calculating `num_cmd_elems`

```
num_cmd_elems (per HBA) = sum of queue_depth of all hdisks on that HBA port / number of HBA ports
```

```bash
# Check current num_cmd_elems
lsattr -El fcs0 | grep num_cmd_elems

# Monitor for exhaustion — look for non-zero values in:
fcstat fcs0 | grep -E "No Command Resource|No Adapter Elements"
# If these are non-zero, increase num_cmd_elems

# Increase num_cmd_elems (requires device to be unused OR use -P flag + reboot):
chdev -l fcs0 -a num_cmd_elems=2048 -P   # -P = pending (takes effect after reboot)
# For physical FC adapters in VIOS: 2048 recommended; 3200 supported with latest VIOS + adapters
```

> **APAR requirement for NPIV adapters > 256**: `num_cmd_elems > 256` for NPIV (virtual FC
> client) adapters requires two APARs to be applied:
> - "INCREASED UPPER LIMIT OF NUM_CMD_ELEMS FOR NPIV ADAPTER TO 2048"
> - "POTENTIAL DATA LOSS USING VIRTUAL FC WITH NUM_CMD_ELEMS > 256"
>
> Verify both APARs are applied before setting `num_cmd_elems > 256` on NPIV adapters.
> Physical FC adapters in VIOS do not have this restriction.

### FC Multiple I/O Queues (AIX 7.2 TL5+)

AIX 7.2 TL5+ added support for **multiple I/O queues per FC port** for both physical and NPIV
adapters (requires current FC adapter hardware).

```bash
# Check if multiple queue support is available on this adapter
lsattr -El fcs0 | grep num_io_queues
# If present, multiple queues are supported

# Note: a new multi-threaded kernel process (emfc_kproc) manages I/O queues.
# Under very high I/O workloads, emfc_kproc can consume significant CPU.
# Monitor with: topas or ps -ef | grep emfc
```

### Removing Uncabled / Unused FC Ports

FC adapter ports with no attached cables or devices cause `cfgmgr` to scan them (adding scan
time) and generate `FCA_ERR4` / `FCA_ERR12` entries in the system error log. Remove them:

```bash
# Remove an unused FC SCSI protocol device from ODM
mdev -l fscsi0 -R
chdev -l fscsi0 -a autoconfig=defined
# This prevents cfgmgr from trying to discover devices on that port at boot/cfgmgr time
```

### Diagnosing FC Adapter Issues

```bash
# Detailed FC statistics including high-watermark and error counts (AIX 7.3 TL2 SP1+)
fcstat -d fcs0
# Key fields:
# - "High water mark of active commands" → compare to num_cmd_elems
#   If high-watermark >= num_cmd_elems → increase num_cmd_elems
# - "No Command Resource Count" → resource exhaustion (increase num_cmd_elems)
# - "No DMA Resource Count" → DMA memory exhaustion (contact IBM Support)
# - max_xfer_size shown as "active" value

# Virtual FC adapter details (AIX 7.3 TL2 SP1+)
fcstat -vd vfchost0   # or: vfcstat -d fcs0 -f tunables
# Shows: requested vs. granted queue depths, NVMe-oF queues, WWPN, physical adapter mapping
```

### Finding the WWPN for SAN Zoning

```bash
# Fastest method (AIX 7.3 TL2 SP1+):
fcstat -vd vfchost0
# or:
# vfcstat -d fcs0 -f wwpn
# Shows VFC adapter → VIOS physical port location code → WWPN
```

### Device Interrupt Handling Change (AIX 7.2 TL5+ / AIX 7.3)

AIX changed I/O interrupt handling to **kernel threads** (`kprocs`) for scalability. In
high-load environments, kernel thread scheduling latency can increase vfclient I/O service times.

```bash
# Mitigation: give I/O kernel threads higher scheduling priority
schedo -a | grep io_latency
# If io_latency != 1:
schedo -p -o io_latency=1
```

---

## 6. VSCSI Adapter Tuning

For environments using VSCSI (virtual SCSI) rather than NPIV:

```bash
# Enable fast failover for VSCSI multi-path
chdev -l vscsi0 -a vscsi_err_recov=fast_fail

# Enable health check path to VIOS
chdev -l vscsi0 -a vscsi_path_to=30

# Verify settings
lsattr -El vscsi0 | grep -E "err_recov|path_to"
```

### Maximum LUNs per VSCSI Adapter

```
Max LUNs = (num_cmd_elems - 2) / (queue_depth + 3)
```

Example: `num_cmd_elems=512`, `queue_depth=32` → max = (512-2)/(32+3) = **14 LUNs per adapter**

If more LUNs are needed, **add additional VSCSI adapters** rather than exceeding this limit.

---

## 7. Storage Layout Strategy

### Guiding Principle: Spread I/O Over All Physical Resources

**Do not** manually separate I/O types to specific devices. This degrades as data volumes
grow and requires constant re-tuning.

**Preferred**: Distribute all I/O of a given type evenly across as many LUNs/hdisks as possible.

### Minimum Layout

| Pool | # hdisks | Notes |
|---|---|---|
| Oracle data/index/temp | 8 (multiples of 8 for large DBs) | Starting point; scale in multiples of 8 |
| Oracle redo logs | 4–8 | Separate pool from data; redo is sequential small I/O |
| OCR/Voting (RAC) | 3 | Standard RAC requirement |
| Oracle binaries | 2 | Separate from database data |

- **Temp**: if workload has very large I/O sizes (parallel sort/hash), consider a **separate
  temp pool** so large temp I/O does not compete with OLTP 8KB random I/O.
- **Flashback log area**: if flashback logging is enabled, consider a dedicated pool shared with
  archive logs (both are sequential write workloads).

---

## 8. ASM Disk Group Layout on AIX

ASM automatically stripes data across all disks in a disk group. Each `hdisk` = one ASM disk.

### Correct ASM on AIX Layout

```bash
# For each LUN in a disk group, create ONE raw logical volume per hdisk:
# (do NOT add hdisks directly to ASM — use raw LVs on AIX)
mkvg -f -y oradg_vg hdisk1 hdisk2 hdisk3 hdisk4 hdisk5 hdisk6 hdisk7 hdisk8
mklv -y oradg_lv01 -t raw oradg_vg 1        # 1 physical partition = one hdisk worth
mklv -y oradg_lv02 -t raw oradg_vg 1
# ... repeat for each hdisk
# Then add /dev/roradg_lv01, /dev/roradg_lv02, etc. to ASM disk group

# ASM Allocation Unit (AU) size default = 1MB. Increase for large databases / DW:
# ALTER DISKGROUP data SET ATTRIBUTE 'AU_SIZE' = '4M';  -- 4MB or 8MB
# AU_SIZE can only be set at disk group CREATION time.
```

### ASM Redundancy

| Storage Type | Recommended ASM Redundancy | Reason |
|---|---|---|
| Enterprise SAN (FlashSystem, etc.) | **External** | Storage has built-in RAID; ASM redundancy doubles I/O for no benefit |
| Internal JBOD / no hardware RAID | Normal or High | No hardware redundancy below ASM |

```sql
-- Create disk group with external redundancy (for enterprise SAN):
CREATE DISKGROUP data EXTERNAL REDUNDANCY
  DISK '/dev/roradg_lv01','/dev/roradg_lv02','/dev/roradg_lv03','/dev/roradg_lv04',
       '/dev/roradg_lv05','/dev/roradg_lv06','/dev/roradg_lv07','/dev/roradg_lv08'
  ATTRIBUTE 'compatible.asm'   = '19.0',
            'compatible.rdbms' = '19.0',
            'au_size'          = '4M';
```

> **Critical**: An ASM disk and an AIX VG both use the **first block** of a disk for management
> data. Adding an ASM disk to a VG corrupts ASM metadata and will likely crash the disk group
> and the Oracle database. AIX 7.2+ prevents this by default, but `chdev -f` (force) bypasses it.

### Protecting ASM Disks

```bash
# Rename hdisks to show ASM usage (use lkdev, not chdev, to lock)
rendev -l hdisk5 -n hdiskASM5

# Lock the disk: prevents chdev, rmdev, chpath, rmpath
lkdev -l hdiskASM5 -a -c "asmdisk"

# Verify lock status
lkdev                             # Lists all locked devices and labels
lspv hdiskASM5                    # Shows "locked" in status field

# Verify: no PVID should be set (ASM disk must not belong to a VG)
lspv hdiskASM5 | grep -i pvid
```

### Consistent hdisk Naming in RAC

```bash
# Each RAC node must have identical hdisk name ↔ LUN mapping
lsmpio -q     # Shows: Vendor, Product, Size, Volume Name per hdisk
# Compare output across all RAC nodes — names and LUN mappings must match
# Can be automated with Ansible

# Example output:
# hdiskADT1 IBM 2145 100GiB data-lun-01
# hdiskADT2 IBM 2145 100GiB data-lun-02
```

### Monitoring ASM I/O with nmon

```bash
# Create nmon ASM definition file
cat > /etc/nmon_asmdef << 'EOF'
CRS    hdiskAO1 hdiskAO2 hdiskAO3
FRECO  hdiskAR1 hdiskAR2 hdiskAR3 hdiskAR4
DATA   hdiskAD1 hdiskAD2 hdiskAD3 hdiskAD4 hdiskAD5 hdiskAD6 hdiskAD7 hdiskAD8
EOF

nmon -g /etc/nmon_asmdef    # Interactive: press 'g' for ASM disk group I/O view
# Shows: disks per group, busy%, KB/s read/write, IO/s — maximum 64 groups
nmon -f -g /etc/nmon_asmdef -V   # Capture for nmon_analyser
```

### ASM Storwize / IBM Storage Rolling Upgrade Pitfall

When performing a rolling Storwize (IBM Storwize/FlashSystem) controller node software upgrade,
temporary path failures can cause ASM to dismount disk groups:

```
ORA-15064: "Waited 15 secs for write IO to PST"
```

```sql
-- Increase ASM heartbeat I/O wait timeout to prevent dismount during rolling upgrades
ALTER SYSTEM SET "_asm_hbeatiowait" = 120 SCOPE=SPFILE;
-- Restart ASM instance for spfile change to take effect
-- Applies to Oracle 11.2.0.3 to 12.1.0.1; see MOS Doc ID 1581684.1
```

---

## 9. JFS2 Mount Options and `filesystemio_options`

### Preferred Method: `filesystemio_options=SETALL`

The preferred way to activate CIO for Oracle on JFS2 is via the **Oracle parameter**
`filesystemio_options=SETALL` — **not** the AIX CIO mount option on the filesystem.

```sql
-- Check current setting
SHOW PARAMETER filesystemio_options;

-- Set preferred value (requires restart to take effect from spfile)
ALTER SYSTEM SET filesystemio_options = SETALL SCOPE=SPFILE;
-- SETALL = asynchronous I/O + CIO for JFS2 (or CIO-equivalent DIO on JFS)
```

> If `filesystemio_options=SETALL`, the AIX CIO mount option on the filesystem is typically
> **not needed**. However, `filesystemio_options=ASYNCH` can still be combined with the
> AIX CIO mount option if desired.

### `filesystemio_options` × JFS2 Mount Option Interaction Matrix

| Oracle `filesystemio_options` | JFS2 default mount | JFS2 `cio` mount |
|---|---|---|
| `ASYNCH` | Asynchronous, cached | Asynchronous, CIO |
| **`SETALL`** | **Asynchronous, CIO** | Asynchronous, CIO |
| `DIRECTIO` | Synchronous, CIO (no cache, no async) | Synchronous, CIO |
| `NONE` | Synchronous, cached | Synchronous, CIO |

> `DIRECTIO` and `NONE` **disable asynchronous I/O** and should not be used in production.

### JFS2 Mount Option Decision Matrix

| Workload / File Type | Recommended | Notes |
|---|---|---|
| Oracle data/index files | `filesystemio_options=SETALL` (preferred) or `cio` mount | No file cache; no inode lock. Most common for Oracle. |
| Oracle redo / control files | `cio` or `SETALL`, **dedicated FS**, `agblksize=512` | Dedicated FS mandatory — redo + data in same FS is severe perf issue |
| Flashback log files | CIO or DIO | Sequential writes sized as multiples of `db_block_size` |
| Archive logs / RMAN backups | `dio` or `rbrw` (release-behind read/write) | Sequential write-once; `rbrw` releases page immediately after I/O |
| Oracle binaries | Standard mount (no CIO/DIO/RBRW), `noatime` | Must stay in file cache; single-writer/multi-reader semantics required |
| Staging / ETL / heavy sequential re-reads | JFS2 buffer cache (default) | Only when same data is frequently re-read |
| Oracle audit logs / trace files | `cio` or dedicated FS, `noatime` | Can generate significant I/O — avoid hot spots by keeping on separate FS |

```bash
# Enable CIO for Oracle data (persistent in /etc/filesystems):
# options = rw,cio
mount -o cio /oradata        # Temporary test

# noatime: suppress access-time updates (use for all Oracle file systems unless auditing requires it)
# Add to /etc/filesystems: options = rw,noatime
# or with CIO: options = rw,cio,noatime

# Verify current mount options
mount | grep /oradata
```

> **Note**: When `filesystemio_options=SETALL` is active, archive logs and RMAN backup files
> are also written with CIO (bypassing the file cache). DIO mount option is not needed.

### CIO vs. DIO

- **CIO (Concurrent I/O)**: No file cache, no inode lock → multiple threads write to the same
  file concurrently. Best for all Oracle database files.
- **DIO (Direct I/O)**: No file cache, but inode lock still held → single writer per file.
  Best for sequential workloads (backups, exports) if CIO is not active.
- **Buffer cache** (default): Uses JFS2 file cache. Beneficial only for parallel queries that
  repeatedly scan the same data, or workloads with high re-read rates.

### `noatime` Mount Option

Always add `noatime` to JFS2 filesystems used by Oracle, unless a security application
explicitly requires access-time tracking. Without it, every read updates the inode's atime,
generating metadata write I/O.

```bash
# Check if noatime is set
mount | grep /oradata
# If not set, add to /etc/filesystems and remount
```

### Parallel Query Exception — When File Cache Helps

Parallel queries discard their data (read into PGA) after execution. If the same query
runs repeatedly, data is re-read from storage each time. JFS2 file cache acts as a secondary
buffer:

| Execution Type | I/O Mode | Observed Latency (IBM ATG Test) |
|---|---|---|
| Serial, 1MB I/O | CIO | 2.76ms |
| Parallel, 1MB I/O | CIO | 95ms (storage overloaded) |
| Parallel, 1MB I/O | JFS2 cache | 0.6ms (data served from cache) |

For heavy DW parallel scan workloads that repeatedly re-read the same data: consider
`DB_BIG_TABLE_CACHE_PERCENT_TARGET` to dedicate part of the buffer cache for parallel reads.

```sql
-- Enable parallel query buffer cache for large tables
ALTER SYSTEM SET db_big_table_cache_percent_target = 50;  -- 50% of buffer cache
-- Combined with parallel_degree_policy = AUTO or ADAPTIVE
ALTER SYSTEM SET parallel_degree_policy = AUTO;
-- MOS: "How To Use Optimizer Processing Rate Statistics" (Doc ID 2253387.1)
```

---

## 10. Redo Log Optimization

### Dedicated JFS2 Filesystem for Redo Logs

Redo and control files **must** be on a dedicated JFS2 filesystem with `agblksize=512`.
Sharing a filesystem with data files is one of the most common causes of severe redo write latency.

```bash
# Create dedicated FS for redo logs
crfs -v jfs2 -d /dev/redo_lv -m /oraredo \
     -a agblksize=512 \
     -a logname=INLINE \
     -A yes
```

> `agblksize` **cannot be changed after filesystem creation** — set it correctly at creation time.

### CIO Demoted I/O — Avoiding "Demoted" Status

If `agblksize` is mismatched for the I/O size, JFS2 silently demotes CIO to DIO or cached I/O.
This is a hard-to-diagnose performance degrader. The correct `agblksize` per file type is covered
in **section 15**. Always create redo/control filesystems with `agblksize=512` before populating.

### 4KB Redo Block Size Option (Flash Storage)

For Oracle 11.2.0.3+ on flash storage, redo logs can use 4KB block size instead of 512B.
This reduces redo wastage (padding to 512B boundaries) and can improve redo write throughput.

```sql
-- Step 1: Enable 4KB sector size override (add to spfile, restart required)
ALTER SYSTEM SET "_disk_sector_size_override" = TRUE SCOPE=SPFILE;

-- Step 2: After restart, add new 4KB redo logs
ALTER DATABASE ADD LOGFILE GROUP 5 '+RECO' SIZE 5G BLOCKSIZE 4096;

-- Step 3: Drop the old 512B redo log groups (once groups are INACTIVE)
ALTER DATABASE DROP LOGFILE GROUP 1;
-- Monitor AWR for "redo wastage" to confirm improvement
```

> For Oracle 12.2+, also see ASM disk group `sector_size` attribute for native 4KB support.

---

## 11. LVM Volume Group and Logical Volume Striping (JFS2)

When using JFS2 (non-ASM), use LVM striping for I/O distribution.

### Option 1: Logical Volume Striping (Recommended)

```bash
# Create VG with 8 hdisks, PP size 32MB (scalable VG required for striped LVs)
mkvg -S -f -y oravg -s 32 hdisk1 hdisk2 hdisk3 hdisk4 hdisk5 hdisk6 hdisk7 hdisk8
# -S = scalable VG

# Create striped LV (MUST be done manually — smitty does not expose all options)
mklv -y data_lv01 -t jfs2 -e x -S 1M oravg 80
# -e x  = maximum spread (round-robin allocation across all hdisks in VG)
# -S 1M = stripe size (1MB matches Oracle's typical sequential I/O)
# 80    = number of PPs (grow in multiples of 8 = N hdisks)

# Create JFS2 filesystem on the LV (do NOT use smitty "create filesystem" — it creates its own LV)
crfs -v jfs2 -d /dev/data_lv01 -m /oradata -A yes -a logname=INLINE
```

**Space growth must be in multiples of N × PP_size** (N = number of hdisks). Growing by less
wastes space because the LV allocation is rounded up but the filesystem cannot use the fraction.

### Option 2: PP Striping ("Poor Man's Striping")

- Small PP sizes (8–32MB) with maximum spread (`-e x`) distribute allocation round-robin.
- Simpler but coarser: a single hot file may land on one PP → one hdisk (hot spot).
- Keep PP sizes ≤ 32MB for Oracle workloads to minimize hot-spot impact.
- Avoid VGs with > ~60,000 PPs (VG management commands slow down).

```bash
# PP striping example
mkvg -S -f -y oravg -s 8 hdisk1 hdisk2 hdisk3 hdisk4   # 8MB PP size
mklv -y data_lv01 -t jfs2 -e x oravg 64                # 64 PPs, max spread
crfs -v jfs2 -d /dev/data_lv01 -m /oradata -A yes -a logname=INLINE
```

### Growing a JFS2 Striped Filesystem

> **⚠️ APAR IJ46487**: Potential undetected data loss after running `chvg -ky` or `chvg -g`.
> Verify your AIX level has this APAR applied before running either command.

```bash
# Preferred: Expand LUNs on storage array, then rediscover — no SAN fabric changes needed
cfgmgr              # Rediscover new disk sizes
chvg -g oravg       # Update VG with new disk sizes (CRITICAL — without this, AIX won't see new space)
                    # ⚠️ Check APAR IJ46487 is applied first
extendlv data_lv01 8   # Grow by 8 PPs (= 1 PP per hdisk for 8-disk VG)
chfs -a size=+8G /oradata

# Alternative (complex): Add additional LUNs to VG + stripe columns
# Creates uneven distribution; requires SAN zoning changes; not recommended
# If unavoidable: add N new LUNs to VG, then manually extendlv to the new hdisks
```

> **ASM 2TB LUN size limit**: ASM has a maximum LUN (disk) size of 2TB. When growing LUNs
> dynamically via the storage array, ensure the resulting LUN does not exceed 2TB for ASM disks.

> **JFS2 Inline Log**: Always use `logname=INLINE` when creating JFS2 filesystems for Oracle.
> Inline logging avoids a shared external JFS2 log that becomes a hot spot at high I/O rates.

### LVM Physical Buffers (pbuf) and JFS2 Buffer Shortages

LVM uses physical buffers (`pbuf`) to queue I/O between LVM and disk drivers. JFS2 uses
separate buffer pools (`fsbuf`). Exhaustion of either blocks I/O.

```bash
# Full buffer shortage diagnostic
vmstat -v | tail -8
# Line-by-line interpretation:
# "pending disk I/Os blocked with no pbuf"         → LVM pbuf shortage
#   Fix: lvmo -v <vgname> -o pv_min_pbuf=512; varyoffvg <vg>; varyonvg <vg>
#
# "paging space I/Os blocked with no psbuf"        → paging space exhausted
#   Fix: add more paging space or reduce memory pressure
#
# "filesystem I/Os blocked with no fsbuf"          → JFS (not JFS2) fsbuf shortage
#   Fix: ioo -p -o numfsbufs=1568  (restricted parameter — rarely needed for JFS2)
#
# "external pager filesystem I/Os blocked with no fsbuf" → JFS2 fsbuf shortage
#   Fix step 1 (dynamic, try first): ioo -o j2_dynamicBufferPreallocation=128
#   Fix step 2 (restricted, requires unmount/remount):
#              ioo -p -o j2_nBufferPerPagerDevice=2048
#              (unmount and remount affected JFS2 filesystems for change to take effect)

# Increase LVM pbufs for a specific VG (requires VG offline)
lvmo -v oravg -o pv_min_pbuf=512    # Default is 512 per PV; increase if persistent blocking
varyoffvg oravg
varyonvg oravg
```

> Reference: https://www.ibm.com/docs/en/aix/7.3?topic=performance-file-system-tuning

---

## 12. RBNA (Reserved But Not Allocated) — JFS2 Sequential Pre-allocation

Available: AIX 7.2 TL4+, AIX 7.3

Pre-allocates sequential extents for sequential file I/O, reducing fragmentation and metadata
overhead. Critical for:
- Concurrent tablespace creation (multiple data files added simultaneously)
- Parallel index builds / data imports
- RMAN backup/restore with multiple channels

```bash
# Set RBNA for a specific filesystem (512 = maximum, recommended for Oracle DB filesystems)
chfs -a options=j2_nPagesPerRBNACluster=512 /oradata

# Or set globally for all new filesystems
ioo -p -o j2_nPagesPerRBNACluster=512

# Check current fragmentation / extent layout
fileplace -pv /oradata/datafile01.dbf    # Shows extent-to-LV-to-hdisk mapping

# Defragment existing layout (I/O intensive — do offline or before DB creation)
defragfs /oradata
```

---

## 13. Buffer Cache Tuning for I/O Reduction

The database buffer cache is the primary I/O avoidance mechanism. Small increases in hit% can
have dramatic effects:

> **At 98% hit ratio**: a 1% improvement (to 99%) **reduces physical I/O by 50%**.

**IBM ATG test result** (9TB batch/transactional DB, same workload):

| Buffer Cache Size | User I/O Wait | Total "In DB" Time |
|---|---|---|
| 6.5 GB | Baseline | Baseline |
| 101.5 GB | −91% | −79% |

```sql
-- Check current buffer cache hit ratio
SELECT 1 - (phyrds.value / (dbgets.value + congets.value)) AS hit_ratio
FROM   v$sysstat phyrds,
       v$sysstat dbgets,
       v$sysstat congets
WHERE  phyrds.name  = 'physical reads'
  AND  dbgets.name  = 'db block gets'
  AND  congets.name = 'consistent gets';

-- Current cache size
SHOW PARAMETER db_cache_size;

-- Increase cache (online, within SGA_TARGET)
ALTER SYSTEM SET db_cache_size = 50G;
-- or increase sga_target to allow Oracle to allocate more automatically
ALTER SYSTEM SET sga_target = 200G;
```

---

## 14. IBM Spectrum Scale (GPFS) Specific Tuning

When Oracle is deployed on IBM Spectrum Scale (GPFS) rather than JFS2 or ASM:

```bash
# Key difference: Oracle's filesystemio_options is IGNORED for GPFS
# Must use Oracle disk_asynch_io=TRUE (controls AIO at the Oracle layer)

# GPFS asynchronous I/O worker threads (equivalent to AIO servers)
mmchconfig workerThreads=512 -i
# Ensure aio_maxservers >= (workerThreads / num_cpus) + 10

# GPFS filesystem page pool (file system buffer cache — used for Oracle binaries, not .dbf)
mmchconfig pagepool=100M -i

# GPFS maximum outstanding I/Os
mmchconfig ipqmaxlen=512 -i

# GPFS block size for Oracle files
# For .dbf files: 512KB or 1MB
# For Oracle binaries: 256KB
# Set at filesystem creation (mmcrfs -Q yes -B <blocksize>)
```

> See MOS Note **2587696.1** for the current IBM Spectrum Scale Oracle tuning guidance.

---

## 15. JFS2 `agblksize` — Filesystem Block Size

The JFS2 allocation block size (`agblksize`) must match Oracle's minimum I/O size for each file
type. A mismatch causes JFS2 to silently demote CIO to DIO or buffered I/O.

> **`agblksize` cannot be changed after filesystem creation.** Set it correctly before creating
> any Oracle files on the filesystem.

| Oracle File Type | JFS2 `agblksize` | Notes |
|---|---|---|
| Data files (8KB DB block) | 4096 (default) | Default JFS2 agblksize matches |
| Data files (16KB DB block) | 4096 (default) | Default works |
| Data files (2KB DB block) | 2048 | Must set at filesystem creation |
| Redo / control files (default 512B sector) | **512** | Dedicated FS required; set at creation |
| Redo / control files (4KB sector — 11.2.0.3+) | 4096 (default) | Use with `_disk_sector_size_override=TRUE` |

```bash
# Create JFS2 FS for redo logs — correct agblksize is critical
crfs -v jfs2 -d /dev/redo_lv -m /oraredo \
     -a agblksize=512 \
     -a logname=INLINE \
     -A yes

# Create JFS2 FS for data files — default agblksize=4096 is correct, but set explicitly:
crfs -v jfs2 -d /dev/data_lv -m /oradata \
     -a agblksize=4096 \
     -a logname=INLINE \
     -A yes
```

---

## 16. OS-Level Limits for Oracle

### `/etc/security/limits`

For the Oracle software owner, `oracle`, `grid`, and `root`:

```bash
# View and edit OS-level resource limits
lsuser -a "data nofiles stack data" oracle

# Set all limits to unlimited except core for Oracle/Grid users
# In /etc/security/limits:
# oracle:
#     fsize = -1        (unlimited file size)
#     core  = 0         (no core dumps — or set to reasonable limit)
#     cpu   = -1        (unlimited CPU time)
#     data  = -1        (unlimited data segment)
#     rss   = -1        (unlimited resident set size)
#     stack = -1        (unlimited stack size)
#     nofiles = -1      (unlimited open file descriptors)

chuser "nofiles=-1" oracle
chuser "nofiles=-1" grid
```

### User Capabilities for Oracle/Grid Processes

Oracle and Grid Infrastructure processes require specific AIX capabilities beyond standard user
permissions:

```bash
# Grant required capabilities to Oracle and Grid software owners
chuser capabilities=CAP_NUMA_ATTACH,CAP_BYPASS_RAC_VMM,CAP_PROPAGATE oracle
chuser capabilities=CAP_NUMA_ATTACH,CAP_BYPASS_RAC_VMM,CAP_PROPAGATE grid

# Capability meanings:
# CAP_NUMA_ATTACH    — allows non-root processes to increase their scheduling priority
# CAP_BYPASS_RAC_VMM — required for oprocd and ocssd.bin to be pinned in memory (RAC)
# CAP_PROPAGATE      — allows parent → child capability propagation

# Verify
lsuser -a capabilities oracle
lsuser -a capabilities grid
```

### `maxuproc` — Maximum User Processes

```bash
# Check current setting
lsattr -El sys0 | grep maxuproc

# For Oracle workloads: should be >= 16384
# For high-concurrency environments (many connections + parallel servers):
#   Set to at least: 128 + PROCESSES + PARALLEL_MAXSERVERS (for all instances in the LPAR)
chdev -l sys0 -a maxuproc=16384
```

### Environment Variables

| Variable | Value | Notes |
|---|---|---|
| `AIXTHREAD_SCOPE` | `S` | System-scope threads; default in AIX 7.x; ensures Oracle threads are scheduled as kernel threads |
| `AIX_TZCACHE` | `ON` | AIX 7.1+; caches timezone info; reduces repeated TZ lookups overhead |
| `LIBPATH` | `$ORACLE_HOME/lib:/usr/lib` | Always use `LIBPATH` on AIX, not `LD_LIBRARY_PATH` |
| `LDR_CNTRL` | see IBM ATG note | Controls loader control flags; see IBM Support #6825029 for current recommendations |

```bash
# Verify AIXTHREAD_SCOPE
echo $AIXTHREAD_SCOPE   # Should be S

# For Oracle startup via srvctl, set env vars in Oracle config:
srvctl setenv database -db mydb -envs "AIXTHREAD_SCOPE=S,AIX_TZCACHE=ON"
```

### Time Synchronization for RAC

```bash
# RAC requires tightly synchronized clocks across all nodes.
# Use xntpd with the -x flag to prevent backward time jumps (which can cause node eviction):
# In /etc/rc.tcpip or /etc/inittab, ensure xntpd is started with -x:
#   /usr/sbin/xntpd -x

# Verify xntpd is running with -x flag
ps -ef | grep xntpd
```

---

## 17. Key Monitoring Commands for I/O

```bash
# --- Disk / LUN level ---
iostat -D hdisk1 5        # Service time, queue depth, sqfull (saturation), throughput
                          # sqfull > 0 → queue filling; serv < 1ms → storage not the bottleneck

# --- Buffer structure shortages ---
vmstat -v | tail -8
# "pending disk I/Os blocked with no pbuf"       → LVM pbuf shortage      (see section 11)
# "paging space I/Os blocked with no psbuf"      → paging space exhausted
# "filesystem I/Os blocked with no fsbuf"        → JFS (not JFS2) buffer shortage
# "external pager filesystem I/Os blocked..."    → JFS2 fsbuf shortage    (see section 11)

# --- Multi-path I/O ---
lsmpio -q                 # Path count, algorithm, storage subsystem, LUN volume name per hdisk
lspath -l hdisk0          # All paths and state (Enabled/Disabled/Failed)

# --- AIO ---
pstat -a | grep aios      # Active AIO server process count (legacy; informational on AIX 7.x)
nxstat                    # NX hardware accelerator availability and usage stats

# --- Fiber channel ---
fcstat fcs0               # Basic FC adapter stats
fcstat -d fcs0            # Detailed: high-watermark, error counters, DMA exhaustion
fcstat -vd vfchost0       # NPIV virtual adapter: tunables, WWPN, queue depths (AIX 7.3 TL2 SP1+)

# --- LVM / LV layout ---
lsvg -p oravg             # Physical volumes (hdisks) in VG
lsvg -l oravg             # Logical volumes in VG
lslv data_lv01            # LV details: STRIPE SIZE, STRIPE WIDTH, PP count
lslv -m data_lv01         # Physical partition map (which PP is on which hdisk)

# --- Filesystem / file ---
mount | grep /oradata     # Verify mount options (cio, noatime, etc.)
fileplace -pv /oradata/datafile01.dbf   # Extent → LV → hdisk mapping (fragmentation check)

# --- Oracle AWR wait events for I/O ---
# In sqlplus or AWR Top Wait Events:
#   'db file sequential read'  = index / single-block reads  (target < 1ms on flash)
#   'db file scattered read'   = full table / index scan (multiblock)
#   'log file sync'            = redo write latency (LGWR wait — target < 1ms)
#   'log file parallel write'  = physical redo write (target < 1ms on flash)
```

---

## 18. Hardware Compression — `pigz` with `zlibNX` (Power9/Power10/Power11)

Power9, Power10, and Power11 include **NX GZIP hardware acceleration** in each core.
The `pigz` command (parallel gzip, open source) uses the `zlibNX` library on AIX 7.2 TL4+
to leverage this hardware.

> **Correct command is `pigz`** (uses `zlibNX`), not `xgzip` (deprecated, single-threaded)
> and not `pixz` (parallel xz -- different tool entirely).
> `pigz` is installed by default on AIX 7.3; part of base media since AIX 7.2 TL5 SP2+.

**NX GZIP Platform Support** (IBM Community, Brian Veale, IBM Power — confirmed):
| Platform | Minimum | Processor compat mode required |
|---|---|---|
| Power9 | FW940 or later | `POWER9` or `POWER9_Base` (but NOT `POWER9_Base` — see note) |
| Power10 | No additional FW req | `POWER9`, `POWER9_Base`, or `POWER10` |
| Power11 | AIX 7300-03-01+ (native mode) | `POWER9`, `POWER10`, or `POWER11` native |

> ⚠ **`POWER9_Base` mode disables the NX GZIP accelerator** even on Power9/Power10/Power11 hardware. Always run in `POWER9` or `POWER10` or `POWER11` compat mode to get acceleration. Verify with `nxstat -S`.

```bash
# Verify zlibNX availability
lslpp -l zlibNX.rte                  # AIX 7.2: installed via Expansion Pack or TL5 SP2+ media
                                     # AIX 7.3: installed by default

# Verify NX accelerator is active in this LPAR
nxstat -S
# nx_accel_mask = 1  -> GZIP accelerator available
# nx_accel_mask = 0  -> NOT available (check compat mode)

# If accelerator is not available, check the LPAR compatibility mode
lparstat -i | grep -i "compat"
# Must be POWER9, POWER10, or POWER11 -- NOT POWER9_Base

# Hardware-accelerated parallel compression
# Optimal parallelism = 8 (do NOT rely on default -- too many threads)
# Higher compression levels (> default -6) significantly increase runtime with little gain
pigz -p 8 /path/to/backupfile.bkp

# Performance comparison (IBM ATG test, E980, 16 cores, AIX 7.3 TL2 SP1, ~230GB data):
# tar + gzip (single thread):   3h 15m
# tar + pigz -p 8:              4m 31s   → >43× faster
# Note: throughput typically limited by I/O subsystem speed, not CPU

# Use cases:
# - Compress RMAN backup pieces after creation
# - Compress archive log files before shipping to tape or object storage
# - tar + pigz pipelines for large data migrations
# - Output is standard gzip-compatible; readable on any platform
```

> Source: IBM Community blog "GZIP Acceleration with AIX on Power Systems" (Brian Veale, IBM, 2022): https://community.ibm.com/community/user/power/blogs/brian-veale1/2022/03/14/gzip-acceleration-with-aix-on-power-systems
> Also: APAR IJ47907 — potential undetected data loss using zlibNX; verify fix is applied before production use.

---

## 19. Critical AIX APARs Affecting Oracle I/O

### APAR IJ53641 — `offload_iodone` Performance Loss (AIX 7.3 TL3)

**High Impact / Highly Pervasive.** AIX 7.3 TL3 LPARs may experience **lower than expected I/O
performance** due to the default `offload_iodone=1` setting, if the LPAR runs in a non-native
compatibility mode:

- Power8 LPARs
- Power9 LPARs **not** in POWER9 mode
- Power10 LPARs **not** in "default" or POWER10 mode

```bash
# Check current setting
schedo -a | grep offload_iodone

# Workaround (if affected):
schedo -p -o offload_iodone=0

# Permanent fix: upgrade to the fixing AIX level (see IBM Support #7230030)
```

### APAR IJ56896 / IJ56918 — Kernel Memory Leak / LPAR Hang / Crash (AIX 7.3 TL3+)

LPARs with **multiple SRADs** and heavy **shared memory activity** (such as large Oracle SGAs
on multi-chip Power10 or Power11 systems) may experience:
- Kernel heap memory leak
- LPAR hang or crash

```bash
# Identify your AIX level
oslevel -s    # 7300-03-02 = AIX 7.3 TL3 SP2

# Fixing levels:
# AIX 7.3 TL3: fixed in 7300-03-03
# AIX 7.3 TL4: fixed in 7300-04-01
# Interim fixes: IJ56896 (TL4), IJ57120 (TL3)

# Assess SRAD configuration
lssrad -va    # Check if LPAR spans multiple SRADs
```

### APAR IJ38518 — `vmo` Output Format Change Breaks Oracle RAC `cluvfy`

AIX 7.3 changed the default output format of performance tuning commands (including `vmo`).
Oracle RAC `cluvfy` parsing of `vmo` output fails on AIX 7.3 < `7300-00-02`.

```bash
# Fixed in AIX 7300-00-02 or later
oslevel -s    # Verify you are on 7300-00-02 or above
```

### APAR IJ50588 — Oracle RAC Multicast Heartbeat Fails (AIX 7.3 TL1)

Oracle RAC uses IP multicast for heartbeat communication. A defect in AIX 7.3 TL1
prevents multicast IP registration, causing Oracle RAC heartbeat failures:

```bash
# Affected: AIX 7300-01-00 through 7300-01-04 (bos.net.tcp.client_core)
# Fix: update to AIX 7300-01-04-2420 or later
oslevel -s    # Verify TL1 level; if < 7300-01-04, apply fix
```

### AIX 7.3 TL4 — Fiber Channel Improvements

AIX 7.3 TL4 includes:
- **Reduced FC path failover times** for redundant FC configurations (e.g., during VIOS
  maintenance and adapter microcode updates) — directly benefits Oracle database availability.
- NVMe over TCP storage connectivity — tech preview for physical NIC LPARs.

```bash
# Verify AIX level
oslevel -s    # Target: 7300-04-xx for FC failover improvements
```

---

## 20. RAC Network Configuration on AIX

### TCP/IP Parameters for Oracle Public Network

```bash
# Standard parameters for 1GbE or 10GbE Oracle public interfaces:
no -p -o tcp_sendspace=262144    # Must be < sb_max
no -p -o tcp_recvspace=262144    # Must be < sb_max
no -p -o rfc1323=1               # TCP window scaling (required for high-throughput)
no -p -o cached_routes=1         # Cache routing table entries (AIX 7.x)
no -p -o rtentry_lock_complex=1  # Complex routing table locking (default in AIX 7.x)

# Enable TCP fast loopback (for same-LPAR application server + DB connections)
no -p -o tcp_fastlo=1
# Note: APAR IV67463 (AIX 6.1 TL9) / IV66228 (AIX 7.1 TL3) fixes a memory leak with tcp_fastlo

# tcp_nodelay on network adapter (helps RAC interconnect and collocated app servers)
chdev -l en0 -a tcp_nodelay=1

# Verify sb_max (sendspace/recvspace must both be < sb_max)
no -o sb_max
```

### RAC Interconnect — UDP Parameters

```bash
# Private interconnect UDP buffer sizing (must be < sb_max)
no -p -o udp_sendspace=65536
no -p -o udp_recvspace=655360    # = 10 × udp_sendspace

# Check for socket buffer overflows (increase udp_recvspace if non-zero and growing)
netstat -s | grep "socket buffer overflows"

# Enable Jumbo Frames if switch supports it (reduces overhead for large RAC traffic)
chdev -l ent1 -a jumbo_frames=yes
lsattr -El ent1 | grep jumbo

# Verify sb_max is large enough for the buffer sizes
no -o sb_max
no -a | grep -E "udp_sendspace|udp_recvspace|sb_max"
```

### TCP/IP Ephemeral Port Range

Oracle 11gR2+ checks the ephemeral port range at installation and warns if not set to the
Oracle-recommended range. High parallelism or large RAC clusters may exhaust the default range:

```bash
no -p -o tcp_ephemeral_low=9000
no -p -o tcp_ephemeral_high=65500
no -p -o udp_ephemeral_low=9000
no -p -o udp_ephemeral_high=65500
# Verify
no -a | grep ephemeral
```

### RAC Network Interface Naming — `rendev`

In RAC, all nodes must have **identical interface names** for the same role. Both the Ethernet
device (`entX`) and the logical interface (`enX`) must be renamed:

```bash
# Rename both entX (device) and enX (interface) — both are required
rendev -l ent2 -n ent_rac_pub    # Example: rename to meaningful name
# AIX automatically renames the corresponding enX → en_rac_pub

# For consistent RAC hdisk naming, also see lsmpio -q (section 8)
```

### IPv6 Interface Ordering Issue (PowerVS RAC)

In PowerVS, management interfaces may appear before your RAC interfaces in OS enumeration.
Oracle RAC detects interfaces in order and may select IPv6-only or unaddressed interfaces first,
even when explicitly excluded. Use `rendev` to ensure IPv4 RAC interfaces appear first (see
`oracle-aix-best-practices-misc` for the full procedure).

### `flexctl_latency` for 25Gbps Adapters

For 25GbE and higher-speed adapters in latency-sensitive RAC interconnect environments:

```bash
# Set latency-sensitive scheduling mode for flex adapter
schedo -p -o flexctl_latency=boost
# "boost" reduces the time for a thread to be dispatched after becoming runnable
# Applicable to 25Gbps flex adapters; verify adapter type before applying
```

---

## 21. Oracle Database Parameters — I/O, Redo, and Performance on Power

### Log Writer — Multiple Processes (I/O Critical)

```sql
-- Multiple log writer processes write redo in parallel — faster on multi-core Power systems.
-- Default in recent Oracle versions; verify it is NOT forced to single-writer:
SHOW PARAMETER _use_single_log_writer;
-- Expected: FALSE (unset = FALSE by default in modern Oracle)
-- If set TRUE, correct it:
ALTER SYSTEM SET "_use_single_log_writer" = FALSE SCOPE=SPFILE;
-- Requires restart; confirms via: ps -ef | grep lgwr (should show lgwr + lg01, lg02...)
```

### Redo Log Sizing — Reducing Log Switches

Excessive log switching (> ~100/hour) forces frequent ARCH I/O, increases LGWRwait, and
causes checkpoint pressure. IBM ATG real-world fix: increased redo log size from 4GB → 8GB.

```sql
-- Check current log switch frequency (last 24 hours by hour):
SELECT to_char(FIRST_TIME, 'YYYY-MM-DD HH24') AS hour,
       COUNT(*) AS switches
FROM   v$log_history
GROUP  BY to_char(FIRST_TIME, 'YYYY-MM-DD HH24')
ORDER  BY 1 DESC FETCH FIRST 24 ROWS ONLY;
-- Target: 4–6 switches per hour (each log group active ~10–15 minutes)

-- Add larger redo log groups, then drop the smaller ones:
ALTER DATABASE ADD LOGFILE GROUP 5 SIZE 8G;
-- Wait until old groups are INACTIVE before dropping:
SELECT GROUP#, STATUS, MEMBERS, BYTES/1024/1024/1024 GB FROM v$log;
ALTER DATABASE DROP LOGFILE GROUP 1;   -- Only when STATUS = INACTIVE or UNUSED
```

### `optimizer_real_time_statistics` — Disable on Pre-19.10 Instances

```sql
-- Real-time statistics introduced in 19c, on by default before 19.10.
-- On large Power10 servers causes high CPU + mutex contention.
-- 19.10+ defaults this to FALSE. Explicitly disable on older 19c:
SHOW PARAMETER optimizer_real_time_statistics;
ALTER SYSTEM SET optimizer_real_time_statistics = FALSE;
-- MOS Doc ID 2747507.1
```

### NUMA-Aware Oracle Parameters (Large Multi-Chip Power Systems)

Applies to Oracle on E1080, E1150, E1180 or any LPAR spanning multiple SRADs:

```sql
-- _gc_numa_lock_elements: NUMA-aware GCS lock distribution
-- IBM ATG testing: TRUE had negative impact; leave at default FALSE
ALTER SYSTEM SET "_gc_numa_lock_elements" = FALSE SCOPE=SPFILE;

-- _numa_buffer_cache_stats: NUMA buffer cache statistics overhead
-- 0 = disabled (reduces overhead on large systems)
ALTER SYSTEM SET "_numa_buffer_cache_stats" = 0 SCOPE=SPFILE;

-- Check active NUMA topology from the OS before changing these:
-- lssrad -va
-- mpstat -d 1 30   (S3hrd = local, S4hrd = near, S5hrd = far NUMA dispatches)
```

### Library Cache Statistics Overhead (Large Power10, Oracle 19c < 19.20)

High `kxsgetruntimelock` / `sskgslcas` CPU in AWR on large Power10:

```sql
-- Temporary workaround (event trace — apply only after Oracle Support confirmation):
ALTER SYSTEM SET EVENTS '32869560 trace name context forever';

-- Permanent fix: upgrade to 19.20+ which includes patches:
-- 32869560, 33380871, 33608329, 29780459
-- Minimum recommended level on large Power10: Oracle 19.20
```

---

## Source Reference

IBM Power Systems Virtual User Group, May 2024:
- Session 2: "Oracle on Power Best Practices — I/O and Miscellaneous" (Ralf Schmidt-Dannert, IBM ATG)
- Deck: `OracleOnPowerTuningConsiderations_AIX_IO_Misc_NEXT.pptx` (~116 slides)

IBM Key Resources:
- AIX with Oracle Database on IBM Power Systems — Performance and Stability (all releases):
  https://www.ibm.com/support/pages/node/6825029 ← **Start here for current patch guidance**
- Oracle Database 19c & RAC on IBM AIX — Tips and Considerations:
  https://www.ibm.com/support/pages/node/6355761
- Power10 Performance Best Practices: https://www.ibm.com/support/pages/node/7038687
- AIX FC NPIV multiple queue support: https://www.ibm.com/docs/en/power9?topic=channel-npiv-multiple-queue-support
- vfcstat command details: https://community.ibm.com/community/user/power/blogs/chris-gibson1/2024/01/24/aix-virtual-fiber-channel-enhancement
- lsmpio pathing and LUN mapping: https://www.ibm.com/support/pages/node/7124296
- VSCSI dual VIOS multipathing: https://www.ibm.com/support/pages/multipathing-and-disk-resiliency-vscsi-dual-vios-configuration
- AIX filesystem performance tuning: https://www.ibm.com/docs/en/aix/7.3?topic=performance-file-system-tuning
- AIX network interface-specific options: https://www.ibm.com/docs/en/aix/7.3?topic=interfaces-interface-specific-network-options
- IBM Spectrum Scale Oracle tuning: MOS Note 2587696.1
- GPFS + RAC: https://www.ibm.com/docs/en/STXKQY/gpfsclustersfaq.html#oracle
- ASM Storwize dismount: MOS Doc ID 1581684.1
- 4K redo sector size: MOS Note 1681266.1
- RAC interconnect monitor option: MOS Doc ID 1949615.1
- Oracle 19c AIX certification: MOS Note 2828936.1
- RAC and Clusterware Best Practices (AIX): MOS Note 811293.1
- Ansible Oracle on AIX automation: https://github.com/IBM/ansible-power-aix-oracle-dba
- zlibNX / pigz reference: https://www.ibm.com/docs/en/aix/7.3?topic=management-data-compression-by-using-zlibnx-library
