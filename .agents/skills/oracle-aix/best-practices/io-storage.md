# Oracle on Power: I/O and Storage Tuning

> **Read this file for:** AIO, hdisk (`queue_depth`, `max_transfer`,
> `reserve_policy`), FC adapters and NPIV, VSCSI, storage layout, ASM on AIX,
> JFS2 mount options and `filesystemio_options`, `agblksize`, LVM striping,
> pbuf/fsbuf shortages, redo logs, buffer cache, Storage Scale (GPFS), and
> I/O-related AIX APARs.
> **Not here:** OS prerequisites and user limits are in `os-prereqs.md`, RAC and
> network settings in `network-rac.md`, pigz/zlibNX in `misc.md` §7, and the
> step-by-step slow-I/O diagnosis in `diagnostics.md` §2.
> **Source:** IBM Power Systems VUG May 2024 (Ralf Schmidt-Dannert, IBM ATG), deck
> `OracleOnPowerTuningConsiderations_AIX_IO_Misc_NEXT.pptx`.
> **OS user:** ASM tasks (`asmcmd`, `sqlplus / as sysasm`) run as `grid`; database
> tasks run as `oracle`. Disk preparation is done as `root`. If the user is missing
> or different, ask the user for the correct username (see `os-prereqs.md` §4).
> **Before changing any tunable**, check that it exists and show its default and
> type with `ioo -L <tunable>`, `schedo -L <tunable>`, or `lsattr -Rl <dev> -a <attr>`.

---

## 1. I/O Optimization Strategy

Priority order, from highest to lowest return:

1. **Reduce the amount of I/O** (DBA):
   - Use the right indexes.
   - Use partitioning to avoid full scans.
   - Avoid parallel queries that re-read the same data.
   - Size the buffer cache (§13). Consider Oracle In-Memory for analytics.
2. **Improve I/O service time and throughput** (sysadmin and storage team):
   - Use flash storage (target < 1 ms for 8 KB reads).
   - Spread I/O over many LUNs.
   - Tune the FC stack and hdisk attributes.
   - Stripe with LVM or ASM.
   - In PowerVS, pick the right storage tier (`misc.md` §8).

> The DBA, system administrator, and storage administrator must work on this
> together. Finger-pointing between teams is the most common cause of slow
> resolution.

---

## 2. The AIX I/O Stack for Oracle

```
Oracle Database (buffer cache)
    ↓
ASM (raw hdisks)  or  JFS2 (CIO / DIO / cached)
    ↓
LVM (JFS2 only) + hdisk driver: queue_depth, max_transfer
    ↓
FC client adapter (NPIV fcsX / fscsiX) or VSCSI (vscsiX) in the LPAR
    ↓
VIOS: physical FC adapter queues (num_cmd_elems, max_xfer_size)
    ↓
SAN fabric → storage array
```

Each layer has its own **queue depth** and **maximum transfer size**, and they must
be tuned together.

> Raw devices are not supported for Oracle database files (12c and later). Use ASM
> (on raw **hdisks**) or JFS2.

---

## 3. Asynchronous I/O (AIO)

AIO is strongly advised for every storage type. On AIX 6.1 and later, the AIO
kernel extension loads on demand. There is no `mkdev aio0` step.

```bash
ioo -L aio_fsfastpath      # JFS2 CIO fastpath: default 1 (restricted, do not change)
ioo -L aio_fastpath        # raw/ASM fastpath: default 1 (restricted, do not change)
ioo -a | grep aio_         # all non-restricted AIO tunables
```

AIO server tunables apply to I/O that doesn't take a fastpath (for example cached
JFS2):

```bash
ioo -L aio_maxservers      # per logical CPU, default 30
ioo -L aio_maxreqs         # default 131072 on AIX 7.x (65536 on AIX 6.1)
ioo -p -o aio_maxservers=60          # example: only if aioservers are saturated

pstat -a | grep -c aioserver         # number of AIO server kprocs (rough indicator)
```

### `lio_listio returned EAGAIN` in the alert log

This means `aio_maxreqs` or `aio_maxservers` is too low, or the storage can't keep
up.

1. Check `errpt` and the storage service times (`iostat -D`) first.
2. Then raise `aio_maxreqs` and `aio_maxservers` with `-p`.

### Oracle AIO parameters

