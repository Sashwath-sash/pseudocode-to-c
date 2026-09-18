"""Structured, typed intermediate representation with three-address temporaries.

The C backend consumes this IR, not the source AST. Blocks preserve source scopes.
"""
from __future__ import annotations
from dataclasses import dataclass
from . import nodes as n
from .semantic import Symbol

@dataclass(frozen=True)
class Atom:
    text: str
    dtype: str
    literal: bool = False

@dataclass(frozen=True)
class Place:
    name: str
    dtype: str
    index: Atom | None = None

@dataclass(frozen=True)
class Let:
    target: Atom
    left: Atom
    op: str
    right: Atom | None = None

@dataclass(frozen=True)
class Declare:
    name: str
    dtype: str
    size: int | None

@dataclass(frozen=True)
class Assign:
    target: Place
    value: Atom

@dataclass(frozen=True)
class Read:
    target: Place

@dataclass(frozen=True)
class Print:
    value: Atom

@dataclass(frozen=True)
class If:
    setup: tuple[Instruction, ...]
    condition: Atom
    yes: Block
    no: Block | None

@dataclass(frozen=True)
class While:
    setup: tuple[Instruction, ...]
    condition: Atom
    body: Block

@dataclass(frozen=True)
class For:
    iterator: str
    start_setup: tuple[Instruction, ...]
    start: Atom
    end_setup: tuple[Instruction, ...]
    end: Atom
    step: int
    body: Block

@dataclass(frozen=True)
class Block:
    instructions: tuple[Instruction, ...]

Instruction = Let | Declare | Assign | Read | Print | If | While | For

class IRBuilder:
    def __init__(self, symbols: list[Symbol]):
        self.symbols = symbols
        self.scopes: list[dict[str, Symbol]] = [{}]
        self.temp_count = 0
        self.reserved = {s.name for s in symbols}

    def lookup(self, name: str) -> Symbol:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise AssertionError(f'semantics should have caught undeclared {name}')

    def temp(self, dtype: str) -> Atom:
        while True:
            self.temp_count += 1
            name = f't{self.temp_count}'
            if name not in self.reserved:
                self.reserved.add(name)
                return Atom(name, dtype)

    def expr(self, expr: n.Expr, output: list[Instruction]) -> Atom:
        if isinstance(expr, n.Literal):
            return Atom(expr.text, expr.kind, True)
        if isinstance(expr, n.Variable):
            return Atom(expr.name, self.lookup(expr.name).dtype)
        if isinstance(expr, n.ArrayAccess):
            sym = self.lookup(expr.name)
            index = self.expr(expr.index, output)
            dest = self.temp(sym.dtype)
            output.append(Let(dest, Atom(f'{expr.name}[{index.text}]', sym.dtype), 'COPY'))
            return dest
        if isinstance(expr, n.Unary):
            value = self.expr(expr.operand, output)
            result = self.temp(value.dtype)
            output.append(Let(result, value, f'UNARY{expr.op}'))
            return result
        if isinstance(expr, n.Binary):
            left = self.expr(expr.left, output)
            right = self.expr(expr.right, output)
            dtype = 'REAL' if 'REAL' in (left.dtype, right.dtype) else 'INTEGER'
            dest = self.temp(dtype)
            output.append(Let(dest, left, expr.op, right))
            return dest
        raise AssertionError('unexpected expression')

    def place(self, node: n.Place, output: list[Instruction]) -> Place:
        dtype = self.lookup(node.name).dtype
        if isinstance(node, n.ArrayAccess):
            idx = self.expr(node.index, output)
            return Place(node.name, dtype, idx)
        return Place(node.name, dtype)

    def condition(self, node: n.Condition, setup: list[Instruction]) -> Atom:
        left = self.expr(node.left, setup)
        right = self.expr(node.right, setup)
        result = self.temp('INTEGER')
        setup.append(Let(result, left, node.op, right))
        return result

    def block(self, source: tuple[n.Stmt, ...]) -> Block:
        self.scopes.append({})
        instructions: list[Instruction] = []
        for statement in source:
            self.statement(statement, instructions)
        self.scopes.pop()
        return Block(tuple(instructions))

    def statement(self, s: n.Stmt, out: list[Instruction]) -> None:
        if isinstance(s, n.Declaration):
            self.scopes[-1][s.name] = Symbol(s.name, s.dtype, s.size, '', s.line)
            out.append(Declare(s.name, s.dtype, s.size))
        elif isinstance(s, n.Assignment):
            target = self.place(s.target, out)
            value = self.expr(s.value, out)
            out.append(Assign(target, value))
        elif isinstance(s, n.Read):
            out.append(Read(self.place(s.target, out)))
        elif isinstance(s, n.Print):
            out.append(Print(self.expr(s.value, out)))
        elif isinstance(s, n.If):
            setup: list[Instruction] = []
            cond = self.condition(s.condition, setup)
            yes = self.block(s.yes)
            no = self.block(s.no) if s.no else None
            out.append(If(tuple(setup), cond, yes, no))
        elif isinstance(s, n.While):
            setup = []
            cond = self.condition(s.condition, setup)
            body = self.block(s.body)
            out.append(While(tuple(setup), cond, body))
        elif isinstance(s, n.For):
            start_setup: list[Instruction] = []
            start = self.expr(s.start, start_setup)
            end_setup: list[Instruction] = []
            end = self.expr(s.stop, end_setup)
            # FOR upper bound is evaluated once, even if the loop body changes it.
            if not end.literal:
                end_snapshot = self.temp('INTEGER')
                end_setup.append(Let(end_snapshot, end, 'COPY'))
                end = end_snapshot
            body = self.block(s.body)
            out.append(For(s.iterator, tuple(start_setup), start, tuple(end_setup), end, s.step, body))
        else:
            raise AssertionError('unexpected statement')

    def build(self, program: n.Program) -> Block:
        result: list[Instruction] = []
        for statement in program.statements:
            self.statement(statement, result)
        return Block(tuple(result))


