# Oracle on AIX: Diagnosis Flows

> **Read this file for:** step-by-step diagnosis of slow I/O, CPU starvation,
> memory pressure and paging, ORA errors and instance crashes, and RAC
> interconnect problems on AIX.
> Every step is **read-only**. Changes are in the topic files the flows point to.
> Collect evidence during the problem, take two samples to compare, and record
> the timestamps.

---

## 1. Baseline Snapshot (run first, read-only)

```bash
# as root on the database LPAR
OUT=/tmp/oradiag-$(hostname)-$(date +%Y%m%d%H%M); mkdir -p "$OUT"
oslevel -s                   > "$OUT/oslevel.txt"
prtconf                      > "$OUT/prtconf.txt" 2>&1
lparstat -i                  > "$OUT/lparstat-i.txt"
lssrad -va                   > "$OUT/lssrad.txt"
smtctl                       > "$OUT/smtctl.txt"
vmo -L                       > "$OUT/vmo.txt"
ioo -L                       > "$OUT/ioo.txt"
schedo -L                    > "$OUT/schedo.txt"
no -L                        > "$OUT/no.txt"
vmstat -v                    > "$OUT/vmstat-v.txt"
lsps -a                      > "$OUT/lsps.txt"
errpt | head -100            > "$OUT/errpt.txt"
emgr -l                      > "$OUT/emgr.txt" 2>&1
nmon -f -s 30 -c 120 -m "$OUT"        # 1 hour recording in the background
```

On the Oracle side, take an AWR or ASH report covering the problem window, plus
`opatch lspatches` for each home. Before any `sqlplus`, `adrci`, or `opatch` call,
verify `ORACLE_HOME`, `ORACLE_SID`, `ORACLE_BASE`, `PATH`, `LIBPATH`, and `TNS_ADMIN`
(if used) with the "Oracle environment pre-flight check" in `SKILL.md`. A wrong
`ORACLE_SID` or `ORACLE_HOME` gives diagnostics for the wrong instance.

---

## 2. Slow I/O

| Step | Command | Finding → next step |
|---|---|---|
| 1. Confirm in Oracle | AWR top events: `db file sequential read`, `log file sync`, `log file parallel write` | Average latency above target (≈1 ms on flash) → continue |
| 2. Device service time | `iostat -D 5 6` (focus on the busy hdisks) | High `avgserv` (read/write) → step 5 (storage or path side). Low `avgserv` but `sqfull` > 0 or high `avgwqsz` → hdisk queue: raise `queue_depth` or add LUNs (`io-storage.md` §4) |
| 3. Adapter resources | `fcstat fcs0` (each port; compare two samples) | "No Command Resource" or "No Adapter Elements" increasing → `num_cmd_elems`. "No DMA Resource" increasing → `max_xfer_size` (`io-storage.md` §5) |
| 4. Buffer shortages | `vmstat -v \| grep -i blocked` (two samples) and `lvmo -a -v <vg>` | pbuf counters growing → `pv_pbuf_count`. JFS2 fsbuf counters growing → `j2_dynamicBufferPreallocation` (`io-storage.md` §11c) |
| 5. Paths and errors | `lspath`, `lsmpio -q`, `errpt \| head` | Failed or missing paths, FC or disk errors (`FCA_ERR*`, `SC_DISK_ERR*`) → storage/SAN team; VIOS check |
| 6. Filesystem layer (JFS2) | `mount`, `lsfs -c`, `SHOW PARAMETER filesystemio_options` | Data on a cached mount without `SETALL`, or redo sharing a filesystem with data, or a wrong `agblksize` → `io-storage.md` §9–§11b |
| 7. Concurrency | Did the problem start with a backup, batch or parallel query? | Isolate the workloads (separate pools, RMAN channel count, DOP) |

---

## 3. CPU Starvation or High CPU

