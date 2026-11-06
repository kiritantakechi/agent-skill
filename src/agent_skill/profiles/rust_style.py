"""rust-style: its own `[M]` rules, applied to its own examples."""

import re
lazy from collections.abc import Iterator

from agent_skill.ids import RuleId
from agent_skill.lang.rust import RUST_STYLE
from agent_skill.profiles.record import (
    LineRule,
    Near,
    NotDecisive,
    Profile,
    Unless,
    keyed,
    rules,
)
from agent_skill.report import Level, declare, note
lazy from agent_skill.model import Block
lazy from agent_skill.report import Finding

#: A doc comment inside an example explains the API, not the skill.
META = (
    r"\b(this example|this rule|the wrapper|as shipped|the block|"
    r"what makes .* testable|for the purposes of)\b"
)

#: The item a line belongs to is declared `#[repr(C)]`: one of the
#: thirteen lines above it says so, before the `}` that closes the item
#: above. Per line, not per block, so a block that mixes a
#: layout-sensitive type with an ordinary one still reports the
#: ordinary one.
REPR_C = Near(r"repr\(C\)", above=13, stop=r"^\s*\}", own=False)

# The branches of `conventions` this standard's own rules fire through.
BOOL_PARAMETER = declare("conventions", "rs_bool_parameter", Level.FAIL)
QUESTION_NAME = declare("conventions", "rs_question", Level.NOTE)
PUBLIC_FIELD = declare("conventions", "rs_public_field", Level.FAIL)
TUPLE_FIELD = declare("conventions", "rs_tuple_field", Level.FAIL)
SETTER = declare("conventions", "rs_setter", Level.FAIL)
META_DOC = declare("conventions", "rs_meta_doc", Level.FAIL)
UNUSED_DEFAULT = declare("conventions", "rs_unused_default", Level.NOTE)

CONVENTIONS = (
    # RS-API-19 — a public signature never takes a bare `bool`.
    LineRule(
        BOOL_PARAMETER,
        r"\bpub (?:async )?fn (\w+)\s*(?:<[^>]*>)?\((?=[^)]*:\s*bool\b)[^)]*\)",
        "`{1}` takes a bool parameter (RS-API-19)",
        unless_own=RuleId.parse("RS-API-19"),
    ),
    # RS-NAME-22 — a `bool`-returning method reads as a question.
    LineRule(
        QUESTION_NAME,
        r"\bpub (?:async )?fn "
        r"(?!is_|has_|can_|should_|may_|will_|wants_|allows_|accepts_|needs_|"
        r"contains|starts_with|ends_with|matches|intersects|all_|any_|"
        r"exceeds|fits|owns|holds|knows)"
        r"(\w+)\([^)]*\)\s*->\s*bool\b",
        "`{1}` returns bool but does not read as a question (RS-NAME-22)",
    ),
    # RS-API-15 — no public field, tuple fields included.
    LineRule(
        PUBLIC_FIELD,
        r"^\s+pub [a-z_]\w*:",
        "public struct field outside `#[repr(C)]` (RS-API-15)",
        comments=True,
        unless=Unless(near=(REPR_C,)),
    ),
    LineRule(TUPLE_FIELD, r"struct \w+\(\s*pub ", "public tuple field (RS-API-15)"),
    # House convention — a by-value setter is `with_*`: a method that
    # takes `self` by value, assigns a field in its first lines, and
    # returns `Self` without taking another `Self`.
    LineRule(
        SETTER,
        r"\bpub fn (?!with_|from_)(\w+)\((?:mut )?self"
        r"(?:,\s*(?![^)]*:\s*(?:&\s*)?Self\b)[^)]*)?\)\s*->\s*Self\b",
        "by-value setter `{1}` is not spelled `with_*`",
        needs=(Near(r"self\.\w+\s*=[^=]", below=7),),
    ),
    LineRule(
        META_DOC,
        rf"(?i)^\s*///.*{META}",
        "doc comment discusses the example rather than the API",
        comments=True,
    ),
)