| Parameter | Default | Recommendation |
|---|---|---|
| `disk_asynch_io` | TRUE | Keep TRUE |
| `filesystemio_options` | NONE (JFS2) | **SETALL** for JFS2 (§9) |

---

## 4. hdisk (LUN) Tuning

```bash
lsattr -El hdisk4                   # current values. Last column "True+" = changeable in use (chdev -U)
lsattr -Rl hdisk4 -a queue_depth    # allowed range
iostat -D hdisk4 5 3                # avgserv, avgsqsz, sqfull
```

| Attribute | Recommendation | Notes |
|---|---|---|
| `queue_depth` | 32–64 to start (flash arrays often higher) | The maximum depends on the driver (often 256). In high-IOPS environments, add LUNs rather than raising it further |
| `max_transfer` | `0x100000` (1 MB) or larger if the array supports it | Must be ≤ the adapter's `max_xfer_size` |
| `reserve_policy` | `no_reserve` | Required for the `round_robin` / `shortest_queue` path algorithms and for disks shared between nodes (ASM/RAC, PowerHA) |
| `algorithm` | `shortest_queue` (default with AIX PCM on recent levels) | `round_robin` for uniform small I/O |
| `rw_timeout` | Default | Raising it hides storage problems |

```bash
# queue_depth while the disk is in use (only if lsattr shows "True+")
chdev -l hdisk4 -a queue_depth=64 -U

# Otherwise write the change to the ODM and let it apply at the next reboot (or when
# the disk is reconfigured)
chdev -l hdisk4 -a max_transfer=0x100000 -P

# no_reserve on all disks of a VG. Changing reservation on in-use disks is a
# change-window operation: confirm first, use -P, and reboot in the window
for d in $(lsvg -p oravg | awk 'NR>2{print $1}'); do
  chdev -l "$d" -a reserve_policy=no_reserve -P
done
```

### qdepth saturation

- In `iostat -D`, a non-zero **`sqfull`** with low `avgserv` (< 1 ms) means the
  hdisk queue is the bottleneck. Increase `queue_depth` or add LUNs.
- High `avgserv` means the storage itself is slow. Raising `queue_depth` on an
  overloaded array makes things worse.
- In high-IOPS environments, use several LUNs per pool (8 is a good start).
  Flash arrays can serve 8 × 100 GB as easily as 1 × 800 GB.
- Some arrays **silently drop** I/O when overloaded. AIX then waits for a timeout
  (seconds) before retrying, which shows up as rare but very long I/Os.

---

## 5. Fibre Channel Adapter Tuning

### NPIV architecture

- The physical FC ports are in the VIOS. Each LPAR sees virtual FC client adapters
  (`fcsX` with a `fscsiX` protocol device).
- The LPAR's `num_cmd_elems` and `max_xfer_size` must be **≤** the VIOS physical
  port values.

```bash
lsattr -El fcs0                 # num_cmd_elems, max_xfer_size (adapter attributes)
lsattr -El fscsi0               # fc_err_recov, dyntrk (protocol device attributes)
lscfg -vl fcs0 | grep "Network Address"   # WWPN for SAN zoning
```

### Recommended settings

```bash
# Fast failover and dynamic tracking are fscsiX attributes (not fcsX).
# If the adapter is in use, -P writes the change to the ODM for the next reboot.
chdev -l fscsi0 -a fc_err_recov=fast_fail -a dyntrk=yes -P

# Transfer size is an fcsX attribute. Must be >= the hdisk max_transfer; never lower an existing larger value
chdev -l fcs0 -a max_xfer_size=0x100000 -P

lsattr -El fscsi0 -a fc_err_recov -a dyntrk
lsattr -El fcs0 -a max_xfer_size -a num_cmd_elems
```

### `num_cmd_elems`

```
num_cmd_elems (per port) ≈ sum of queue_depth of the hdisks using that port
```

```bash
fcstat fcs0 | grep -E "No Command Resource Count|No Adapter Elements Count|No DMA Resource Count"
# "No Command Resource" / "No Adapter Elements" increasing  -> raise num_cmd_elems
# "No DMA Resource" increasing                              -> raise max_xfer_size (it also sizes DMA memory)

chdev -l fcs0 -a num_cmd_elems=1024 -P    # applies at the next reboot
```

