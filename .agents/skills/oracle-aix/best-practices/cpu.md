# Oracle on Power: CPU and LPAR Tuning

> **Read this file for:** SMT mode, CPU folding (`vpm_throughput_mode`), vCPU and
> entitlement sizing, dedicated vs shared LPARs, VP dispatch monitoring, Oracle
> parameters derived from `cpu_count`, and Power11 migration.
> **Source:** IBM Power Systems VUG May 2024 (Ralf Schmidt-Dannert, IBM ATG), plus
> the IBM support notes listed at the end.
> **Before changing any `schedo` tunable**, check that it exists at the user's
> AIX level and show its default and type with `schedo -L <tunable>`.

---

## 1. SMT Mode Selection

IBM Power supports the SMT modes SMT1, SMT2, SMT4, and SMT8 (SMT8 on Power8 and
later).

| Platform | Starting recommendation | Notes |
|---|---|---|
| Power11 | SMT8 | AIX 7.3 TL3 SP1+ for native POWER11 mode (see §9) |
| Power10 | SMT8 | Best overall throughput |
| Power9 | SMT8 | Best overall throughput |
| Power8 | SMT4 | Previous best practice |

- **Start with SMT8** for Oracle on Power9, Power10, and Power11.
- If the workload can't use the extra logical CPUs (for example single-threaded
  batch with low parallelism), evaluate SMT4. It may improve per-thread response
  time.
- Changing the SMT mode **changes the number of logical CPUs**. Oracle picks this
  up dynamically, and it affects `cpu_count`, `db_writer_processes`,
  `parallel_max_servers`, and optimizer costing. Check them after the change.
- Changing the SMT mode dynamically also **changes the number of memory pools**.
  Watch for uneven pool sizes afterwards (see `memory.md` §1).

```bash
# Show the current SMT mode
smtctl

# Change now (dynamic; lasts until reboot)
smtctl -t 4 -w now          # SMT4
smtctl -t 8 -w now          # SMT8

# Change at the next boot (persistent): then run bosboot and reboot
smtctl -t 4 -w boot
bosboot -a

# SMT off (SMT1). Prefer -t <n> to set an explicit thread count
smtctl -m off -w boot
```

---

## 2. CPU Folding and `vpm_throughput_mode`

**CPU folding**: AIX doesn't schedule work on virtual processors (VPs) it doesn't
need, and tells the hypervisor not to dispatch them. This reduces wasted physical
CPU cycles in shared pools.

### `vpm_throughput_mode` (schedo)

This tunable controls how many SMT threads of the already-unfolded VPs AIX loads
before it unfolds another VP.

| Mode | Behaviour | Trade-off |
|---|---|---|
| 0 | Legacy raw mode: unfold based on primary-thread utilisation | Best response time, highest physical CPU use |
| 1 | Enhanced raw mode: like 0, with a higher load threshold before unfolding | Slightly better efficiency than 0 |
| 2 | Scaled mode: load the primary and secondary threads of each VP first | Balanced. IBM ATG recommends it for Power10 |
| 4 | Scaled mode: load 4 threads per VP first | Higher throughput per physical core, longer response time |
| 8 | Scaled mode: load all 8 threads per VP first | Most efficient, highest response time |

Defaults described in the source: mode 1 on Power9 and mode 2 on Power10, with
AIX 7.3. Always read the actual value:

```bash
schedo -L vpm_throughput_mode       # CUR, DEF and BOOT values
schedo -p -o vpm_throughput_mode=2  # persistent change (stored in /etc/tunables/nextboot)
```

> **After a hardware migration:** a value set explicitly with `-p` is stored in
> `/etc/tunables/nextboot` and carries over to the new server. A value left at its
> default follows the default of the new platform and AIX level. Check
> `schedo -L vpm_throughput_mode` after every migration (see the §9 checklist).

### `vpm_throughput_core_threshold`

This sets how many VPs are unfolded in raw mode before the scaled mode chosen by
`vpm_throughput_mode` takes over.

- The default is 1.
- Raising it lets a busy LPAR ramp up VPs quickly, up to the threshold, and then
  switch to the more efficient mode.
- Useful for latency-sensitive LPARs in busy multi-LPAR shared pools.

