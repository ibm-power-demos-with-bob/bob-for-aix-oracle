---
id: S00
title: AIX command accuracy (no Linux hallucinations)
mode: aix
skills: [aix]
reads: [.agents/skills/aix/SKILL.md, .bob/rules-aix/01-core-rules.md]
prompt: >-
  On my AIX 7.3 LPAR: show me the memory usage, restart sshd, create a user
  "jdoe" in the staff group, and show the kernel messages from the last hour.
must_include:
  - "svmon -G"
  - "stopsrc -s sshd"
  - "startsrc -s sshd"
  - "mkuser"
  - "errpt"
  - "perl -MPOSIX"
must_not_include:
  - '\bfree\s+-[bkmgh]\b'
  - '\bsystemctl\b'
  - '\bservice\s+sshd\b'
  - '\buseradd\b'
  - '\bdmesg\b'
  - '\bjournalctl\b'
  - '\bdate\s+-d\b'
---

# Scenario S00: AIX command accuracy

**Goal:** show that Bob answers with AIX-native commands only, and says "verify"
instead of inventing a flag. This is the demo for the "hallucinated AIX command
lines" problem. Every trap below is also a case in
[`evals/hallucination_cases.yaml`](../hallucination_cases.yaml).

## Demo script

1. Select the **AIX** mode.
2. Paste the prompt from the front matter. It contains four Linux reflexes:
   `free`, `systemctl`, `useradd`, and `dmesg` / `date -d`.
3. Point out that Bob captures context first (`oslevel -s`, `lparstat -i`) and
   that no command in the answer comes from Linux.
4. Follow up with a trap: *"Use `iostat -x 5` to find the slow disk."* Bob must
   say that AIX `iostat` has no `-x` flag, give `iostat -D 5 3`, and show how to
   check (`man iostat`).

## Reference answer

```bash
# Purpose: capture context first (read-only)
oslevel -s
lparstat -i | head -20

# Memory: AIX has no `free`
svmon -G                 # real memory, pinned, computational vs file pages
vmstat -v | head -20     # detail: numperm, free frames, blocked I/O counters
lsps -a                  # paging space use

# sshd is an SRC subsystem, there is no systemd
lssrc -s sshd
stopsrc -s sshd
startsrc -s sshd
lssrc -s sshd            # must show "active"

# User: AIX uses mkuser / chuser / lsuser
mkuser pgrp=staff groups=staff home=/home/jdoe shell=/usr/bin/ksh jdoe
lsuser -f jdoe
pwdadm -f ADMCHG jdoe    # force a password change at first login

# Kernel messages: the AIX error log is errpt. AIX date has no -d, so compute
# the timestamp (mmddHHMMyy) with perl, which ships with base AIX.
errpt -a -s "$(perl -MPOSIX -e 'print strftime("%m%d%H%M%y", localtime(time-3600))')" | more
```

Expected caveats in the answer:

- `stopsrc` on `sshd` does not kill existing sessions, but if the user is connected
  by SSH, keep a second session open before restarting.
- `mkuser` writes `/etc/passwd` and `/etc/security/*`; the user has no password
  until `passwd jdoe` is run by root.
- `rmuser -p jdoe` removes the account but **not** the home directory (checked on
  AIX 7.3 TL4: `/home/<user>/.profile` stays). Remove the directory by hand, and
  only after checking what it contains.

## What this scenario demonstrates

- The `aix` skill "AIX vs Linux" table and the always-on rules in
  `.bob/rules-aix/01-core-rules.md`.
- Read-before-write, verification after the change.
- Honesty: an unknown flag is reported as "verify with `man`", not guessed.
