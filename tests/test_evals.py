"""The eval suite: generated from the standards, and run by no test.

What is tested is what the suite is made of, never what a model does
with it: a run is a model session on the owner's credential. So each
property a run depends on is held here instead — the documented case
format, literals that mean in JavaScript what they say, a grader that
cannot pass on its own prompt, and a negative case in another language.
"""

import json
import re
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from agent_skill import build, cli
from agent_skill.checks import demo
from agent_skill.checks import evals as check
from agent_skill.checks.demo import PROFILE as DEMO
from agent_skill.doc import Doc, Fence, opening_span
from agent_skill.evals import (
    MIGRATION,
    NEGATIVE,
    REVIEW,
    TOOLS,
    Case,
    Suite,
    compare,
    generate,
    literal,
    on_disk,
    write,
)
from agent_skill.layout import EVALS, RESULTS, SKILLS, root_of
from agent_skill.model import Skill, Tree, discover
from agent_skill.proc import have, run
from agent_skill.profiles import PROFILES, Evals
from agent_skill.profiles.record import listed
from agent_skill.report import Level

REPO = Path(__file__).resolve().parents[1]

# The format as `claude plugin eval` documents it (Claude Code 2.1.269
# and later): the keys a case's `prompt.md` may set, an unknown one
# being an error, and each grader type's options.
PROMPT_KEYS = frozenset(
    {
        "schema_version",
        "name",
        "description",
        "tags",
        "plugins",
        "runs",
        "expected_outcome",
        "model",
        "max_turns",
        "timeout_seconds",
        "allowed_tools",
        "append_system_prompt",
        "env",
    }
)
GRADER_KEYS = frozenset({"type", "weight", "arm"})
OPTIONS = {
    "regex": frozenset({"pattern", "flags", "match", "target"}),
    "tool_used": frozenset({"tool", "input_match", "min", "max"}),
    "tool_order": frozenset({"before", "after"}),
    "file_exists": frozenset({"path", "exists"}),
}
#: The tools a case may list that a run grants without `--allow-tools`.
READ_ONLY = frozenset(
    {
        "Read",
        "Glob",
        "Grep",
        "NotebookRead",
        "Skill",
        "AskUserQuestion",
        "Agent",
        "TodoWrite",
        "TaskCreate",
        "TaskGet",
        "TaskList",
        "TaskUpdate",
        "TaskStop",
    }
)


@pytest.fixture(scope="module")
def suite(skills: list[Skill]) -> Suite:
    """The suite the shipped standards generate, once."""
    return generate(Tree.of(skills))


def frontmatter(text: str) -> dict[str, str]:
    """Each key of a file's frontmatter, and its value as written."""
    held = Doc.parse(text).frontmatter
    assert held is not None, text
    return dict(line.split(": ", 1) for line in held.split("\n"))


def unquoted(value: str) -> str:
    """A single-quoted YAML scalar, read."""
    assert value.startswith("'"), value
    assert value.endswith("'"), value
    return value[1:-1].replace("''", "'")


def fence(case: Case) -> Fence:
    """The one example a case's prompt sends."""
    (found,) = (b for b in case.prompt if isinstance(b, Fence))
    return found


def graders(case: Case) -> dict[str, dict[str, str]]:
    """Each grader of `case`, by name, as its frontmatter reads."""
    return {g.name: frontmatter(g.text) for g in case.graders}


def test_every_shipped_profile_selects_two_rules_and_two_spellings() -> None:
    for profile in PROFILES.values():
        assert profile.evals is not None, profile.name
        assert len(profile.evals.review) == len(profile.evals.migrate) == 2


def test_each_standard_has_two_reviews_two_migrations_and_one_negative(
    suite: Suite,
) -> None:
    assert suite.refused == ()
    kinds = {
        name: sorted(c.kind for c in suite.cases if c.standard == name)
        for name in PROFILES
    }
    assert kinds == {
        name: [MIGRATION, MIGRATION, NEGATIVE, REVIEW, REVIEW] for name in PROFILES
    }


def test_every_case_is_tagged_with_its_standard_and_kind(suite: Suite) -> None:
    names = [c.name for c in suite.cases]
    assert len(set(names)) == len(names)
    for case in suite.cases:
        held = frontmatter(case.files[f"{case.directory}/prompt.md"])
        assert held["tags"] == f"[{case.standard}, {case.kind}]"
        assert held["name"] == case.name


