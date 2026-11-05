#!/usr/bin/env python3
"""Evaluations for the demo recipes in recipes/ and the AIX command hallucination cases.

Static suite (no LLM, no AIX host needed), run with `python evals/run_evals.py` or
`python evals/recipe_evals.py`:

  * recipe structure: front matter fields, unique ids, known mode, existing skills and files;
  * groundedness: each recipe's reference answer satisfies its own `must_include` and
    `must_not_include` rules;
  * AIX accuracy: shell blocks in recipes and skills contain no Linux-only commands and
    none of the known wrong forms listed in evals/hallucination_cases.yaml;
  * hallucination cases: every case regex matches its example and every fix is documented.

CLI (to grade the real answer of a Bob session):

  python evals/recipe_evals.py --prompts              print id, mode and prompt of each recipe
  python evals/recipe_evals.py --grade R04 answer.txt grade a saved answer (exit code 1 on failure)
"""

from __future__ import annotations

import argparse
import re
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".agents" / "skills"
RECIPES = ROOT / "recipes"
CASES_FILE = ROOT / "evals" / "hallucination_cases.yaml"
MODES_FILE = ROOT / ".bob" / "custom_modes.yaml"

REQUIRED_FIELDS = ("id", "title", "mode", "skills", "reads", "prompt", "must_include",
                   "must_not_include")
SHELL_LANGS = {"bash", "sh", "ksh", "shell", "sql"}
FENCE_RE = re.compile(r"^```(\w*)\s*$")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.S)

# Linux/GNU-only commands that must not appear in executable AIX code.
LINUXISMS = [
    re.compile(r"\bdate\s+(-d|--date)\b"),
    re.compile(r"\bpgrep\b"),
    re.compile(r"\bsystemctl\b"),
    re.compile(r"\buseradd\b|\busermod\b"),
    re.compile(r"\bsysctl\b"),
    re.compile(r"\bjournalctl\b|\bdmesg\b"),
    re.compile(r"\blspci\b"),
    re.compile(r"\bfree\s+-[bkmgh]\b"),
    re.compile(r"\bsed\s+-i\b"),
    re.compile(r"\bgrep\s+-[A-Za-z]*P"),
    re.compile(r"\bexport\s+LD_LIBRARY_PATH\b"),
]


# --------------------------------------------------------------------------- helpers

class Recipe:
    def __init__(self, path: Path) -> None:
        self.path = path
        text = path.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        if not match:
            raise ValueError(f"{path.name}: missing front matter")
        self.meta: dict = yaml.safe_load(match.group(1)) or {}
        self.body: str = match.group(2)

    @property
    def id(self) -> str:
        return str(self.meta.get("id", self.path.stem))


def load_recipes() -> list[Recipe]:
    return [Recipe(p) for p in sorted(RECIPES.glob("*.md")) if p.name != "README.md"]


def load_cases() -> list[dict]:
    return yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))["cases"]


def mode_slugs() -> set[str]:
    data = yaml.safe_load(MODES_FILE.read_text(encoding="utf-8"))
    return {m["slug"] for m in data["customModes"]}


def skill_names() -> set[str]:
    return {p.parent.name for p in SKILLS.glob("*/SKILL.md")}


def code_lines(text: str, shell_only: bool = True) -> list[tuple[int, str]]:
    """Executable lines of fenced code blocks: comment lines and trailing comments removed."""
    lines: list[tuple[int, str]] = []
    lang: str | None = None
    for lineno, line in enumerate(text.splitlines(), 1):
        fence = FENCE_RE.match(line.strip())
        if fence:
            lang = None if lang is not None else (fence.group(1) or "")
            continue
        if lang is None or (shell_only and lang not in SHELL_LANGS):
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "--", ":")):
            continue
        lines.append((lineno, line.split(" #", 1)[0]))
    return lines


def knowledge_files() -> list[Path]:
    files = [p for p in SKILLS.rglob("*.md") if "operations" not in p.relative_to(SKILLS).parts]
    files += [p for p in RECIPES.glob("*.md")]
    return sorted(files)


