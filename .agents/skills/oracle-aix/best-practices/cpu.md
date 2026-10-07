---
name: oracle-aix-best-practices-cpu
description: >-
  Use when tuning CPU and LPAR configuration for Oracle Database on IBM Power Systems / AIX.
  Covers SMT mode selection, CPU folding, vpm_throughput_mode, vCPU sizing, entitlement ratios,
  dedicated vs shared LPARs, virtual processor dispatch monitoring, and Oracle CPU-related
  parameters. Trigger phrases: "CPU tuning Oracle AIX", "SMT Oracle Power", "vpm_throughput_mode",
  "CPU folding AIX", "vCPU entitlement ratio", "lparstat Oracle", "mpstat dispatch", "schedo",
  "parallel threads per cpu", "Oracle cpu_count AIX", "dedicated cpu lpar", "shared processor pool Oracle".
---

# Oracle Power CPU Tuning

Expert guidance for CPU and LPAR configuration for Oracle Database on IBM Power Systems.

---

## 1. SMT Mode Selection

IBM Power supports Simultaneous Multi-Threading (SMT) modes: SMT1, SMT2, SMT4, SMT8.

### Recommendations

| Platform | Default Recommendation | Notes |
|---|---|---|
| Power11 | SMT8 | AIX 7.3 TL3 SP1+ recommended (native mode); see Power11 section below |
| Power10 | SMT8 | Best overall throughput; default on AIX 7.0.3 |
| Power9 | SMT8 | Best overall throughput |
| Power8 | SMT4 | Previous best practice |

- **Start with SMT8** for Power9/Power10/Power11 Oracle workloads.
- If workload does not leverage additional logical processors (e.g., single-threaded OLTP with very low parallelism), evaluate SMT4 — may improve per-thread response time.
- Changing SMT mode **dynamically changes the number of logical CPUs** — which directly impacts Oracle parameters: `cpu_count`, `db_writer_processes`, `parallel_max_servers`, cost-based optimizer decisions. Verify after any SMT change.
- Changing SMT mode also **changes memory pool count** — monitor for uneven pool distribution after dynamic changes.

```bash
# Check current SMT level
smtctl

# Change SMT level (persistent)
smtctl -m off -w boot    # SMT1
smtctl -m 4 -w boot      # SMT4
smtctl -m on -w boot     # SMT8 (default for Power9/10)
```

---

## 2. CPU Folding and vpm_throughput_mode

**CPU folding** (AIX 6.1+): AIX avoids scheduling work on virtual processors (VPs) that have nothing to do, and tells the hypervisor not to dispatch those VPs to physical CPUs. This reduces wasted physical CPU cycles.

### vpm_throughput_mode Parameter (schedo)

Controls when AIX "unfolds" (activates) an additional VP when workload grows.

| Mode | Behavior | Use Case |
|---|---|---|
| 0 | Unfolds a new VP as soon as ALL primary threads of all unfolded VPs are busy | Best response time, highest physical CPU usage |
| 1 | Unfolds when all primary + secondary threads of active VPs are busy | AIX 7.0.3 Power9 default |
| 2 | Unfolds when all primary + secondary threads of active VPs are busy | AIX 7.0.3 Power10 default (**recommended for Power10**); likely default for Power11 — verify after migration |
| 4 | Unfolds when 4 threads per active VP are busy | Higher throughput per physical CPU |
| 8 | Unfolds when all 8 threads per active VP are busy (SMT8 full) | Maximum physical CPU efficiency, but highest response time |

**Power10 default**: AIX 7.0.3 on Power10 automatically uses `vpm_throughput_mode=2` (upgraded from 1 on Power9). This is based on Power10's physical architecture and proven to be the best balance.

> **Note**: On a fresh AIX 7.0.3 installation on Power10, the default is mode=2. The value is **preserved** across hardware migrations — it is not automatically changed. If migrating from Power9 (where mode=1 is the default), your LPAR will retain mode=1 on Power10 unless you explicitly change it.

> **Power11 note**: ⚠️ The default `vpm_throughput_mode` set by AIX on Power11 has not been confirmed in available documentation. After migrating to Power11, always verify the value with `schedo -a | grep vpm_throughput_mode` and check IBM's AIX 7.3 TL release notes for the Power11-specific default.

```bash
# Check current setting
schedo -a | grep vpm_throughput_mode

# Adjust (example — Power10, mode 2 is default and recommended)
schedo -p -o vpm_throughput_mode=2
```

### vpm_throughput_cost_threshold Parameter