def test_the_shipped_suite_on_disk_is_the_generated_one(suite: Suite) -> None:
    assert compare(REPO, suite) == ([], [])


def test_every_file_keeps_to_the_documented_format(suite: Suite) -> None:
    for rel, text in suite.files.items():
        held = frontmatter(text)
        if rel.endswith("/prompt.md"):
            assert set(held) <= PROMPT_KEYS, rel
            assert held["schema_version"] == '"1.1"'
            assert 1 <= int(held["runs"]) <= 50
            assert 1 <= int(held["max_turns"]) <= 200
            listed_tools = held["allowed_tools"].strip("[]").split(", ")
            assert set(listed_tools) <= READ_ONLY
            assert tuple(listed_tools) == TOOLS
            assert Doc.parse(text).blocks, f"{rel} sends no prompt"
        else:
            kind = held["type"]
            assert kind in OPTIONS, f"{rel}: {kind} is not a grader decided for free"
            assert set(held) <= GRADER_KEYS | OPTIONS[kind], rel
            assert Doc.parse(text).blocks == (), f"{rel} has a body"


def test_every_case_has_a_grader_scored_against_no_plugin(suite: Suite) -> None:
    """A two-arm run leaves out each `Skill` grader not set `both`."""
    for case in suite.cases:
        scored = [
            g
            for g in graders(case).values()
            if g.get("arm") != "with-only"
            and (g.get("tool") != "Skill" or g.get("arm") == "both")
        ]
        assert scored, case.name


def test_every_case_but_the_negative_reports_its_own_skill_firing(
    suite: Suite,
) -> None:
    for case in suite.cases:
        held = graders(case)
        if case.kind == NEGATIVE:
            assert held == {
                "skill-silent": {
                    "type": "tool_used",
                    "tool": "Skill",
                    "input_match": held["skill-silent"]["input_match"],
                    "min": "0",
                    "max": "0",
                    "arm": "both",
                }
            }
        else:
            assert held["skill-fired"].keys() == {"type", "tool", "input_match"}
        (pattern,) = (unquoted(g["input_match"]) for g in held.values() if "tool" in g)
        for name in PROFILES:
            call = json.dumps({"skill": f"style-standards:{name}"})
            assert bool(re.search(pattern, call)) is (name == case.standard)


def test_a_review_is_graded_on_its_rule_and_a_migration_on_its_row(
    suite: Suite,
) -> None:
    for case in suite.cases:
        held = graders(case)
        if case.kind == REVIEW:
            assert unquoted(held["cites-rule"]["pattern"]) == case.slug.upper()
        if case.kind == MIGRATION:
            assert held["target-spelling"]["type"] == "regex"
            assert held["cites-rule"]["type"] == "regex"


def test_no_grader_seeks_what_its_own_prompt_holds(suite: Suite) -> None:
    """A reply quoting its prompt passes no grader on that alone."""
    for case in suite.cases:
        prompt = case.files[f"{case.directory}/prompt.md"]
        body = prompt.split("---\n", 2)[2]
        for name, held in graders(case).items():
            if held["type"] == "regex":
                assert not re.search(unquoted(held["pattern"]), body), (case.name, name)


def test_the_negative_prompt_is_the_first_review_of_another_language(
    suite: Suite, skills: list[Skill]
) -> None:
    language = {s.name: s.profile.all_marked[0] for s in skills}
    first_review = {}
    for case in suite.cases:
        if case.kind == REVIEW:
            first_review.setdefault(case.standard, case)
    for case in suite.cases:
        if case.kind != NEGATIVE:
            continue
        other = next(
            s.name for s in skills if language[s.name] != language[case.standard]
        )
        assert case.slug == other
        assert fence(case).info != language[case.standard]
        assert case.prompt == first_review[other].prompt


def test_a_rust_standard_and_its_delta_take_no_negative_from_each_other(
    suite: Suite,
) -> None:
    sources = {c.standard: c.slug for c in suite.cases if c.kind == NEGATIVE}
    assert sources == {
        "bevy-style": "python-style",
        "python-style": "bevy-style",
        "rust-style": "python-style",
        "zig-style": "bevy-style",
    }


