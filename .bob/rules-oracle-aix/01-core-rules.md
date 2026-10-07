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
7. Licensing answers are technical input only. The Oracle contract governs, so direct
   compliance decisions to the licensing team.
