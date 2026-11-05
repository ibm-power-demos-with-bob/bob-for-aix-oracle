---
id: R03
title: Backup of AIX (mksysb, alt_disk) and Oracle (RMAN, home)
mode: oracle-aix
skills: [aix, oracle-aix, ansible-aix]
reads:
  - .agents/skills/aix/SKILL.md
  - .agents/skills/oracle-aix/SKILL.md
  - .agents/skills/ansible-aix/SKILL.md
prompt: >-
  Design the backup before our maintenance window: AIX rootvg, the Oracle
  home, and the database (RMAN), on an AIX 7.3 LPAR. Include verification and
  the restore path.
must_include:
  - "mksysb -i -e"
  - "lsmksysb -l"
  - "alt_disk_copy -B"
  - "bootlist -m normal -o"
  - "rman target /"
  - "BACKUP DATABASE PLUS ARCHIVELOG"
  - "SHOW RETENTION POLICY"
  - "df -g"
  - "tar"
  - "ORACLE_HOME"
  - "confirm"
must_not_include:
  - '\bdd\s+if='
  - '\bsed\s+-i\b'
  - '\brsync\s+--info\b'
  - '\bLD_LIBRARY_PATH\s*='
---

# Recipe R03: Backup

**Goal:** a layered backup that covers the three things a maintenance window can
break: the AIX image, the Oracle software, and the data. Each layer has a
verification and a restore path. The recipe also shows the trap in
`alt_disk_copy`: **without `-B` the bootlist points at the clone**.

## Demo script

1. Select **Oracle on AIX/Power**, paste the prompt.
2. Bob first asks which user owns the home and runs the pre-flight check
   (`ORACLE_HOME`, `ORACLE_SID`, `LIBPATH`...), then orders the layers.
3. Ask: *"Why not just `alt_disk_copy -d hdisk1`?"* Bob must explain that the
   command sets the bootlist to the clone unless `-B` is given, and show
   `bootlist -m normal -o` as the check.
4. Show the Ansible variant for the AIX layer (second block below).

## Reference answer

Layer 1, AIX image (as root):

```bash
# Purpose: bootable rootvg backup. -i regenerates /image.data, -e honours /etc/exclude.rootvg.
df -g /backup                                   # free space first
mksysb -i -e /backup/$(hostname).mksysb
lsmksysb -l -f /backup/$(hostname).mksysb       # verify: VG, date, oslevel, LV/FS list
# Expected: oslevel matches `oslevel -s`; the LV list matches `lsvg -l rootvg`.

# Purpose: second, faster rollback path: clone rootvg to a spare disk.
lspv                                            # target disk must show VG "None"
alt_disk_copy -B -d hdisk1                      # -B: do NOT change the bootlist
bootlist -m normal -o                           # must still list the current rootvg disk
# Fall back later (only if needed, in a change window): bootlist -m normal hdisk1, then reboot.
```

Layer 2, Oracle software (as `oracle`; `grid` for the Grid home):

```bash
# Purpose: file-level copy of the home and inventory, taken with the home stopped.
: "${ORACLE_HOME:?ORACLE_HOME is not set}"
cat /etc/oraInst.loc || find /u01 -maxdepth 3 -name oraInst.loc   # inventory location (custom -invPtrLoc)
$ORACLE_HOME/OPatch/opatch lspatches             # record the current patch level
df -g /backup
tar -cf /backup/oracle_home_$(hostname).tar "$ORACLE_HOME"
# Also back up the central inventory directory named by /etc/oraInst.loc.
```

Layer 3, database (as `oracle`, after the Oracle environment pre-flight check):

```bash
# Purpose: hot backup. First confirm FRA space and the retention policy.
df -g /u01/app/oracle/fast_recovery_area
rman target / <<EOF
  SHOW RETENTION POLICY;
EOF
# The DELETE below is destructive: confirm the retention policy and that archived logs are backed up.
rman target / <<EOF
  BACKUP DATABASE PLUS ARCHIVELOG;
  DELETE NOPROMPT OBSOLETE;
EOF
```

Statements the answer must include:

- Which user runs which layer, and that the Oracle commands start only after the
  pre-flight check passes.
- A restore test: `mksysb` is restored by NIM or boot media, the home from `tar`,
  the database with `RESTORE DATABASE` / `RECOVER DATABASE` in a non-production
  LPAR first. Never claim a backup is good until a restore or `RESTORE ... VALIDATE`
  has been done.
- ASM data is **not** in the `mksysb`: only RMAN protects it.

## Ansible variant (AIX layer)

`ibm.power_aix.backup` and `ibm.power_aix.alt_disk` wrap `mksysb` and
`alt_disk_copy`. Confirm the parameters and check-mode behaviour with
`ansible-doc ibm.power_aix.backup` before use. The `alt_disk` parameter
`bootlist` defaults to `false`, which is the equivalent of `-B`.

```yaml
- name: Back up rootvg with mksysb
  ibm.power_aix.backup:
    action: create
    type: mksysb
    location: "{{ backup_dir }}/{{ inventory_hostname }}.mksysb"
    exclude_files: true     # honours /etc/exclude.rootvg
    extend_fs: true
  tags: [backup]

- name: Clone rootvg to the spare disk without changing the bootlist
  ibm.power_aix.alt_disk:
    action: copy
    targets: "{{ spare_disks }}"
    bootlist: false
  tags: [backup]
```

## What this recipe demonstrates

- Layered backup with verification (`lsmksysb`, `opatch lspatches`, RMAN).
- The `alt_disk_copy -B` trap and its check.
- Destructive commands (`DELETE OBSOLETE`) gated by confirmation.
- Shell and Ansible variants that stay consistent.