> **NPIV adapters with `num_cmd_elems > 256`** need two APARs:
> - "INCREASED UPPER LIMIT OF NUM_CMD_ELEMS FOR NPIV ADAPTER TO 2048"
> - "POTENTIAL DATA LOSS USING VIRTUAL FC WITH NUM_CMD_ELEMS > 256"
>
> Confirm both are applied before going above 256. Physical adapters in the VIOS
> are commonly set to 2048.

### Multiple I/O queues (AIX 7.2 TL5+)

```bash
lsattr -El fcs0 | grep num_io_queues     # present = multiple queues are supported
ps -ek | grep emfc                       # emfc_kproc: watch its CPU use under very high I/O rates
```

### Unused FC ports

Uncabled ports slow down `cfgmgr` and log `FCA_ERR4` / `FCA_ERR12` entries. First
confirm that **no disks or paths** use the port (`lspath | grep fscsi1`). Then:

```bash
rmdev -l fscsi1 -R                       # unconfigure the port's protocol device and its children
chdev -l fscsi1 -a autoconfig=defined    # keep cfgmgr from configuring it at boot
```

### Virtual FC statistics (AIX 7.3 TL2 SP1+)

```bash
vfcstat -d fcs0 -f tunables   # requested vs granted queue depths, mapping (see the Chris Gibson blog in the references)
```

### Device interrupt handling (AIX 7.2 TL5+ / 7.3)

AIX moved I/O interrupt handling to kernel threads. Under heavy load, their
scheduling latency can add to I/O service time. The source mentions a `schedo`
tunable `io_latency` as a mitigation. **Check that it exists at your level before
using it:**

```bash
schedo -h io_latency 2>&1 | head -5     # error = the tunable doesn't exist at this level
schedo -L io_latency
```

---

## 6. VSCSI Adapter Tuning

```bash
chdev -l vscsi0 -a vscsi_err_recov=fast_fail -a vscsi_path_to=30 -P
lsattr -El vscsi0 -a vscsi_err_recov -a vscsi_path_to
```

Maximum LUNs per VSCSI adapter = `(num_cmd_elems - 2) / (queue_depth + 3)`. For
example, with 512 command elements and queue depth 32: (512 - 2) / 35 = **14
LUNs**. If you need more LUNs, add adapters.

---

## 7. Storage Layout Strategy

Spread each I/O type evenly over as many LUNs as possible. Don't hand-place files
on specific devices: that degrades as data grows.

| Pool | LUNs | Notes |
|---|---|---|
| Data / index / temp | 8, or a multiple of 8 | Starting point |
| Redo logs | 4–8 | A separate pool from data |
| OCR / voting (RAC) | 3 | Standard RAC requirement (normal redundancy) |
| Oracle binaries | 2 | Separate from data |

- For large parallel sort and hash I/O, consider a separate temp pool.
- Flashback logs and archive logs (both sequential writes) can share a pool.

---

## 8. ASM on AIX

ASM stripes across all disks in a disk group. **Each ASM disk is a whole raw hdisk
(`/dev/rhdiskN`)**, not an LV inside a VG.

### Prepare the disks (as root, on every node for RAC)

```bash
lspv | grep -w hdisk10        # must show "none" as PVID and VG (never part of a VG)

chdev -l hdisk10 -a reserve_policy=no_reserve -a queue_depth=32 -a max_transfer=0x100000 -P
# (on a new, unused disk the change can also be made directly without -P)

chown grid:asmadmin /dev/rhdisk10
chmod 660 /dev/rhdisk10
ls -l /dev/rhdisk10           # crw-rw---- grid asmadmin
```

- Never assign a PVID (`chdev -l hdiskN -a pv=yes`) to an ASM disk.
- Never run `mkvg` or `extendvg` on it. A VG and ASM both write their metadata
  near the start of the disk, so either would **corrupt the ASM disk header**.
  AIX 7.2 and later refuse by default, but `-f` overrides that.
- Device numbers and names can change after `rmdev`/`cfgmgr`. Re-check ownership
  after any disk reconfiguration.

### Protect and rename ASM disks

```bash
rendev -l hdisk10 -n hdiskASMD01          # meaningful, consistent name (disk must not be open)
lkdev -l hdiskASMD01 -a -c "ASM DATA"     # lock: blocks chdev / rmdev / chpath / rmpath
lkdev                                     # list locked devices
chown grid:asmadmin /dev/rhdiskASMD01     # renaming creates new device files: set ownership again
```

### Consistent naming across RAC nodes

