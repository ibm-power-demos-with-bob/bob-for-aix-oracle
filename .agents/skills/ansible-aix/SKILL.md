---
name: ansible-aix
description: >-
  Use when writing, reviewing, or refactoring Ansible playbooks and roles that
  target IBM AIX with the ibm.power_aix collection: software (installp, TL/SP,
  iFixes), users, LVM, filesystems, NFS mounts, devices and MPIO, tunables,
  networking, services (SRC), NIM, and VIOS updates, to ansible-lint production
  standards. Trigger phrases: "Ansible AIX", "ibm.power_aix", "playbook for AIX",
  "AIX automation", "NIM ansible", "VIOS ansible", "power_aix_bootstrap".
---

# Ansible AIX Skill

Reference for writing production-grade Ansible content that targets IBM AIX with the
[`ibm.power_aix`](https://ibm.github.io/ansible-power-aix/) collection.

**Before using any module, confirm its parameters for the installed collection
version** with `ansible-doc ibm.power_aix.<module>`. Never invent module names or
parameters. If a capability is not in the tables below, check the
[module index](https://ibm.github.io/ansible-power-aix/modules.html), or use
`ansible.builtin.command` with the rules in the "Idempotency" section.

---

## Reuse Existing Playbooks Before Writing New Ones

Do not reinvent the wheel. Before writing a new playbook or role, check whether an
existing one already covers the need and reuse or adapt it.

1. **Oracle on AIX**: first review the IBM playbooks in
   <https://github.com/IBM/ansible-power-aix-oracle/tree/main/playbooks>. The
   directory contains, among others:
   - `demo_play_aix_oracle.yml`, `goldimage_play_aix_oracle.yml`,
     `podba_create_oracle_db.yml`, `powervc_oracle_play.yml`, and
     `deinstall_play_aix_oracle.yml`
   - `vars/`, `roles/`, `inventory`, and `ansible.cfg` as a reference layout
   
   Per the repository README, it automates an Oracle 19c single-instance
   installation on a new AIX LPAR (AIX 7.2 TL4 SP1 or later) and creates a test
   database on a filesystem or on Oracle ASM. It uses `ibm.power_aix` modules.
2. **AIX platform tasks** (software, LVM, users, NIM, VIOS): prefer the roles of the
   `ibm.power_aix` collection (see "Collection Roles" below) over custom tasks.
3. **Reuse, then adapt**: import or copy the existing playbook or role, then
   override its variables instead of rewriting the logic. Keep upstream task names
   and variable names where possible so future updates are easy to merge.
4. **Review before running**: the upstream content is not guaranteed to meet this
   skill's rules. Check it for FQCN, idempotency, `--check` support, Vault secrets,
   and `ansible-lint --profile production`, and fix gaps in a thin wrapper or an
   overlay rather than by forking the whole playbook.
5. **Write new content only for the gap**: if nothing suitable exists, say what you
   searched and why it does not fit, then write the minimal new code.
6. **Always cite the source**: state which upstream playbook or role you reused and
   link it, and note that it must be tested on a non-production LPAR first.

---

## Non-Negotiable Rules

1. **FQCN**: always `ibm.power_aix.<module>` or `ansible.builtin.<module>`. Do not
   use the `collections:` play keyword.
2. **Idempotency**: every task must be safe to re-run. Prefer modules over
   `command`/`shell`. Use absolute sizes, not relative ones like `size=+1G`, which
   grow the filesystem again on every run.
3. **Check mode**: playbooks must run with `--check`. Read-only `command` tasks
   get `check_mode: false` and `changed_when: false`, so they gather data during
   dry runs. **Never** put `check_mode: false` on a task that changes the system,
   because it would then make changes during `--check`.
4. **Secrets**: only from Ansible Vault (`vault_*` variables) or an external
   secrets lookup. Never inline them, and use `no_log: true` on tasks that handle
   them.
5. **Verify the real state**: after a change, check the resulting state with a
   facts module (`lpp_facts`, `lvm_facts`, `lpar_facts`) or a read-only command,
   then `ansible.builtin.assert` on it. Asserting `r is succeeded` adds nothing,
   because a failed task already stops the play.
6. **Variables**: hostnames, paths, sizes, and names go in `vars:`,
   `defaults/main.yml`, or the inventory. Never hardcode them in tasks.
7. **Tags**: put functional tags (`packages`, `users`, `lvm`, `network`,
   `security`, `nim`, `tuning`) on every task.
8. **Handlers**: restart services through handlers, never inline.
9. **Lint**: `ansible-lint --profile production` must pass with zero findings.

---

## Control Node and Inventory Requirements

- AIX targets need Python 3 from the AIX Toolbox. Bootstrap fresh nodes with the
  `ibm.power_aix.power_aix_bootstrap` role (`pkgtype: dnf`, run with
  `gather_facts: false`), which works without Python on the target.
- Set the interpreter explicitly, because AIX has no `/usr/bin/python3` by
  default:

```yaml
# group_vars/aix.yml
ansible_python_interpreter: /opt/freeware/bin/python3
ansible_become_method: sudo      # sudo comes from the AIX Toolbox; otherwise use su
```

- On large fleets, `gather_facts: true` can be slow. Gather only what you need
  with `ibm.power_aix.lpar_facts`, `lpp_facts`, or `lvm_facts`.

---

## Module Reference (`ibm.power_aix.<module>`)

These modules exist in the collection. Check each one's parameters with
`ansible-doc` before use.

| Domain | Modules |
|---|---|
| Software and fixes | `installp`, `install_all_updates`, `geninstall`, `emgr`, `suma`, `flrtvc`, `lpp_facts`, `lku` |
| Users and security | `user`, `group`, `chsec`, `aixpert`, `audit`, `password_rules_policies`, `password_hash` |
| LVM and filesystems | `lvg`, `lvol`, `filesystem` (local and NFS), `mount`, `lvm_facts`, `pagingspace` |
| Devices and boot | `devices`, `mpio`, `bootlist`, `bosboot`, `alt_disk`, `sysdumpdev` |
| Tuning | `tunables`, `tunfile_mgmt`, `mktun`, `smtctl` |
| Network | `mktcpip`, `route`, `mkfilt`, `netstat`, `entstat`, `traceroute` |
| System | `inittab`, `reboot`, `timezone_mgmt`, `getconf`, `lpar_facts`, `backup` (mksysb/savevg), `errpt`, `errclear`, `snap` |
| Monitoring (read-only) | `lparstat`, `vmstat`, `iostat`, `fcstat`, `nmon`, `ps` |
| NIM and VIOS | `nim`, `nimclient`, `nim_resource`, `nim_backup`, `nim_suma`, `nim_flrtvc`, `nim_select_target_disk`, `nim_updateios`, `nim_viosupgrade`, `nim_vios_alt_disk`, `nim_vios_hc` |
| Encryption | `hdcrypt_auth`, `hdcrypt_conv`, `hdcrypt_facts`, `hdcrypt_pks` |

The collection has **no** modules named `service`, `dnf`, `vg`, `disk`, `nfs`,
`network`, or `vios`. Use these instead:

| Need | Use |
|---|---|
| Start, stop, or restart an SRC subsystem | `ansible.builtin.service` (supports AIX SRC) |
| Boot-time start entries | `ibm.power_aix.inittab` |
| Toolbox RPM packages | `ansible.builtin.dnf` (after `power_aix_bootstrap`) |
| Volume groups | `ibm.power_aix.lvg` |
| NFS mounts | `ibm.power_aix.filesystem` / `ibm.power_aix.mount` |
| VIOS updates and health checks | `nim_updateios`, `nim_viosupgrade`, `nim_vios_hc` (run against the NIM master) |

---

## Collection Roles: Prefer Them Over Custom Tasks

Full role docs: <https://ibm.github.io/ansible-power-aix/roles.html>

| Role | When to use |
|---|---|
| `ibm.power_aix.power_aix_bootstrap` | Fresh node: installs dnf and Python before any other play |
| `ibm.power_aix.nim_alt_disk_migration` | OS migration via an alternate-disk clone. Never hand-script it |
| `ibm.power_aix.nim_master_migration` | Migrating the NIM master itself |
| `ibm.power_aix.live_kernel_update` | Apply updates without a reboot (Live Kernel Update) |
| `ibm.power_aix.power_aix_vioshc` | VIOS health check before and after changes |
| `ibm.power_aix.inetd` | Idempotent inetd entry management |
| `ibm.power_aix.bootptab` | `/etc/bootptab` NIM/BOOTP client registration |
| `ibm.power_aix.ipsec` | IPsec configuration |

---

## Playbook Skeleton

```yaml
---
- name: <Play description>
  hosts: "{{ target_hosts | default('aix') }}"
  gather_facts: false
  become: true
  vars:
    svc_name: xntpd
  handlers:
    - name: Restart time service
      ansible.builtin.service:
        name: "{{ svc_name }}"
        state: restarted
  tasks:
    - name: <Change something>
      ibm.power_aix.<module>:
        # parameters confirmed with ansible-doc
      notify: Restart time service
      tags: [<functional_tag>]

    - name: Read back the resulting state
      ibm.power_aix.<facts_module>:
      tags: [<functional_tag>]

    - name: Assert the desired state
      ansible.builtin.assert:
        that:
          - <condition on the facts>
        fail_msg: <what is wrong and how to fix it>
      tags: [<functional_tag>]
```

Complete, lint-clean examples are in [`examples/`](examples/):

- [`examples/install-fileset.yml`](examples/install-fileset.yml): installs a fileset
  from an lpp_source directory and verifies it with `lpp_facts`.
- [`examples/filesystem.yml`](examples/filesystem.yml): creates or resizes a JFS2
  filesystem idempotently and verifies it with a read-only `lsfs`.

---

## Example: Set a JFS2 Filesystem Size (Idempotent)

```yaml
- name: Ensure /data exists with the requested size
  ibm.power_aix.filesystem:
    filesystem: "{{ fs_mount }}"
    vg: "{{ fs_vg }}"
    fs_type: jfs2
    attributes: "size={{ fs_size }}"    # absolute size, e.g. 20G: idempotent
    auto_mount: "yes"
    state: present
  tags: [lvm]
```

## Example: Install a Fileset with installp

```yaml
- name: Install bos.net.tcp.client from the lpp_source
  ibm.power_aix.installp:
    action: apply
    device: "{{ lpp_source_dir }}"
    install_list: [bos.net.tcp.client]
    agree_licenses: true
    extend_fs: true
  tags: [packages]

- name: Read fileset facts
  ibm.power_aix.lpp_facts:
    filesets: [bos.net.tcp.client]
  tags: [packages]

- name: Assert fileset is installed
  ansible.builtin.assert:
    that: "'bos.net.tcp.client' in ansible_facts.filesets"
  tags: [packages]
```

---

## AIX-Specific Cautions

| Concern | Guidance |
|---|---|
| Filesystem type | `ibm.power_aix.filesystem` defaults to `fs_type: jfs2` |
| ODM / device attributes | Use `ibm.power_aix.devices`, not raw `chdev` commands |
| Kernel tunables | Use `ibm.power_aix.tunables` / `tunfile_mgmt`. Persistent changes only, and never restricted tunables without IBM Support |
| NIM operations | Long-running: use `async` with `poll` (or `async_status`) to avoid connection timeouts |
| VIOS | `padmin` has a restricted shell where normal Ansible modules fail. Drive VIOS updates from the NIM master with `nim_updateios`, `nim_viosupgrade`, `nim_vios_alt_disk`, and `nim_vios_hc` |
| Reboots | Use `ibm.power_aix.reboot`, and serialise (`serial: 1`) across redundant pairs such as VIOS and PowerHA nodes |
| Uncertain behaviour | Say so, link the module doc, run with `--check --diff`, and test on a non-production LPAR first |
| Destructive operations | Warn clearly, take a backup first (`ibm.power_aix.backup` for mksysb/savevg, or `alt_disk`), and document the rollback |

---

## Checklist Before Delivering a Playbook

0. Did you check the existing playbooks and roles (IBM `ansible-power-aix-oracle`,
   `ibm.power_aix` roles) before writing new code?
1. Is every module name and parameter confirmed with `ansible-doc`?
2. Are all variables externalised (no hardcoded paths, sizes, or hosts)?
3. Does it run cleanly with `--check`, and with no changes on a second run?
4. Is every change followed by a check of the real state, not `is succeeded`?
5. Are secrets in Vault, with `no_log: true` where needed?
6. Does it pass `ansible-lint --profile production`?

---

## Documentation References

- [ibm.power_aix collection](https://ibm.github.io/ansible-power-aix/)
- [ibm.power_aix modules](https://ibm.github.io/ansible-power-aix/modules.html)
- [ibm.power_aix roles](https://ibm.github.io/ansible-power-aix/roles.html)
- [Oracle on AIX automation (IBM)](https://github.com/IBM/ansible-power-aix-oracle-dba)
- [Oracle 19c install playbooks for AIX (IBM)](https://github.com/IBM/ansible-power-aix-oracle/tree/main/playbooks)
- [IBM AIX 7.3 documentation](https://www.ibm.com/docs/en/aix/7.3)
