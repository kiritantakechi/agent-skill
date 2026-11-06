"""The `agent-skill` command line.

It checks, packages, installs, formats and revises the skills in this
repository. `--help` prints `DESCRIPTION`, not this
docstring, so rewrapping one never rewords the other.
"""

import argparse
import json
import sys
from pathlib import Path
lazy from collections.abc import Callable

from agent_skill import build
from agent_skill.checks import all_checks
from agent_skill.doc.chapter import print_becomes
from agent_skill.fmt import format_skill
from agent_skill.ids import RuleId
from agent_skill.lang import toolchain_for
from agent_skill.layout import SKILLS, root_of
from agent_skill.model import Skill, Tree, discover
from agent_skill.report import Level, Result
lazy from agent_skill import revise
lazy from agent_skill.measure import table

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS = REPO / SKILLS

#: What `--help` says the command is for. It names every subcommand: it
#: named three of seven, and `fmt` and `revise`, with its aliases
#: `renumber` and `demote`, are the ones a person needs telling of.
DESCRIPTION = (
    "`agent-skill` — check the skills in this repository; fmt them; revise "
    "their rules, or renumber and demote, which are revise by other names; "
    "build them into packages, install them into each agent, list them, and "
    "measure how far each is from the normal form."
)


class _Parsed(argparse.Namespace):
    """The parsed command line, typed where `main` reads it."""

    #: the subcommand's handler, which `set_defaults` puts here
    func: Callable[[argparse.Namespace], int]


def _emit(result: Result, *, verbose: bool, limit: int = 25) -> None:
    """Print one check's verdict, its details, and its findings."""
    label = "ok  " if result.ok else ("FAIL" if result.fails else "????")
    print(f"  {label}  {result.name}")
    for detail in result.details:
        print(f"          {detail}")
    for level, items in (
        (Level.FAIL, result.fails),
        (Level.UNRUN, result.unrun),
        (Level.NOTE, result.notes),
    ):
        shown = items if verbose else items[:limit]
        for finding in shown:
            head, *rest = str(finding).split("\n")
            print(f"          {level.value}  {head}")
            for line in rest:
                print(f"          {line}")
        if len(items) > len(shown):
            print(
                f"          …     {len(items) - len(shown)} more "
                f"{level.value} (--verbose)"
            )


def _unknown(flag: str, asked: list[str] | None, known: list[str]) -> str:
    """The complaint about each name in `asked` that `known` lacks.

    "" when every name is known. A name that matches nothing used to
    select nothing, and nothing selected passes: `--only no-such-check`
    printed ALL CHECKS PASSED.
    """
    missing = sorted(set(asked or ()) - set(known))
    if not missing:
        return ""
    return (
        f"{flag}: nothing is called {', '.join(missing)}; "
        f"the names are {', '.join(sorted(known))}"
    )


def cmd_check(args: argparse.Namespace) -> int:
    """Run the checks, print their findings, and say whether all passed.

    Exit 1 when any check failed or could not run, and 2 when there is
    nothing to check or a name asked for matches nothing.

    `--skill` chooses findings, not what a check reads: every check runs
    over the whole tree, and what is shown is what lies in a chosen
    skill or in none. Narrowing the input instead left a cross-skill
    check without its siblings: given one skill, `crossref` had no
    anchor to check a delta against and passed, and `plugin` failed
    because the plugin ships four.
    """
    tree = Tree.of(discover(args.skills))
    checks = all_checks()
    complaint = _unknown("--skill", args.skill, [s.name for s in tree]) or _unknown(
        "--only", args.only, [c.name for c in checks]
    )
    if complaint:
        print(complaint, file=sys.stderr)
        return 2
    if not tree.skills:
        print(f"no skills under {args.skills}", file=sys.stderr)
        return 2
    chosen = args.skill or [s.name for s in tree]

    print(f"== {', '.join(s.name for s in tree.only(chosen))} ==")
    failed = False
    results: list[Result] = []
    for c in checks:
        if args.only and c.name not in args.only:
            continue
        if args.fast and c.slow:
            continue
        result = c.run(tree, about=chosen, fast=args.fast).within(chosen)
        results.append(result)
        _emit(result, verbose=args.verbose)
        failed |= not result.ok
    print()
    print("SOME CHECKS FAILED" if failed else "ALL CHECKS PASSED")
    if failed and not any(r.fails for r in results):
        print("(nothing failed; something could not be run)")
    return 1 if failed else 0