```bash
lsmpio -q        # vendor, product, size and volume name per hdisk: compare on all nodes
```

### Disk group creation

```sql
-- External redundancy on enterprise SAN storage (the array provides RAID)
CREATE DISKGROUP data EXTERNAL REDUNDANCY
  DISK '/dev/rhdiskASMD01','/dev/rhdiskASMD02','/dev/rhdiskASMD03','/dev/rhdiskASMD04',
       '/dev/rhdiskASMD05','/dev/rhdiskASMD06','/dev/rhdiskASMD07','/dev/rhdiskASMD08'
  ATTRIBUTE 'compatible.asm'   = '19.0',
            'compatible.rdbms' = '19.0',
            'au_size'          = '4M';     -- AU size can only be set at CREATE time
```

| Storage | ASM redundancy | Why |
|---|---|---|
| Enterprise SAN (FlashSystem and similar) | **External** | The array provides RAID. ASM mirroring would double the writes for no benefit |
| Internal disks / JBOD / server NVMe without RAID | Normal or High | No redundancy below ASM |

- **Disk size limits:** with `compatible.asm` and `compatible.rdbms` ≥ 12.1, ASM
  supports very large disks. The old 2 TB per-disk limit applies only to disk
  groups with `compatible.rdbms` < 12.1.
- Set `asm_diskstring` to match the naming you chose, for example
  `'/dev/rhdiskASM*'`.

### nmon view of ASM disk groups

```bash
cat > /etc/nmon_asmdef << 'EOF'
DATA   hdiskASMD01 hdiskASMD02 hdiskASMD03 hdiskASMD04
RECO   hdiskASMR01 hdiskASMR02
EOF
nmon -g /etc/nmon_asmdef           # interactive: press 'g' for the disk group view
nmon -f -g /etc/nmon_asmdef -s 60 -c 1440   # recording for nmon analyser
```

### Storage controller rolling upgrade (IBM FlashSystem / Storwize)

Temporary path loss during a rolling controller upgrade can make ASM dismount a
disk group with `ORA-15064: Waited 15 secs for write IO to PST` (Oracle 11.2.0.3
to 12.1.0.1).

- MOS Doc ID 1581684.1 describes raising `_asm_hbeatiowait`.
- That is an **underscore parameter**: set it only with Oracle Support's agreement.

---

## 9. JFS2 Mount Options and `filesystemio_options`

The preferred way to get CIO for Oracle on JFS2 is the Oracle parameter
`filesystemio_options=SETALL`, rather than the `cio` mount option.

```sql
SHOW PARAMETER filesystemio_options                             -- record the current value
ALTER SYSTEM SET filesystemio_options = SETALL SCOPE=SPFILE;    -- takes effect at the next restart
-- Revert: ALTER SYSTEM SET filesystemio_options = <old_value> SCOPE=SPFILE;
```

| `filesystemio_options` | JFS2 default mount | JFS2 `cio` mount |
|---|---|---|
| `ASYNCH` | Async, cached | Async, CIO |
| **`SETALL`** | **Async, CIO** | Async, CIO |
| `DIRECTIO` | Sync, CIO | Sync, CIO |
| `NONE` | Sync, cached | Sync, CIO |

`DIRECTIO` and `NONE` turn off asynchronous I/O. Don't use them in production.

| Files | Recommendation | Notes |
|---|---|---|
| Data / index | `SETALL` (or a `cio` mount) | No file cache, no inode lock |
| Redo / control files | `SETALL` or `cio`, **dedicated filesystem**, `agblksize=512` | Never share a filesystem with data files |
| Flashback logs | CIO or DIO | |
| Archive logs / RMAN backups | `dio` or `rbrw` (release-behind) | Write-once sequential |
| Oracle binaries | Normal mount (no CIO/DIO), `noatime` | Must use the file cache |
| Repeatedly re-read staging / ETL data | Normal (cached) mount | Only when the same data is re-read |
| Audit / trace files | Separate filesystem, `noatime` | |

```bash
mount | grep /oradata                     # current mount options
lsfs -c /oradata                          # options stored in /etc/filesystems

# chfs -a options= REPLACES the whole option list: include every option you want to keep
chfs -a options=rw,cio,noatime /oradata   # takes effect at the next mount (umount/mount in a window)
```

### CIO vs DIO vs cached

