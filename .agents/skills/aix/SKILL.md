---
name: aix
description: >-
  Use when administering, troubleshooting, tuning, or automating IBM AIX systems
  (shell commands, scripts, runbooks). Covers AIX-native commands, the System
  Resource Controller (SRC), LVM/JFS2, devices and MPIO, kernel tunables
  (vmo/ioo/schedo/no), networking, performance triage, error log, software
  maintenance (installp, emgr, TL/SP), backup (mksysb, alt_disk), NIM, users and
  security, and VIOS basics. Trigger phrases: "AIX", "IBM Power LPAR", "lsdev",
  "errpt", "smitty", "lsvg", "topas", "nmon", "oslevel", "lslpp", "installp",
  "emgr", "mksysb", "lssrc", "startsrc", "JFS2", "LVM on AIX", "VIOS".
---

# AIX Skill

## Core Principles

1. **Accuracy first**: only give commands and flags that exist on AIX. If you are
   not sure a flag or tunable exists, say so and show how to check it
   (`man <cmd>`, `<cmd> -?`, `vmo -h <tunable>`, `vmo -L <tunable>`).
2. **AIX-native only**: never substitute Linux or GNU tools (see the table below).
   AIX `date`, `df`, `ps`, `grep`, `sed`, and `awk` are not GNU. For example,
   `date -d`, `grep -P`, and `sed -i` do not exist.
3. **Version awareness**: behaviour and defaults differ by AIX level and Power
   generation. Capture the context before advising (next section).
4. **Read before write**: show how to inspect the current state before any change,
   and how to verify the result afterwards.

---

## Capture Context First (read-only)

```bash
oslevel -s                 # e.g. 7300-02-02-2420 = AIX 7.3 TL2 SP2
prtconf | head -25         # model, processor type, implementation (compat) mode, memory
lparstat -i                # LPAR type, mode (capped/uncapped), entitlement, vCPUs, pool
uname -M                   # machine model
smtctl | head -5           # SMT mode
instfix -i | grep -E 'ML|SP' | tail -3   # TL/SP consistency
```

---

## AIX vs Linux: Key Differences

| Domain | AIX command | Do NOT use (Linux) |
|---|---|---|
| Hardware listing | `lsdev`, `lscfg -vl <dev>` | `lspci`, `lsusb`, `lshw` |
| Device attributes | `lsattr -El <dev>`, `chdev` | `udevadm` |
| Error log | `errpt` (plus syslog, if configured in `/etc/syslog.conf`) | `dmesg`, `journalctl` |
| Services | `lssrc`, `startsrc`, `stopsrc`, `refresh` (SRC) | `systemctl`, `service` |
| OS version | `oslevel -s` | `uname -r`, `/etc/os-release` |
| Base OS software | `lslpp`, `installp`, `install_all_updates`, `emgr` | `dpkg`, `apt` |
| Open-source packages | `dnf` / `rpm` (AIX Toolbox only, under `/opt/freeware`) | n/a |
| Kernel tuning | `vmo`, `ioo`, `schedo`, `no`, `nfso`, `raso` | `sysctl`, `/proc/sys` |
| Paging space | `lsps -a`, `mkps`, `chps` | `swapon`, `mkswap` |
| LVM | `lsvg`, `lspv`, `lslv`, `mklv`, `extendlv` | `vgs`, `pvs`, `lvcreate` |
| Users | `mkuser`, `chuser`, `lsuser`, `rmuser`, `chsec` | `useradd`, `usermod` |
| Memory | `svmon -G`, `vmstat -v` | `free` |
| Network install | NIM (`nim`, `lsnim`) | PXE / kickstart |
| Menu UI | `smitty` (use `smitty -x` to preview the command) | n/a |

---

## System Resource Controller (SRC)

```bash
lssrc -a                    # all subsystems and their state
lssrc -s sshd               # one subsystem
lssrc -ls xntpd             # long status (subsystem-specific detail)
stopsrc -s sshd; startsrc -s sshd
refresh -s syslogd          # reload configuration
lssrc -g tcpip              # subsystem group
chssys -s xntpd -a "-x"     # change the arguments a subsystem is started with
```

Boot-time start is controlled by `/etc/inittab` (`lsitab`, `mkitab`, `chitab`,
`rmitab`) and `/etc/rc.tcpip`. There is no systemd.

---

## Devices, Disks and Multipath

