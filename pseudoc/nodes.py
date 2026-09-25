"""Typed source AST for the restricted pseudocode language."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Literal:
    text: str
    kind: str  # INTEGER, REAL, CHAR
    line: int

@dataclass(frozen=True)
class Variable:
    name: str
    line: int

@dataclass(frozen=True)
class ArrayAccess:
    name: str
    index: Expr
    line: int

@dataclass(frozen=True)
class Unary:
    op: str
    operand: Expr
    line: int

@dataclass(frozen=True)
class Binary:
    left: Expr
    op: str
    right: Expr
    line: int

Expr = Literal | Variable | ArrayAccess | Unary | Binary
Place = Variable | ArrayAccess

@dataclass(frozen=True)
class Condition:
    left: Expr
    op: str
    right: Expr
    line: int

@dataclass(frozen=True)
class Declaration:
    name: str
    dtype: str
    size: int | None
    line: int

@dataclass(frozen=True)
class Assignment:
    target: Place
    value: Expr
    line: int

@dataclass(frozen=True)
class Read:
    target: Place
    line: int

@dataclass(frozen=True)
class Print:
    value: Expr
    line: int

@dataclass(frozen=True)
class Require:
    condition: Condition
    line: int

@dataclass(frozen=True)
class Ensure:
    condition: Condition
    line: int

@dataclass(frozen=True)
class If:
    condition: Condition
    yes: tuple[Stmt, ...]
    no: tuple[Stmt, ...]
    line: int

@dataclass(frozen=True)
class While:
    condition: Condition
    body: tuple[Stmt, ...]
    line: int

@dataclass(frozen=True)
class For:
    iterator: str
    start: Expr
    stop: Expr
    step: int
    body: tuple[Stmt, ...]
    line: int

@dataclass(frozen=True)
class Break:
    line: int

@dataclass(frozen=True)
class Continue:
    line: int

Stmt = Declaration | Assignment | Read | Print | Require | Ensure | If | While | For | Break | Continue

@dataclass(frozen=True)
class Program:
    statements: tuple[Stmt, ...]
