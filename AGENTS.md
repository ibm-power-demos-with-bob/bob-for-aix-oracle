# AGENTS.md

## Repository Instructions for AI Agents

This repository provides skills, rules, and configuration for AI agents (including **IBM Bob**, Claude Code, Cursor, GitHub Copilot, and other LLM agent frameworks) operating on IBM AIX, Ansible automation for AIX, and Oracle Database on IBM AIX / IBM Power Systems.

### Core Guidelines

1. **Language Requirement:**
   - **All content in this repository must be written in English.**
   - This includes all documentation, code comments, skill files (`SKILL.md`), rule definitions, companion guides, script outputs, commit messages, and examples.
   - User interactions or prompt responses may follow the user's preferred language, but any files or content committed or created in this codebase must be in English.

2. **AIX & Power Systems Specifics:**
   - Always adhere to native AIX commands and utilities (e.g. `lssrc`, `startsrc`, `mkuser`, `chuser`, `vmo`, `ioo`, `no`, `schedo`, `errpt`, `lsdev`, `lscfg`, `svmon`, `vmstat`).
   - Do **not** use Linux-specific commands or flags (e.g. `systemctl`, `journalctl`, `date -d`, `free`, `useradd`, `sed -i`, `grep -P`, `export LD_LIBRARY_PATH`). Use AIX equivalents (e.g. `LIBPATH`).
   - For Ansible automation, only use verified modules and roles from the `ibm.power_aix` collection.

3. **Code Quality and Validation:**
   - Before submitting changes, run `python scripts/validate.py` to ensure all links, modes, and YAML schemas are valid.
   - When updating skill frontmatter descriptions, synchronize Bob pointer files via `python scripts/sync_bob_skills.py`.
   - Ensure Ansible examples adhere to production standards (`ansible-lint`).