```bash
lsdev -Cc disk                       # disks and state (Available / Defined)
lsdev -Cc disk -F "name status"      # parseable
lscfg -vl hdisk0                     # VPD, location code
lsattr -El hdisk0                    # current attributes (last column: user-settable)
lsattr -Rl hdisk0 -a queue_depth     # allowed values for an attribute
lsmpio -q                            # MPIO: LUN size/vendor/volume name per hdisk
lspath -l hdisk0                     # paths and their state
cfgmgr                               # discover new devices

chdev -l hdisk0 -a queue_depth=32 -P   # -P: write to ODM only, applies at reboot
chdev -l hdisk0 -a queue_depth=32 -U   # -U: change while in use (only "True+" attributes)

rmdev -l hdisk5        # unconfigure: device goes to Defined, ODM definition kept
rmdev -dl hdisk5       # delete the definition (destructive, confirm first)
```

---

## LVM and JFS2

AIX's default filesystem is **JFS2** (not ext4 or XFS).

```bash
lsvg                     # all VGs;  lsvg -o = varied-on VGs only
lsvg -l datavg           # LVs and filesystems in a VG
lsvg -p datavg           # PVs in a VG, free PPs per PV
lspv                     # PVs, PVIDs, VG membership
lslv data_lv             # LV details (PP count, stripe size/width)
lsfs -c /data            # filesystem attributes (colon-separated)

mkvg -S -y datavg hdisk2 hdisk3          # scalable VG
mklv -t jfs2 -y data_lv datavg 10G       # size in LPs, or with a unit (M/G)
crfs -v jfs2 -d data_lv -m /data -A yes -a logname=INLINE
mount /data

chfs -a size=+2G /data      # grow (relative; the LV is extended automatically)
chfs -a size=20G /data      # set an absolute size (idempotent)
chlv -x 2048 data_lv        # raise the LV's maximum number of LPs
chvg -g datavg              # pick up LUNs that grew on the storage side
                            # (check APAR IJ46487 is applied first)
```

The ODM (device configuration database) lives in `/etc/objrepos`,
`/usr/lib/objrepos`, and `/usr/share/lib/objrepos`. Never edit it with `odmchange`
or `odmdelete` unless IBM Support asks you to.

---

## Kernel Tunables (`vmo`, `ioo`, `schedo`, `no`, `nfso`, `raso`)

```bash
vmo -L minfree            # CUR / DEF / BOOT / MIN / MAX / UNIT / TYPE / DEPENDENCIES
vmo -h minfree            # help text: also confirms the tunable exists at this level
vmo -a                    # all non-restricted tunables
vmo -F -a                 # include restricted tunables (display only)

vmo -o minfree=1024 -o maxfree=2048      # runtime only (lost at reboot)
vmo -p -o minfree=1024 -o maxfree=2048   # now + persistent (/etc/tunables/nextboot)
vmo -r -o lgpg_regions=0                 # TYPE "R" tunables: next boot (run bosboot -a)
```

- `-p` makes a change persistent. Without `-p`, say explicitly that the change is
  temporary.
- **Restricted tunables** (shown only with `-F`) must not be changed unless IBM
  Support asks you to.
- Some tunables depend on each other (for example `maxfree` must be greater than
  `minfree`), so change them together.
- **Network:** with `use_isno=1` (the default), interface-specific options on
  `enX` override the global `no` values for `tcp_sendspace`, `tcp_recvspace`,
  `rfc1323`, `tcp_nodelay`, and `tcp_mssdflt`. Check with `lsattr -El en0` and
  `ifconfig en0`, and set them per interface:

```bash
chdev -l en0 -a tcp_sendspace=262144 -a tcp_recvspace=262144 -a rfc1323=1
```

---

## Networking

```bash
ifconfig -a                 # interfaces (ISNO values are shown per interface)
netstat -rn                 # routing table
netstat -in                 # interface counters
entstat -d ent0             # adapter statistics (use entX, not enX)
lsattr -El inet0            # hostname, static routes
mktcpip -h <host> -a <ip> -m <mask> -i en0 -g <gw>   # IP configuration (writes to the ODM)
no -p -o tcp_ephemeral_low=9000   # global TCP/IP tunable (persistent)
cat /etc/netsvc.conf        # name resolution order, e.g. hosts = local, bind4
```

---

## Performance Triage

| Symptom | First commands | Look at |
|---|---|---|
| CPU | `lparstat 2 10`, `mpstat -s 2 5`, `topas` | `%entc`, `physc`, `app` (pool idle), run queue in `vmstat` (`r`) |
| Memory | `vmstat 2 10`, `svmon -G`, `lsps -a`, `vmstat -v` | `pi`/`po` (paging space I/O), `fr`/`sr` (page stealing), `fre` |
| Disk I/O | `iostat -D 2 5`, `vmstat -v` | `avgserv`, `sqfull`, `% tm_act`; "blocked with no pbuf/fsbuf" counters |
| FC adapters | `fcstat fcs0` | "No Command Resource Count", "No DMA Resource Count" |
| Network | `netstat -s`, `entstat -d ent0` | retransmits, "socket buffer overflows", adapter errors |
| Recording | `nmon -f -s 60 -c 1440` | 24 h capture for nmon analyser |

