# Oracle on Power: Miscellaneous Best Practices

> **Read this file for:** mutex contention (`cursor: mutex X`), mutex spin count,
> `DBMS_SHARED_POOL.MARKHOT`, reading process CPU % under SMT, NUMA-related and
> library-cache issues on large Power servers, the embedded JDK, PowerVS storage
> tiers, pigz/zlibNX hardware compression, and known 19c issues on Power.
> **Not here:** installation and patching are in `os-prereqs.md`, RAC networking
> in `network-rac.md`, and ASM redundancy in `io-storage.md` §8.
> **Source:** IBM Power Systems VUG May 2024 (Ralf Schmidt-Dannert, IBM ATG).
> **Underscore (hidden) parameters and events in this file must only be set with
> Oracle Support's agreement.**

---

## 1. Mutex Contention and Spin Count (High-Throughput OLTP)

Oracle protects cursors and library cache objects with mutexes. A process that
can't get a mutex spins for a while, then sleeps.

| Parameter | Controls | Default |
|---|---|---|
| `_mutex_spin_count` | Spins before sleeping on a **mutex** (`cursor: mutex X`, `library cache: mutex X`) | 255 |
| `_spin_count` | Spins on a **latch** | 2000 |

> The source deck labels the mutex spin value `_spin_count`. The parameter that
> controls mutex spinning, with a default of 255, is `_mutex_spin_count`.
> Confirm the parameter and value with Oracle Support for your release.

The default mutex spin is short for modern Power cores.

IBM ATG results (Swingbench OLTP):

| Configuration | TPS |
|---|---|
| Default (255) | ~12,000 |
| Spin count 4000 | ~22,000 (+83%) |
| Spin count 4000 plus MARKHOT on the hottest objects | ~38,000 (+217%) |

### Procedure

```sql
-- 1. Is mutex contention a top wait?
SELECT event, total_waits, round(time_waited_micro/1e6) seconds
FROM   v$system_event
WHERE  event LIKE '%mutex%'
ORDER  BY time_waited_micro DESC;

-- 2. Current values. Hidden parameters are not in v$parameter, so query them as SYS
SELECT i.ksppinm name, v.ksppstvl value, v.ksppstdf is_default
FROM   x$ksppi i JOIN x$ksppcv v ON i.indx = v.indx
WHERE  i.ksppinm IN ('_mutex_spin_count','_spin_count');

-- 3. Only with Oracle Support's agreement, and test on non-production first
ALTER SYSTEM SET "_mutex_spin_count" = 4000 SCOPE=SPFILE;   -- takes effect at the next restart
-- Revert: ALTER SYSTEM RESET "_mutex_spin_count" SCOPE=SPFILE;
```

---

## 2. `DBMS_SHARED_POOL.MARKHOT`: Hot Object Copies

MARKHOT creates multiple copies of a very hot library cache object, which spreads
the mutex contention across the copies.

**Use it when:**
- `cursor: mutex X` or `library cache: mutex X` is a top wait, **and**
- a few objects have extreme execution counts, **and**
- raising the spin count alone didn't remove the wait.

```sql
-- Candidate objects
SELECT owner, name, type, namespace, executions, loads, kept
FROM   v$db_object_cache
WHERE  executions > 100000
  AND  type IN ('PACKAGE','PACKAGE BODY','TYPE','TYPE BODY','TRIGGER','FUNCTION','PROCEDURE')
ORDER  BY executions DESC
FETCH FIRST 20 ROWS ONLY;

-- Generate MARKHOT calls. Signature: MARKHOT(schema, objname, namespace).
-- Library cache namespaces: 1 = TABLE/PROCEDURE (package/type spec, function,
-- procedure), 2 = BODY (package/type body), 3 = TRIGGER
SELECT 'EXEC DBMS_SHARED_POOL.MARKHOT(''' || owner || ''', ''' || name || ''', ' ||
       CASE WHEN type IN ('PACKAGE BODY','TYPE BODY') THEN 2
            WHEN type = 'TRIGGER' THEN 3
            ELSE 1 END || ');' AS cmd
FROM   v$db_object_cache
WHERE  executions > 500000
  AND  type IN ('PACKAGE','PACKAGE BODY','TYPE','TYPE BODY','TRIGGER','FUNCTION','PROCEDURE')
ORDER  BY executions DESC
FETCH FIRST 10 ROWS ONLY;
```

