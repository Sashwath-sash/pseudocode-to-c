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
    index2: Expr | None = None

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

@dataclass(frozen=True)
class Call:
    name: str
    arguments: tuple[Expr, ...]
    line: int

Expr = Literal | Variable | ArrayAccess | Unary | Binary | Call
Place = Variable | ArrayAccess

@dataclass(frozen=True)
class Condition:
    left: Expr
    op: str
    right: Expr
    line: int

@dataclass(frozen=True)
class BoolOp:
    left: ConditionExpr
    op: str
    right: ConditionExpr
    line: int

@dataclass(frozen=True)
class BoolNot:
    operand: ConditionExpr
    line: int

ConditionExpr = Condition | BoolOp | BoolNot

@dataclass(frozen=True)
class Declaration:
    name: str
    dtype: str
    size: int | None
    line: int
    size2: int | None = None

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

@dataclass(frozen=True)
class Return:
    value: Expr
    line: int

Stmt = Declaration | Assignment | Read | Print | Require | Ensure | If | While | For | Break | Continue | Return

@dataclass(frozen=True)
class Parameter:
    name: str
    dtype: str
    line: int

@dataclass(frozen=True)
class Function:
    name: str
    parameters: tuple[Parameter, ...]
    return_type: str
    body: tuple[Stmt, ...]
    line: int

@dataclass(frozen=True)
class Program:
    statements: tuple[Stmt, ...]
    functions: tuple[Function, ...] = ()