Modifies the transition point for CPU folding:

- If the number of unfolded VPs is **below** this threshold, AIX behaves as if `vpm_throughput_mode=0` (most aggressive unfolding) regardless of the mode setting.
- Default: 1 (minimal effect). Increasing this value allows fast ramp-up of VPs to meet entitlement, then switches to the more efficient mode.
- Special value `0`: Aggressively unfolds VPs until entitlement is met, then switches to the configured mode. This is especially beneficial for multi-LPAR shared processor pools.

```bash
schedo -a | grep vpm_throughput_cost_threshold
schedo -p -o vpm_throughput_cost_threshold=0
```

### vpm_3_cpus Parameter

Specifies the **minimum number of VPs** AIX will keep unfolded at all times — prevents all VPs from being folded during idle periods.

```bash
schedo -a | grep vpm_3_cpus
# Set minimum 2 VPs always active (example for a database with periodic bursts)
schedo -p -o vpm_3_cpus=2
```

---

## 3. Monitoring Virtual Processor Dispatch Efficiency

The `mpstat -v` command (AIX 7.0.1 TL3 SP2+) shows how long each VP was actually running on a physical CPU. This is the **only** time your workload makes real progress.

```bash
mpstat -v 5
```

Key fields:
- **`run`**: Milliseconds the VP was dispatched to a physical CPU (in the sample interval).
- If VP ran for 4995ms out of 5000ms → very efficient (near 100% physical CPU usage).
- If VP ran for only 1000ms out of 5000ms → physical CPUs are oversubscribed; workload will suffer.

**Interpretation**: In a shared processor pool where demand exceeds physical capacity, `run` values will drop. This is an early warning for CPU starvation.

---

## 4. vCPU Sizing Rules

### Capped vs. Uncapped LPARs

| LPAR Type | vCPU Recommendation |
|---|---|
| **Capped** | Set vCPU to nearest integer **≥** entitlement (e.g., entitlement=3.5 → vCPU=4) |
| **Uncapped** | Set vCPU to **peak CPU demand** of the workload |

### Over-Allocation Limits

| Environment | Max vCPU:Entitlement Ratio |
|---|---|
| Production | ≤ 1.3× (preferred) to 1.5× (maximum) |
| Non-production | Can be higher (e.g., 3–5×), as entitlement is low |

> **Rule**: vCPU count must always be ≤ physical capacity of the Shared Processor Pool (SPP). If your SPP has 16 physical cores and your LPAR has 20 vCPUs, 4 vCPUs can never be dispatched simultaneously — pure waste.

### Why Over-Allocating vCPUs Matters
- Each vCPU in the mix that the hypervisor must cycle through adds scheduling overhead.
- Before CPU folding (pre-AIX 6.1), the penalty was severe. With CPU folding, it is lower but still non-zero.
- **NUMA impact**: The hypervisor uses `max_virtual_procs` (not current vCPU count) when determining the physical spread of LPAR resources. Setting max too high can force multi-CEC placement.

```bash
# Check LPAR configuration
lparstat -i

# Monitor CPU entitlement utilization
lparstat 1 10    # Shows %ent (entitlement usage %)
# If %ent consistently > 100%, the LPAR is using cap-busting cycles (uncapped)

# DLPAR CPU add/remove is recognized by Oracle automatically
# Oracle updates cpu_count, db_writer_processes, etc. without restart
```

---

## 5. Dedicated vs. Shared CPU LPARs

| Type | Best For | Trade-off |
|---|---|---|
| **Dedicated CPU** | Latency-sensitive, single/lightly threaded OLTP | Best response time; lowest flexibility; CPU cycles wasted if idle |
| **Shared CPU (SPP)** | Most Oracle workloads | Flexible, better utilization; slightly higher latency variability |
| **Dedicated Donating** | Dedicated with some sharing | Finer-grained than dedicated, but less flexible than shared SPP |

- In practice, **most Oracle on AIX environments use shared CPU LPARs** with a Shared Processor Pool.
- Dedicated CPUs are warranted only for very latency-sensitive workloads with consistent, predictable demand.

---

## 6. Oracle CPU-Related Parameters on AIX

### cpu_count
On AIX with SMT, `cpu_count` reflects **logical CPUs** (SMT threads), not physical cores.
- SMT8 with 4 physical cores = `cpu_count = 32`.
- Automatically updated by Oracle when DLPAR CPU changes occur.

### db_writer_processes (DBWn)
- Default: 1 process per every 8 logical CPUs.
- Automatically scales with `cpu_count`.

