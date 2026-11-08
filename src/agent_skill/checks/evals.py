"""The eval suite on disk, against what the standards generate.

The suite `claude plugin eval` runs is written by `agent-skill evals`
from the standards and each profile's selection, so a case cannot test
a rule as it once read. Written once and then edited, or left behind
when the rule it tests is rewritten, it would test what nobody wrote
and pass or fail on that. So the directory is compared with its
generation, file by file, and a selection that names nothing a case can
be built from fails where it is made.

Nothing here runs the suite: each run is a model session on the
owner's credential, and the README gives the command.
"""

lazy from collections.abc import Iterator

from agent_skill.checks import check
from agent_skill.evals import Invalid, compare, generate
from agent_skill.ids import Location
from agent_skill.layout import EVALS, in_repository, root_of
from agent_skill.report import Level, declare, fail, unrun
lazy from agent_skill.model import Tree
lazy from agent_skill.report import Finding

# The branches a finding of this check comes from: one for each reason
# a selection is refused, then the two ways the directory can differ
# from its generation.
UNKNOWN_RULE = declare("evals", "unknown_rule", Level.FAIL)
NO_BAD = declare("evals", "no_bad", Level.FAIL)
BAD_CITES = declare("evals", "bad_cites", Level.FAIL)
NOT_GONE = declare("evals", "not_gone", Level.FAIL)
SHAPE = declare("evals", "shape", Level.FAIL)
NO_CODE_SPAN = declare("evals", "no_code_span", Level.FAIL)
DRIFT = declare("evals", "drift", Level.FAIL)
EXTRA = declare("evals", "extra", Level.FAIL)
UNCOMPARED = declare("evals", "uncompared", Level.UNRUN)

#: The branch each refusal reports through.
REFUSED = {
    Invalid.UNKNOWN_RULE: UNKNOWN_RULE,
    Invalid.NO_BAD: NO_BAD,
    Invalid.BAD_CITES: BAD_CITES,
    Invalid.NOT_GONE: NOT_GONE,
    Invalid.SHAPE: SHAPE,
    Invalid.NO_CODE_SPAN: NO_CODE_SPAN,
}


@check("evals", "the eval suite under the plugin, against what the standards generate")
def evals(tree: Tree) -> Iterator[Finding]:
    """Each refused selection, then each file that is not as generated.

    A refused selection leaves the suite undefined, so nothing is
    compared, and that is said where every run shows it: a run choosing
    other skills would otherwise read the comparison as done.
    """
    suite = generate(tree)
    for refused in suite.refused:
        yield fail(refused.message, refused.where, REFUSED[refused.why])
    if not tree.skills or not in_repository(skills := tree.skills[0].root.parent):
        return
    where = Location(file=EVALS.as_posix())
    if suite.refused:
        yield unrun(
            "the suite was not compared with its generation, which a refused "
            "selection leaves undefined",
            where,
            UNCOMPARED,
        )
        return
    drifted, extra = compare(root_of(skills), suite)
    for rel in drifted:
        yield fail(
            "is missing or differs from what the standards generate; "
            "`agent-skill evals` writes it",
            Location(file=(EVALS / rel).as_posix()),
            DRIFT,
        )
    for rel in extra:
        yield fail(
            "is no file of the generated suite, so it tests what no standard says; "
            "`agent-skill evals` removes it",
            Location(file=(EVALS / rel).as_posix()),
            EXTRA,
        )
