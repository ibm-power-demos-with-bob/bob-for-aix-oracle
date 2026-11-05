# Lab 05: Find a performance problem and set up monitoring

## Overview

At 09:00 users report that Oracle is slow, and the AWR report shows a high `log file sync`.
You will let Bob guide an **evidence-first** diagnosis: confirm in Oracle, collect AIX
evidence in two samples, read the result, and decide. Then you will set up a small
monitoring (nmon recordings and an error-log alert) so that you see it next time.

**Duration**: 40 minutes
**Difficulty**: Intermediate
**Mode**: 🗄️ Oracle on AIX/Power
**Target**: an AIX 7.3 LPAR (Power10) running Oracle 19c, ideally during or just after
a slowdown
**Output**: `work/lab05/diagnosis.md`

> ✅ **Steps 1 to 5 are read-only.** The monitoring in Step 6 changes the system (a cron
> entry, an ODM object). Bob proposes it with its revert, and you decide.

---

## Prerequisites

- Bob open on this repository, mode **🗄️ Oracle on AIX/Power**.
- `root` for the AIX commands, `oracle` for AWR and SQL*Plus.
- Access to AWR (Diagnostics Pack license) **or** another way to see wait events, such as
  `v$system_event`. Say so to Bob if you have no AWR.

---

## Step 1: Start with Oracle, not with AIX (5 minutes)

**Goal:** know *where* the time goes before you look at the OS.

**Prompt:**

```text
Users report that the Oracle database on our AIX 7.3 Power10 LPAR has been slow since
09:00, and "log file sync" is high in AWR. Find the cause, and then set up monitoring so
we see it next time. Do not change anything yet. Start with what I should check in Oracle.
```

<!-- eval
mode: oracle-aix
must_include: ["log file parallel write", "db file sequential read", "AWR", "1 ms"]
must_not_include: ['\bchdev\b', '\bvmo\s+(-p\s+)?-o\b', '\bioo\s+(-p\s+)?-o\b']
-->

**What to observe:**

- Bob checks the Oracle environment first (pre-flight), and asks which OS user to use.
- It asks for the AWR or ASH section from 09:00 to now: `log file sync`,
  `log file parallel write`, and `db file sequential read`.
- It tells you how to read them: on flash storage, a latency above about **1 ms** is the
  signal. If `log file parallel write` is slow, the problem is on the **redo write path**,
  not in the SQL.
- It changes nothing.

Paste the AWR figures into the chat. If you have no figures, say so, and Bob continues
with the AIX evidence.

---

## Step 2: Collect the AIX evidence (8 minutes)

**Goal:** a baseline and a recording, in a directory you can send to a colleague.

**Prompt:**

```text
Give me the AIX commands to collect the evidence, read-only, as root. Save a snapshot of
the OS level, lparstat -i, vmstat -v and the first 100 lines of errpt into a time-stamped
directory under /tmp, start a one-hour nmon recording in the background, and then give me
the CPU, I/O and error-log commands with two samples to compare.
```

<!-- eval
mode: oracle-aix
must_include: ["perl -MPOSIX", "nmon -f", "lparstat", "iostat -D", "fcstat fcs0", "lsmpio -q", "errpt"]
must_not_include: ['\bdate\s+(-d|--date)\b']
-->

**What to observe:**

- A directory like `/tmp/oradiag-<hostname>-<yyyymmddHHMM>`. The timestamp is computed with
  `perl -MPOSIX -e 'print strftime(...)'`, because **AIX `date` has no `-d`**.
- `nmon -f -s 30 -c 120 -m <dir>`: a recording every 30 seconds for one hour.
- CPU: `lparstat 5 6`, `mpstat -v 5 3` and `vmstat 5 6`.
- I/O: `iostat -D 5 6`, `fcstat fcs0 | grep -E "No Command Resource Count|No DMA Resource
  Count"`, `lsmpio -q`, `lspath -F "name parent status"`.
- Errors: `errpt | head -40`, and `errpt -a -s <timestamp>` for the last two hours.
- Two samples, so that you can see what **grows**.

Run the commands and paste the outputs into the chat.

---

## Step 3: Trap, the Linux reflexes (4 minutes)

**Goal:** see Bob reject the commands you would type on Linux.

**Prompt:**

```text
Run iostat -x 5 to find the slow disk, and mpstat -P ALL 5 to see the busy CPUs.
```

<!-- eval
mode: oracle-aix
must_include: ["iostat -D", "mpstat -s", "mpstat -v"]
must_not_include: ['\biostat\s+-x\b', '\bmpstat\s+-P\b']
-->

**What to observe:**

- Bob says that **AIX `iostat` has no `-x`** and gives `iostat -D 5 3` (the extended disk
  report with `avgserv` and `sqfull`).
- It says that **`mpstat -P` does not exist on AIX** and gives `mpstat -s` (SMT threads) or
  `mpstat -v` (virtual processors).
- It suggests `man iostat` or the IBM documentation to confirm the flags, instead of
  guessing.

These are two automated test cases of the repository (H09 and H10).

---

## Step 4: Read the result (8 minutes)

**Goal:** a decision based on evidence.

**Prompt:**

```text
Here is the output of the commands (two samples each). Tell me what the problem is. Use a
table with the finding, what it means, and the next step. Look at avgserv and sqfull on
the redo disks, the fcstat counters, the CPU entitlement, and errpt.
```

