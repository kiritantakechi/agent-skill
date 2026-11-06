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
            "RS-API-12": ("pub fn items(&self) -> &Vec<Item> {",),
            "RS-API-49": ("pub fn set_limit(&mut self, limit: usize) -> &mut Self {",),
            "RS-BUILD-14": ('serde = { version = "1", optional = true }',),
            "RS-BUILD-21": ('serde = "=1.0.200"',),
            "RS-BUILD-23": ("#![deny(missing_docs)]",),
            "RS-BUILD-24": ('pedantic = "allow"',),
            "RS-BUILD-26": (
                'RUSTFLAGS="-Dwarnings" cargo build',
                'RUSTDOCFLAGS="-D warnings" cargo doc',
            ),
            "RS-CONC-24": ("let guard = state.lock().unwrap();",),
            "RS-CONC-27": (
                "static mut COUNTER: u32 = 0;",
                "static CACHE: Mutex<Option<Config>> = Mutex::new(None);",
            ),
            "RS-DOC-25": ("    // TODO: handle the empty case",),
            "RS-ERR-08": ("let n = s.parse::<u32>().map_err(|_| Error::Parse)?;",),
            "RS-ERR-29": ('panic = "abort"',),
            "RS-MOD-13": ("pub use crate::matcher::*;",),
            "RS-NAME-07": ("use-simd = []",),
            "RS-NAME-16": ("pub fn get_name(&self) -> &str {",),
            "RS-NAME-21": ("pub fn new_with_capacity(capacity: usize) -> Self {",),
            "RS-NAME-29": ("pub trait ParserTrait {",),
            "RS-NAME-33": ("fn first<'life>(items: &'life [u8]) -> &'life u8 {",),
            "RS-OWN-30": ("let shared: Arc<String> = Arc::new(name);",),
            "RS-PERF-21": ("reader.read(&mut [0u8; 1])?;",),
            "RS-TEST-17": ('let path = Path::new("/tmp/out.txt");',),
            "RS-TRAIT-28": (
                "default fn describe(&self) -> String {",
                "#![feature(specialization)]",
            ),
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
            "RS-API-49": NotDecisive(
                "fn set_",
                "the span finds every `set_` method; whether the type is a builder "
                "decides, and an ordinary struct's setter is not this rule's subject",
            ),
            "RS-ERR-08": NotDecisive(
                "map_err(|_|",
                "the span finds every erased error; whether the erasure is a "
                "commented decision rather than an oversight decides",
            ),
            "RS-NAME-16": NotDecisive(
                "fn get_",
                "the span finds every `get_`; whether the method returns `Option` or "
                "`Result`, or is the `_unchecked`/`_mut` sibling of one that does, "
                "decides",
            ),
            "RS-PERF-07": NotDecisive(
                "Vec::new",
                "the span finds every `Vec::new`; whether it sits inside a loop body "
                "decides, which is a fact about what encloses it",
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