```sql
EXEC DBMS_SHARED_POOL.MARKHOT('SYS', 'DBMS_SQL', 1);     -- package spec
EXEC DBMS_SHARED_POOL.MARKHOT('SYS', 'DBMS_SQL', 2);     -- package body
-- Revert:
EXEC DBMS_SHARED_POOL.UNMARKHOT('SYS', 'DBMS_SQL', 1);
EXEC DBMS_SHARED_POOL.UNMARKHOT('SYS', 'DBMS_SQL', 2);
```

> **Don't overuse it.** Marking many objects can make Enterprise Manager and
> dictionary queries on `v$db_object_cache` take minutes. Limit it to the 3–10
> most contended objects. Sequences can't be marked hot.
> MARKHOT is not persistent across instance restarts: re-apply it at startup, for
> example from a startup trigger or job.

---

## 3. Reading Process CPU % Under SMT

`topas` and `nmon` report a process's CPU % relative to the **whole LPAR's
capacity**, and AIX accounts CPU time with PURR. What a single fully CPU-bound
thread shows therefore depends on how busy the other SMT threads of its core are.

On a 4-core LPAR at SMT8 (32 logical CPUs):

| Situation | Approximate % for one fully busy thread |
|---|---|
| Other threads on its core idle | Up to about **100 / cores = 25%**, because the thread gets most of the core's cycles |
| All threads on all cores busy | About **100 / logical CPUs ≈ 3.1%** |

So a "low" percentage doesn't mean a process is idle. To confirm a CPU-bound
process, check its state over time (`ps -o pid,stat,time,args`), and look at the
AWR CPU time for its session.

### Create a reference for your LPAR

The ratio differs by Power generation and SMT mode. Re-measure after hardware
migrations.

```bash
perl -e 'while(1){}' &      # one CPU-bound thread
SPIN_PID=$!
topas                       # note the %CPU shown for this PID on an otherwise quiet LPAR
kill "$SPIN_PID"
```

---

## 4. Large Power Servers: NUMA and Library Cache Issues

These apply to LPARs spanning several SRADs, such as large E1080, E1150, or E1180
LPARs. **Check the placement first** with `lssrad -va` and `mpstat -d 1 30` (see
`memory.md` §4).

- **`_gc_numa_lock_elements` (RAC):** IBM ATG measured a negative effect with
  TRUE. Leave it at its default.
- **`_numa_buffer_cache_stats`:** the source suggests 0 to reduce overhead on
  large systems. Only set it with Oracle Support's agreement:

```sql
-- Hidden parameters: query them as SYS (see §1), never change them without Oracle Support
SELECT i.ksppinm, v.ksppstvl, v.ksppstdf
FROM   x$ksppi i JOIN x$ksppcv v ON i.indx = v.indx
WHERE  i.ksppinm IN ('_gc_numa_lock_elements','_numa_buffer_cache_stats');
```

- **High `kxsgetruntimelock` / `sskgslcas` CPU in AWR on large Power10
  (19c < 19.20):** the fixes are in Oracle patches 32869560, 33380871, 33608329,
  and 29780459, which are all included in **19.20 and later**. Run 19.20 or later
  on large Power10 systems. Don't use diagnostic events as a workaround without
  Oracle Support.

- **Real-time statistics:** high CPU and mutex contention from statistics
  gathering on conventional DML was reported on large Power10 servers with early
  19c RUs. The `optimizer_real_time_statistics` parameter exists only from 19.10,
  where it defaults to FALSE. On older RUs, ask Oracle Support (MOS 2747507.1)
  rather than setting hidden parameters.

---

## 5. Embedded JDK in Oracle Homes: Keep It Updated

Every Oracle home on AIX includes its own IBM Java (`$ORACLE_HOME/jdk`). It is
separate from the OS Java and has its own security fixes.

```bash
: "${ORACLE_HOME:?ORACLE_HOME is not set}"   # see the pre-flight check in SKILL.md
$ORACLE_HOME/jdk/bin/java -version 2>&1
```

- Oracle's packaging of JDK updates has changed over time: separate quarterly JDK
  patches, or JDK updates included in the RU. **Check the RU README** for your
  release.
- If the JDK isn't included, apply the separate JDK patch to **every** DB and Grid
  home in the same patch cycle. Search MOS for "JDK and PERL patches for Oracle
  Database Home and Fusion Middleware Home".

---

## 6. Known Oracle 19c Issues on Power (as of May 2024)

Check the current status on My Oracle Support.