Other tools: `svmon -P <pid>` (process memory), `filemon` and `tprof` (tracing and
profiling; these add overhead, so use them in short windows), and `probevue`
(dynamic tracing).

---

## Error Reporting

```bash
errpt | head -20                     # summary, newest first
errpt -a -j <IDENTIFIER> | head -60  # detail for one error ID
errpt -N hdisk3                      # by resource name
errpt -d H -T PERM                   # permanent hardware errors

# Entries since one hour ago. AIX date has no -d option, so compute the
# timestamp (mmddHHMMyy) with perl, which ships with base AIX:
errpt -a -s "$(perl -MPOSIX -e 'print strftime("%m%d%H%M%y", localtime(time-3600))')"

errclear 30      # deletes entries older than 30 days. Destructive: confirm and
                 # archive first (errpt -a > /tmp/errpt.$(hostname).txt)
```

---

## Software Maintenance

```bash
oslevel -s                    # current level
oslevel -rq                   # known TL levels;  oslevel -sq = known SP levels
lslpp -l bos.rte              # fileset level and state (APPLIED / COMMITTED)
lslpp -Lc | head              # parseable
instfix -ik IJ12345           # is an APAR fixed?
lppchk -v                     # fileset consistency check
emgr -l                       # installed interim fixes (iFixes / efixes)

# TL/SP update: always preview first
install_all_updates -d /mnt/7300-03-01 -p -Y   # -p = preview only
install_all_updates -d /mnt/7300-03-01 -Y      # apply (not committed)
installp -s                                     # list APPLIED (uncommitted) software
installp -c all                                 # commit (removes the rollback ability)
installp -r -f <list>                           # reject applied updates (rollback)

emgr -p -e IJ12345s1a.epkg.Z     # preview an iFix
emgr -e IJ12345s1a.epkg.Z        # install an iFix;  emgr -r -L <label> to remove
```

Leave updates APPLIED (not committed) until they are validated, so you can reject
them. Remove iFixes that a TL/SP replaces before updating.

### Live Update (Live Kernel Update, LKU)

Live Update loads kernel-level interim fixes without a reboot. It is **not** a
stand-alone command: start it with `geninstall -k` (or from NIM). Inputs come from
`/var/adm/ras/liveupdate/lvupdate.data`; the template with every field is
`/var/adm/ras/liveupdate/lvupdate.template`.

```bash
hmcauth -u hscroot -a <hmc_name>                      # HMC-managed LPAR (PowerVC: pvcauth -u root -a <powervc_host>)
geninstall -k -p -d /tmp IZ12345.140806.epkg.Z        # PREVIEW first: estimates blackout time and resources
geninstall -k -d /tmp IZ12345.140806.epkg.Z           # install the iFix and Live Update
geninstall -k                                         # re-run after a failure once the cause is fixed
                                                      # (updates are already installed: pass no -d or software)
                                                      # NEVER run it bare to display usage: it starts the
                                                      # Live Update verification
genld -u                                              # processes still using old libraries (AIX 7.2 TL1+): restart them
```

- It is meant for iFixes with kernel or kernel-extension changes. A fixed shared
  library on disk is **not** picked up by running processes: restart them.
- Needs at least 2 extra disks (surrogate `lvup_rootvg` and a rootvg mirror), all I/O
  virtualized through VIOS, and at least 2 paths to every disk. After an iFix-only
  Live Update the mirror is kept as `old_rootvg` and can be booted to go back. If
  updates were applied, take a rootvg backup first.
- Not supported, among others: Active Memory Sharing, remote restart, Advanced
  Accounting, multibos, a process that locked memory with `plock()` or holds
  `/dev/kmem`, exclusive resource sets, and a rootvg that already has 3 mirror copies.
  Check the full list in the IBM documentation "Live Update restrictions".
- `geninstall -k` does not update RPM packages: update them before the operation.
- Logs: `/var/adm/ras/liveupdate/logs`. For IBM Support: `snap -U`.
- Observed on AIX 7.3 TL4 SP2: a bare `geninstall -k` prints `Pre-Live Update Verification...`
  and creates `/var/adm/ras/liveupdate/lvupdate.data`. Use the documented preview
  (`geninstall -k -p -d <dir> <ifix>`) and ask the user before any `geninstall -k`.
- Ansible: the `ibm.power_aix.live_kernel_update` role (see the `ansible-aix` skill).

---

## Backup, Boot and Alternate Disk

