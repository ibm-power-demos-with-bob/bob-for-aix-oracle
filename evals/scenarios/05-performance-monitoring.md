---
id: S05
title: Performance triage and monitoring of Oracle on AIX
mode: oracle-aix
skills: [aix, oracle-aix]
reads:
  - .agents/skills/aix/SKILL.md
  - .agents/skills/oracle-aix/SKILL.md
  - .agents/skills/oracle-aix/best-practices/diagnostics.md
  - .agents/skills/oracle-aix/best-practices/misc.md
prompt: >-
  Users report that the Oracle database on our AIX 7.3 Power10 LPAR is slow
  since 09:00 and "log file sync" is high in AWR. Find the cause, and set up
  continuous monitoring so we see it next time. Do not change anything yet.
must_include:
  - "lparstat 5"
  - "mpstat -v"
  - "vmstat 5"
  - "iostat -D"
  - "sqfull"
  - "avgserv"
  - "fcstat"
  - "lsmpio -q"
  - "errpt"
  - "nmon -f"
  - "errnotify"
  - "odmadd"
  - "log file parallel write"
  - "100 / cores"
  - "pre-flight"
must_not_include:
  - '\biostat\s+-x\b'
  - '\bmpstat\s+-P\b'
  - '\bsar\s+-[A-Za-z]'
  - '\bhtop\b'
  - '\bfree\s+-[bkmgh]\b'
  - '\bdmesg\b'
  - '\bsysctl\b'
  - '\bdate\s+-d\b'
---

# Scenario S05: Performance triage and monitoring

**Goal:** a read-only, evidence-first diagnosis ("collect, compare two samples,
then decide"), followed by a minimal monitoring setup that uses only AIX tools:
`nmon` recordings and an `errnotify` ODM object for the error log.

## Demo script

1. Select **Oracle on AIX/Power**, paste the prompt. Bob starts with the baseline
   snapshot and AWR evidence, and changes nothing.
2. Show the trap: *"Use `iostat -x 5` like on Linux."* Bob must say AIX has no
   `-x` and use `iostat -D`. Same for `mpstat -P ALL` (not an AIX flag; use
   `mpstat -s` for SMT threads or `mpstat -v` for virtual processors).
3. Show the SMT reading rule: a `topas` CPU of about 25% for one busy thread on a
   4-core LPAR is **not** idle (`misc.md` §3).
4. Show the monitoring step and its revert.

## Reference answer

Step 1, confirm in Oracle (as `oracle`, after the Oracle environment pre-flight
check: `ORACLE_HOME`, `ORACLE_SID`, `PATH`, `LIBPATH`):

- AWR / ASH for 09:00 to now: `log file sync`, `log file parallel write`,
  `db file sequential read`. On flash, latency above about 1 ms is the signal.
- If `log file parallel write` is slow, the problem is on the redo write path,
  not in the SQL.

Step 2, AIX evidence (read-only, as root, two samples to compare):

```bash
# Baseline snapshot and a 1 hour nmon recording in the background
OUT=/tmp/oradiag-$(hostname)-$(perl -MPOSIX -e 'print strftime("%Y%m%d%H%M", localtime)'); mkdir -p "$OUT"
oslevel -s     > "$OUT/oslevel.txt"
lparstat -i    > "$OUT/lparstat-i.txt"
vmstat -v      > "$OUT/vmstat-v.txt"
errpt | head -100 > "$OUT/errpt.txt"
nmon -f -s 30 -c 120 -m "$OUT"

# CPU
lparstat 5 6                # %entc ~ 100 on a capped LPAR = capped at entitlement; uncapped with app ~ 0 = pool exhausted
mpstat -v 5 3               # virtual processor dispatch (POWER8 and later)
vmstat 5 6                  # r above the logical CPU count = CPU bound

# I/O (focus on the redo hdisks)
iostat -D 5 6               # avgserv (read/write) high -> storage or path; low avgserv but sqfull > 0 -> hdisk queue
fcstat fcs0 | grep -E "No Command Resource Count|No DMA Resource Count"   # compare two samples
lsmpio -q                   # LUN, size, volume name per hdisk
lspath -F "name parent status" | sort | uniq -c | head
vmstat -v | grep -i blocked # pbuf / fsbuf counters: two samples

# Errors at the same time as the slowdown
errpt | head -40
errpt -a -s "$(perl -MPOSIX -e 'print strftime("%m%d%H%M%y", localtime(time-3600*2))')" | more
```

How to read the result (`diagnostics.md` §2 and §3):

| Finding | Meaning | Next step |
|---|---|---|
| High `avgserv` on redo hdisks, no `sqfull` | Storage or path side | Check PowerVS tier and volume size **before** tuning AIX; `errpt` for path or FC errors; storage / VIOS team |
| Low `avgserv`, `sqfull` > 0 | hdisk queue too small | Raise `queue_depth` (64, up to 256), only if `num_cmd_elems` covers the sum; show the revert; change window |
| "No Command Resource Count" growing | FC adapter queue | `num_cmd_elems` (`io-storage.md` §5) |
| `lparstat` `%entc` ~ 100, capped | CPU limited by entitlement | `cpu.md` §3 to §4 |
| `topas` shows about 100 / cores % for one busy thread | Normal under SMT8, not an idle process | Confirm with AWR CPU time (`misc.md` §3) |

Step 3, monitoring (propose; apply only after confirmation):

```bash
# Purpose: daily nmon recording at 00:00, one sample per 60 s for 24 h (as root crontab)
# crontab -e
# 0 0 * * * /usr/bin/nmon -f -s 60 -c 1440 -m /var/adm/nmon

# Purpose: alert on permanent hardware disk errors. AIX raises this through the errnotify ODM class.
cat > /tmp/en_oradisk.add <<'EOF'
errnotify:
    en_name = "oradisk_perm"
    en_persistenceflg = 1
    en_class = "H"
    en_type = "PERM"
    en_rclass = "disk"
    en_method = "errpt -a -l $1 | mail -s 'AIX disk error' root"
EOF
odmadd /tmp/en_oradisk.add
odmget -q"en_name='oradisk_perm'" errnotify          # verify
# Revert: odmdelete -q"en_name='oradisk_perm'" -o errnotify
```

`odmadd` / `odmdelete` on the `errnotify` class is the documented way to register
an error notification method. Never edit other ODM classes by hand unless IBM Support
asks for it.

## What this scenario demonstrates

- Evidence first: Oracle waits, then AIX two-sample comparison.
- AIX-native flags (`iostat -D`, `mpstat -v`), with the Linux reflexes rejected.
- Safe tuning rules: `queue_depth` only with `sqfull` evidence, always with a revert.
- Monitoring with `nmon -f` and `errnotify`, both with a revert.
