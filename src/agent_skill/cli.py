"""The `agent-skill` command line.

It checks, packages, installs, formats, renumbers and demotes the
skills in this repository. `--help` prints `DESCRIPTION`, not this
docstring, so rewrapping one never rewords the other.
"""

import argparse
import json
import sys
from pathlib import Path
lazy from collections.abc import Callable

from agent_skill import build
from agent_skill.checks import all_checks
from agent_skill.fmt import format_skill
from agent_skill.model import discover
from agent_skill.report import Level, Result
lazy from agent_skill import demote, renumber

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS = REPO / "skills"

#: What `--help` says the command is for.
DESCRIPTION = (
    "`agent-skill` — check, package, and install the skills in this repository."
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


def cmd_check(args: argparse.Namespace) -> int:
    """Run the checks, print their findings, and say whether all passed.

    Exit 1 when any check failed or could not run, and 2 when there is
    nothing to check.
    """
    skills = discover(args.skills)
    if args.skill:
        skills = [s for s in skills if s.name in args.skill]
    if not skills:
        print(f"no skills under {args.skills}", file=sys.stderr)
        return 2

    print(f"== {', '.join(s.name for s in skills)} ==")
    failed = False
    results: list[Result] = []
    for c in all_checks():
        if args.only and c.name not in args.only:
            continue
        if args.fast and c.slow:
            continue
        result = c.run(skills, fast=args.fast)
        results.append(result)
        _emit(result, verbose=args.verbose)
        failed |= not result.ok
    print()
    print("SOME CHECKS FAILED" if failed else "ALL CHECKS PASSED")
    if failed and not any(r.fails for r in results):
        print("(nothing failed; something could not be run)")
    return 1 if failed else 0


def cmd_build(args: argparse.Namespace) -> int:
    """Package every skill as `<name>.skill`, and print each path."""
    for skill in discover(args.skills):
        target = build.package(skill, args.out)
        print(
            f"  {target.relative_to(REPO) if args.out.is_relative_to(REPO) else target}"
        )
    return 0


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
    """Format each skill in place, and print what changed."""
    for skill in discover(args.skills):
        if args.skill and skill.name not in args.skill:
            continue
        lines = format_skill(skill)
        print(f"  {skill.name}")
        for line in lines or ["already formatted"]:
            print(f"      {line}")
    return 0


def cmd_renumber(args: argparse.Namespace) -> int:
    """Print the renumbering plan, and carry it out unless `--dry-run`.

    Exit 1, having written nothing, when the plan cannot be made.
    """
    chapters = dict(pair.split("=", 1) for pair in args.chapters or [])
    try:
        plan = renumber.plan(REPO, args.skill, chapters)
    except renumber.RenumberError as e:
        print(f"renumber: {e}", file=sys.stderr)
        print("nothing was written", file=sys.stderr)
        return 1
    for old, new in plan.moves.items():
        print(f"  move    {old.relative_to(REPO)} -> {new.name}")
    print(f"  ids     {plan.changed} of {len(plan.ids)} renumbered")
    for path in sorted(plan.writes):
        print(f"  write   {path.relative_to(REPO)}")
    for line in plan.leftovers:
        print(f"  look    {line}")
    if args.dry_run:
        print("dry run: nothing was written")
        return 0
    renumber.apply(REPO, plan)
    return 0


def cmd_demote(args: argparse.Namespace) -> int:
    """Print the demotion plan, and carry it out unless `--dry-run`.

    Exit 1, having written nothing, when the plan cannot be made.
    """
    try:
        demotion = demote.plan(REPO, args.skill, json.loads(args.plan.read_text()))
    except demote.DemoteError as e:
        print(f"demote: {e}", file=sys.stderr)
        print("nothing was written", file=sys.stderr)
        return 1
    for rid, becomes in demotion.dispositions.items():
        print(f"  demote  {rid} -> {becomes}")
    for path in sorted(demotion.writes):
        print(f"  write   {path.relative_to(REPO)}")
    for line in demotion.leftovers:
        print(f"  look    {line}")
    if args.dry_run:
        print("dry run: nothing was written")
        return 0
    demote.apply(demotion)
    print(f"next: `agent-skill renumber {args.skill}` closes the gaps")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Print each skill's prefix, counts, and toolchain."""
    for skill in discover(args.skills):
        rules = len(skill.rules)
        blocks = len(skill.blocks(verified=True))
        print(
            f"  {skill.name:<12} prefix={skill.prefix}  {rules} rules  "
            f"{blocks} verified blocks  toolchain={skill.profile.toolchain}"
        )
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
    pack.add_argument("--out", type=Path, default=REPO / "dist")
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
    fmt = sub.add_parser(
        "fmt", help="rewrite each verified example as its formatter would have it"
    )
    fmt.add_argument("--skill", action="append", help="limit to one skill (repeatable)")
    fmt.set_defaults(func=cmd_fmt)
    num = sub.add_parser(
        "renumber",
        help="rename chapters, renumber rules densely, rewrite every citation",
    )
    num.add_argument("skill", help="the skill to renumber")
    num.add_argument(
        "--chapters",
        action="append",
        metavar="OLD=NEW",
        help="rename a chapter (repeatable)",
    )
    num.add_argument(
        "--dry-run", action="store_true", help="show the plan and write nothing"
    )
    num.set_defaults(func=cmd_renumber)
    dem = sub.add_parser(
        "demote",
        help="turn rules into lint-table rows, merges or removals, and record each",
    )
    dem.add_argument("skill", help="the skill whose rules are demoted")
    dem.add_argument(
        "plan", type=Path, help="JSON: rule ID -> rows, lint, merge or remove"
    )
    dem.add_argument(
        "--dry-run", action="store_true", help="show the plan and write nothing"
    )
    dem.set_defaults(func=cmd_demote)
    sub.add_parser("list", help="what is in this repository").set_defaults(
        func=cmd_list
    )

    args = parser.parse_args(argv, namespace=_Parsed())
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
