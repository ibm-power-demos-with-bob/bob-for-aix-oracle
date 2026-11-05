#!/usr/bin/env python3
"""Static checks for the skills, Bob modes, rules, and commands in this repository.

Checks:
  * .bob/custom_modes.yaml parses, slugs are valid and unique, required fields are present,
    groups are known to Bob, and every fileRegex compiles.
  * Every .agents/skills/<name>/SKILL.md has frontmatter whose `name` matches the folder and
    a non-empty `description`. Companion files carry no frontmatter (they are not skills).
  * The .bob/skills pointer skills are in sync (scripts/sync_bob_skills.py --check).
  * Relative Markdown links and companion-file references (best-practices/*.md, ...) resolve
    (skills, .bob, recipes/ and evals/recipes/).
  * Every `ibm.power_aix.<name>` reference is a real module or role of the collection.
  * Shell code blocks contain no Linux/GNU-only commands (date -d, pgrep, systemctl, ...).
  * Ansible example playbooks are valid YAML.
  * Bob slash commands have a `description` in their frontmatter.

Usage: python scripts/validate.py   (exit code 1 on any error)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".agents" / "skills"
BOB = ROOT / ".bob"
EXCLUDED_DIRS = {"operations"}  # cloned Oracle community content (git-ignored)

# Bob tool groups, from https://bob.ibm.com/docs/ide/configuration/custom-modes
BOB_GROUPS = {"read", "edit", "execute", "mcp", "skill", "workflow", "todo", "subtask",
              "subagent", "mode"}

# ibm.power_aix modules and roles, from https://ibm.github.io/ansible-power-aix/
POWER_AIX_MODULES = {
    "_nim_upgradeios", "aixpert", "alt_disk", "audit", "backup", "bootlist", "bosboot",
    "chsec", "clvupdate", "devices", "emgr", "entstat", "errclear", "errpt", "fcstat",
    "filesystem", "flrtvc", "geninstall", "getconf", "group", "hdcrypt_auth", "hdcrypt_conv",
    "hdcrypt_facts", "hdcrypt_pks", "inittab", "install_all_updates", "installp", "iostat",
    "lku", "llvupdate", "lpar_facts", "lparstat", "lpp_facts", "lvg", "lvm_facts", "lvol",
    "mkfilt", "mktcpip", "mktun", "mount", "mpio", "netstat", "nim", "nim_backup",
    "nim_flrtvc", "nim_resource", "nim_select_target_disk", "nim_suma", "nim_updateios",
    "nim_vios_alt_disk", "nim_vios_hc", "nim_viosupgrade", "nimclient", "nmon", "pagingspace",
    "password_hash", "password_rules_policies", "ps", "reboot", "route", "smtctl", "snap",
    "suma", "sysdumpdev", "timezone_mgmt", "traceroute", "tunables", "tunfile_mgmt", "user",
    "vmstat",
}
POWER_AIX_ROLES = {
    "bootptab", "inetd", "ipsec", "live_kernel_update", "nim_alt_disk_migration",
    "nim_master_migration", "power_aix_bootstrap", "power_aix_vioshc",
}

# Linux/GNU-only commands that must not appear in AIX shell examples.
LINUXISMS = [
    (re.compile(r"\bdate\s+(-d|--date)\b"), "GNU `date -d` (AIX date has no -d)"),
    (re.compile(r"\bpgrep\b"), "`pgrep` is not in base AIX"),
    (re.compile(r"\bsystemctl\b"), "`systemctl` (AIX uses SRC: lssrc/startsrc/stopsrc)"),
    (re.compile(r"\buseradd\b|\busermod\b"), "`useradd`/`usermod` (AIX: mkuser/chuser)"),
    (re.compile(r"\bsysctl\b"), "`sysctl` (AIX: vmo/ioo/schedo/no)"),
    (re.compile(r"\bjournalctl\b|\bdmesg\b"), "`journalctl`/`dmesg` (AIX: errpt)"),
    (re.compile(r"\blspci\b"), "`lspci` (AIX: lsdev/lscfg)"),
    (re.compile(r"\bfree\s+-[bkmgh]\b"), "`free` (AIX: svmon -G / vmstat -v)"),
    (re.compile(r"\bsed\s+-i\b"), "GNU `sed -i`"),
    (re.compile(r"\bgrep\s+-[A-Za-z]*P"), "GNU `grep -P`"),
    (re.compile(r"\bexport\s+LD_LIBRARY_PATH\b"), "`LD_LIBRARY_PATH` (AIX: LIBPATH)"),
]
SHELL_LANGS = {"bash", "sh", "ksh", "shell"}

FENCE_RE = re.compile(r"^```(\w*)\s*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
COMPANION_RE = re.compile(r"`((?:best-practices|examples|scripts)/[\w./-]+)`")
BARE_MD_RE = re.compile(r"`([a-z][\w-]*\.md)(?:\s+§[\w.]+)?`")
POWER_AIX_RE = re.compile(r"\bibm\.power_aix\.([a-z_0-9]+)\b")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)

errors: list[str] = []
warnings: list[str] = []


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def skill_files() -> list[Path]:
    return sorted(
        p for p in SKILLS.rglob("*.md")
        if not EXCLUDED_DIRS.intersection(p.relative_to(SKILLS).parts)
    )


def frontmatter(path: Path) -> dict | None:
    match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    return yaml.safe_load(match.group(1)) if match else None


def check_modes() -> None:
    path = BOB / "custom_modes.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    slugs = set()
    for mode in data.get("customModes", []):
        slug = mode.get("slug", "")
        where = f"{rel(path)} [{slug or '?'}]"
        if not re.fullmatch(r"[A-Za-z0-9-]+", slug):
            errors.append(f"{where}: invalid slug (letters, digits and hyphens only)")
        if slug in slugs:
            errors.append(f"{where}: duplicate slug")
        slugs.add(slug)
        for field in ("name", "roleDefinition", "groups"):
            if not mode.get(field):
                errors.append(f"{where}: missing `{field}`")
        for group in mode.get("groups", []):
            if isinstance(group, list):
                group_name, options = group[0], (group[1] if len(group) > 1 else {})
                if "fileRegex" in options:
                    try:
                        re.compile(options["fileRegex"])
                    except re.error as exc:
                        errors.append(f"{where}: fileRegex does not compile: {exc}")
            else:
                group_name = group
            if group_name not in BOB_GROUPS:
                warnings.append(f"{where}: group `{group_name}` is not a documented Bob group "
                                f"(documented: {', '.join(sorted(BOB_GROUPS))}); per the Bob docs "
                                f"unknown groups grant no access")
        rules_dir = BOB / f"rules-{slug}"
        if slug in {"aix", "ansible-aix", "oracle-aix"} and not rules_dir.is_dir():
            warnings.append(f"{where}: no {rel(rules_dir)}/ always-on rules directory")


def check_skills() -> None:
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        fm = frontmatter(skill_md)
        if fm is None:
            errors.append(f"{rel(skill_md)}: missing YAML frontmatter")
            continue
        if fm.get("name") != skill_md.parent.name:
            errors.append(f"{rel(skill_md)}: frontmatter name `{fm.get('name')}` "
                          f"does not match folder `{skill_md.parent.name}`")
        if not str(fm.get("description", "")).strip():
            errors.append(f"{rel(skill_md)}: empty description (Bob ignores such skills)")
    for path in skill_files():
        if path.name != "SKILL.md" and frontmatter(path) is not None:
            errors.append(f"{rel(path)}: companion files must not have skill frontmatter "
                          f"(they are not discovered as skills); use a 'Read this file for' note")


def check_bob_pointers() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_bob_skills  # noqa: E402

    if sync_bob_skills.main(["--check"]) != 0:
        errors.append(".bob/skills pointers are out of sync: run python scripts/sync_bob_skills.py")


def check_references_and_code() -> None:
    files = (skill_files() + sorted(BOB.rglob("*.md")) + sorted((ROOT / "recipes").glob("*.md"))
             + sorted((ROOT / "evals" / "recipes").glob("*.md")))
    for path in files:
        text = path.read_text(encoding="utf-8")
        skill_root = next((p for p in [path.parent, *path.parents] if (p / "SKILL.md").exists()
                           and SKILLS in p.parents), None)

        for target in LINK_RE.findall(text):
            if re.match(r"^(https?:|mailto:|#)", target):
                continue
            resolved = (path.parent / target.split("#")[0]).resolve()
            if not resolved.exists():
                errors.append(f"{rel(path)}: broken link `{target}`")

        if skill_root is not None:
            known = {p.name for p in skill_root.rglob("*") if p.is_file()}
            for ref in COMPANION_RE.findall(text):
                ref = ref.rstrip(".,")
                if not (skill_root / ref).exists() and not (path.parent / ref).exists():
                    errors.append(f"{rel(path)}: reference to missing file `{ref}`")
            for name in BARE_MD_RE.findall(text):
                if name not in known and name not in {"SKILL.md", "README.md"}:
                    errors.append(f"{rel(path)}: reference to missing companion `{name}`")

        for name in POWER_AIX_RE.findall(text):
            if name not in POWER_AIX_MODULES | POWER_AIX_ROLES:
                errors.append(f"{rel(path)}: `ibm.power_aix.{name}` is not a module or role "
                              f"of the collection")

        lang = None
        for lineno, line in enumerate(text.splitlines(), 1):
            fence = FENCE_RE.match(line.strip())
            if fence:
                lang = None if lang is not None else (fence.group(1) or "")
                continue
            if lang in SHELL_LANGS and not line.lstrip().startswith("#"):
                code = line.split(" #", 1)[0]
                for pattern, message in LINUXISMS:
                    if pattern.search(code):
                        errors.append(f"{rel(path)}:{lineno}: {message}")


def check_ansible_examples() -> None:
    for path in sorted(SKILLS.glob("*/examples/*.yml")):
        text = path.read_text(encoding="utf-8")
        try:
            yaml.safe_load(text)
        except yaml.YAMLError as exc:
            errors.append(f"{rel(path)}: invalid YAML: {exc}")
        for name in POWER_AIX_RE.findall(text):
            if name not in POWER_AIX_MODULES | POWER_AIX_ROLES:
                errors.append(f"{rel(path)}: unknown module `ibm.power_aix.{name}`")


def check_commands() -> None:
    for path in sorted((BOB / "commands").glob("**/*.md")):
        fm = frontmatter(path) or {}
        if not str(fm.get("description", "")).strip():
            warnings.append(f"{rel(path)}: no `description` frontmatter (shown in the command menu)")


def main() -> int:
    check_modes()
    check_skills()
    check_bob_pointers()
    check_references_and_code()
    check_ansible_examples()
    check_commands()
    for message in warnings:
        print(f"WARNING {message}")
    for message in errors:
        print(f"ERROR   {message}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
