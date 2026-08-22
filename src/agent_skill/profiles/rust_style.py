"""rust-style: its own `[M]` rules, applied to its own examples."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..model import repr_c_above
from ..report import Finding, fail, note
from ..text import strip_comment
from . import Profile, register

#: RS-NAM-24 — a `bool`-returning method reads as a question.
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
    exempt: dict = field(
        default_factory=lambda: {
            # RS-API-24: "Every hit that is not on a `#[repr(C)]` type is a defect"
            "RS-API-24": lambda lines, j, in_test: repr_c_above(lines, j),
        }
    )

    def conventions(self, skill) -> Iterable[Finding]:
        for b in skill.blocks("rust"):
            # A BAD block and a quotation are evidence rather than advice.
            if b.marker.evidence:
                continue
            lines = b.lines
            for j, raw in enumerate(lines):
                where = f"{b.file}:{b.at(j)} [{b.rule}]"
                code = strip_comment(raw)

                # RS-API-30 — a public signature never takes a bare `bool`
                m = re.search(r"\bpub (?:async )?fn (\w+)\s*(?:<[^>]*>)?\(([^)]*)\)", code)
                if m and re.search(r":\s*bool\b", m.group(2)) and b.rule != "RS-API-30":
                    yield fail(f"`{m.group(1)}` takes a bool parameter (RS-API-30)", where)

                # RS-NAM-24 — a `bool`-returning method reads as a question
                m = re.search(r"\bpub (?:async )?fn (\w+)\([^)]*\)\s*->\s*bool\b", code)
                if m and not QUESTION.match(m.group(1)):
                    yield note(
                        f"`{m.group(1)}` returns bool but does not read as a question (RS-NAM-24)",
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
