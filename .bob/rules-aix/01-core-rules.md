# AIX mode: always-on rules

These rules apply to every answer in this mode, even if the `aix` skill is not loaded.
The full reference is `.agents/skills/aix/SKILL.md`.

1. Use AIX-native commands only. Never use `systemctl`, `useradd`, `sysctl`, `free`,
   `dmesg`, `lspci`, or GNU-only options such as `date -d`, `grep -P`, or `sed -i`.
2. Before advising, capture or ask for the context: `oslevel -s`, `prtconf`, `lparstat -i`.
3. Never invent flags or tunables. When unsure, say so and give the check
   (`man <cmd>`, `<tunable-cmd> -L <tunable>`, `-h <tunable>`).
4. Tunable changes: use `-p` for persistent and `-r` for reboot-type tunables, and change
   dependent pairs together. Never change restricted tunables without IBM Support.
5. Show how to inspect the current state before a change, how to verify it after, and the rollback.
6. Warn and ask for confirmation before destructive or disruptive operations (`rmdev -d`,
   `rmlv`, `rmfs`, `reducevg`, `exportvg`, `errclear`, `installp -c`, reboots), and
   recommend `mksysb`, `savevg`, or `alt_disk_copy` first.
7. Command execution & scripts: IBM Bob executes commands via bash (`execute_command`/bash tool).
   All shell examples and one-liners must use bash-compatible / POSIX syntax. AIX standalone
   scripts support both bash and ksh93 (`#!/usr/bin/env bash` or `#!/usr/bin/ksh`), are idempotent,
   check `$?` or use `set -e`, and log to timestamped files.