def unused_defaults(b: Block) -> Iterator[Finding]:
    """A derived `Default` nobody can reach is dead weight.

    Read across the whole example rather than a line: whether anything
    reaches the derive is a fact about every other line of it.
    """
    for m in re.finditer(
        r"#\[derive\([^)]*\bDefault\b[^)]*\)\]\s*\n"
        r"(?:\s*#\[[^\]]*\]\s*\n)*\s*pub enum (\w+)",
        b.body,
    ):
        name = m.group(1)
        if not (
            re.search(rf":\s*(Option<)?{name}\b", b.body)
            or f"{name}::default()" in b.body
            or "..Default::default()" in b.body
            or f"<{name}>" in b.body
        ):
            yield note(
                f"`{name}` derives Default that nothing in the block uses",
                b.where,
                UNUSED_DEFAULT,
            )


PROFILE = Profile(
    name="rust-style",
    prefix="RS",
    languages=("rust",),
    marked_languages=("toml",),
    tools=("rustc", "clippy", "rustdoc"),
    language="Rust",
    verified_as="compiles as written against Rust {toolchain}, edition 2024",
    strict_scope="library and high-reliability",
    toolchain=RUST_STYLE,
    # Each snippet is the defect its rule forbids, written the way it
    # turns up in real code. A fixture shaped to match proves the
    # fixture, not the pattern.
    fires=keyed(
        {
            # A dependency the standard library replaced, one per
            # pattern.
            "RS-MIG-01": ('lazy_static = "1.5"', 'fd-lock = "4"'),
            # A grab-bag module, declared inline and from a file.
            "RS-NAME-05": ("pub mod utils;", "mod helpers {"),
            "RS-MIG-02": (
                "counter.fetch_update(Ordering::SeqCst, Ordering::SeqCst, step)",
                "let ceiling = std::i32::MAX;",
            ),
            "RS-DOC-19": ("    // let unused = compute_total(&items);",),
            "RS-DOC-27": ("/// See [the guide](https://docs.rs/serde/latest/serde/).",),
        }
    ),
    # Each of these ships an `rg` pattern that no fixture in `fires`
    # proves yet. Giving one a fixture means deleting it here, which
    # `sensitivity` insists on, so the list only shrinks.
    unproven=rules(
        "RS-API-15",
        "RS-MOD-07",
        "RS-MOD-10",
        "RS-OWN-36",
    ),
    # Measured, not judged: each of these was promoted to accuse and
    # hit the standard's own compliant examples. The reason names what
    # the span finds and what, outside the match, decides whether the
    # hit is a defect — never how many examples it hit the day someone
    # measured, which is a number `_render` already prints live two
    # fields away and nothing re-measures.
    not_decisive=keyed(
        {
            "RS-API-04": NotDecisive(
                "std::collections::",
                "the span finds every `std::collections::`; whether it appears in a "
                "public return type rather than inside a body decides",
            ),
            "RS-API-08": NotDecisive(
                "to_owned()",
                "the span finds every `to_owned()`; whether it is applied to a `&str` "
                "parameter the function goes on to store decides",
            ),
            "RS-API-19": NotDecisive(
                ": bool",
                "the span finds every `bool` parameter, private ones included; "
                "whether the signature is public decides, and their number chooses "
                "between an enum and an options struct",
            ),
            "RS-API-49": NotDecisive(
                "fn set_",
                "the span finds every `set_` method; whether the type is a builder "
                "decides, and an ordinary struct's setter is not this rule's subject",
            ),
            "RS-CLI-03": NotDecisive(
                "env::var",
                "the span finds every environment read, the sanctioned one included; "
                "whether it sits outside the single construction path decides",
            ),
            "RS-CLI-30": NotDecisive(
                "env::var",
                "the span finds every environment read; whether that name is prefixed "
                "and documented in the help output decides, and neither fact is on "
                "the line",
            ),
            "RS-CONC-12": NotDecisive(
                "join()",
                "the span finds every `join()`; whether its result is discarded "
                "rather than handled decides",
            ),
            "RS-CONC-20": NotDecisive(
                "lock()",
                "the span finds every `lock()`; whether an `.await` sits between it "
                "and the end of its scope decides",
            ),
            "RS-CONC-30": NotDecisive(
                "std::fs",
                "the span finds every `std::fs`; whether the enclosing body is "
                "`async` decides, which the matched line does not say",
            ),
            "RS-CONC-46": NotDecisive(
                "spawn(",
                "the span finds every `spawn(`; whether its handle is kept, joined, "
                "or detached with a comment decides",
            ),
            "RS-ERR-02": NotDecisive(
                "let _ = ",
                "the span finds every discarded binding; whether what it discards is "
                "a `Result`, and whether a comment names why that failure does not "
                "matter, decides",
            ),
            "RS-ERR-08": NotDecisive(
                "map_err(|_|",
                "the span finds every erased error; whether the erasure is a "
                "commented decision rather than an oversight decides",
            ),
            "RS-ERR-23": NotDecisive(
                "ok_or(",
                "the span finds every eager combinator; whether its argument is a "
                "`Copy` constant, rather than something that allocates or calls, "
                "decides",
            ),
            "RS-FUNC-03": NotDecisive(
                "Vec::new()",
                "the span finds every `Vec::new()`; whether a `for` whose body is a "
                "single `push` follows decides",
            ),
            "RS-FUNC-04": NotDecisive(
                "sum()",
                "the span matches `sum()`, which is the spelling this rule asks for; "
                "whether a hand-written `for` accumulating a scalar remains beside it "
                "decides",
            ),
            "RS-FUNC-17": NotDecisive(
                "into_iter().collect()",
                "the span finds every round trip through `into_iter().collect()`; "
                "whether the collection the caller needs could have been collected "
                "into directly decides",
            ),
            "RS-FUNC-19": NotDecisive(
                "len() - 1",
                "the span finds every `len() - 1`; whether an adapter encodes the "
                "same arithmetic decides, and the loop it belongs to is not on the "
                "line",
            ),
            "RS-NAME-16": NotDecisive(
                "fn get_",
                "the span finds every `get_`; whether the method returns `Option` or "
                "`Result`, or is the `_unchecked`/`_mut` sibling of one that does, "
                "decides",
            ),
            "RS-NAME-28": NotDecisive(
                "not_",
                "the span finds every negated name; whether it is the one conversion "
                "at the boundary the rule allows decides",
            ),
            "RS-OWN-02": NotDecisive(
                ".clone()",
                "the span finds every `.clone()`; whether it is applied to a "
                "parameter in the opening lines of a function that should have taken "
                "ownership decides",
            ),
            "RS-OWN-10": NotDecisive(
                ".clone()",
                "the span finds every `.clone()`; whether the receiver's type is "
                "`Arc` or `Rc` decides, and the type is not on the line",
            ),
            "RS-OWN-12": NotDecisive(
                "to_lowercase()",
                "the span finds every `to_lowercase()`; whether it is inside a "
                "condition or a comparison, rather than producing a value that is "
                "kept, decides",
            ),
            "RS-PERF-07": NotDecisive(
                "Vec::new",
                "the span finds every `Vec::new`; whether it sits inside a loop body "
                "decides, which is a fact about what encloses it",
            ),
            "RS-PERF-30": NotDecisive(
                "try_from",
                "the span matches `try_from`, which is the conversion this rule asks "
                "for; the defect is an `as` cast that could exceed the target range, "
                "which this span does not find",
            ),
            "RS-MOD-11": NotDecisive(
                "pub(crate)",
                "the span matches `pub(crate)`; whether the item is used only from "
                "`#[cfg(test)]`, and was widened to satisfy a test, decides",
            ),
            "RS-TEST-11": NotDecisive(
                "assert!(",
                "the span finds every `assert!(`; whether it contains `==`, `.len()`, "
                "or `&&` — an `assert_eq!` that would print more — decides",
            ),
        }
    ),
    exempt=keyed(
        {
            # RS-API-15: "Every hit that is not on a `#[repr(C)]` type
            # is a defect"
            "RS-API-15": Unless(near=(REPR_C,)),
        }
    ),
    conventions=CONVENTIONS,
    structural=(unused_defaults,),
)