def _p(place: Place) -> str:
    return place.name if place.index is None else f'{place.name}[{place.index.text}]'

def _render(instr: Instruction, level: int, output: list[str]):
    pre = '    ' * level
    if isinstance(instr, Declare):
        suffix = '' if instr.size is None else f'[{instr.size}]'
        output.append(f'{pre}DECLARE {instr.name}{suffix} : {instr.dtype}')
    elif isinstance(instr, Let):
        if instr.op == 'COPY':
            rhs = instr.left.text
        elif instr.op.startswith('UNARY'):
            rhs = f'{instr.op[-1]}{instr.left.text}'
        else:
            rhs = f'{instr.left.text} {instr.op} {instr.right.text}'
        output.append(f'{pre}{instr.target.text} = {rhs}')
    elif isinstance(instr, Assign):
        output.append(f'{pre}{_p(instr.target)} = {instr.value.text}')
    elif isinstance(instr, Read):
        output.append(f'{pre}READ {_p(instr.target)}')
    elif isinstance(instr, Print):
        output.append(f'{pre}PRINT {instr.value.text}')
    elif isinstance(instr, If):
        for step in instr.setup:
            _render(step, level, output)
        output.append(f'{pre}IF {instr.condition.text} THEN')
        for step in instr.yes.instructions:
            _render(step, level+1, output)
        if instr.no is not None:
            output.append(f'{pre}ELSE')
            for step in instr.no.instructions:
                _render(step, level+1, output)
        output.append(f'{pre}ENDIF')
    elif isinstance(instr, While):
        output.append(f'{pre}WHILE:')
        for step in instr.setup:
            _render(step, level+1, output)
        output.append(f'{pre}    IF NOT {instr.condition.text}: BREAK')
        for step in instr.body.instructions:
            _render(step, level+1, output)
        output.append(f'{pre}ENDWHILE')
    elif isinstance(instr, For):
        for step in instr.start_setup:
            _render(step, level, output)
        for step in instr.end_setup:
            _render(step, level, output)
        output.append(f'{pre}FOR {instr.iterator} = {instr.start.text} TO {instr.end.text} STEP {instr.step}')
        for step in instr.body.instructions:
            _render(step, level+1, output)
        output.append(f'{pre}ENDFOR')


def render(block: Block) -> str:
    lines: list[str] = []
    for instr in block.instructions:
        _render(instr, 0, lines)
    return '\n'.join(lines)