- **CIO**: no file cache and no inode lock, so concurrent writers to one file are
  allowed. Best for database files.
- **DIO**: no file cache, but the inode lock is kept. Fine for sequential single
  writers.
- **Cached**: uses the JFS2 file cache. Only helps workloads that re-read the same
  data (for example repeated parallel scans).

### When the file cache helps parallel queries

Parallel query reads into the PGA and throws the data away afterwards.

IBM ATG measured 1 MB reads:

| Execution | I/O mode | Latency |
|---|---|---|
| Serial | CIO | 2.76 ms |
| Parallel | CIO | 95 ms (storage saturated) |
| Parallel | JFS2 cache | 0.6 ms |

The Oracle-side alternative is `DB_BIG_TABLE_CACHE_PERCENT_TARGET`, used with
`PARALLEL_DEGREE_POLICY=AUTO`. That is a significant behaviour change for all
parallel SQL, so test it first:

```sql
SHOW PARAMETER db_big_table_cache_percent_target
SHOW PARAMETER parallel_degree_policy
ALTER SYSTEM SET db_big_table_cache_percent_target = 50 SCOPE=BOTH;
ALTER SYSTEM SET parallel_degree_policy = AUTO SCOPE=BOTH;
-- Revert: set both back to the recorded values (defaults: 0 and MANUAL)
```

---

## 10. Redo Logs

### Dedicated JFS2 filesystem

```bash
crfs -v jfs2 -d redo_lv -m /oraredo -a agblksize=512 -a logname=INLINE -A yes
```

- You can't change `agblksize` after the filesystem is created.
- A mismatch between `agblksize` and the I/O size makes JFS2 **demote** CIO
  without any message (§11b).

### 4 KB redo block size (flash storage)

- 4 KB redo blocks reduce redo wastage.
- **With ASM:** use disk groups whose `sector_size` is 4096 (12.2+, see MOS
  1681266.1).
- **Without native 4K sectors:** this needs the underscore parameter
  `_disk_sector_size_override`, which should only be set with Oracle Support's
  agreement.

```sql
-- Add the new groups first. Never drop a group that is CURRENT or ACTIVE, or not yet archived.
ALTER DATABASE ADD LOGFILE GROUP 5 ('+REDO') SIZE 8G BLOCKSIZE 4096;
SELECT group#, status, archived, blocksize FROM v$log;
ALTER SYSTEM SWITCH LOGFILE;           -- repeat until the old groups are INACTIVE
ALTER SYSTEM CHECKPOINT;
-- Destructive, so confirm first. Keep at least 2 (3+ recommended) groups per thread.
ALTER DATABASE DROP LOGFILE GROUP 1;
```

### Sizing: avoid frequent log switches

More than about 100 switches an hour causes heavy archiver I/O and checkpoint
pressure. Aim for **4–6 switches an hour**. In the source, IBM ATG fixed a case by
growing the logs from 4 GB to 8 GB.

```sql
SELECT to_char(first_time,'YYYY-MM-DD HH24') hour, count(*) switches
FROM   v$log_history
WHERE  first_time > sysdate - 1
GROUP  BY to_char(first_time,'YYYY-MM-DD HH24')
ORDER  BY 1 DESC;
```

To resize, add the larger groups, then drop the old ones with the same checks as
above.

### Multiple log writers (12c+)

The default `_use_single_log_writer=ADAPTIVE` switches between one LGWR and
LGWR plus LGnn workers. Check what is running:

```bash
: "${ORACLE_SID:?ORACLE_SID is not set}"   # see the pre-flight check in SKILL.md
ps -ef | grep -E "ora_lg(wr|[0-9]{2})_${ORACLE_SID}" | grep -v grep
```

Hidden parameters don't show up in `SHOW PARAMETER`. Leave this parameter at its
default unless Oracle Support advises otherwise.

---

## 11. LVM Striping for JFS2

### LV striping (recommended)

```bash
mkvg -S -y oravg -s 32 hdisk1 hdisk2 hdisk3 hdisk4 hdisk5 hdisk6 hdisk7 hdisk8   # scalable VG, 32 MB PPs
mklv -y data_lv01 -t jfs2 -S 1M oravg 80 hdisk1 hdisk2 hdisk3 hdisk4 hdisk5 hdisk6 hdisk7 hdisk8
# -S 1M = 1 MB stripe size. Stripe width = the hdisks listed. 80 PPs = a multiple of 8
crfs -v jfs2 -d data_lv01 -m /oradata -A yes -a logname=INLINE
```