```bash
schedo -L vpm_throughput_core_threshold
schedo -h vpm_throughput_core_threshold   # check the exact semantics at your AIX level
```

### `vpm_xvcpus`

This sets the number of **additional** VPs to keep unfolded beyond what the
current load needs. It's a way to absorb bursts at the cost of some efficiency.
The default is 0.

```bash
schedo -L vpm_xvcpus
schedo -p -o vpm_xvcpus=1     # example: keep one spare VP unfolded
```

---

## 3. Monitoring Virtual Processor Dispatch

`mpstat -v` shows how long each VP actually ran on a physical core. That is the
only time the workload makes progress.

```bash
mpstat -v 5 3
lparstat 5 6        # %entc (entitlement used), physc, app (idle cores in the pool)
```

- A VP that ran close to the full interval (for example 4995 ms out of 5000 ms) is
  being dispatched efficiently.
- Low run times while there is demand mean the shared pool is oversubscribed. This
  is an early warning of CPU starvation.
- `app` near 0 in `lparstat` confirms the pool has no idle capacity left.

---

## 4. vCPU Sizing Rules

| LPAR type | vCPU recommendation |
|---|---|
| **Capped** | The nearest integer **≥** the entitlement (for example EC 3.5 → 4 vCPUs) |
| **Uncapped** | The workload's **peak CPU demand** |

| Environment | Maximum vCPU : entitlement ratio |
|---|---|
| Production | ≤ 1.3× preferred, 1.5× maximum |
| Non-production | Can be higher (3–5×), since entitlement is low |

- **Rule**: an LPAR's vCPU count must not exceed the physical cores in its shared
  processor pool. Those extra vCPUs can never be dispatched together.
- **NUMA impact**: the hypervisor places LPAR resources based on
  `max_virtual_procs` (and maximum memory), not the current values. Inflated
  maximums can spread the LPAR across nodes (see `memory.md` §4).

```bash
lparstat -i     # LPAR configuration
lparstat 1 10   # %entc > 100 means an uncapped LPAR is using capacity beyond its entitlement
```

Oracle picks up DLPAR CPU changes automatically (`cpu_count`,
`db_writer_processes`, and so on) without a restart.

---

## 5. Dedicated vs Shared CPU LPARs

| Type | Best for | Trade-off |
|---|---|---|
| **Dedicated** | Latency-sensitive OLTP with steady demand | Best response time, idle cycles wasted |
| **Shared (SPP)** | Most Oracle workloads | Flexible and efficient, more latency variability |
| **Dedicated donating** | Dedicated with idle cycles given back to the pool | In between |

---

## 6. Oracle CPU-Related Parameters on AIX

- **`cpu_count`**: counts logical CPUs (SMT threads). 4 cores at SMT8 gives
  `cpu_count = 32`.
- **`db_writer_processes`**: by default the greater of 1 and `cpu_count / 8`.
- **RAC LMS (GCS server) processes**: the count is derived from `cpu_count`. Keep
  the CPU configuration consistent across RAC instances. Very large LPARs can start
  too many LMS processes (see `misc.md` §6).
- **Degree of parallelism**: the default DOP is
  `cpu_count × parallel_threads_per_cpu`. The default
  `parallel_threads_per_cpu` is 2 on most platforms, which can create too many
  PX servers at SMT4/SMT8. Consider 1:

```sql
SHOW PARAMETER parallel_threads_per_cpu                  -- record the current value
ALTER SYSTEM SET parallel_threads_per_cpu = 1 SCOPE=BOTH;
-- Revert: ALTER SYSTEM SET parallel_threads_per_cpu = <old_value> SCOPE=BOTH;
```

### AWR limitation above 1031 logical CPUs

On LPARs with **more than 1031 logical CPUs** (large E1080, E1150, or E1180 LPARs
at SMT8), AWR omits some OS detail metrics. Ask Oracle Support for the one-off
patch for your release.

```sql
SHOW PARAMETER cpu_count
SHOW PARAMETER parallel_threads_per_cpu
SHOW PARAMETER parallel_max_servers
SHOW PARAMETER db_writer_processes
```

---

## 7. LPAR CPU Checklist

