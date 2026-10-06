# Oracle DB on AIX/Power -- Platform Identity Rules

These rules are always active in the `oracle-power` mode, regardless of which skill is loaded.

## Platform Constraints

- **AIX commands only** -- never substitute Linux equivalents for any OS-level operation.
  | Task | AIX command | Never use |
  |---|---|---|
  | Error log | `errpt` | `dmesg`, `journalctl` |
  | Device listing | `lsdev`, `lsattr` | `lspci`, `udevadm` |
  | Memory / CPU tuning | `vmo`, `ioo`, `schedo`, `no` | `sysctl` |
  | Performance | `topas`, `nmon`, `svmon` | `htop`, `free` |
  | LV management | `lslv`, `mklv`, `chlv`, `lsvg` | `lvcreate`, `lvextend` |
  | User management | `lsuser`, `chuser`, `mkuser` | `useradd`, `usermod` |

- **Library path on AIX**: always use `LIBPATH`, never `LD_LIBRARY_PATH`.

  ```bash
  export LIBPATH=$ORACLE_HOME/lib:/usr/lib
  ```

- **Oracle environment** must be set before any Oracle command:

  ```bash
  export ORACLE_BASE=/u01/app/oracle
  export ORACLE_HOME=$ORACLE_BASE/product/19.0.0/dbhome_1
  export ORACLE_SID=<SID>
  export PATH=$ORACLE_HOME/bin:$PATH
  export LIBPATH=$ORACLE_HOME/lib:/usr/lib
  ```

## Power Platform Awareness

- Oracle on Power has specific tuning considerations that differ from x86 Linux:
  - SMT threading model affects `cpu_count` and all derived Oracle parameters.
  - NUMA/SRAD topology affects SGA memory latency.
  - 16MB large pages are a Power-specific SGA optimization.
  - Fiber channel SAN via NPIV/VIOS is the standard storage path.
- Always consider the IBM Power hardware layer when diagnosing Oracle performance issues.
- When relevant, ask or note which Power generation (Power8/9/10/11) and AIX version (7.1/7.2/7.3/7.3 TL3+) the user is on -- recommendations differ.

## Skill Routing (always-on awareness)

The following skills are available and will auto-activate on matching topics.
If a topic clearly falls into one of these areas, proactively load the skill:

| Topic | Skill to activate |
|---|---|
| Memory pools, SGA page size, 16MB pages, vmo, minfree, JFS2 inode cache, NUMA/SRAD | `oracle-best-practices-memory` |
| SMT mode, vCPU sizing, CPU folding, vpm_throughput_mode, entitlement, lparstat | `oracle-best-practices-cpu` |
| hdisk, qdepth, fiber channel, ASM layout, JFS2 mount options, striping, CIO/DIO | `oracle-best-practices-io-storage` |
| Oracle licensing, hard partition, CAPPED LPAR, SPP, PowerVS, lparstat -i | `oracle-best-practices-licensing` |
| Oracle 19c install/patch, mutex spin count, mark_hot, CPU% SMT, RAC network/IPv6, ASM redundancy, pigz parallelism, zlibNX, PowerVS storage tiers, IBM Java update, known 19c bugs | `oracle-best-practices-misc` |
| General Oracle DBA tasks (SQL, RMAN, Data Guard, AWR, patching, RAC) | `oracle-dba-aix` |

Future skill categories planned:
- `oracle-admin-*` -- administration tasks (RMAN, patching, Data Guard operations)
- `oracle-tuning-*` -- optimization and SQL/AWR tuning
- `oracle-arch-*` -- architecture (RAC design, Data Guard topology, storage architecture)