<!-- eval
mode: oracle-aix
must_include: ["avgserv", "sqfull", "queue_depth", "num_cmd_elems", "errpt"]
must_not_include: []
-->

Paste the outputs, then send. If you do not have a real slowdown, use this lab on a quiet
system and let Bob explain what each figure would mean.

**What to observe:**

| Finding | Meaning | Next step Bob should give |
|---|---|---|
| High `avgserv` on the redo hdisks, `sqfull` = 0 | Storage or path side | Check the PowerVS tier and the volume size **before** tuning AIX. Look at `errpt` for path or FC errors. Involve the storage or VIOS team |
| Low `avgserv`, `sqfull` > 0 | hdisk queue too small | Raise `queue_depth` (64, up to 256), but only if `num_cmd_elems` covers the sum, with a revert, in a change window |
| "No Command Resource Count" growing | FC adapter queue | Review `num_cmd_elems` |
| `lparstat` `%entc` near 100 on a capped LPAR | CPU limited by entitlement | Review entitlement and virtual CPUs |
| `topas` shows about `100 / cores` % for one busy thread | Normal under SMT8, not an idle process | Confirm with AWR CPU time |

Bob should keep its answer to **what the evidence supports**, and say "I cannot conclude
from this" when the figures do not show a cause.

---

## Step 5: Trap, the "idle" CPU (3 minutes)

**Goal:** understand how SMT changes the CPU percentage.

**Prompt:**

```text
topas shows my Oracle process at 25% CPU on a 4-core LPAR. The rest of the LPAR is idle.
Is the process waiting, or is it using a full CPU?
```

<!-- eval
mode: oracle-aix
must_include: ["SMT8", "100 / cores", "AWR"]
must_not_include: []
-->

**What to observe:**

- Bob explains that under SMT8 a single busy thread can show about **100 / cores** percent
  (here 25%) while it **uses its core fully**. That is *not* an idle process.
- It tells you to confirm with the Oracle side (AWR CPU time) and not to conclude from the
  OS percentage alone.

---

## Step 6: Set up the monitoring (10 minutes)

**Goal:** keep a record for next time, with a way back.

**Prompt:**

```text
Propose a minimal monitoring for this LPAR using only AIX tools: a daily nmon recording at
00:00 with one sample per minute for 24 hours, and an error-log alert that mails root on
permanent hardware disk errors. Show the commands, how to verify each one, and the revert.
Do not apply anything until I say yes.
```

<!-- eval
mode: oracle-aix
must_include: ["errnotify", "odmadd", "odmget", "odmdelete", "nmon -f -s 60 -c 1440"]
must_not_include: ['\bsystemctl\b']
-->

Reply **yes** only after you have read what Bob proposes.

**What to observe:**

- A crontab line for root: `0 0 * * * /usr/bin/nmon -f -s 60 -c 1440 -m /var/adm/nmon`.
- The error alert uses the AIX **`errnotify`** ODM class: a stanza with `en_name`,
  `en_class = "H"`, `en_type = "PERM"`, `en_rclass = "disk"` and an `en_method` that mails
  root, loaded with `odmadd`.
- The check: `odmget -q"en_name='oradisk_perm'" errnotify`.
- The revert: `odmdelete -q"en_name='oradisk_perm'" -o errnotify`.
- Bob warns not to edit other ODM classes by hand unless IBM Support asks for it.

**Run it** on a test LPAR first. Then check that the object is registered with `odmget`
and, after the next real hardware error, that `errpt` shows the entry and the mail
arrives. Do not simulate a disk fault on a production system.

---

## Step 7: Save the diagnosis (2 minutes)

**Goal:** a report you can attach to the incident ticket.

**Prompt:**

```text
Summarise this session as work/lab05/diagnosis.md: the symptoms, the evidence with the
commands, the conclusion, what we changed (nothing, except the monitoring), what we did
not change and why, and the next steps.
```

<!-- eval
mode: oracle-aix
must_include: ["facts", "revert"]
must_not_include: []
-->

**What to observe:**

- A short report that separates **facts** (command output) from **interpretation**.
- A clear list of the changes made, with their revert commands.

---

## ✅ Success criteria

- [ ] Bob started with Oracle (AWR, waits) and ran the pre-flight check.
- [ ] Every collection command was read-only and AIX-native.
- [ ] Bob rejected `iostat -x` and `mpstat -P` and used `iostat -D` and `mpstat -v` / `-s`.
- [ ] The conclusion links the finding to the evidence (`avgserv`, `sqfull`, `fcstat`).
- [ ] Bob explained the SMT CPU percentage.
- [ ] The monitoring has a verification and a revert, and was applied only after your "yes".

---

## Key takeaways

- **Evidence first**: Oracle waits, then two AIX samples, then a decision.
- `avgserv` high points to the storage side. `sqfull` with a low `avgserv` points to the
  hdisk queue. The two lead to different actions.
- A tunable change needs evidence, a revert and a change window.
- AIX has its own tools: `iostat -D`, `mpstat -v`, `nmon`, `errpt`, `errnotify`.

---

## Next steps

You completed the five labs. To check your LPAR against the rules from the beginning,
run [Lab 02](02-assess-best-practices.md) again. To test Bob's answers automatically, see
[Automated tests](README.md#automated-tests) and the
[eval scenarios](../evals/scenarios/README.md).
