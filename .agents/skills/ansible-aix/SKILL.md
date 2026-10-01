---
name: ansible-aix
description: >-
  Use when writing, reviewing, or refactoring Ansible playbooks and roles
  targeting AIX with the ibm.power_aix collection. Covers packages, users, LVM,
  filesystems, NFS, network, security, services, NIM, and VIOS to
  production-lint standards. Trigger phrases: "Ansible AIX", "ibm.power_aix",
  "playbook for AIX", "AIX automation", "NIM ansible", "VIOS ansible".
---

# Ansible AIX Skill

Reference for writing production-grade Ansible content targeting IBM AIX using
the [`ibm.power_aix`](https://ibm.github.io/ansible-power-aix/) collection.

---

## Non-Negotiable Rules

1. **FQCN** — always use `ibm.power_aix.<module>`, never short names.
2. **Idempotency** — use `state` / `creates` / `removes`; every task must be
   safe to re-run.
3. **check_mode** — destructive tasks get `check_mode: false` plus an
   explanatory comment.
4. **Secrets** — `vault_*` variables only; never inline credentials.
5. **Register + assert** — register every mutating task, assert the result
   immediately after.
6. **Variables** — all hostnames, paths, sizes, and names go in `vars:` or
   `defaults/main.yml`; never hardcoded inline.
7. **Tags** — apply functional tags (`packages`, `users`, `lvm`, `network`,
   `security`, `nim`, …) to every task.
8. **Handlers** — notify handlers for service restarts; never restart inline.
9. **Lint** — target `ansible-lint profile=production`, zero warnings.

---

## Module Reference (`ibm.power_aix.<module>`)

| Domain | Modules |
|---|---|
| Packages | `dnf`, `suma`, `installp` |
| User / Group | `user`, `group` |
| LVM / FS | `lvol`, `filesystem`, `vg`, `disk` |
| Network | `network`, `tcp_facts`, `no_facts` |
| NFS | `nfs`, `mount` |
| Services | `service` |
| Security | `chsec`, `aixpert`, `backup` |
| NIM | `nim`, `nim_viosupgrade`, `nim_flrtvc` |
| VIOS | `vios` |
| Facts | `aixpert_facts`, `filesystem_facts`, `vg_facts` |

Full module docs: <https://ibm.github.io/ansible-power-aix/modules.html>

---

## Collection Roles — Prefer Over Custom Tasks

Full role docs: <https://ibm.github.io/ansible-power-aix/roles.html>

| Role | When to use |
|---|---|
| `ibm.power_aix.power_aix_bootstrap` | Fresh node: installs dnf/pip before any play |
| `ibm.power_aix.nim_alt_disk_migration` | OS upgrade via alt-disk clone — never hand-script |
| `ibm.power_aix.live_kernel_update` | Apply TL/SP without reboot (LKU) |
| `ibm.power_aix.power_aix_vioshc` | VIOS health-check before/after changes |
| `ibm.power_aix.inetd` | Idempotent inetd entry management |
| `ibm.power_aix.bootptab` | `/etc/bootptab` NIM/BOOTP client registration |

---

## Playbook Skeleton

```yaml
---
- name: <play description>
  hosts: "{{ target_hosts }}"
  gather_facts: true
  become: true
  collections: [ibm.power_aix]
  vars:
    # All tunables here — no hardcoded values in tasks
    svc_name: xntpd
    fs_mount: /data
    fs_size: 1G

  handlers:
    - name: restart <svc>
      ibm.power_aix.service:
        name: "{{ svc_name }}"
        state: restarted

  tasks:
    - name: <task description>
      ibm.power_aix.<module>:
        # parameters
      register: r_<task>
      tags: [<functional_tag>]

    - name: Assert <task> succeeded
      ansible.builtin.assert:
        that: r_<task> is succeeded
      tags: [<functional_tag>]
```

Role usage:

```yaml
roles:
  - role: ibm.power_aix.<role_name>
```

---

## AIX-Specific Cautions

| Concern | Guidance |
|---|---|
| File system type | Always set `fs_type: jfs2` — JFS2 is the AIX default |
| ODM changes | Use `ibm.power_aix.devices`, not raw `chdev` shell commands |
| NIM operations | Long-running — use `async` + `poll` to avoid connection timeouts |
| VIOS | Requires `become_user: padmin` |
| Uncertain behaviour | State it, link to docs, add `check_mode: true` dry-run, test on a NIM client first |
| Destructive ops | Warn clearly, suggest `mksysb` / `savevg` backup, provide a rollback handler stub |

---

## Example: Grow a JFS2 Filesystem

```yaml
- name: Extend /data filesystem
  ibm.power_aix.filesystem:
    filesystem: "{{ fs_mount }}"
    size: "+{{ fs_size }}"
    state: present
  register: r_extend_fs
  tags: [lvm]

- name: Assert filesystem extended
  ansible.builtin.assert:
    that: r_extend_fs is succeeded
  tags: [lvm]
```

---

## Example: Install a Fileset via installp

```yaml
- name: Install bos.net.tcp.client
  ibm.power_aix.installp:
    filesets: bos.net.tcp.client
    action: install
    agree_licenses: true
  register: r_installp
  tags: [packages]

- name: Assert fileset installed
  ansible.builtin.assert:
    that: r_installp is succeeded
  tags: [packages]
```

---

## Safety Checklist Before Generating a Playbook

1. Are all variables externalised (no hardcoded paths / sizes)?
2. Does every mutating task have `register` + `assert`?
3. Do destructive tasks have `check_mode: false` with a comment?
4. Are secrets in `vault_*` variables?
5. Does the play pass `ansible-lint profile=production`?

---

## Documentation References

- [ibm.power_aix collection](https://ibm.github.io/ansible-power-aix/)
- [ibm.power_aix modules](https://ibm.github.io/ansible-power-aix/modules.html)
- [ibm.power_aix roles](https://ibm.github.io/ansible-power-aix/roles.html)
- [IBM AIX 7.3 Documentation](https://www.ibm.com/docs/en/aix/7.3)
