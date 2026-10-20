"""rust-style: its own `[M]` rules, applied to its own examples."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..lang.rust import RUST_STYLE, Crate
from ..model import repr_c_above
from ..report import Finding, fail, note
from ..text import strip_comment
from . import NotDecisive, Profile, register

#: RS-NAME-24 — a `bool`-returning method reads as a question.
QUESTION = re.compile(
    r"^(is_|has_|can_|should_|may_|will_|wants_|allows_|accepts_|needs_|"
    r"contains|starts_with|ends_with|matches|intersects|all_|any_|"
    r"exceeds|fits|owns|holds|knows)"
)

#: A doc comment inside an example explains the API, not the skill.
META = re.compile(
    r"\b(this example|this rule|the wrapper|as shipped|the block|"
    r"what makes .* testable|for the purposes of)\b",
    re.I,
)


@dataclass
class RustStyle(Profile):
    name: str = "rust-style"
    prefix: str = "RS"
    languages: tuple[str, ...] = ("rust",)
    marked_languages: tuple[str, ...] = ("toml",)
    toolchain: str | None = "rust"
    tools: tuple[str, ...] = ("rustc", "clippy", "rustdoc")
    exempt_from_structure: str | None = "converted in milestone 2 of refresh-skills"
    language: str = "Rust"
    verified_as: str = "compiles as written against Rust {rust}, edition 2024"
    strict_scope: str = "library and high-reliability"
    crate: Crate | None = RUST_STYLE
    #: Each snippet is the defect its rule forbids, written the way it turns up
    #: in real code. A fixture shaped to match proves the fixture, not the pattern.
    fires: dict = field(
        default_factory=lambda: {
            # A dependency the standard library replaced, one per pattern.
            "RS-MIG-01": ('lazy_static = "1.5"', 'async-trait = "0.1"'),
            "RS-MIG-02": (
                "counter.fetch_update(Ordering::SeqCst, Ordering::SeqCst, step)",
                "let ceiling = std::i32::MAX;",
            ),
            "RS-DOC-23": ("    // let unused = compute_total(&items);",),
            "RS-DOC-31": ("/// See [the guide](https://docs.rs/serde/latest/serde/).",),
        }
    )
    #: Measured, not judged: each of these was promoted to accuse and hit the
    #: standard's own compliant examples. The reason names what the span finds
    #: and what, outside the match, decides whether the hit is a defect — never
    #: how many examples it hit the day someone measured, which is a number
    #: `_render` already prints live two fields away and nothing re-measures.
    not_decisive: dict = field(
        default_factory=lambda: {
            "RS-API-06": NotDecisive(
                "std::collections::",
                "the span finds every `std::collections::`; whether it appears in a public return "
                "type rather than inside a body decides",
            ),
            "RS-API-14": NotDecisive(
                "to_owned()",
                "the span finds every `to_owned()`; whether it is applied to a `&str` parameter "
                "the function goes on to store decides",
            ),
            "RS-API-30": NotDecisive(
                ": bool",
                "the span finds every `bool` parameter, private ones included; whether the "
                "signature is public decides, and their number chooses between an enum and an "
                "options struct",
            ),
            "RS-API-66": NotDecisive(
                "fn set_",
                "the span finds every `set_` method; whether the type is a builder decides, and an "
                "ordinary struct's setter is not this rule's subject",
            ),
            "RS-CLI-04": NotDecisive(
                "env::var",
                "the span finds every environment read, the sanctioned one included; whether it "
                "sits outside the single construction path decides",
            ),
            "RS-CLI-37": NotDecisive(
                "env::var",
                "the span finds every environment read; whether that name is prefixed and "
                "documented in the help output decides, and neither fact is on the line",
            ),
            "RS-CONC-12": NotDecisive(
                "join()",
                "the span finds every `join()`; whether its result is discarded rather than "
                "handled decides",
            ),
            "RS-CONC-22": NotDecisive(
                "lock()",
                "the span finds every `lock()`; whether an `.await` sits between it and the end of "
                "its scope decides",
            ),
            "RS-CONC-33": NotDecisive(
                "std::fs",
                "the span finds every `std::fs`; whether the enclosing body is `async` decides, "
                "which the matched line does not say",
            ),
            "RS-CONC-39": NotDecisive(
                "spawn(",
                "the span finds every `spawn(`; whether its handle is kept, joined, or detached "
                "with a comment decides",
            ),
            "RS-ERR-02": NotDecisive(
                "let _ = ",
                "the span finds every discarded binding; whether what it discards is a `Result`, "
                "and whether a comment names why that failure does not matter, decides",
            ),
            "RS-ERR-09": NotDecisive(
                "map_err(|_|",
                "the span finds every erased error; whether the erasure is a commented decision "
                "rather than an oversight decides",
            ),
            "RS-ERR-29": NotDecisive(
                "ok_or(",
                "the span finds every eager combinator; whether its argument is a `Copy` constant, "
                "rather than something that allocates or calls, decides",
            ),
            "RS-FUNC-04": NotDecisive(
                "Vec::new()",
                "the span finds every `Vec::new()`; whether a `for` whose body is a single `push` "
                "follows decides",
            ),
            "RS-FUNC-05": NotDecisive(
                "sum()",
                "the span matches `sum()`, which is the spelling this rule asks for; whether a "
                "hand-written `for` accumulating a scalar remains beside it decides",
            ),
            "RS-FUNC-23": NotDecisive(
                "into_iter().collect()",
                "the span finds every round trip through `into_iter().collect()`; whether the "
                "collection the caller needs could have been collected into directly decides",
            ),
            "RS-FUNC-25": NotDecisive(
                "len() - 1",
                "the span finds every `len() - 1`; whether an adapter encodes the same arithmetic "
                "decides, and the loop it belongs to is not on the line",
            ),
            "RS-NAME-17": NotDecisive(
                "fn get_",
                "the span finds every `get_`; whether the method returns `Option` or `Result`, or "
                "is the `_unchecked`/`_mut` sibling of one that does, decides",
            ),
            "RS-NAME-31": NotDecisive(
                "not_",
                "the span finds every negated name; whether it is the one conversion at the "
                "boundary the rule allows decides",
            ),
            "RS-OWN-03": NotDecisive(
                ".clone()",
                "the span finds every `.clone()`; whether it is applied to a parameter in the "
                "opening lines of a function that should have taken ownership decides",
            ),
            "RS-OWN-14": NotDecisive(
                ".clone()",
                "the span finds every `.clone()`; whether the receiver's type is `Arc` or `Rc` "
                "decides, and the type is not on the line",
            ),
            "RS-OWN-16": NotDecisive(
                "to_lowercase()",
                "the span finds every `to_lowercase()`; whether it is inside a condition or a "
                "comparison, rather than producing a value that is kept, decides",
            ),
            "RS-PERF-06": NotDecisive(
                "Vec::new()",
                "the span finds every `Vec::new()`; whether a loop with a known bound follows, "
                "making it a missing `with_capacity`, decides",
            ),
            "RS-PERF-08": NotDecisive(
                "Vec::new",
                "the span finds every `Vec::new`; whether it sits inside a loop body decides, "
                "which is a fact about what encloses it",
            ),
            "RS-PERF-09": NotDecisive(
                ".collect::<Vec<_>>()",
                "the span finds every `.collect::<Vec<_>>()`; whether an `.iter()` follows it, "
                "making the pair a deletable round trip, decides",
            ),
            "RS-PERF-41": NotDecisive(
                "try_from",
                "the span matches `try_from`, which is the conversion this rule asks for; the "
                "defect is an `as` cast that could exceed the target range, which this span does "
                "not find",
            ),
            "RS-MOD-13": NotDecisive(
                "pub(crate)",
                "the span matches `pub(crate)`, which is the visibility this rule asks for; "
                "whether a plain `pub` outside the crate root should have been one decides",
            ),
            "RS-MOD-18": NotDecisive(
                "pub(crate)",
                "the span matches `pub(crate)`; whether the item is used only from `#[cfg(test)]`, "
                "and was widened to satisfy a test, decides",
            ),
            "RS-TEST-12": NotDecisive(
                "assert!(",
                "the span finds every `assert!(`; whether it contains `==`, `.len()`, or `&&` — an "
                "`assert_eq!` that would print more — decides",
            ),
        }
    )
    exempt: dict = field(
        default_factory=lambda: {
            # RS-API-24: "Every hit that is not on a `#[repr(C)]` type is a defect"
            "RS-API-24": lambda lines, at, in_test: repr_c_above(lines, at.start - 1),
        }
    )

    def pin(self) -> str | None:
        return self.crate.rust_version if self.crate else None

    def conventions(self, skill) -> Iterable[Finding]:
        for b in skill.advice("rust"):
            lines = b.lines
            for j, raw in enumerate(lines):
                where = f"{b.file}:{b.at(j)} [{b.rule}]"
                code = strip_comment(raw)

                # RS-API-30 — a public signature never takes a bare `bool`
                m = re.search(r"\bpub (?:async )?fn (\w+)\s*(?:<[^>]*>)?\(([^)]*)\)", code)
                if m and re.search(r":\s*bool\b", m.group(2)) and b.rule != "RS-API-30":
                    yield fail(f"`{m.group(1)}` takes a bool parameter (RS-API-30)", where)

                # RS-NAME-24 — a `bool`-returning method reads as a question
                m = re.search(r"\bpub (?:async )?fn (\w+)\([^)]*\)\s*->\s*bool\b", code)
                if m and not QUESTION.match(m.group(1)):
                    yield note(
                        f"`{m.group(1)}` returns bool but does not read as a question (RS-NAME-24)",
                        where,
                    )

                # RS-API-24 / RS-API-26 — no public field, no public tuple field
                if re.match(r"^\s+pub [a-z_]\w*:", raw) and not repr_c_above(lines, j):
                    yield fail("public struct field outside `#[repr(C)]` (RS-API-24)", where)
                if re.search(r"struct \w+\(\s*pub ", code):
                    yield fail("public tuple field (RS-API-26)", where)

                # house convention — a by-value setter is `with_*`
                m = re.search(r"\bpub fn (\w+)\((mut )?self(?:,\s*([^)]*))?\)\s*->\s*Self\b", code)
                if m:
                    fn, param = m.group(1), (m.group(3) or "")
                    assigns = any(re.search(r"self\.\w+\s*=[^=]", ln) for ln in lines[j : j + 8])
                    takes_self = re.search(r":\s*(&\s*)?Self\b", param)
                    if assigns and not takes_self and not fn.startswith(("with_", "from_")):
                        yield fail(f"by-value setter `{fn}` is not spelled `with_*`", where)

                if raw.lstrip().startswith("///") and META.search(raw):
                    yield fail("doc comment discusses the example rather than the API", where)

            # a derived `Default` nobody can reach is dead weight
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
                    yield note(f"`{name}` derives Default that nothing in the block uses", b.where)


register(RustStyle())
