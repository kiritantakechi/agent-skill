"""`agent-skill` itself: what it refuses, and what each check reads."""

import re
lazy from collections.abc import Iterator
lazy from pathlib import Path

import pytest

from agent_skill import cli
from agent_skill.checks import Check, per_skill
from agent_skill.ids import Branch, Location
from agent_skill.layout import SKILLS
from agent_skill.model import Skill, Tree
from agent_skill.report import note
from structure_fixture import build
lazy from agent_skill.report import Finding


def help_text(capsys: pytest.CaptureFixture[str], *argv: str) -> str:
    with pytest.raises(SystemExit, match=r"^0$"):
        cli.main([*argv, "--help"])
    return " ".join(capsys.readouterr().out.split())


def test_the_description_names_every_subcommand(
    capsys: pytest.CaptureFixture[str],
) -> None:
    usage = help_text(capsys)
    commands = re.search(r"\{([a-z,]+)\}", usage)
    assert commands is not None
    for command in commands.group(1).split(","):
        assert re.search(rf"\b{command}\b", cli.DESCRIPTION), command


def test_every_option_and_rewrite_is_described(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert "directory the packages are written to" in help_text(capsys, "build")
    rewrites = help_text(capsys, "fmt")
    assert "shared passage from its template" in rewrites
    assert "prose to the line limit" in rewrites


def test_an_unknown_check_is_refused_not_passed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["check", "--only", "no-such-check"]) == 2
    out, err = capsys.readouterr()
    assert "ALL CHECKS PASSED" not in out
    assert "no-such-check" in err
    assert "anatomy" in err


