#!/usr/bin/env python3
"""Evaluations for the eval scenarios, the step-by-step recipes and the AIX hallucination cases.

Static suite (no LLM, no AIX host needed), run with `python evals/run_evals.py` or
`python evals/scenario_evals.py`:

  * scenario structure (evals/scenarios/): front matter fields, unique ids, known mode,
    existing skills and files;
  * groundedness: each scenario's reference answer satisfies its own `must_include` and
    `must_not_include` rules;
  * recipes (recipes/): every step has a prompt and an `<!-- eval -->` block with the mode,
    the strings a correct answer must contain and the patterns it must not contain; the
    recipe text itself must satisfy these rules, so a recipe and its test never drift apart;
  * AIX accuracy: shell blocks in scenarios, recipes and skills contain no Linux-only
    commands and none of the known wrong forms listed in evals/hallucination_cases.yaml;
  * hallucination cases: every case regex matches its example and every fix is documented.

CLI (to grade the real answer of a Bob session):

  python evals/scenario_evals.py --prompts                   print id, mode and prompt of each scenario
  python evals/scenario_evals.py --grade S04 answer.txt      grade a saved answer (exit code 1 on failure)
  python evals/scenario_evals.py --recipe-prompts            print mode and prompt of each recipe step
  python evals/scenario_evals.py --grade-recipe 03:2 a.txt   grade a saved answer for step 2 of recipe 03
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
SCENARIOS = ROOT / "evals" / "scenarios"  # technical eval scenarios (front matter + reference answer)
RECIPES = ROOT / "recipes"                # human-oriented, step-by-step recipes (also test cases)
CASES_FILE = ROOT / "evals" / "hallucination_cases.yaml"
MODES_FILE = ROOT / ".bob" / "custom_modes.yaml"

REQUIRED_FIELDS = ("id", "title", "mode", "skills", "reads", "prompt", "must_include",
                   "must_not_include")
SHELL_LANGS = {"bash", "sh", "ksh", "shell", "sql"}
FENCE_RE = re.compile(r"^```(\w*)\s*$")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.S)
SECTION_RE = re.compile(r"^(?=## )", re.M)
STEP_TITLE_RE = re.compile(r"^## Step (\d+): (.*)$", re.M)
EVAL_BLOCK_RE = re.compile(r"<!--\s*eval\r?\n(.*?)\r?\n-->\r?\n?", re.S)

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

class Scenario:
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


class RecipeStep:
    """One `## Step N:` section of a recipe, with its prompt and its `<!-- eval -->` rules."""

    def __init__(self, path: Path, number: int, title: str, section: str) -> None:
        self.path = path
        self.number = number
        self.title = title
        blocks = EVAL_BLOCK_RE.findall(section)
        self.eval_blocks = len(blocks)
        self.meta: dict = (yaml.safe_load(blocks[0]) or {}) if blocks else {}
        self.text = EVAL_BLOCK_RE.sub("", section)   # what a reader sees
        self.prompt = self._prompt_before_eval(section)

    @property
    def recipe(self) -> str:
        return self.path.name[:2]

    @property
    def key(self) -> str:
        return f"{self.recipe}:{self.number}"

    @staticmethod
    def _prompt_before_eval(section: str) -> str:
        """The ```text block that closes just before the eval comment is the prompt."""
        match = EVAL_BLOCK_RE.search(section)
        head = section[: match.start()] if match else section
        blocks = re.findall(r"```text\r?\n(.*?)\r?\n```", head, re.S)
        return blocks[-1].strip() if blocks else ""


def load_scenarios() -> list[Scenario]:
    return [Scenario(p) for p in sorted(SCENARIOS.glob("*.md")) if p.name != "README.md"]


def recipe_files() -> list[Path]:
    return sorted(RECIPES.glob("[0-9][0-9]-*.md"))


def load_recipe_steps() -> list[RecipeStep]:
    steps: list[RecipeStep] = []
    for path in recipe_files():
        for section in SECTION_RE.split(path.read_text(encoding="utf-8")):
            title = STEP_TITLE_RE.match(section)
            if title:
                steps.append(RecipeStep(path, int(title.group(1)), title.group(2).strip(), section))
    return steps


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
    files += [p for p in SCENARIOS.glob("*.md")]
    files += [p for p in RECIPES.glob("*.md")]
    return sorted(files)


def grade_text(answer: str, must_include: list, must_not_include: list, cases: list[dict]) -> list[str]:
    """Return the list of failures for a real answer; an empty list means PASS."""
    failures: list[str] = []
    lowered = answer.lower()
    for needle in must_include:
        if str(needle).lower() not in lowered:
            failures.append(f"missing required content: {needle!r}")
    # Prose may quote a wrong command to warn against it, so only code is scanned.
    # An answer with no fenced block is scanned line by line.
    scanned = code_lines(answer, shell_only=False) or list(enumerate(answer.splitlines(), 1))
    for pattern in must_not_include:
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


def grade_answer(scenario: Scenario, answer: str, cases: list[dict]) -> list[str]:
    return grade_text(answer, scenario.meta["must_include"], scenario.meta["must_not_include"], cases)


def grade_step(step: RecipeStep, answer: str, cases: list[dict]) -> list[str]:
    return grade_text(answer, step.meta["must_include"], step.meta["must_not_include"], cases)


# --------------------------------------------------------------------------- scenario tests

class TestScenarioStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenarios = load_scenarios()

    def test_scenarios_exist(self) -> None:
        self.assertGreaterEqual(len(self.scenarios), 6)

    def test_required_fields(self) -> None:
        for s in self.scenarios:
            for field in REQUIRED_FIELDS:
                self.assertTrue(s.meta.get(field), f"{s.path.name}: missing `{field}`")
            for field in ("skills", "reads", "must_include", "must_not_include"):
                self.assertIsInstance(s.meta[field], list, f"{s.path.name}: `{field}` must be a list")

    def test_ids_unique_and_well_formed(self) -> None:
        ids = [s.id for s in self.scenarios]
        self.assertEqual(len(ids), len(set(ids)), "duplicate scenario ids")
        for s in self.scenarios:
            self.assertRegex(s.id, r"^S\d\d$", s.path.name)
            self.assertTrue(s.path.name.startswith(s.id[1:] + "-"),
                            f"{s.path.name}: file name must start with {s.id[1:]}-")

    def test_mode_skills_and_reads_exist(self) -> None:
        slugs, skills = mode_slugs(), skill_names()
        for s in self.scenarios:
            self.assertIn(s.meta["mode"], slugs, f"{s.id}: unknown mode")
            for skill in s.meta["skills"]:
                self.assertIn(skill, skills, f"{s.id}: unknown skill {skill}")
            for ref in s.meta["reads"]:
                self.assertTrue((ROOT / ref).is_file(), f"{s.id}: `reads` file missing: {ref}")

    def test_must_not_include_regex_compile(self) -> None:
        for s in self.scenarios:
            for pattern in s.meta["must_not_include"]:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    self.fail(f"{s.id}: bad regex {pattern!r}: {exc}")

    def test_prompt_is_a_task(self) -> None:
        for s in self.scenarios:
            self.assertGreater(len(str(s.meta["prompt"]).split()), 8, f"{s.id}: prompt too short")


class TestScenarioReferenceAnswers(unittest.TestCase):
    """The reference answer in each scenario must satisfy the scenario's own grading rules."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.scenarios = load_scenarios()
        cls.cases = load_cases()

    def test_reference_answers_pass_their_own_grading(self) -> None:
        for s in self.scenarios:
            failures = grade_answer(s, s.body, self.cases)
            self.assertEqual(failures, [], f"{s.id} ({s.path.name}): " + "; ".join(failures))

    def test_scenarios_do_not_run_destructive_commands_unconfirmed(self) -> None:
        """Destructive AIX commands may appear only with a nearby confirmation note."""
        destructive = re.compile(r"\b(rmvg|reducevg|rmlv|rmfs|bosboot|installp\s+-c|"
                                 r"alt_disk_copy|geninstall\s+-k\s+-d)\b")
        for s in self.scenarios:
            lines = s.body.splitlines()
            for lineno, line in code_lines(s.body):
                idx = lineno - 1
                if not destructive.search(line):
                    continue
                window = " ".join(lines[max(0, idx - 6): idx + 2]).lower()
                self.assertTrue(
                    any(w in window for w in ("confirm", "preview", "-p", "backup", "rollback",
                                              "fallback", "removes that ability")),
                    f"{s.id}:{idx + 1}: destructive command without confirm/preview/backup "
                    f"context: {line.strip()}")


class TestAixAccuracy(unittest.TestCase):
    def test_scenario_shell_blocks_have_no_linuxisms(self) -> None:
        for s in load_scenarios():
            for lineno, line in code_lines(s.body):
                for pattern in LINUXISMS:
                    self.assertIsNone(pattern.search(line),
                                      f"{s.path.name}:{lineno}: Linux-only command: {line.strip()}")

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
                                                 f"skill, scenario or recipe")

    def test_source_exists(self) -> None:
        for c in self.cases:
            if not c["source"].startswith("http"):
                self.assertTrue((ROOT / c["source"]).is_file(), f"{c['id']}: source missing")

    def test_grader_rejects_each_wrong_form(self) -> None:
        scenario = load_scenarios()[0]
        for c in self.cases:
            answer = f"```bash\n{c['example']}\n```\n"
            failures = grade_answer(scenario, answer, self.cases)
            self.assertTrue(any(f.startswith(c["id"]) for f in failures),
                            f"{c['id']}: grader accepted the wrong form {c['example']!r}")

    def test_grader_ignores_wrong_form_in_prose_when_code_exists(self) -> None:
        scenario = load_scenarios()[0]
        answer = "Do not use systemctl on AIX.\n```bash\nlssrc -s sshd\n```\n"
        failures = grade_answer(scenario, answer, self.cases)
        self.assertFalse(any(f.startswith("H02") for f in failures))


# --------------------------------------------------------------------------- recipe tests

class TestRecipes(unittest.TestCase):
    """The step-by-step recipes in recipes/ keep one structure and stay AIX-accurate."""
    REQUIRED_SECTIONS = ("## Overview", "## Prerequisites", "## ✅ Success criteria",
                         "## Key takeaways")
    OVERVIEW_FIELDS = ("**Duration**", "**Difficulty**", "**Mode**", "**Output**")
    MODE_NAMES = ("Oracle on AIX/Power", "AIX/Oracle Review", "Ansible AIX")

    @classmethod
    def setUpClass(cls) -> None:
        cls.recipes = recipe_files()
        cls.index = (RECIPES / "README.md").read_text(encoding="utf-8")

    def test_recipes_exist_and_are_numbered_contiguously_from_01(self) -> None:
        numbers = [p.name[:2] for p in self.recipes]
        self.assertGreaterEqual(len(numbers), 5)
        self.assertEqual(numbers, [f"{n:02d}" for n in range(1, len(numbers) + 1)])

    def test_recipes_are_listed_in_the_index(self) -> None:
        for recipe in self.recipes:
            self.assertIn(f"({recipe.name})", self.index, f"{recipe.name}: not linked from recipes/README.md")

    def test_recipes_have_no_unfinished_placeholders(self) -> None:
        """A scaffolded lab (lab-author skill) must have every TODO replaced."""
        for recipe in self.recipes:
            for lineno, line in enumerate(recipe.read_text(encoding="utf-8").splitlines(), 1):
                self.assertNotRegex(line, r"\bTODO\b", f"{recipe.name}:{lineno}: unfinished TODO")

    def test_recipe_structure(self) -> None:
        for recipe in self.recipes:
            text = recipe.read_text(encoding="utf-8")
            self.assertRegex(text, rf"^# Lab {recipe.name[:2]}: ",
                             f"{recipe.name}: title must be 'Lab {recipe.name[:2]}: ...'")
            for section in self.REQUIRED_SECTIONS:
                self.assertIn(section, text, f"{recipe.name}: missing section {section!r}")
            for field in self.OVERVIEW_FIELDS:
                self.assertIn(field, text, f"{recipe.name}: overview lacks {field}")
            self.assertTrue(any(m in text for m in self.MODE_NAMES), f"{recipe.name}: no Bob mode named")

    def test_each_step_has_a_copy_paste_prompt(self) -> None:
        for recipe in self.recipes:
            text = recipe.read_text(encoding="utf-8")
            steps = re.split(r"^## Step \d+:", text, flags=re.M)[1:]
            self.assertGreaterEqual(len(steps), 4, f"{recipe.name}: fewer than 4 steps")
            for number, step in enumerate(steps, 1):
                self.assertIn("```text", step, f"{recipe.name}: Step {number} has no ```text prompt block")
                self.assertIn("**Goal:**", step, f"{recipe.name}: Step {number} has no **Goal:**")

    def test_recipes_have_at_least_one_trap_or_confirmation(self) -> None:
        """Every recipe either demonstrates a Linux-reflex trap or gates a change on a confirmation."""
        for recipe in self.recipes:
            text = recipe.read_text(encoding="utf-8").lower()
            self.assertTrue("**trap" in text or "confirm" in text, f"{recipe.name}: no trap or confirmation")

    def test_recipe_shell_blocks_have_no_linuxisms(self) -> None:
        for recipe in self.recipes:
            for lineno, line in code_lines(recipe.read_text(encoding="utf-8")):
                for pattern in LINUXISMS:
                    self.assertIsNone(pattern.search(line),
                                      f"{recipe.name}:{lineno}: Linux-only command: {line.strip()}")

    def test_recipes_are_written_in_english(self) -> None:
        french = re.compile(r"\b(les|des|pour|avec|vous|est|une|dans|cette)\b")
        for recipe in self.recipes + [RECIPES / "README.md"]:
            for lineno, line in enumerate(recipe.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(french.search(line.lower()),
                                  f"{recipe.name}:{lineno}: looks French: {line.strip()}")


class TestRecipeSteps(unittest.TestCase):
    """Each recipe step is an automated test case: prompt, mode and grading rules."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.steps = load_recipe_steps()
        cls.cases = load_cases()

    def test_every_step_has_exactly_one_eval_block(self) -> None:
        self.assertGreaterEqual(len(self.steps), 20)
        for step in self.steps:
            self.assertEqual(step.eval_blocks, 1,
                             f"{step.path.name} step {step.number}: needs exactly one <!-- eval --> block")

    def test_eval_block_schema(self) -> None:
        slugs = mode_slugs()
        for step in self.steps:
            where = f"{step.path.name} step {step.number}"
            self.assertIn(step.meta.get("mode"), slugs, f"{where}: unknown mode")
            for field in ("must_include", "must_not_include"):
                self.assertIsInstance(step.meta.get(field), list, f"{where}: `{field}` must be a list")
            self.assertTrue(step.meta["must_include"], f"{where}: `must_include` is empty")
            for pattern in step.meta["must_not_include"]:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    self.fail(f"{where}: bad regex {pattern!r}: {exc}")

    def test_prompt_precedes_the_eval_block(self) -> None:
        for step in self.steps:
            self.assertGreater(len(step.prompt.split()), 8,
                               f"{step.path.name} step {step.number}: no prompt before the eval block")

    def test_expected_content_is_described_in_the_step(self) -> None:
        """Every `must_include` string must appear in the step text a reader sees."""
        for step in self.steps:
            lowered = step.text.lower()
            for needle in step.meta["must_include"]:
                self.assertIn(str(needle).lower(), lowered,
                              f"{step.path.name} step {step.number}: `{needle}` is expected in the "
                              f"answer but not described in the step")

    def test_step_code_passes_its_own_rules(self) -> None:
        """The commands shown in a step must not match the step's `must_not_include`."""
        for step in self.steps:
            for pattern in step.meta["must_not_include"]:
                for lineno, line in code_lines(step.text):
                    self.assertIsNone(re.search(pattern, line),
                                      f"{step.path.name} step {step.number}: `{line.strip()}` "
                                      f"matches forbidden pattern {pattern!r}")

    def test_grader_accepts_a_complete_answer_and_rejects_an_incomplete_one(self) -> None:
        for step in self.steps:
            complete = "\n".join(str(n) for n in step.meta["must_include"])
            self.assertEqual(grade_step(step, complete, self.cases), [],
                             f"{step.path.name} step {step.number}: complete answer rejected")
            failures = grade_step(step, "I do not know.", self.cases)
            self.assertTrue(any("missing required content" in f for f in failures),
                            f"{step.path.name} step {step.number}: empty answer accepted")

    def test_grader_rejects_forbidden_patterns(self) -> None:
        samples = {
            r"\buseradd\b": "useradd oracle",
            r"\bsysctl\b": "sysctl -w kernel.shmmax=1",
            r"\biostat\s+-x\b": "iostat -x 5",
            r"\bmpstat\s+-P\b": "mpstat -P ALL 5",
            r"\bdate\s+(-d|--date)\b": "date -d yesterday",
            r"\bsystemctl\b": "systemctl restart x",
        }
        checked = 0
        for step in self.steps:
            complete = "\n".join(str(n) for n in step.meta["must_include"])
            for pattern in step.meta["must_not_include"]:
                if pattern in samples:
                    answer = f"{complete}\n```bash\n{samples[pattern]}\n```\n"
                    failures = grade_step(step, answer, self.cases)
                    self.assertTrue(failures, f"{step.path.name} step {step.number}: {pattern!r} not enforced")
                    checked += 1
        self.assertGreater(checked, 0)


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--prompts", action="store_true", help="print scenario id, mode and prompt")
    parser.add_argument("--grade", nargs=2, metavar=("ID", "ANSWER_FILE"),
                        help="grade a saved Bob answer against a scenario, e.g. S04 answer.txt")
    parser.add_argument("--recipe-prompts", action="store_true",
                        help="print recipe, step, mode and prompt of each recipe step")
    parser.add_argument("--grade-recipe", nargs=2, metavar=("RECIPE:STEP", "ANSWER_FILE"),
                        help="grade a saved Bob answer against a recipe step, e.g. 03:2 answer.txt")
    args = parser.parse_args(argv)

    if args.prompts:
        for s in load_scenarios():
            print(f"{s.id}  [{s.meta['mode']}]  {s.meta['title']}\n    {' '.join(str(s.meta['prompt']).split())}\n")
        return 0

    if args.recipe_prompts:
        for step in load_recipe_steps():
            print(f"{step.key}  [{step.meta.get('mode', '?')}]  {step.title}\n    {' '.join(step.prompt.split())}\n")
        return 0

    if args.grade:
        scenario_id, answer_file = args.grade
        scenario = next((s for s in load_scenarios() if s.id == scenario_id.upper()), None)
        if scenario is None:
            print(f"Unknown scenario {scenario_id}", file=sys.stderr)
            return 2
        answer = Path(answer_file).read_text(encoding="utf-8")
        failures = grade_answer(scenario, answer, load_cases())
        for failure in failures:
            print(f"FAIL {scenario.id}: {failure}")
        print(f"{scenario.id}: {'PASS' if not failures else f'{len(failures)} failure(s)'}")
        return 1 if failures else 0

    if args.grade_recipe:
        key, answer_file = args.grade_recipe
        recipe, _, number = key.partition(":")
        step = next((s for s in load_recipe_steps()
                     if s.recipe == recipe.zfill(2) and str(s.number) == number), None)
        if step is None:
            print(f"Unknown recipe step {key} (expected RECIPE:STEP, e.g. 03:2)", file=sys.stderr)
            return 2
        answer = Path(answer_file).read_text(encoding="utf-8")
        failures = grade_step(step, answer, load_cases())
        for failure in failures:
            print(f"FAIL {step.key}: {failure}")
        print(f"{step.key}: {'PASS' if not failures else f'{len(failures)} failure(s)'}")
        return 1 if failures else 0

    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