def cmd_build(args: argparse.Namespace) -> int:
    """Package every skill as `<name>.skill`, and print each path.

    Exit 1 when any skill could not be packaged.
    """
    failed = False
    for skill in discover(args.skills):
        try:
            target = build.package(skill, args.out)
        except OSError as e:
            print(f"  {skill.name}: not packaged — {e}", file=sys.stderr)
            failed = True
            continue
        print(
            f"  {target.relative_to(REPO) if args.out.is_relative_to(REPO) else target}"
        )
    return 1 if failed else 0


def cmd_install(args: argparse.Namespace) -> int:
    """Link every skill into each agent this machine has installed."""
    targets = [t for t in build.TARGETS if not args.target or t.name in args.target]
    skills = discover(args.skills)
    for target in targets:
        if not target.present:
            print(f"  {target.name:<12} not installed on this machine; skipped")
            continue
        print(f"  {target.name}")
        for skill in skills:
            link, how = build.install(skill, target)
            print(f"      {link}  ({how})")
    return 0


def cmd_fmt(args: argparse.Namespace) -> int:
    """Format each skill in place, and print what changed.

    Exit 1 when anything could not be rewritten — a formatter failed, or
    a block or passage was skipped — and 2 when a `--skill` asked for is
    not there.
    """
    skills = discover(args.skills)
    if complaint := _unknown("--skill", args.skill, [s.name for s in skills]):
        print(complaint, file=sys.stderr)
        return 2
    failed = False
    for skill in skills:
        if args.skill and skill.name not in args.skill:
            continue
        findings = format_skill(skill)
        print(f"  {skill.name}")
        for finding in findings:
            label = "FAIL  " if finding.level is Level.FAIL else ""
            print(f"      {label}{finding}")
        if not findings:
            print("      already formatted")
        failed |= any(f.level is Level.FAIL for f in findings)
    return 1 if failed else 0


def _chapter_rename(pair: str) -> tuple[str, str]:
    """`OLD=NEW` as the pair it names.

    Anything else is a usage error, which argparse reports.
    """
    old, sep, new = pair.partition("=")
    if not (old and sep and new):
        msg = f"{pair!r} is not OLD=NEW"
        raise argparse.ArgumentTypeError(msg)
    return old, new


def _repo_for(command: str, args: argparse.Namespace) -> Path | None:
    """The repository whose skill `args.skill` names, or None.

    None, having said why, when `--skills` is not a repository's skills
    directory or holds no such skill. A rewrite reaches the repository's
    `src/`, `tests/` and README as well as its skills, so it needs the
    root `--skills` sits in; it used to rewrite this checkout whatever
    `--skills` said.
    """
    skills = args.skills.resolve()
    if len(skills.parts) <= len(SKILLS.parts) or root_of(skills) / SKILLS != skills:
        print(
            f"{command}: {args.skills} is not a repository's `{SKILLS}`, "
            "so there is no repository to rewrite citations in",
            file=sys.stderr,
        )
        return None
    if complaint := _unknown("skill", [args.skill], [s.name for s in discover(skills)]):
        print(f"{command}: {complaint}", file=sys.stderr)
        return None
    return root_of(skills)


def _plan(command: str, args: argparse.Namespace, skill: Skill) -> revise.Plan | None:
    """The plan `args.plan` states, empty if there is none.

    None, having said why, when the file is not there or is not a plan.
    """
    if args.plan is None:
        return dict[RuleId, revise.Becomes]()
    try:
        return revise.read_plan(json.loads(args.plan.read_text()), skill)
    except (OSError, ValueError, revise.PlanError) as e:
        print(f"{command}: {args.plan}: {e}", file=sys.stderr)
        return None


def _show(repo: Path, plan: revise.Plan, revision: revise.Revision) -> None:
    """What a revision moves, renames, writes and leaves to a person."""
    for old, new in revision.moves.items():
        print(f"  move    {old.relative_to(repo)} -> {new.name}")
    for rid in plan:
        print(f"  revise  {rid} -> {print_becomes(revision.renamed[rid])}")
    print(f"  ids     {len(revision.renamed)} of {revision.rules} changed")
    for path in sorted(revision.writes):
        print(f"  write   {path.relative_to(repo)}")
    for line in revision.leftovers:
        print(f"  look    {line}")


