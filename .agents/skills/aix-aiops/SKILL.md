---
name: aix-aiops
description: >-
  Use when administering, troubleshooting, tuning, or automating IBM AIX
  systems. Covers AIX-native commands (lsdev, errpt, lsvg, topas, nmon, smitty),
  LVM, JFS2, networking, performance monitoring, and AIOps automation. Trigger
  phrases: "AIX", "IBM Power", "lsdev", "errpt", "smitty", "lsvg", "topas",
  "nmon", "oslevel", "lslpp", "JFS2", "LVM on AIX".
---

# AIX AIOps Skill

## Core Principles

1. **Accuracy first** — only provide commands that are valid and tested on AIX.
2. **No hallucinations** — if uncertain about a command or feature, state the
   uncertainty explicitly and suggest verification methods.
3. **AIX-specific** — always use AIX-native commands, never Linux equivalents.
4. **Version awareness** — ensure commands and features are compatible with the
   target AIX version (check with `oslevel -s`).

---

## AIX vs Linux — Key Differences

| Domain | AIX command | Linux equivalent (do NOT use) |
|---|---|---|
| Hardware listing | `lsdev` | `lspci`, `lsusb` |
| Error log | `errpt` | `dmesg`, `journalctl` |
| Device attributes | `lsattr -El <dev>` | `udevadm` |
| System management | `smitty` / `smit` | — |
| OS version | `oslevel -s` | `uname -r` |
| Package management | `lslpp`, `installp`, `dnf` | `rpm`, `dpkg`, `apt` |
| Network install | `nim` | PXE / cobbler |
| Performance | `topas`, `nmon` | `htop`, `atop` |
| Paging space | `lsps -a` | `swapon -s` |
| LVM | `lsvg`, `lspv`, `lslv` | `vgs`, `pvs`, `lvs` |
| Kernel tuning | `ioo`, `vmo`, `no`, `schedo` | `sysctl` |

---

## File System

- AIX default FS type is **JFS2** (not ext4 / XFS).
- Always set `fs_type: jfs2` when creating filesystems.
- Standard mount points: `/usr`, `/var`, `/tmp`, `/home`, `/opt`.
- ODM (Object Data Manager) lives in `/etc/objrepos`.

---

## Networking

```bash
# Show interfaces
ifconfig -a

# AIX-specific network tuning (not sysctl)
no -a | grep <param>
no -o rfc1323=1

# Network parameters via ODM
lsattr -El inet0
```

---

## Performance & Monitoring

| Tool | Purpose |
|---|---|
| `topas` | Real-time performance monitor (CPU, disk, net) |
| `nmon` | Nigel's monitor — interactive or batch recording |
| `vmstat` | Virtual memory stats (AIX version) |
| `iostat` | Disk I/O stats (AIX version) |
| `netstat` | Network stats (AIX flags differ from Linux) |
| `svmon` | Detailed memory segment statistics |
| `filemon` | File system activity tracing |
| `tprof` | CPU profiling |
| `probevue` | DTrace-style dynamic tracing |

---

## LVM Management

```bash
# Volume groups
lsvg                    # list all VGs
lsvg -l <vg>           # list LVs in a VG

# Physical volumes
lspv                    # list all PVs

# Logical volumes
lslv <lv>              # LV details
mklv -t jfs2 -y <name> <vg> <size>   # create LV
chlv -x <max_pp> <lv>  # extend LV limit
rmlv <lv>              # remove LV

# File systems
crfs -v jfs2 -d <lv> -m <mountpoint>
chfs -a size=+<NNNm> <mountpoint>    # grow FS
```

---

## System Management

```bash
# Menu-driven interface
smitty                  # full TUI
smitty storage          # storage sub-menu
smitty nim              # NIM sub-menu

# Device management
lsdev -Cc disk          # list disk devices
chdev -l <dev> -a <attr>=<val>
mkdev -l <dev>
rmdev -l <dev>

# Boot management
bosboot -a -d /dev/hdisk0
bootlist -m normal hdisk0
```

---

## Error Reporting

```bash
# Recent errors (all)
errpt

# Detailed error report
errpt -a | head -100

# Errors for a specific resource
errpt -N hdisk0

# Clear error log (destructive — confirm first)
errclear 0
```

---

## NIM (Network Installation Management)

```bash
# Long-running — always use async + poll in Ansible
nim -o define -t standalone -a if1="find_net <hostname> <mac>" <client>
nim -o bos_inst -a source=mksysb -a mksysb=<res> <client>
nim -o lpp_source -a server=master -a location=/nim/lpp <lpp_res>
```

---

## AIOps Automation Guidelines

- Prefer **parseable output**: use `-c` (colon-separated) or JSON flags where available.
- Always include **error detection**: check `$?` after each command.
- Use **logging**: redirect output to timestamped log files.
- Consider **idempotency**: check current state before making changes.
- Integrate with monitoring: forward `errpt` entries to your SIEM/AIOps platform.

```bash
# Example: parseable disk info for automation
lspv -c | awk -F: '{print $1, $2, $3}'

# Example: errpt to JSON-friendly output (pipe to processor)
errpt -a -s $(date -d '1 hour ago' +%m%d%H%M%y) 2>/dev/null
```

---

## Safety Checks

- **Always warn** before destructive operations (`rmdev`, `rmlv`, `errclear`).
- **Suggest backup** (`mksysb`, `savevg`) before structural changes.
- **Recommend testing** in a non-production environment first.
- **Include rollback** procedures where applicable.

---

## When Uncertain

1. State the uncertainty explicitly.
2. Suggest verification: `man <cmd>`, `<cmd> -?`, or `smitty`.
3. Recommend testing in a non-production environment.

---

## Response Format

```bash
# Description of what the command does
command -options arguments

# Expected output or result
# Warnings or AIX-specific considerations
```

---

## Documentation References

- [IBM AIX 7.3 Documentation](https://www.ibm.com/docs/en/aix/7.3)
- AIX Commands Reference (`man` pages on system)
- AIX System Management Guide
- AIX Performance Management Guide
