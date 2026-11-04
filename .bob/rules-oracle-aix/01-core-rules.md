# Oracle on AIX/Power mode: always-on rules

These rules apply to every answer in this mode, even if the `oracle-aix` skill is not loaded.
The full reference is `.agents/skills/oracle-aix/SKILL.md`. Before answering a topic
question, read the matching file listed in its routing table.

1. Combine Oracle knowledge with the AIX/Power context. Never use Linux commands in
   place of AIX-native ones.
2. Use `LIBPATH`, not `LD_LIBRARY_PATH`. For databases started by `srvctl`, set the
   environment with `srvctl setenv`, because shell profiles are ignored.
3. Ask for or capture the context first: Oracle release and RU, `oslevel -s`, Power
   generation and compatibility mode (`prtconf`), `lparstat -i`, and whether the
   system is production.
4. For every `ALTER SYSTEM`, record the current value and show the revert. Underscore
   parameters and diagnostic events need Oracle Support's agreement, so say so each time.
5. AIX tunables: check they exist (`-L`/`-h`), use `-p` or `-r` explicitly, and never
   change restricted tunables without IBM Support.
6. Warn and ask for confirmation before destructive operations (drops, RMAN deletes,
   Data Guard role changes, LVM/filesystem removal, `chdev` on in-use disks, DLPAR
   removals), and recommend an RMAN backup or `mksysb` first.
7. Before running or recommending any Oracle command or script (`sqlplus`, `rman`,
   `srvctl`, `crsctl`, `lsnrctl`, `tnsping`, `adrci`, `opatch`, `datapatch`, `dbca`,
   `expdp`/`impdp`), verify the Oracle environment is defined: `ORACLE_HOME`,
   `ORACLE_SID`, `ORACLE_BASE`, `PATH` (contains `$ORACLE_HOME/bin`), `LIBPATH`
   (contains `$ORACLE_HOME/lib`), and `TNS_ADMIN` when set or when `tnsnames.ora` is used.
   Use the "Oracle environment pre-flight check" in the skill's `SKILL.md`. Never assume
   the variables are set and never guess an `ORACLE_HOME`: confirm it with the user or
   `/etc/oratab`. If a check fails, stop and fix the environment before running the command.
   In scripts, fail fast with `: "${ORACLE_HOME:?ORACLE_HOME is not set}"`.
8. OS user: by default run database / RDBMS tasks as `oracle` and Grid Infrastructure /
   ASM / RAC / Clusterware tasks as `grid`. Use `root` only for steps documented as
   root-only (`root.sh`, `opatchauto`, `ocrcheck`, `slibclean`, `errpt`). Verify the
   user with `id oracle; id grid`, `lsuser`, `/etc/passwd`, and the owner of
   `ORACLE_HOME` and of the running `ora_pmon_*` / `asm_pmon_*` processes. If `oracle`
   or `grid` does not exist, or the real owner is a different user, stop and ask the
   user for the correct username. Never guess, and never fall back to `root` or
   another account for Oracle tasks. See "Oracle OS user" in the skill's `SKILL.md`.
