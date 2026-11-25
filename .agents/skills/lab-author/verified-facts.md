# Verified facts for lab authors

Read by `SKILL.md`. These facts were checked on a real AIX 7.3 LPAR (POWER10) or in the
`ibm.power_aix` collection. Reuse them. If a command is not here, verify it in the IBM
documentation before you put it in a lab.

## AIX behaviours that surprise authors

- `lsuser -a <attrs> oracle,grid` takes ONE comma-separated list. `oracle grid` fails with
  "Usage: lsuser".
- A bare `geninstall -k` starts the Live Update verification. It is not a usage query.
  Preview with `geninstall -k -p -d <dir> <ifix>`.
- `rmuser -p` leaves the home directory behind.
- `/etc/oraInst.loc` may be absent. Fall back to `find /u01 -maxdepth 3 -name oraInst.loc`.
- Remote restart is not shown by `lparstat -i`. Read it from the HMC (or the cloud console).
  Live Update is unsupported when remote restart is enabled.
- `alt_disk_copy` without `-B` sets the bootlist to the clone. Use `alt_disk_copy -B -d <hdisk>`
  and check `bootlist -m normal -o`.
- ASM disks are whole raw hdisks with no PVID. Never `mkvg` or `extendvg` on an ASM `rhdisk`.
- `LIBPATH` replaces `LD_LIBRARY_PATH`. Oracle database tools run as `oracle` (or `grid`),
  never as `root`.

## Wrong on AIX (confirmed): use these as trap material

`date -d`, `free -m`, `iostat -x`, `mpstat -P`, `systemctl`, `useradd`, `sysctl -w`,
`dmesg`, `journalctl`, `sed -i`, `grep -P`, `lspci`, `lvcreate`, `yum`/`apt-get` for base AIX.
The regexes live in `evals/hallucination_cases.yaml` (H01 to H20).

## Confirmed valid commands

`svmon -G`, `vmstat -v`, `lsps -a`, `lssrc`, `lsmpio`, `lsmpio -q`, `lspath -F "name parent"`,
`genld -u`, `smtctl`, `vmo -L`, `schedo -L vpm_throughput_mode`, `ioo -a`, `iostat -D`,
`mpstat -s`, `mpstat -v`, `lparstat`, `lparstat -i`, `vmstat`, `fcstat`, `lsattr -El`,
`emgr -l`, `emgr -p -e`, `installp -s`, `install_all_updates -p`, `lppchk -v`, `lsmksysb`,
`odmget errnotify`, `nmon -m <dir>`, `mkuser`, `pwdadm -f ADMCHG`, `mkssys`, `startsrc`,
`stopsrc`, `rmssys`, `errpt`, `oslevel -s`, `prtconf`, `bootlist -m normal -o`.

The `perl -MPOSIX` timestamp for `errpt -s` is accepted by `errpt`.

## Ansible (`ibm.power_aix`)

- `ibm.power_aix.backup`: `action`, `type`, `location`, `exclude_files`, `extend_fs`.
- `ibm.power_aix.alt_disk`: `action`, `targets`, `bootlist` (default `false`).
- `live_kernel_update` role variables: `live_kernel_update_hmc_name`,
  `live_kernel_update_hmc_password`, `live_kernel_update_directory`,
  `live_kernel_update_file_name`, `live_kernel_update_preview_mode`.
- List the real parameters of any module with
  `ansible-doc -t module ibm.power_aix.<module> --json`. The module names allowed in the repo
  are the set `POWER_AIX_MODULES` in `validate.py` (in the repo `scripts` directory).
- `ansible-lint` does not run natively on Windows. Use WSL, with a script file (inline
  `bash -lc` mangles `$`) and `ANSIBLE_COLLECTIONS_PATH` pointing at the collection.

## Tooling quirks

- Windows PowerShell: `&&` does not work, `2>&1` on native commands prints
  NativeCommandError noise, and git prints LF/CRLF warnings (harmless).
- Over SSH to an AIX LPAR: strip CRs from piped scripts. `head` without `-n` and `$?`
  embedded in piped scripts sometimes fail.
- `update_todo_list` rejects a list that drops completed items: always keep them.