1. Set `max_virtual_procs` to the realistic maximum, not an arbitrary large number.
2. Set maximum memory to the realistic maximum. Inflated maximums force spreading
   across nodes.
3. Keep vCPU : entitlement ≤ 1.5× for production shared LPARs.
4. Check `vpm_throughput_mode` (`schedo -L`). Mode 2 is the starting point on
   Power10 and Power11, and mode 1 on Power9.
5. For latency-critical LPARs in contended pools, evaluate
   `vpm_throughput_core_threshold`.
6. Keep system firmware current. Past firmware defects caused poor CPU and memory
   placement.
7. Control LPAR **boot order**: high-priority LPARs boot first and get the best
   placement.
8. After any vCPU or SMT change, recheck the Oracle parameters derived from
   `cpu_count`.

Key `lparstat -i` fields: Type, Mode, Entitled Capacity, Online/Maximum Virtual
CPUs, Shared Pool ID, and Maximum Capacity of Pool.

---

## 8. IBM Power Virtual Server (PowerVS)

- PowerVS runs on the same Power hardware and VIOS stack as on-premises systems.
- Oracle LPARs in PowerVS are deployed with a **hard pin policy** (no LPM). The
  PowerVS availability SLA, which relies on LPM, then no longer applies, so
  provide HA with PowerHA, Data Guard, or RAC.
- PowerHA Resource Optimized High Availability (ROHA) can grow a standby LPAR on
  failover.

---

## 9. IBM Power11 Notes

Power11 was announced in **July 2025**. Check models and levels against IBM's
current documentation. The items below come from the IBM support notes in the
References section.

| Item | Detail |
|---|---|
| Minimum AIX (supported) | AIX 7.2 TL5 SP10 or AIX 7.3 TL2 SP4. These run in POWER9 / POWER9_Base compatibility mode |
| Native POWER11 mode | AIX 7.3 TL3 SP1 (7300-03-01) or later |
| SMT | SMT1/2/4/8, using the same `smtctl` commands |
| Hardware compression | NX GZIP is available. Needs POWER9, POWER10, or POWER11 mode, not POWER9_Base (see `misc.md` §7) |
| `cpu_count` | Same counting: cores × SMT threads |
| CPU folding | Same mechanism (`vpm_throughput_mode`). Check the default after migration |

### Check the compatibility mode

```bash
prtconf | grep -i "Processor Implementation Mode"   # e.g. POWER 10, POWER 9_Base
prtconf | grep -i "Processor Version"
```

### Migration checklist: Power9/Power10 → Power11

1. **Upgrade AIX before moving hardware** whenever you can. Target 7.3 TL3 SP1 or
   later for native mode.
2. **Record a baseline before migrating:**

   ```bash
   STAMP=$(hostname)-$(date +%Y%m%d)
   lparstat -i     > /tmp/lparstat-pre-$STAMP.txt
   schedo -L       > /tmp/schedo-pre-$STAMP.txt
   vmo -L          > /tmp/vmo-pre-$STAMP.txt
   lssrad -va      > /tmp/lssrad-pre-$STAMP.txt
   ```

3. **After migrating, compare.** Check the compatibility mode (`prtconf`), the
   SMT level, `lparstat -i`, and `schedo -L vpm_throughput_mode`.
4. **Reassess NUMA placement:** `lssrad -va` and `mpstat -d 1 30` (S3hrd local /
   S4hrd near / S5hrd far).
5. **Recheck Oracle:** `cpu_count`, `parallel_threads_per_cpu`, and
   `parallel_max_servers`. Check the AWR > 1031 logical CPU limit on large LPARs.

---

## References

- IBM Support: AIX on Power11 supported levels: https://www.ibm.com/support/pages/node/7240644
- IBM Support: Power11 AIX compatibility modes: https://www.ibm.com/support/pages/node/7282898
- IBM AIX support lifecycle: https://www.ibm.com/support/pages/aix-support-lifecycle-information
- AIX with Oracle Database on IBM Power, performance and stability: https://www.ibm.com/support/pages/node/6825029
- `schedo` command: https://www.ibm.com/docs/en/aix/7.3?topic=s-schedo-command
