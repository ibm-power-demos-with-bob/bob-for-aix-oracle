# Ansible AIX mode: always-on rules

These rules apply to every answer in this mode, even if the `ansible-aix` skill is not loaded.
The full reference is `.agents/skills/ansible-aix/SKILL.md`. Linted examples are in
`.agents/skills/ansible-aix/examples/`.

0. Do not reinvent the wheel: before writing new Ansible content, check whether existing
   playbooks or roles can be reused or adapted. For Oracle on AIX, start with
   <https://github.com/IBM/ansible-power-aix-oracle/tree/main/playbooks>; for AIX platform
   tasks, start with the `ibm.power_aix` roles. Cite what you reused, and write new code
   only for the gap.
1. Use only modules that exist in `ibm.power_aix` (see the skill's module table) or
   `ansible.builtin`. Confirm parameters with `ansible-doc ibm.power_aix.<module>`.
   The collection has no `service` module: use `ansible.builtin.service` for SRC subsystems.
2. Always use FQCN, never the `collections:` keyword.
3. Make every task idempotent: use absolute sizes (not `size=+1G`), and add
   `changed_when` / `creates` on commands.
4. Playbooks must support `--check`: give read-only commands `check_mode: false` and
   `changed_when: false`, and never put `check_mode: false` on a mutating task.
5. After a change, verify the real state with facts modules (`lpp_facts`, `lvm_facts`,
   `lpar_facts`) or read-only commands, then `assert`. Never assert just `is succeeded`.
6. Externalise variables, keep secrets in Vault with `no_log: true`, tag every task, and
   restart through handlers.
7. Targets need `ansible_python_interpreter: /opt/freeware/bin/python3`. Bootstrap fresh
   nodes with `ibm.power_aix.power_aix_bootstrap`.
8. Output must pass `ansible-lint --profile production`.
