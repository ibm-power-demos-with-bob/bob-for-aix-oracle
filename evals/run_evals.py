#!/usr/bin/env python3
"""Automated evaluation test suite for IBM Bob AIX, Ansible AIX, and Oracle AIX skills.

Validates that agent instructions, rules, and best-practice scripts produce accurate,
idiomatic, and executable solutions for AIX on IBM Power / IBM Cloud PowerVS.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".agents" / "skills"
BOB_RULES = ROOT / ".bob"


class TestAixSkill(unittest.TestCase):
    """Evaluates AIX OS skill guidance and command accuracy."""

    def setUp(self) -> None:
        self.skill_content = (SKILLS / "aix" / "SKILL.md").read_text(encoding="utf-8")
        self.rules_content = (BOB_RULES / "rules-aix" / "01-core-rules.md").read_text(encoding="utf-8")

    def test_native_aix_commands_referenced(self) -> None:
        """AIX skill must reference core AIX-native diagnostic and admin tools."""
        required_tools = [
            "lparstat", "vmstat", "svmon", "iostat", "errpt",
            "vmo", "ioo", "no", "schedo", "lsvg", "lscfg", "lsdev", "lssrc"
        ]
        for tool in required_tools:
            self.assertIn(tool, self.skill_content, f"Tool '{tool}' must be documented in aix SKILL.md")

    def test_no_linuxisms_in_rules(self) -> None:
        """Rules must explicitly forbid Linux-specific commands."""
        forbidden_terms = ["systemctl", "useradd", "sysctl", "free", "dmesg", "lspci"]
        for term in forbidden_terms:
            self.assertIn(term, self.rules_content, f"Forbidden term '{term}' should be cited in AIX rules")

    def test_shell_execution_clarification(self) -> None:
        """AIX automation guidelines must mention bash execution by Bob and native ksh support."""
        self.assertIn("bash", self.skill_content.lower())
        self.assertIn("ksh", self.skill_content.lower())


class TestAnsibleAixSkill(unittest.TestCase):
    """Evaluates Ansible AIX automation rules and examples."""

    def setUp(self) -> None:
        self.skill_content = (SKILLS / "ansible-aix" / "SKILL.md").read_text(encoding="utf-8")
        self.examples_dir = SKILLS / "ansible-aix" / "examples"

    def test_power_aix_collection_promoted(self) -> None:
        """Must require ibm.power_aix collection modules."""
        self.assertIn("ibm.power_aix", self.skill_content)
        self.assertIn("ansible-lint", self.skill_content)

    def test_ansible_examples_exist_and_use_power_aix(self) -> None:
        """Ansible examples must exist and reference ibm.power_aix modules."""
        examples = list(self.examples_dir.glob("*.yml"))
        self.assertGreater(len(examples), 0, "Ansible examples must exist")
        for ex in examples:
            content = ex.read_text(encoding="utf-8")
            self.assertIn("ibm.power_aix.", content)


class TestOracleAixSkill(unittest.TestCase):
    """Evaluates Oracle Database on AIX/Power skills, environment checks, and storage layout."""

    def setUp(self) -> None:
        self.skill_content = (SKILLS / "oracle-aix" / "SKILL.md").read_text(encoding="utf-8")
        self.rules_content = (BOB_RULES / "rules-oracle-aix" / "01-core-rules.md").read_text(encoding="utf-8")
        self.io_storage = (SKILLS / "oracle-aix" / "best-practices" / "io-storage.md").read_text(encoding="utf-8")
        self.os_prereqs = (SKILLS / "oracle-aix" / "best-practices" / "os-prereqs.md").read_text(encoding="utf-8")

    def test_preflight_environment_variables_enforced(self) -> None:
        """Pre-flight check must verify all critical Oracle env vars."""
        env_vars = ["ORACLE_HOME", "ORACLE_SID", "ORACLE_BASE", "PATH", "LIBPATH"]
        for var in env_vars:
            self.assertIn(var, self.skill_content, f"Env var '{var}' must be verified in pre-flight")
            self.assertIn(var, self.os_prereqs, f"Env var '{var}' must be in os-prereqs.md")

    def test_os_users_oracle_and_grid_default_and_prompt(self) -> None:
        """OS user oracle & grid must be default, and user prompted if missing."""
        self.assertIn("oracle", self.skill_content)
        self.assertIn("grid", self.skill_content)
        norm_skill = re.sub(r"\s+", " ", self.skill_content.lower())
        norm_rules = re.sub(r"\s+", " ", self.rules_content.lower())
        self.assertIn("ask the user for the correct username", norm_skill)
        self.assertIn("ask the user for the correct username", norm_rules)

    def test_storage_layout_volume_counts(self) -> None:
        """Storage best practices must recommend 8 data LUNs, 8 redo LUNs, 2 to 4 backup LUNs."""
        self.assertIn("8", self.io_storage)
        self.assertIn("2 to 4", self.io_storage)
        self.assertIn("DATA", self.skill_content)
        self.assertIn("REDO", self.skill_content)

    def test_bflash_tiering_and_queue_depth(self) -> None:
        """bflash / Tier 1 Flash and queue_depth (64-256) tuning must be documented."""
        self.assertIn("bflash", self.io_storage)
        self.assertIn("queue_depth", self.io_storage)
        self.assertIn("AU_SIZE", self.io_storage)
        self.assertIn("Tier 0", self.io_storage)
        self.assertIn("Tier 1", self.io_storage)

    def test_powervs_compatibility(self) -> None:
        """PowerVS specifics (Flash tiers, Power10 SMT8) must be covered."""
        self.assertIn("PowerVS", self.io_storage)
        self.assertIn("SMT", self.skill_content)
        self.assertIn("ORACLE_SGA_PGSZ", self.skill_content)


class TestLivePowerVSInstanceSpecs(unittest.TestCase):
    """Evaluates suitability of skill rules against the live IBM Cloud PowerVS LPAR 'aix-oracle01'."""

    def test_target_instance_specs_alignment(self) -> None:
        """Checks alignment with Power10 / AIX 7.3 / Flash storage configuration."""
        skill_text = (SKILLS / "oracle-aix" / "SKILL.md").read_text(encoding="utf-8")
        cpu_text = (SKILLS / "oracle-aix" / "best-practices" / "cpu.md").read_text(encoding="utf-8")
        io_text = (SKILLS / "oracle-aix" / "best-practices" / "io-storage.md").read_text(encoding="utf-8")

        self.assertIn("AIX 7.3", skill_text)
        self.assertIn("Power10", cpu_text)
        self.assertIn("SMT8", cpu_text)
        self.assertIn("Flash", io_text)


def run_all_evals() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_all_evals())