def grade_answer(recipe: Recipe, answer: str, cases: list[dict]) -> list[str]:
    """Return the list of failures for a real answer; an empty list means PASS."""
    failures: list[str] = []
    lowered = answer.lower()
    for needle in recipe.meta["must_include"]:
        if str(needle).lower() not in lowered:
            failures.append(f"missing required content: {needle!r}")
    # Prose may quote a wrong command to warn against it, so only code is scanned.
    # An answer with no fenced block is scanned line by line.
    scanned = code_lines(answer, shell_only=False) or list(enumerate(answer.splitlines(), 1))
    for pattern in recipe.meta["must_not_include"]:
        if any(re.search(pattern, line) for _, line in scanned):
            failures.append(f"forbidden pattern present: {pattern!r}")
    for case in cases:
        regex = re.compile(case["wrong"])
        for lineno, line in scanned:
            if regex.search(line):
                failures.append(f"{case['id']} line {lineno}: {line.strip()!r} -> {case['fix']} "
                                f"({case['why']})")
                break
    return failures


# --------------------------------------------------------------------------- tests

class TestRecipeStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recipes = load_recipes()

    def test_recipes_exist(self) -> None:
        self.assertGreaterEqual(len(self.recipes), 6)

    def test_required_fields(self) -> None:
        for r in self.recipes:
            for field in REQUIRED_FIELDS:
                self.assertTrue(r.meta.get(field), f"{r.path.name}: missing `{field}`")
            for field in ("skills", "reads", "must_include", "must_not_include"):
                self.assertIsInstance(r.meta[field], list, f"{r.path.name}: `{field}` must be a list")

    def test_ids_unique_and_well_formed(self) -> None:
        ids = [r.id for r in self.recipes]
        self.assertEqual(len(ids), len(set(ids)), "duplicate recipe ids")
        for r in self.recipes:
            self.assertRegex(r.id, r"^R\d\d$", r.path.name)
            self.assertTrue(r.path.name.startswith(r.id[1:] + "-"),
                            f"{r.path.name}: file name must start with {r.id[1:]}-")

    def test_mode_skills_and_reads_exist(self) -> None:
        slugs, skills = mode_slugs(), skill_names()
        for r in self.recipes:
            self.assertIn(r.meta["mode"], slugs, f"{r.id}: unknown mode")
            for skill in r.meta["skills"]:
                self.assertIn(skill, skills, f"{r.id}: unknown skill {skill}")
            for ref in r.meta["reads"]:
                self.assertTrue((ROOT / ref).is_file(), f"{r.id}: `reads` file missing: {ref}")

    def test_must_not_include_regex_compile(self) -> None:
        for r in self.recipes:
            for pattern in r.meta["must_not_include"]:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    self.fail(f"{r.id}: bad regex {pattern!r}: {exc}")

    def test_prompt_is_a_task(self) -> None:
        for r in self.recipes:
            self.assertGreater(len(str(r.meta["prompt"]).split()), 8, f"{r.id}: prompt too short")