### GCS Server Processes (RAC)
- In RAC, the number of GCS (Global Cache Service) server processes is based on CPU count.
- **Must match across all RAC instances** in a cluster. If different, RAC interconnect performance degrades.

### Degree of Parallelism
- Default degree on AIX: `cpu_count × parallel_threads_per_cpu`
- `parallel_threads_per_cpu` default on AIX = **2**
- With SMT4/SMT8, this may create too many parallel slaves. Consider reducing to 1:
  ```sql
  ALTER SYSTEM SET parallel_threads_per_cpu = 1;
  ```

### AWR Reporting Limitation on Large Systems
For Power10/Power11 or E1080 servers with > **1031 logical CPUs**: AWR does not report some server detail metrics.
- Power11 systems (especially E1150/E1180 with many cores at SMT8) are particularly susceptible to this limit.
- **Fix**: Apply Oracle one-off patch (Bug listed in Oracle MOS). Request from Oracle Support for your specific release (19c, 18c, etc.).

```sql
-- Check cpu_count
SHOW PARAMETER cpu_count;

-- Check parallel settings
SHOW PARAMETER parallel_threads_per_cpu;
SHOW PARAMETER parallel_max_servers;

-- Verify dbwriter count
SELECT name, value FROM v$parameter WHERE name = 'db_writer_processes';
```

---

## 7. LPAR Configuration Best Practices for CPU

```bash
# Full LPAR configuration report (use this for Oracle licensing documentation)
lparstat -i

# Key fields in lparstat -i output for Oracle licensing:
# - Maximum Virtual CPUs
# - Shared Physical CPUs
# - Maximum Physical CPUs
# - Entitled Capacity
# - Shared Processor Pool (max_pool_capacity)
```

### Checklist

1. **Set `max_virtual_procs` to the realistic maximum** your workload will ever need — not an arbitrary large number.
2. **Set `max_memory` to the realistic maximum** — over-allocation forces multi-CEC placement for both CPU and memory.
3. For shared processor LPARs: keep **vCPU:entitlement ≤ 1.5×** for production.
4. For production: `vpm_throughput_mode=2` is the AIX 7.0.3 default on fresh Power10 installations; mode=1 is the default on Power9. These values are **preserved across hardware migrations** — explicitly verify and adjust post-migration if the retained value is no longer optimal for the destination platform.
5. For latency-critical workloads with pool competition, evaluate `vpm_throughput_cost_threshold=0` to enable fast VP ramp-up.
6. Stay current on **firmware** — past firmware bugs caused suboptimal CPU/memory allocation algorithms.
7. Control **LPAR boot order**: high-priority LPARs boot first to get optimal physical placement.
8. After any vCPU/SMT change, verify **Oracle parameters** that are derived from `cpu_count`.

---

## 8. IBM Power Virtual Server (PowerVS) — CPU Notes

- PowerVS uses the same physical infrastructure as on-premises Power servers.
- Oracle LPARs in PowerVS **must be hard-pinned** (no Live Partition Mobility — LPM) due to Oracle licensing rules.
- Hard-pinning means the PowerVS SLA (which assumes LPM capability) does not apply → additional HA technology required (PowerHA, HADR, Oracle Data Guard, RAC).
- CPU and memory resources for Oracle LPARs can be dynamically allocated/released via PowerHA Resource Optimization.

---

## 9. IBM Power11 — CPU Tuning Notes

Power11 was announced in October 2024. The following reflects IBM public product information.

### Confirmed for Power11

| Item | Detail |
|---|---|
| **Announcement** | October 2024 |
| **Models** | Scale-out: S1112 (SE2-eligible), S1024, S1042 (e.g. L1122/L1124) / Enterprise: E1150, E1180 |
| **Minimum AIX (supported)** | AIX 7.2 TL5 SP10 (7200-05-10-2520) or AIX 7.3 TL2 SP4 (7300-02-04-2520) — runs in **POWER9/POWER9_Base compatibility mode** |
| **Recommended AIX (native)** | AIX 7.3 TL3 SP1 (7300-03-01) or later — enables **POWER11 native compatibility mode**; AIX 7.3 TL4 is the current preferred level |
| **SMT support** | SMT8 supported; SMT1/2/4/8 modes available — same `smtctl` command |
| **Core count** | Up to 24 cores per chip (increased from 15 on Power10) |
| **Hardware compression** | NX GZIP hardware accelerator confirmed for Power11. Use `pigz -p 8` with `zlibNX`. Requires `POWER9`, `POWER10`, or `POWER11` compat mode — NOT `POWER9_Base`. Verify with `nxstat -S`. |
| **cpu_count behaviour** | Same SMT-based logical CPU counting applies: 4 physical cores × SMT8 = 32 logical CPUs |
| **AWR >1031 CPU patch** | Still required — Power11 E1150/E1180 configurations with many cores at SMT8 will exceed 1031 logical CPUs; request Oracle patch for your release |
| **CPU folding** | Still controlled via `schedo vpm_throughput_mode` — mechanism unchanged |