- Grow striped LVs in multiples of *stripe width × PP size*.
- Use `logname=INLINE` for Oracle filesystems, so there's no shared JFS2 log
  hot spot.

### PP striping (maximum inter-disk spread)

```bash
mkvg -S -y oravg -s 8 hdisk1 hdisk2 hdisk3 hdisk4
mklv -y data_lv01 -t jfs2 -e x oravg 64        # -e x = spread PPs over all disks
crfs -v jfs2 -d data_lv01 -m /oradata -A yes -a logname=INLINE
```

- Use PP sizes ≤ 32 MB to limit hot spots.
- Avoid VGs with more than about 60,000 PPs, because LVM commands slow down.

### Growing after the LUNs were expanded on the array

> **APAR IJ46487** (potential undetected data loss after `chvg -g` or `chvg -ky`):
> confirm the fix is installed before running either command
> (`instfix -ik IJ46487`, or check the iFix list).

```bash
cfgmgr                     # rediscover disk sizes
chvg -g oravg              # VG picks up the new LUN sizes
chfs -a size=+8G /oradata  # chfs extends the LV as needed
```

Adding new LUNs to a striped LV instead needs the same stripe width again. That is
complex, so prefer expanding the existing LUNs.

### 11b. `agblksize` per file type

| Files | `agblksize` |
|---|---|
| Data files, 8 KB or 16 KB DB block | 4096 (default) |
| Data files, 2 KB DB block | 2048 |
| Redo / control files, 512-byte blocks | **512**, on a dedicated filesystem |
| Redo with 4 KB blocks | 4096 |

### 11c. pbuf and fsbuf shortages

```bash
vmstat -v | grep -i blocked
# "pending disk I/Os blocked with no pbuf"                -> LVM pbuf shortage
# "paging space I/Os blocked with no psbuf"               -> paging space I/O pressure
# "filesystem I/Os blocked with no fsbuf"                 -> JFS (not JFS2)
# "external pager filesystem I/Os blocked with no fsbuf"  -> JFS2 buffer shortage

lvmo -a -v oravg        # pv_pbuf_count, total_vg_pbufs, pervg_blocked_io_count for this VG
lvmo -v oravg -o pv_pbuf_count=1024     # more pbufs per PV in this VG. Online, no varyoff needed

ioo -L j2_dynamicBufferPreallocation
ioo -p -o j2_dynamicBufferPreallocation=128   # JFS2 fsbuf shortage: try this first (dynamic)
# j2_nBufferPerPagerDevice is restricted: change it only at IBM Support's request
```

The counters are cumulative since boot. Compare two samples taken during the
problem.

---

## 12. RBNA (Reserved But Not Allocated) for JFS2

On AIX 7.2 TL4 and AIX 7.3, RBNA pre-allocates sequential extents. This helps
concurrent data file creation, parallel loads, and multi-channel RMAN restores.
**Check the tunable name at your level before using it:**

```bash
ioo -L | grep -i rbna            # e.g. j2_nPagesPerRBNACluster
ioo -h j2_nPagesPerRBNACluster   # error = not available at this level
fileplace -pv /oradata/users01.dbf   # extent placement (fragmentation check)
defragfs -q /oradata                  # report fragmentation; defragfs /oradata to run (heavy I/O)
```

---

## 13. Buffer Cache Sizing

At a 98% hit ratio, gaining 1 point (to 99%) **halves** physical reads. In an IBM
ATG test, growing the cache from 6.5 GB to 101.5 GB cut user I/O wait by 91% and
DB time by 79%.

```sql
SELECT name, block_size, size_for_estimate/1024 est_gb, estd_physical_read_factor
FROM   v$db_cache_advice
WHERE  name = 'DEFAULT' AND advice_status = 'ON'
ORDER  BY size_for_estimate;

SHOW PARAMETER sga_target
SHOW PARAMETER db_cache_size
ALTER SYSTEM SET sga_target = 200G SCOPE=BOTH;   -- must be <= sga_max_size. Check 16 MB page sizing (memory.md §5)
-- Revert: ALTER SYSTEM SET sga_target = <old_value> SCOPE=BOTH;
```

---

## 14. IBM Storage Scale (GPFS)

