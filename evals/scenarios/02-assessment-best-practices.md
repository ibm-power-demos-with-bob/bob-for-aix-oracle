---
id: S02
title: Assessment and best-practices review of an Oracle on AIX LPAR
mode: oracle-aix
skills: [oracle-aix]
reads:
  - .agents/skills/oracle-aix/SKILL.md
  - .agents/skills/oracle-aix/best-practices/cpu.md
  - .agents/skills/oracle-aix/best-practices/memory.md
  - .agents/skills/oracle-aix/best-practices/io-storage.md
  - .agents/skills/oracle-aix/best-practices/os-prereqs.md
prompt: >-
  Assess our Oracle 19c LPAR on AIX 7.3 (Power10, PowerVS) against the best
  practices: CPU/SMT, memory and large pages, storage layout and queue depth,
  OS users and limits, environment variables. Read-only, change nothing.
must_include:
  - "smtctl"
  - "lparstat -i"
  - "vmo -L lgpg_regions"
  - "v_pinshm"
  - "svmon -G"
  - "lsmpio -q"
  - "queue_depth"
  - "iostat -D"
  - "capabilities"
  - "LIBPATH"
  - "AIXTHREAD_SCOPE"
  - "srvctl getenv"
  - "read-only"
must_not_include:
  - '\bvmo\s+(-p\s+)?-o\b'
  - '\bchdev\b'
  - '\bchuser\b'
  - '\bmkuser\b'
  - '\bLD_LIBRARY_PATH\s*='
  - '\bsysctl\b'
---

# Scenario S02: Assessment against best practices

**Goal:** a read-only health check that turns the repository's rules into a
PASS / WARN / FAIL table. The same checks can be handed to the
**AIX/Oracle Review** mode to review a change plan before it is executed.

## Demo script

1. Select **Oracle on AIX/Power** and paste the prompt. Bob asks for (or
   captures) the context, then runs only read-only commands.
2. Show that every finding names the companion file it comes from
   (`cpu.md §1`, `memory.md §5`, `io-storage.md §7`, `os-prereqs.md §4`).
3. Switch to **AIX/Oracle Review**, paste a script that runs
   `chdev -l hdisk4 -a queue_depth=256` on a live ASM disk, and show that the
   review rates it HIGH (in-use disk, no revert, no `sqfull` evidence).

## Reference answer

All commands are read-only. Run them as `root` for the AIX layer, and as
`oracle` / `grid` for the Oracle layer after the pre-flight check passes.

```bash
# 1. Context
oslevel -s
prtconf | grep -E "System Model|Processor Type|Processor Implementation Mode"
lparstat -i | grep -E "^Type|^Mode|^Entitled Capacity|^Online Virtual CPUs|^Shared Pool ID"

# 2. CPU: expect SMT8 on Power10 (cpu.md §1)
smtctl | head -5
schedo -L vpm_throughput_mode

# 3. Memory and large pages (memory.md §5): only relevant for SGA >= 100 GB
vmo -L lgpg_regions
vmo -L v_pinshm            # must be 1 only when 16 MB pages are in use
svmon -G                   # 16 MB row: PoolSize vs inuse
lsuser -a capabilities oracle,grid    # CAP_NUMA_ATTACH,CAP_BYPASS_RAC_VMM,CAP_PROPAGATE

# 4. Storage layout (io-storage.md §7)
lsmpio -q                  # LUN count and size per pool: 8 DATA, 8 REDO, 2 to 4 FRA, equal sizes
lspath -F "name parent" | awk '{n[$2]++} END{for(p in n) print p, n[p]}'   # paths per fscsiX: balanced?
lsattr -El hdisk4 -a queue_depth -a reserve_policy -a max_transfer
iostat -D 5 3              # sqfull > 0 with avgserv < 1 ms is the only reason to raise queue_depth
fcstat fcs0 | grep -E "No Command Resource Count|No DMA Resource Count"

# 5. OS prerequisites (os-prereqs.md §3 to §5)
id oracle; id grid
lsdev -Cc iocp
lsattr -El sys0 -a maxuproc -a ncargs
lsuser -a fsize data stack rss nofiles cpu oracle,grid

# 6. Environment: use the Oracle pre-flight check from SKILL.md, then
env | grep -E '^(LIBPATH|LD_LIBRARY_PATH)='   # LIBPATH must hold $ORACLE_HOME/lib; LD_LIBRARY_PATH must be absent
srvctl getenv database -db <db>    # AIXTHREAD_SCOPE=S, AIX_TZCACHE=ON for Clusterware-managed databases
```

Findings table the answer must produce:

| Area | Check | PASS when | Source |
|---|---|---|---|
| CPU | SMT mode | `smtctl` shows SMT8 on Power10 | `cpu.md` §1 |
| Memory | Large pages | SGA >= 100 GB uses 16 MB pages with `v_pinshm=1` and `LOCK_SGA=TRUE`, otherwise default 64 KB and `ORACLE_SGA_PGSZ` unset | `memory.md` §5 |
| Storage | LUN counts | 8 DATA, 8 REDO, 2 to 4 FRA, equal sizes per pool | `io-storage.md` §7 |
| Storage | Flash tiers | redo and OLTP data on Tier 0 / Tier 1, backups on Tier 3, no mixed tiers per disk group | `io-storage.md` §7b |
| Storage | `queue_depth` | 64 on flash, raised only with `sqfull` evidence and `num_cmd_elems` budget | `io-storage.md` §7b |
| ASM | `AU_SIZE` | `4M` or `8M` (`v$asm_diskgroup.allocation_unit_size`) | `io-storage.md` §7b |
| OS | Users | `oracle` and `grid` exist and own their homes; otherwise **ask the user** | `os-prereqs.md` §4 |
| OS | Limits and `sys0` | unlimited limits, `maxuproc` >= 16384 | `os-prereqs.md` §4, §5 |
| Env | Library path | `LIBPATH` has `$ORACLE_HOME/lib`, `LD_LIBRARY_PATH` unset | `SKILL.md` |

Every FAIL row comes with the **change, its revert, and the safety note**, but
the assessment itself changes nothing.

## What this scenario demonstrates

- A reusable read-only audit built from the companion files, with sources.
- The review mode catching an unsafe `chdev` before it runs.
- Honest scoping: large pages are only recommended for SGA >= 100 GB.