| Issue | Affected | Resolution |
|---|---|---|
| Extended statistics locking (spin waits) under high-concurrency OLTP | 19c < 19.13 | 19.13 or later (prefer the current RU) |
| Too many LMS processes on very large RAC LPARs | 19c on large Power10/Power11 | Follow MOS guidance for the LMS count on large systems. Don't change `gcs_server_processes` blindly |
| AWR missing OS metrics with > 1031 logical CPUs | 18c / 19c | One-off patch from Oracle Support (see `cpu.md` §6) |
| VG doesn't see grown LUNs | AIX after a SAN resize | `cfgmgr` then `chvg -g <vg>`, after checking APAR IJ46487 (`io-storage.md` §11) |

```bash
: "${ORACLE_HOME:?ORACLE_HOME is not set}"   # see the pre-flight check in SKILL.md
$ORACLE_HOME/OPatch/opatch lspatches
ps -ef | grep "[o]ra_lms" | wc -l          # LMS process count per instance
```

---

## 7. pigz with zlibNX: Hardware-Accelerated gzip (Power9/10/11)

Power9, Power10, and Power11 have an **NX GZIP accelerator**.

- `pigz` (parallel gzip) uses it through the **zlibNX** library on AIX 7.2 TL4
  and later.
- It's on the base media from AIX 7.2 TL5 SP2 and installed by default on AIX 7.3.
- Use `pigz`, not `xgzip` (deprecated, single-threaded) or `pixz` (xz, which
  doesn't use NX).

```bash
lslpp -l zlibNX.rte                 # library installed?
nxstat -S                           # accelerator availability for this LPAR
prtconf | grep -i "Processor Implementation Mode"
```

| Hardware | Compatibility modes that enable NX GZIP |
|---|---|
| Power9 (firmware FW940 or later) | POWER9 |
| Power10 | POWER9 or POWER10 |
| Power11 | POWER9, POWER10, or POWER11 (native from AIX 7300-03-01) |

**`POWER9_Base` mode disables the accelerator** on every generation.

```bash
pigz -p 8 /backup/full_01.bkp       # parallelism 8 gave the best throughput in IBM tests
tar -cf - /u02/export | pigz -p 8 > /backup/export.tar.gz
```

- In IBM ATG tests (E980, 16 cores, about 230 GB), `tar | gzip` took 3 h 15 min
  and `tar | pigz -p 8` took 4 min 31 s.
- Throughput is usually limited by the I/O subsystem.
- Higher compression levels than the default `-6` add a lot of time for little
  gain.
- Uses: compressing RMAN backup pieces or archived logs before shipping them, and
  data migrations. The output is standard gzip.

> **APAR IJ47907:** potential undetected data loss using zlibNX. Confirm the fix
> is installed (`instfix -ik IJ47907`) before using it in production.
> Reference: IBM Community, "GZIP Acceleration with AIX on Power Systems" (Brian
> Veale, 2022).

---

## 8. PowerVS Storage Tiers for Oracle

PowerVS tiers are rated in **IOPS per GB**, so a volume's IOPS grow with its size.

| Tier | IOPS/GB | Typical Oracle use |
|---|---|---|
| Tier 0 | 25 | Redo logs, latency-critical OLTP data |
| Tier 1 | 10 | Data, indexes, temp |
| Tier 3 | 3 | Binaries, archive logs, RMAN backups |
| Fixed IOPS | 5,000 per volume, regardless of size | Small volumes that need a guaranteed IOPS floor |

Check the current tier definitions and limits in the IBM Cloud PowerVS
documentation. They change over time.

```bash
ibmcloud pi volume create --help        # check flag names for your CLI version (tier flag)
ibmcloud pi volume list
ibmcloud pi volume get <volume-id>      # shows the tier
```

If AWR shows `db file sequential read` or `log file parallel write` above target,
check the tier and size **before** tuning AIX. A larger volume, or a higher tier
where PowerVS allows changing it, raises the IOPS ceiling.

---

## 9. Key Reference Documents

1. **IBM: "AIX with Oracle Database on IBM Power Systems: Considerations for
   Performance and Stability"**, the living document for parameters, APARs and
   iFixes: https://www.ibm.com/support/pages/node/6825029
2. **Oracle certification matrix** (MOS, Certifications tab).
3. IBM Power Systems VUG decks (May 2024):
   `OracleOnPowerTuningConsiderations_CPU_Memory_NEXT.pptx`,
   `OracleOnPowerTuningConsiderations_AIX_IO_Misc_NEXT.pptx`.