```bash
mksysb -i -e /backup/$(hostname).mksysb   # rootvg backup (-e honours /etc/exclude.rootvg)
savevg -i -f /backup/datavg.savevg datavg # non-rootvg VG backup
lsmksysb -l -f /backup/$(hostname).mksysb # verify an image: VG, date, oslevel, LV/FS list (-L: filesets)
alt_disk_copy -B -d hdisk1                # clone rootvg before an update (fallback boot). -B keeps the
                                          # bootlist on the current rootvg; without it the bootlist is
                                          # set to the clone, so a reboot would start the OLD copy
bootlist -m normal -o                     # show the boot list
bootlist -m normal hdisk0 hdisk1          # set the boot list
bosboot -ad /dev/ipldevice                # rebuild the boot image on the boot disk
```

---

## NIM (Network Installation Management)

```bash
lsnim                                   # all NIM objects
lsnim -l <client>                       # one object in detail
nim -o define -t lpp_source -a server=master \
    -a location=/export/nim/lpp_7300 -a source=/dev/cd0 lpp_7300
nim -o define -t mksysb -a server=master \
    -a location=/export/nim/mksysb/host1.mksysb mksysb_host1
nim -o define -t standalone -a platform=chrp -a netboot_kernel=64 \
    -a if1="find_net <hostname> 0" <client>
nim -o bos_inst -a source=mksysb -a mksysb=mksysb_host1 \
    -a spot=<spot> -a accept_licenses=yes <client>
```

NIM operations are long-running. In automation, use asynchronous execution with
polling, and check `lsnim -l <client>` (`Cstate`) for progress.

---

## Users and Security

```bash
mkgroup -A dba
mkuser pgrp=staff groups=staff,dba home=/home/jdoe shell=/usr/bin/ksh jdoe
lsuser -f jdoe                # all attributes, stanza format
chuser maxage=13 jdoe         # change attributes
pwdadm -f ADMCHG jdoe         # force a password change at next login
lssec -f /etc/security/limits -s default -a fsize
chsec -f /etc/security/limits -s jdoe -a nofiles=-1
lsrole ALL; lsauth ALL | head # RBAC
```

---

## VIOS (Virtual I/O Server) Basics

- `padmin` uses a restricted shell (`ioscli` commands). `oem_setup_env` switches to
  a root shell. Use it only when a procedure requires it.
- Useful `ioscli` commands: `lsmap -all` (vSCSI), `lsmap -all -npiv` (virtual FC),
  `lsdev -virtual`, `ioslevel`.
- Before VIOS maintenance, confirm that client LPARs have redundant paths through
  the second VIOS (`lspath` on each client).

---

## Automation Guidelines

- **Command execution by IBM Bob / Agents:** IBM Bob executes shell commands using `bash`
  (`execute_command` / bash tool, or bash on AIX via AIX Toolbox `/opt/freeware/bin/bash` or
  `/usr/bin/bash`). All commands, one-liners, and execution examples must use bash-compatible /
  POSIX syntax so they execute cleanly without relying on ksh-only quirks or non-portable constructs.
- **Native AIX Scripts:** Native standalone scripts generated for AIX should be portable across
  both `bash` and `ksh93`/`ksh` (the AIX default login shell). Use `#!/usr/bin/env bash` or
  `#!/usr/bin/bash` with fallback to `#!/usr/bin/ksh`.
- Prefer parseable output: `lsdev -F`, `lsattr -El <dev> -O`, `lsfs -c`,
  `lslpp -Lc`, `lsuser -c`, `lssrc -a`.
- Check `$?` after each critical command (or use `set -e`), and log to
  timestamped files.
- Make scripts idempotent: test the current state (`lsfs`, `lsattr`, `lslpp`)
  before changing it.
- Forward `errpt` entries to monitoring using `errnotify` ODM stanzas or syslog.

---

## Safety Checks

- **Warn and ask for confirmation** before destructive operations: `rmdev -d`,
  `rmlv`, `rmfs`, `reducevg`, `exportvg`, `errclear`, `installp -c`/`-u`,
  `chdev` on in-use disks, and anything that reboots.
- **Back up first**: `mksysb` or `alt_disk_copy` before OS updates, `savevg`
  before VG restructuring.
- **Test in non-production first**, and include rollback steps (`installp -r`,
  `emgr -r`, boot from the alternate disk).

---

## Response Format

```bash
# Purpose: what this does and why
command -options arguments

# Expected result / what to check in the output
# Warnings, AIX-level or Power-generation caveats, rollback
```

When you are unsure, state the uncertainty, give the verification command
(`man`, `-h`, `-L`, `smitty -x`), and recommend a non-production test.

---

## Documentation References

- [IBM AIX 7.3 documentation](https://www.ibm.com/docs/en/aix/7.3)
- [AIX commands reference](https://www.ibm.com/docs/en/aix/7.3?topic=commands)
- [AIX performance tuning](https://www.ibm.com/docs/en/aix/7.3?topic=management-performance-tuning)
- [IBM Fix Central](https://www.ibm.com/support/fixcentral/) and the FLRT tool for levels and APARs