def test_a_review_prompt_sends_the_example_without_its_marker(
    suite: Suite, skills: list[Skill]
) -> None:
    by_name = {s.name: s for s in skills}
    for case in suite.cases:
        if case.kind != REVIEW:
            continue
        code = fence(case).body
        assert "verified — BAD" not in code
        skill = by_name[case.standard]
        assert any(
            code.strip("\n") in b.body
            for b in skill.blocks(fence(case).info)
            if b.marker.bad and str(b.rule).lower() == case.slug
        ), case.name


# ------------------------------------------------------------------
# the literals a grader seeks

#: Each character `RegExp` reads as syntax, the spec's example, and
#: what the shipped selections seek.
LITERALS = (
    "Query::single()",
    r"a\b^c$d.e|f?g*h+i(j)k[l]m{n}o/p",
    "#[unsafe(no_mangle)]",
    "r#gen",
    "co_lines()",
    "__spec__.cached",
    "PS-MIG-04",
    "x-y",
)


def sought(suite: Suite) -> list[str]:
    """Each literal a grader of the suite seeks, read back from it."""
    out = []
    for case in suite.cases:
        for g in case.graders:
            held = dict(g.fields)
            if held["type"] == "regex":
                pattern = unquoted(held["pattern"])
                text = re.sub(r"\\(.)", r"\1", pattern)
                assert literal(text) == pattern
                out.append(text)
    return out


def perturbed(text: str) -> list[str]:
    """`text` with each character in turn replaced, then removed."""
    swapped = [
        text[:i] + ("x" if c != "x" else "y") + text[i + 1 :]
        for i, c in enumerate(text)
    ]
    return swapped + [text[:i] + text[i + 1 :] for i in range(len(text))]


def test_a_metacharacter_in_a_literal_is_matched_as_itself() -> None:
    assert literal("Query::single()") == r"Query::single\(\)"
    assert literal("x-y") == "x-y"


def test_each_literal_finds_itself_and_no_perturbation_of_it(suite: Suite) -> None:
    for text in (*LITERALS, *sought(suite)):
        pattern = re.compile(literal(text))
        assert pattern.search(text), text
        assert not [p for p in perturbed(text) if pattern.search(p)], text