def cmd_revise(args: argparse.Namespace) -> int:
    """Print what the revision does, and do it unless `--dry-run`.

    `renumber` is this with no plan, and `demote` this with one: a plan
    now closes its own gaps, so neither leaves the other a step to do.
    Exit 1, having written nothing, when the revision cannot be done,
    and 2 when there is no such skill or the plan file is not a plan.
    """
    command = str(args.command)
    repo = _repo_for(command, args)
    if repo is None:
        return 2
    skill = Skill(repo / SKILLS / args.skill)
    plan = _plan(command, args, skill)
    if plan is None:
        return 2
    try:
        revision = revise.revise(Tree.of([skill]), plan, dict(args.chapters or []))
    except revise.ReviseError as e:
        print(f"{command}: {e}", file=sys.stderr)
        print("nothing was written", file=sys.stderr)
        return 1
    if revision.empty:
        print("nothing to revise: the plan is empty and every family is dense")
        return 0
    _show(repo, plan, revision)
    if args.dry_run:
        print("dry run: nothing was written")
        return 0
    revision.apply()
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Print each skill's prefix, counts, and toolchain."""
    for skill in discover(args.skills):
        rules = len(skill.chapter_rules)
        blocks = len(skill.blocks(verified=True))
        toolchain = toolchain_for(skill.profile.toolchain)
        print(
            f"  {skill.name:<12} prefix={skill.prefix}  {rules} rules  "
            f"{blocks} verified blocks  toolchain={toolchain.name if toolchain else ''}"
        )
    return 0


def cmd_measure(args: argparse.Namespace) -> int:
    """Print how far each standard is from the normal form."""
    print(table(discover(args.skills)))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the subcommand `argv` names and return its exit status.

    `argv` defaults to the process's own arguments.
    """
    parser = argparse.ArgumentParser(prog="agent-skill", description=DESCRIPTION)
    parser.add_argument(
        "--skills",
        type=Path,
        default=DEFAULT_SKILLS,
        help="directory holding the skills",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="run every check")
    check.add_argument(
        "--skill", action="append", help="limit to one skill (repeatable)"
    )
    check.add_argument(
        "--only", action="append", help="limit to one check (repeatable)"
    )
    check.add_argument(
        "--fast", action="store_true", help="skip the checks that need a compiler"
    )
    check.add_argument(
        "--verbose", "-v", action="store_true", help="do not truncate findings"
    )
    check.set_defaults(func=cmd_check)

    pack = sub.add_parser("build", help="package each skill as <name>.skill")
    pack.add_argument(
        "--out",
        type=Path,
        default=REPO / "dist",
        help="directory the packages are written to (default: dist/)",
    )
    pack.set_defaults(func=cmd_build)

    put = sub.add_parser(
        "install", help="symlink each skill into every agent that reads skills"
    )
    put.add_argument(
        "--target",
        action="append",
        choices=[t.name for t in build.TARGETS],
        help="limit to one agent (repeatable); default is every one present",
    )
    put.set_defaults(func=cmd_install)
    rewrites = (
        "rewrite each verified example as its formatter would have it, each "
        "shared passage from its template, and prose to the line limit"
    )
    fmt = sub.add_parser("fmt", help=rewrites, description=rewrites)
    fmt.add_argument("--skill", action="append", help="limit to one skill (repeatable)")
    fmt.set_defaults(func=cmd_fmt)
    revising = (
        ("revise", "merge, demote or remove rules, then renumber densely", True),
        ("renumber", "rename chapters, renumber rules densely", False),
        ("demote", "turn rules into lint-table rows, merges or removals", True),
    )
    for name, does, planned in revising:
        said = f"{does}, rewrite every citation, and record each old ID"
        cmd = sub.add_parser(name, help=said, description=said)
        cmd.add_argument("skill", help="the skill to revise")
        if planned:
            cmd.add_argument(
                "plan",
                type=Path,
                nargs="?" if name == "revise" else None,
                help="JSON: rule ID -> rows, lint, merge or remove",
            )
        cmd.add_argument(
            "--chapters",
            action="append",
            type=_chapter_rename,
            metavar="OLD=NEW",
            help="rename a chapter (repeatable)",
        )
        cmd.add_argument(
            "--dry-run", action="store_true", help="show the plan and write nothing"
        )
        cmd.set_defaults(func=cmd_revise, plan=None)
    sub.add_parser("list", help="what is in this repository").set_defaults(
        func=cmd_list
    )
    measured = "how far each standard is from the normal form, as a table"
    sub.add_parser("measure", help=measured, description=measured).set_defaults(
        func=cmd_measure
    )

    args = parser.parse_args(argv, namespace=_Parsed())
    if not args.skills.is_dir():
        print(f"--skills: {args.skills} is not a directory", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