@pytest.mark.parametrize("command", ["check", "fmt"])
def test_an_unknown_skill_is_refused_with_the_names_there_are(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main([command, "--skill", "no-such-style"]) == 2
    err = capsys.readouterr().err
    assert "no-such-style" in err
    assert "python-style" in err


#: The branch the stand-in checks below report through.
SAID = Branch("x", "said")


def test_skill_chooses_findings_and_never_what_a_check_reads(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A cross-skill check reads every skill; one skill's findings show.

    A per-skill check reads only the skill chosen, which drops nothing:
    each finding it makes lies in the skill it is reading.
    """
    given: dict[str, list[str]] = {}

    def across(tree: Tree) -> Iterator[Finding]:
        given["across"] = [s.name for s in tree]
        for s in tree:
            yield note(f"across read {s.name}", Location(s.name), SAID)
        yield note("across read the repository", Location(file="README.md"), SAID)

    def each(skill: Skill) -> Iterator[Finding]:
        given.setdefault("each", []).append(skill.name)
        yield note(f"each read {skill.name}", skill.at(), SAID)

    fakes = [Check("across", "x", across), Check("each", "x", per_skill(each))]
    monkeypatch.setattr(cli, "all_checks", lambda: fakes)

    assert cli.main(["check", "--verbose", "--skill", "bevy-style"]) == 0
    assert given["each"] == ["bevy-style"]
    assert given["across"] == ["bevy-style", "python-style", "rust-style", "zig-style"]
    shown = re.findall(r"note  (.*)", capsys.readouterr().out)
    assert shown == [
        "bevy-style: across read bevy-style",
        "./README.md: across read the repository",
        "bevy-style: each read bevy-style",
    ]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository of one demo standard, apart from this checkout."""
    build(tmp_path / SKILLS)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    return tmp_path


def snapshot(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_demote_closes_its_own_gap_so_renumber_has_nothing_left(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both are `revise`: one with a plan, one without."""
    skills = str(repo / SKILLS)
    plan = repo / "plan.json"
    plan.write_text('{"DS-ERR-01": {"remove": "said nothing"}}')

    assert cli.main(["--skills", skills, "demote", "demo-style", str(plan)]) == 0
    out = capsys.readouterr().out
    assert "revise  DS-ERR-01 -> removed — said nothing" in out
    assert f"write   {SKILLS}/demo-style/references/errors.md" in out
    assert f"write   {SKILLS}/demo-style/references/renames.md" in out
    assert cli.main(["--skills", skills, "renumber", "demo-style"]) == 0
    assert capsys.readouterr().out.startswith("nothing to revise")

    after = Skill(repo / SKILLS / "demo-style")
    assert [r.id for r in after.rules] == ["DS-ERR-01", "DS-MIG-01"]
    assert after.by_id["DS-ERR-01"].title == "Name them"


def test_revise_takes_a_plan_and_chapter_renames_at_once(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skills = str(repo / SKILLS)
    plan = repo / "plan.json"
    plan.write_text('{"DS-ERR-01": {"merge": "DS-ERR-02"}}')
    argv = ["--skills", skills, "revise", "demo-style", str(plan)]

    assert cli.main([*argv, "--chapters", "errors=api"]) == 0

    out = capsys.readouterr().out
    assert "revise  DS-ERR-01 -> `DS-API-01`" in out
    assert "move    " in out
    after = Skill(repo / SKILLS / "demo-style")
    assert [r.id for r in after.rules] == ["DS-API-01", "DS-MIG-01"]


#: A demotion whose plan file is not there.
NO_PLAN = "<no plan file>"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["renumber", "no-such-style"], "nothing is called no-such-style"),
        (["revise", "no-such-style"], "nothing is called no-such-style"),
        (["revise", "demo-style", '{"DS-ERR-01": {"merge": "x"}}'], "a merge names"),
        (["demote", "no-such-style", "{}"], "nothing is called no-such-style"),
        (["demote", "demo-style", NO_PLAN], "No such file"),
        (["demote", "demo-style", "{"], "Expecting"),
        (["demote", "demo-style", '{"DS-ERR-01": "remove"}'], "exactly one"),
        (["demote", "demo-style", "{}"], "naming at least one rule"),
        (["demote", "demo-style", "[]"], "naming at least one rule"),
        (["demote", "demo-style", '{"DS-ERR-01": {"rows": "x"}}'], "rows are"),
        (["demote", "demo-style", '{"DS-ERR-01": {"lint": ["x"]}}'], "a lint is"),
        (["demote", "demo-style", '{"DS-ERR-01": {"merge": 1}}'], "a merge names"),
    ],
)
def test_a_command_that_cannot_start_says_why_and_exits_2(
    repo: Path, argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A demotion's third word is the plan file's text."""
    args = list(argv)
    if args[0] in {"demote", "revise"} and len(args) > 2:
        plan = repo / "plan.json"
        if args[2] != NO_PLAN:
            plan.write_text(args[2])
        args[2] = str(plan)
    before = snapshot(repo)
    assert cli.main(["--skills", str(repo / SKILLS), *args, "--dry-run"]) == 2
    assert message in capsys.readouterr().err
    assert snapshot(repo) == before


def test_a_skills_directory_that_is_not_there_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--skills", str(tmp_path / "nowhere"), "list"]) == 2
    assert "is not a directory" in capsys.readouterr().err


def test_a_skills_directory_outside_a_repository_has_nothing_to_renumber(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    build(tmp_path)
    assert cli.main(["--skills", str(tmp_path), "renumber", "demo-style"]) == 2
    assert "no repository" in capsys.readouterr().err


def test_fmt_that_leaves_a_passage_unrewritten_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    demo = build(tmp_path)
    skill_md = demo.skill_md
    skill_md.write_text(
        skill_md.read_text().replace(
            "Rules are cited by ID", "An aside.\n\nRules are cited by ID", 1
        )
    )
    assert cli.main(["--skills", str(tmp_path), "fmt"]) == 1
    assert re.search(
        r"FAIL  demo-style/SKILL\.md:\d+: text outside a free region",
        capsys.readouterr().out,
    )


def test_build_that_cannot_package_a_skill_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    taken = tmp_path / "taken"
    taken.write_text("a file where the output directory would go")
    assert cli.main(["build", "--out", str(taken)]) == 1
    assert "not packaged" in capsys.readouterr().err


def test_a_chapter_rename_without_its_new_name_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match=r"^2$"):
        cli.main(["renumber", "--chapters", "errors", "python-style", "--dry-run"])
    assert "is not OLD=NEW" in capsys.readouterr().err