@pytest.mark.skipif(not have("node"), reason="`node` is not on PATH")
def test_each_literal_means_the_same_to_javascript(suite: Suite) -> None:
    """The command compiles a pattern as `new RegExp(pattern)` does."""
    cases = [
        {"pattern": literal(t), "text": t, "others": perturbed(t)}
        for t in (*LITERALS, *sought(suite))
    ]
    script = (
        "const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        "const wrong = cases.filter(c => { const r = new RegExp(c.pattern);"
        " return !r.test(c.text) || c.others.some(o => r.test(o)); });"
        "process.stdout.write(JSON.stringify(wrong.map(c => c.text)));"
    )
    ran = run(["node", "-e", script], stdin=json.dumps(cases), timeout=60)
    assert ran.ok, ran.err
    assert json.loads(ran.out) == []


@pytest.mark.skipif(not have("node"), reason="`node` is not on PATH")
def test_each_skill_pattern_means_the_same_to_javascript(suite: Suite) -> None:
    patterns = sorted(
        {
            unquoted(dict(g.fields)["input_match"])
            for case in suite.cases
            for g in case.graders
            if dict(g.fields)["type"] == "tool_used"
        }
    )
    calls = [json.dumps({"skill": f"style-standards:{n}"}) for n in PROFILES]
    script = (
        "const [patterns, calls] = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        "process.stdout.write(JSON.stringify(patterns.map(p =>"
        " calls.map(c => new RegExp(p).test(c)))));"
    )
    ran = run(["node", "-e", script], stdin=json.dumps([patterns, calls]), timeout=60)
    assert ran.ok, ran.err
    found = json.loads(ran.out)
    named = [[bool(re.search(p, c)) for c in calls] for p in patterns]
    assert found == named
    assert all(row.count(True) == 1 for row in found)


@pytest.mark.parametrize(
    ("cell", "code"),
    [
        ("`new_name`", "new_name"),
        ("`glob.glob()` with `root_dir=`", "glob.glob()"),
        ("``a ` b`` and more", "a ` b"),
        ("` x `", "x"),
        ("`  `", None),
        ("returns an error", None),
        ("`unclosed", None),
    ],
)
def test_the_code_span_a_cell_opens_with(cell: str, code: str | None) -> None:
    assert opening_span(cell) == code


# ------------------------------------------------------------------
# writing the suite, and the check


def test_writing_twice_writes_nothing_the_second_time(scratch: Path) -> None:
    root = root_of(scratch)
    tree = Tree.of(discover(scratch))
    first = generate(tree)
    assert generate(tree).files == first.files
    stale = root / EVALS / "python-style" / "review-gone" / "prompt.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("by hand\n")
    kept = root / RESULTS / "2026-11-07" / "report.html"
    kept.parent.mkdir(parents=True)
    kept.write_text("<p>a run</p>\n")
    (root / EVALS / "zig-style" / "migration-std-gpu" / "prompt.md").unlink()
    written, removed = write(root, first)
    assert written == ["zig-style/migration-std-gpu/prompt.md"]
    assert removed == ["python-style/review-gone/prompt.md"]
    assert not stale.parent.exists()
    assert kept.is_file()
    assert write(root, first) == ([], [])
    assert compare(root, first) == ([], [])
    assert on_disk(root) == list(first.files)


def test_the_command_writes_the_suite_and_says_so(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case = root_of(scratch) / EVALS / "rust-style" / "migration-gen" / "prompt.md"
    case.write_text("edited\n")
    assert cli.main(["--skills", str(scratch), "evals"]) == 0
    assert (
        f"write   {EVALS}/rust-style/migration-gen/prompt.md" in capsys.readouterr().out
    )
    assert cli.main(["--skills", str(scratch), "evals"]) == 0
    assert "already as generated" in capsys.readouterr().out


def test_the_command_writes_nothing_for_a_refused_selection(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    migration = scratch / "rust-style" / "references" / "migration.md"
    text = migration.read_text()
    migration.write_text(
        text.replace("| `gen` | `r#gen` where", "| `gen` | r#gen where")
    )
    before = {p: p.read_text() for p in (root_of(scratch) / EVALS).rglob("*.md")}
    assert cli.main(["--skills", str(scratch), "evals"]) == 1
    assert "opens with no code span" in capsys.readouterr().out
    assert {
        p: p.read_text() for p in (root_of(scratch) / EVALS).rglob("*.md")
    } == before


def test_the_command_needs_a_repository(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir()
    assert cli.main(["--skills", str(tmp_path / "skills"), "evals"]) == 2


def test_a_refused_selection_leaves_the_suite_uncompared_where_every_run_sees_it(
    scratch: Path,
) -> None:
    tree = Tree.of(
        Skill(
            s.root,
            replace(s.profile, evals=Evals(review=listed("RS-OUT-02")))
            if s.name == "python-style"
            else None,
        )
        for s in discover(scratch)
    )
    found = list(check.evals(tree))
    assert [(f.level, f.branch, f.where.skill) for f in found] == [
        (Level.FAIL, check.UNKNOWN_RULE, "python-style"),
        (Level.UNRUN, check.UNCOMPARED, None),
    ]


def test_a_standard_selecting_nothing_has_no_case(scratch: Path) -> None:
    tree = Tree.of(
        Skill(s.root, replace(s.profile, evals=None)) for s in discover(scratch)
    )
    assert generate(tree) == Suite((), ())


def test_the_demo_alone_has_no_negative_case(tmp_path: Path) -> None:
    demo.build(tmp_path)
    suite = generate(Tree.of([Skill(tmp_path / DEMO.name, DEMO)]))
    assert [c.kind for c in suite.cases] == [REVIEW, MIGRATION]
    assert [dict(g.fields)["pattern"] for g in suite.cases[1].graders[:2]] == [
        "'new_name'",
        "'DS-MIG-01'",
    ]


# ------------------------------------------------------------------
# what ships, and what does not


def test_a_package_holds_no_part_of_the_suite(
    tmp_path: Path, skills: list[Skill]
) -> None:
    for skill in skills:
        for archive in build.package(skill, tmp_path):
            with zipfile.ZipFile(archive) as package:
                names = package.namelist()
            assert not [n for n in names if "evals" in Path(n).parts]
    assert all(not s.root.is_relative_to(REPO / EVALS) for s in skills)
    assert (REPO / SKILLS).parent == (REPO / EVALS).parent


def test_a_runs_results_are_ignored_by_git() -> None:
    ignored = (REPO / ".gitignore").read_text().split("\n")
    assert f"{RESULTS.as_posix()}/" in ignored