class TestRecipeReferenceAnswers(unittest.TestCase):
    """The reference answer in each recipe must satisfy the recipe's own grading rules."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.recipes = load_recipes()
        cls.cases = load_cases()

    def test_reference_answers_pass_their_own_grading(self) -> None:
        for r in self.recipes:
            failures = grade_answer(r, r.body, self.cases)
            self.assertEqual(failures, [], f"{r.id} ({r.path.name}): " + "; ".join(failures))

    def test_recipes_do_not_run_destructive_commands_unconfirmed(self) -> None:
        """Destructive AIX commands may appear only with a nearby confirmation note."""
        destructive = re.compile(r"\b(rmvg|reducevg|rmlv|rmfs|bosboot|installp\s+-c|"
                                 r"alt_disk_copy|geninstall\s+-k\s+-d)\b")
        for r in self.recipes:
            lines = r.body.splitlines()
            for lineno, line in code_lines(r.body):
                idx = lineno - 1
                if not destructive.search(line):
                    continue
                window = " ".join(lines[max(0, idx - 6): idx + 2]).lower()
                self.assertTrue(
                    any(w in window for w in ("confirm", "preview", "-p", "backup", "rollback",
                                              "fallback", "removes that ability")),
                    f"{r.id}:{idx + 1}: destructive command without confirm/preview/backup "
                    f"context: {line.strip()}")


class TestAixAccuracy(unittest.TestCase):
    def test_recipe_shell_blocks_have_no_linuxisms(self) -> None:
        for r in load_recipes():
            for lineno, line in code_lines(r.body):
                for pattern in LINUXISMS:
                    self.assertIsNone(pattern.search(line),
                                      f"{r.path.name}:{lineno}: Linux-only command: {line.strip()}")

    def test_knowledge_files_have_no_known_wrong_forms(self) -> None:
        cases = load_cases()
        for path in knowledge_files():
            text = path.read_text(encoding="utf-8")
            for lineno, line in code_lines(text):
                for case in cases:
                    self.assertIsNone(
                        re.search(case["wrong"], line),
                        f"{path.relative_to(ROOT).as_posix()}:{lineno}: {case['id']} "
                        f"{case['area']}: {line.strip()} (use: {case['fix']})")


class TestHallucinationCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases()
        cls.corpus = "\n".join(p.read_text(encoding="utf-8") for p in knowledge_files())

    def test_case_schema(self) -> None:
        ids = [c["id"] for c in self.cases]
        self.assertEqual(len(ids), len(set(ids)), "duplicate case ids")
        for c in self.cases:
            for field in ("id", "area", "wrong", "example", "fix", "why", "source"):
                self.assertTrue(c.get(field), f"{c.get('id')}: missing `{field}`")
            self.assertRegex(c["id"], r"^H\d\d$")

    def test_regex_matches_example(self) -> None:
        for c in self.cases:
            self.assertIsNotNone(re.search(c["wrong"], c["example"]),
                                 f"{c['id']}: regex does not match its own example")

    def test_fix_is_documented(self) -> None:
        for c in self.cases:
            self.assertIn(c["fix"], self.corpus, f"{c['id']}: fix {c['fix']!r} not found in any "
                                                 f"skill or recipe")

    def test_source_exists(self) -> None:
        for c in self.cases:
            if not c["source"].startswith("http"):
                self.assertTrue((ROOT / c["source"]).is_file(), f"{c['id']}: source missing")

    def test_grader_rejects_each_wrong_form(self) -> None:
        recipe = load_recipes()[0]
        for c in self.cases:
            answer = f"```bash\n{c['example']}\n```\n"
            failures = grade_answer(recipe, answer, self.cases)
            self.assertTrue(any(f.startswith(c["id"]) for f in failures),
                            f"{c['id']}: grader accepted the wrong form {c['example']!r}")

    def test_grader_ignores_wrong_form_in_prose_when_code_exists(self) -> None:
        recipe = load_recipes()[0]
        answer = "Do not use systemctl on AIX.\n```bash\nlssrc -s sshd\n```\n"
        failures = grade_answer(recipe, answer, self.cases)
        self.assertFalse(any(f.startswith("H02") for f in failures))


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--prompts", action="store_true", help="print recipe id, mode and prompt")
    parser.add_argument("--grade", nargs=2, metavar=("ID", "ANSWER_FILE"),
                        help="grade a saved Bob answer against a recipe, e.g. R04 answer.txt")
    args = parser.parse_args(argv)

    if args.prompts:
        for r in load_recipes():
            print(f"{r.id}  [{r.meta['mode']}]  {r.meta['title']}\n    {' '.join(str(r.meta['prompt']).split())}\n")
        return 0

    if args.grade:
        recipe_id, answer_file = args.grade
        recipe = next((r for r in load_recipes() if r.id == recipe_id.upper()), None)
        if recipe is None:
            print(f"Unknown recipe {recipe_id}", file=sys.stderr)
            return 2
        answer = Path(answer_file).read_text(encoding="utf-8")
        failures = grade_answer(recipe, answer, load_cases())
        for failure in failures:
            print(f"FAIL {recipe.id}: {failure}")
        print(f"{recipe.id}: {'PASS' if not failures else f'{len(failures)} failure(s)'}")
        return 1 if failures else 0

    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