| Step | Command | Finding → next step |
|---|---|---|
| 1. LPAR capacity | `lparstat 5 6` | `%entc` ≈ 100 on a capped LPAR → capped at entitlement. Uncapped with `app` ≈ 0 → the shared pool is exhausted |
| 2. VP dispatch | `mpstat -v 5 3` | VPs running much less than the interval → pool oversubscribed (`cpu.md` §3–§4) |
| 3. Run queue | `vmstat 5 6` (`r` column) | `r` consistently above the logical CPU count → CPU-bound |
| 4. Top consumers | `topas`, `ps aux \| sort -rn -k3 \| head` | Read the percentages with the SMT rules in `misc.md` §3 |
| 5. Oracle view | AWR: DB CPU, top SQL by CPU, `cursor: mutex X`, latch waits | Mutex waits → `misc.md` §1–§2. Bad SQL → tune the SQL |
| 6. Folding / SMT | `schedo -L vpm_throughput_mode`, `smtctl` | Check against `cpu.md` §1–§2 |

---

## 4. Memory Pressure and Paging

| Step | Command | Finding → next step |
|---|---|---|
| 1. Paging activity | `vmstat 5 6` (`pi`, `po`, `fr`, `sr`, `fre`) | `pi`/`po` > 0 sustained → computational memory overcommitted. High `sr`/`fr` → LRUD stealing |
| 2. Memory use | `svmon -G`, `lsps -a` | Compare "inuse" computational memory with real memory. Paging space growing |
| 3. Large pages | `svmon -G` (16 MB row), `vmo -L lgpg_regions` | Unused pre-allocated 16 MB pages are memory nobody else can use (`memory.md` §5) |
| 4. Oracle memory | `v$sgainfo`, `v$pgastat` (total PGA allocated vs `pga_aggregate_limit`) | PGA growth from runaway sessions → limit or fix them |
| 5. File cache | `vmstat -v` (numperm %), `vmo -L maxperm% minperm%` | `memory.md` §2 |
| 6. JFS2 metadata | `cat /proc/sys/fs/jfs2/memory_usage` | Inode/metadata caches oversized for a database server → `memory.md` §3 |

The goal is **zero paging-space activity** from the database.

---

## 5. ORA Errors, Instance Crash, Node Eviction

1. **Read the alert log** (`adrci exec="show alert -tail 200"`) and note the exact
   timestamp and error stack.
2. **Translate the error:** `oerr ora <code>`. For ORA-27xxx (OS-dependent
   errors), look at the "Additional information" and AIX `errno` values in the
   trace file.
3. **Correlate with AIX at the same timestamp:**

```bash
errpt | head -40
errpt -a -s <MMDDhhmmYY> -e <MMDDhhmmYY> | more   # window around the event
```

| AIX finding | Typical meaning |
|---|---|
| Disk, FC, or path errors | I/O timeouts behind the ORA errors (ORA-15080, ORA-27072 and similar) |
| `SYSDUMP`, `CORE_DUMP` | Kernel or process crash. Collect with `snap -ac` for IBM |
| Memory errors (`MEM*`) | Hardware: open a hardware ticket |
| Clock or NTP messages | RAC eviction risk (`os-prereqs.md` §8) |

4. **Startup failures with large pages:**
   - ORA-27126 or ORA-27102 at startup with `LOCK_SGA` → not enough 16 MB pages,
     or `v_pinshm` / capabilities missing (`memory.md` §5).
   - ORA-00847 → `MEMORY_TARGET` combined with `LOCK_SGA`.
5. **RAC node eviction:** check the CSSD/OHASD logs under the Grid base
   (`$ORACLE_BASE/diag/crs/<host>/crs/trace/`), `oifcfg getif`, and §6 below.

---

## 6. RAC Interconnect Problems

| Step | Command | Finding → next step |
|---|---|---|
| 1. Oracle view | AWR `gc` waits (`gc cr block lost`, `gc current block 2-way`), `v$cluster_interconnects` | Lost blocks → network. High latency → network or LMS CPU |
| 2. UDP drops | `netstat -s \| grep -i -E "overflow\|dropped"` (two samples) | Socket buffer overflows growing → `udp_recvspace` (`network-rac.md` §3) |
| 3. Adapter | `entstat -d entX` | CRC or receive errors, "No Resource Errors" → adapter, switch, or MTU mismatch |
| 4. Configuration | `oifcfg getif`, `ifconfig -a`, `lsattr -El enX` | Wrong interface classification, MTU mismatch between nodes (jumbo frames) |
| 5. CPU of the LMS processes | `ps -ef \| grep [o]ra_lms`, `topas` | LMS starved for CPU → LPAR entitlement or priority (`cpu.md`) |
