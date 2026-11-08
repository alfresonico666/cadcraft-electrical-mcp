"""Runs validation rules and summarises the result."""

from __future__ import annotations

from dataclasses import dataclass

from .rules import ALL_RULES, Issue, Rule, Severity, ValidationContext


@dataclass
class ValidationReport:
    issues: list[Issue]

    @property
    def errors(self) -> int:
        return sum(1 for i in self.issues if i.severity is Severity.ERROR)

    @property
    def warnings(self) -> int:
        return sum(1 for i in self.issues if i.severity is Severity.WARNING)

    @property
    def ok(self) -> bool:
        return self.errors == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "infos": len(self.issues) - self.errors - self.warnings,
            "issues": [
                {"rule": i.rule, "severity": i.severity.value, "message": i.message, "ref": i.ref}
                for i in sorted(
                    self.issues, key=lambda i: ["error", "warning", "info"].index(i.severity.value)
                )
            ],
        }


def validate(ctx: ValidationContext, rules: list[Rule] | None = None) -> ValidationReport:
    issues: list[Issue] = []
    for rule in rules or ALL_RULES:
        issues.extend(rule.check(ctx))
    return ValidationReport(issues)


def describe_rules() -> list[dict[str, str]]:
    return [{"id": r.id, "description": r.description} for r in ALL_RULES]
