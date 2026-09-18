"""Diagnostics with original source line and column numbers."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Issue:
    stage: str
    message: str
    line: int
    column: int = 1

    def __str__(self) -> str:
        return f"{self.stage} error at line {self.line}, column {self.column}: {self.message}"

class TranslationError(Exception):
    def __init__(self, issues: list[Issue] | Issue):
        self.issues = [issues] if isinstance(issues, Issue) else issues
        super().__init__("\n".join(map(str, self.issues)))