- According to the source, `filesystemio_options` is ignored on GPFS, and the
  Oracle-side switch is `disk_asynch_io=TRUE` (keep it TRUE).
- Use the GPFS `workerThreads` and `pagepool` settings for tuning (`mmlsconfig`,
  then `mmchconfig ... -i`). Take values from the current IBM / MOS guidance
  (MOS 2587696.1, IBM Storage Scale FAQ).
- Block size: typically 512 KB–1 MB for data files and 256 KB for binaries
  (`mmcrfs -B`).
- `ipqmaxlen` is an AIX network tunable, not a GPFS setting. It's a reboot
  tunable: `no -r -o ipqmaxlen=512`.

---

## 15. I/O Monitoring Commands

```bash
iostat -D hdisk4 5 3              # avgserv, avgsqsz, sqfull
iostat -aD 5 3                    # include adapter throughput
vmstat -v | grep -i blocked       # pbuf / fsbuf shortages (§11c)
lsmpio -q; lspath -l hdisk4       # multipath status
fcstat fcs0                       # FC adapter counters
lslv -m data_lv01 | head          # PP placement
fileplace -pv <file>              # file extent placement
```

Oracle wait events (AWR):

| Event | Meaning | Target on flash |
|---|---|---|
| `db file sequential read` | Single-block reads | < 1 ms |
| `db file scattered read` | Multiblock reads | |
| `log file sync` | Commit wait | < 1 ms |
| `log file parallel write` | LGWR physical write | < 1 ms |

---

## 16. AIX APARs Affecting Oracle I/O

**Check each APAR's number and fixing levels on IBM Fix Central / FLRT** for the
exact AIX level before acting. The items below come from the source.

### `offload_iodone` performance loss (AIX 7.3 TL3, APAR IJ53641)

- **Affects:** LPARs that are **not** in their native compatibility mode
  (Power8; Power9 not in POWER9 mode; Power10 not in POWER10 mode). They may see
  lower I/O performance with the default `offload_iodone=1`.
- **Workaround:** set the value to 0 with the command that owns the tunable.
- **Fix:** upgrade to the fixing level (IBM Support note 7230030).

```bash
schedo -L offload_iodone 2>/dev/null || ioo -L offload_iodone   # find which command owns it
```

### Kernel memory leak, LPAR hang or crash with multiple SRADs (AIX 7.3 TL3/TL4)

- **Affects:** LPARs spanning several SRADs with heavy shared-memory activity,
  such as large Oracle SGAs.
- **APARs** (per the source): IJ57120 (TL3) and IJ56896 (TL4).
- **Fixes** (per the source): 7300-03-03 and 7300-04-01.

```bash
oslevel -s
lssrad -va       # more than one SRAD with memory = potentially exposed
```

### AIX 7.3 TL4 FC improvements

TL4 shortens FC path failover (for example during VIOS maintenance) and adds NVMe
over TCP (technology preview).

---

## Source and References

- IBM Power Systems VUG, May 2024, Session 2: "Oracle on Power Best Practices,
  I/O and Miscellaneous" (Ralf Schmidt-Dannert, IBM ATG)
- AIX with Oracle Database on IBM Power, performance and stability (start here for
  current patch guidance): https://www.ibm.com/support/pages/node/6825029
- Oracle Database 19c and RAC on AIX, tips and considerations: https://www.ibm.com/support/pages/node/6355761
- Power10 performance best practices: https://www.ibm.com/support/pages/node/7038687
- NPIV multiple queue support: https://www.ibm.com/docs/en/power9?topic=channel-npiv-multiple-queue-support
- `vfcstat`: https://community.ibm.com/community/user/power/blogs/chris-gibson1/2024/01/24/aix-virtual-fiber-channel-enhancement
- `lsmpio` path and LUN mapping: https://www.ibm.com/support/pages/node/7124296
- VSCSI dual-VIOS multipathing: https://www.ibm.com/support/pages/multipathing-and-disk-resiliency-vscsi-dual-vios-configuration
- AIX filesystem performance tuning: https://www.ibm.com/docs/en/aix/7.3?topic=performance-file-system-tuning
- Oracle ASM administrator's guide (19c): https://docs.oracle.com/en/database/oracle/oracle-database/19/ostmg/
- MOS: 1581684.1 (ASM dismount during storage upgrade), 1681266.1 (4K redo), 2587696.1 (Storage Scale)