```bash
# After migrating to Power11, always verify
smtctl                                          # Confirm SMT level
schedo -a | grep vpm_throughput_mode            # Verify AIX-set default for Power11
lssrad -va                                      # Check NUMA topology (new chip layout)
lparstat -i | grep -E "Mode|Type|Entitled"      # Confirm LPAR config carried over correctly
```

### AIX Compatibility Mode — Power9 / Power10 / Power11

| Power Generation | AIX Level | Compatibility Mode | Notes |
|---|---|---|---|
| **Power9** | AIX 7.1 TL5+ / AIX 7.2 TL1+ | POWER9 / POWER9_Base | Native Power9 mode |
| **Power10** | AIX 7.2 TL4+ | POWER10 / POWER10_Base | Native Power10 mode; `vpm_throughput_mode` default = 2 on fresh AIX 7.0.3 install |
| **Power11** | AIX 7.2 TL5 SP10 (7200-05-10-2520) | POWER9 / POWER9_Base | Runs on Power11 hardware in compat mode only; no Power11-native features |
| **Power11** | AIX 7.3 TL3 SP1 (7300-03-01) | **POWER11 native** | First AIX level with native Power11 mode; minimum for full capability |
| **Power11** | AIX 7.3 TL4 | **POWER11 native** | Current preferred level for new Power11 deployments |

```bash
# Check the active processor compatibility mode on any Power generation
lparstat -i | grep -i "compat"
# or
prtconf | grep -i "Processor Version"
```

### Migration Checklist: Power10 → Power11

**1. Plan and upgrade the AIX level before the hardware migration.**

Target **AIX 7.3 TL4** (fix support through December 2028):
- AIX 7.3 TL3 SP1: first level with native Power11 mode
- AIX 7.3 TL4: adds Power11-specific scalability, up to 256 cores / 2048 hardware threads per LPAR
- Upgrade AIX **before** moving to Power11 hardware whenever practical.

**2. Capture a complete `lparstat -i` snapshot before migration.**

```bash
lparstat -i > /tmp/lparstat-pre-migration-$(hostname)-$(date +%Y%m%d).txt
```

**3. Capture `schedo` and `vmo` parameter baselines before migration.**

```bash
schedo -a > /tmp/schedo-pre-migration-$(hostname)-$(date +%Y%m%d).txt
vmo -a    > /tmp/vmo-pre-migration-$(hostname)-$(date +%Y%m%d).txt
```

**4. After migration — verify processor compatibility mode.**

```bash
lparstat -i > /tmp/lparstat-post-migration-$(hostname)-$(date +%Y%m%d).txt
diff /tmp/lparstat-pre-migration-*.txt /tmp/lparstat-post-migration-*.txt
```

**5. After migration — reassess NUMA/SRAD topology.**

```bash
lssrad -va
mpstat -d 1 30    # Check S3hrd (local) / S4hrd (near) / S5hrd (far) ratios
```

**6. After migration — review `vpm_throughput_mode` for Power11 optimality.**

```bash
schedo -a | grep vpm_throughput_mode
```

**7. Revalidate Oracle CPU configuration.**

```sql
-- Verify Oracle sees the correct logical CPU count
SHOW PARAMETER cpu_count;
SHOW PARAMETER parallel_threads_per_cpu;
SHOW PARAMETER parallel_max_servers;
```

**8. Check AWR for `> 1031 logical CPUs` warning** if on large E1150/E1180 configs with SMT8.

**9. Verify Oracle SE2 eligibility for Power11** with Oracle licensing team if planning an SE2 deployment.

---

## References

- IBM Support: AIX on Power11 supported levels — https://www.ibm.com/support/pages/node/7240644
- IBM Support: Power11 AIX compatibility modes — https://www.ibm.com/support/pages/node/7282898
- IBM AIX Support Lifecycle — https://www.ibm.com/support/pages/aix-support-lifecycle-information
- AIX with Oracle Database on IBM Power Systems — Performance and Stability: https://www.ibm.com/support/pages/node/6825029
