---
id: R04
title: Patching AIX, Oracle and Live Kernel Update
mode: oracle-aix
skills: [aix, oracle-aix, ansible-aix]
reads:
  - .agents/skills/aix/SKILL.md
  - .agents/skills/oracle-aix/SKILL.md
  - .agents/skills/oracle-aix/best-practices/os-prereqs.md
  - .agents/skills/oracle-aix/best-practices/memory.md
prompt: >-
  We must apply an AIX interim fix with a kernel change and then the latest
  Oracle 19c Release Update on the same AIX 7.3 LPAR, with the least downtime.
  Can we use Live Kernel Update? Give the sequence, the checks and the rollback.
must_include:
  - "geninstall -k -p"
  - "lvupdate.data"
  - "hmcauth"
  - "genld -u"
  - "old_rootvg"
  - "emgr -p"
  - "install_all_updates"
  - "-p -Y"
  - "slibclean"
  - "opatch prereq CheckConflictAgainstOHWithDetail"
  - "datapatch -verbose"
  - "opatch rollback"
  - "separate change"
  - "ORACLE_HOME"
must_not_include:
  - '\byum\s+update\b'
  - '\bapt(-get)?\s+upgrade\b'
  - '\bdnf\s+upgrade\b.*bos'
  - '\bsed\s+-i\b'
  - '\bLD_LIBRARY_PATH\s*='
---

# Recipe R04: Patching AIX + Oracle + Live Kernel Update

**Goal:** show that Bob separates three changes (AIX fix, AIX TL/SP, Oracle RU),
previews each one, keeps a rollback path, and knows what Live Kernel Update
(LKU) does and does **not** do.

## Demo script

1. Select **Oracle on AIX/Power**, paste the prompt.
2. Bob must answer *"yes, if..."*: LKU is for **kernel / kernel-extension**
   interim fixes. A fixed shared library on disk is not picked up by running
   processes, and **an Oracle instance keeps running the old library** until it is
   restarted. LKU does not replace the Oracle RU.
3. Ask: *"Can I skip the preview?"* Bob must refuse: `geninstall -k -p` estimates
   blackout time and checks the limits before anything changes.
4. Ask: *"The LPAR has Active Memory Sharing"*. LKU is not supported there.
5. Show the Ansible variant (`ibm.power_aix.live_kernel_update`, preview by
   default).

## Reference answer

Step 0, prerequisites and eligibility (read-only, as root):

```bash
oslevel -s; emgr -l; lppchk -v
lparstat -i | grep -E "^Type|^Mode|Memory Mode"      # AMS and remote restart: LKU not supported
lspv                                                 # at least 2 free disks (surrogate rootvg + mirror)
lspath                                               # at least 2 paths per disk, all I/O through VIOS
lsvg -l rootvg | head                                # a rootvg with 3 mirror copies blocks LKU
cat /var/adm/ras/liveupdate/lvupdate.data            # disk stanzas for an HMC-managed LPAR
```

Step 1, backup and rollback path (see recipe R03):

```bash
mksysb -i -e /backup/$(hostname).mksysb
lsmksysb -l -f /backup/$(hostname).mksysb
```

Step 2, the AIX interim fix with a kernel change, using Live Update:

```bash
hmcauth -u hscroot -a <hmc_name>                     # PowerVC: pvcauth -u root -a <powervc_host>
emgr -p -e /tmp/IZ12345s1a.epkg.Z                    # preview the iFix
geninstall -k -p -d /tmp IZ12345.140806.epkg.Z       # PREVIEW: blackout estimate, resources, limits
# Review the output with the DBA. The Oracle instance is checkpointed and moved: plan a quiet window.
geninstall -k -d /tmp IZ12345.140806.epkg.Z          # install and Live Update (confirm before running)
genld -u                                             # processes still on old libraries: restart them
snap -U                                              # only if IBM Support needs data after a failure
```

Facts the answer must state (IBM AIX 7.3 documentation, "Live Update"):

- Live Update is started by `geninstall -k` (or NIM), never by a stand-alone command.
- After an iFix-only Live Update the rootvg mirror is kept as `old_rootvg` and can be
  booted to go back. If updates were applied, rely on the `mksysb` from Step 1.
- If it fails after the install steps, fix the cause and re-run `geninstall -k` with no
  `-d` and no software: the fixes are already installed.
- Not supported: Active Memory Sharing, remote restart, Advanced Accounting, multibos,
  processes with locked memory (`plock()`), a 3-copy rootvg mirror.
- `geninstall -k` does not update RPM packages: update them first.

Step 3, AIX TL/SP (a **separate change** from the Oracle patch):

```bash
install_all_updates -d /mnt/7300-04-01 -p -Y         # preview only
install_all_updates -d /mnt/7300-04-01 -Y            # apply, leaves updates APPLIED (not committed)
installp -s                                          # list APPLIED software, validate before committing
# Rollback before committing: installp -r -f <list>. Commit (installp -c all) removes that ability: confirm first.
```

A TL/SP update changes the kernel and needs a reboot, or a Live Update for the
kernel part where the fix allows it. Use `alt_disk_copy -B` or the `mksysb` as the
fallback (recipe R03).

Step 4, Oracle Release Update (as `oracle`; `opatchauto` as root for Grid):

```bash
# Purpose: first run the Oracle environment pre-flight check for THE home being patched.
: "${ORACLE_HOME:?ORACLE_HOME is not set}"
$ORACLE_HOME/OPatch/opatch lspatches                 # record the level
$ORACLE_HOME/OPatch/opatch prereq CheckConflictAgainstOHWithDetail -ph ./
$ORACLE_HOME/OPatch/opatch prereq CheckSystemSpace -ph ./
# Stop instances, listeners and agents that run from this home, then as root:
/usr/sbin/slibclean
genld -l | grep -i "$ORACLE_HOME"                    # must return nothing before opatch apply
$ORACLE_HOME/OPatch/opatch apply                     # DB home (Grid home: opatchauto apply as root)
$ORACLE_HOME/OPatch/datapatch -verbose               # all PDBs open
# Rollback: opatch rollback -id <patch_id>, then datapatch -verbose
```

After an AIX TL update, run `/usr/sbin/slibclean` and relink the Oracle binaries
(`relink all` as the owner, home stopped) when the install guide for your
release requires it.

## Ansible variant

```yaml
- name: Preview a Live Kernel Update (default is preview mode)
  ansible.builtin.include_role:
    name: ibm.power_aix.live_kernel_update
  vars:
    live_kernel_update_directory: "{{ fix_dir }}"
    live_kernel_update_file_name: "{{ fix_file }}"
    live_kernel_update_preview_mode: true
  tags: [packages]
```

Role variables (from the collection documentation): `live_kernel_update_hmc_name`,
`live_kernel_update_hmc_password` (Vault only, `no_log: true`),
`live_kernel_update_directory`, `live_kernel_update_file_name`,
`live_kernel_update_preview_mode` (default `true`). Set `preview_mode: false`
only after the preview was reviewed. The role needs AIX 7.2 or later.

## What this recipe demonstrates

- LKU is a kernel-fix tool: libraries and the Oracle RU still need a restart.
- Preview first, `APPLIED` not committed, one change at a time.
- A rollback path for each layer (`old_rootvg`, `installp -r`, `opatch rollback`).
- The Oracle home actually being patched is verified before `opatch` runs.
