"""Structured, typed intermediate representation with three-address temporaries.

The C backend consumes this IR, not the source AST. Blocks preserve source scopes.
"""
from __future__ import annotations
from dataclasses import dataclass
from . import nodes as n
from .semantic import Symbol, SemanticAnalyzer

@dataclass(frozen=True)
class Atom:
    text: str
    dtype: str
    literal: bool = False
    inline: bool = False

@dataclass(frozen=True)
class Place:
    name: str
    dtype: str
    index: Atom | None = None
    index2: Atom | None = None

@dataclass(frozen=True)
class Let:
    target: Atom
    left: Atom
    op: str
    right: Atom | None = None
    line: int = 0

@dataclass(frozen=True)
class Declare:
    name: str
    dtype: str
    size: int | None
    size2: int | None = None

@dataclass(frozen=True)
class Assign:
    target: Place
    value: Atom
    line: int = 0

@dataclass(frozen=True)
class Read:
    target: Place
    line: int = 0

@dataclass(frozen=True)
class Print:
    value: Atom

@dataclass(frozen=True)
class Contract:
    kind: str
    condition: Atom
    line: int

@dataclass(frozen=True)
class BoundsCheck:
    array: str
    index: Atom
    size: int
    line: int

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
    line: int = 0

@dataclass(frozen=True)
class Break:
    pass

@dataclass(frozen=True)
class Continue:
    pass

@dataclass(frozen=True)
class Call:
    target: Atom
    name: str
    arguments: tuple[Atom, ...]

@dataclass(frozen=True)
class Return:
    value: Atom

@dataclass(frozen=True)
class Function:
    name: str
    parameters: tuple[n.Parameter, ...]
    return_type: str
    body: Block

@dataclass(frozen=True)
class Block:
    instructions: tuple[Instruction, ...]
    functions: tuple[Function, ...] = ()

Instruction = Let | Declare | Assign | Read | Print | Contract | BoundsCheck | If | While | For | Break | Continue | Call | Return

class IRBuilder:
    def __init__(self, symbols: list[Symbol]):
        self.symbols = symbols
        self.scopes: list[dict[str, Symbol]] = [{}]
        self.temp_count = 0
        self.reserved = {s.name for s in symbols}
        self.function_types: dict[str, str] = {}

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
        if isinstance(expr, n.Call):
            arguments = tuple(self.expr(arg, output) for arg in expr.arguments)
            target = self.temp(self.function_types[expr.name])
            output.append(Call(target, expr.name, arguments))
            return target
        if isinstance(expr, n.Literal):
            return Atom(expr.text, expr.kind, True)
        if isinstance(expr, n.Variable):
            return Atom(expr.name, self.lookup(expr.name).dtype)
        if isinstance(expr, n.ArrayAccess):
            sym = self.lookup(expr.name)
            index = self.expr(expr.index, output)
            if sym.size is not None and SemanticAnalyzer.constant_int(expr.index) is None:
                output.append(BoundsCheck(expr.name, index, sym.size, expr.line))
            index2 = None
            if expr.index2 is not None:
                index2 = self.expr(expr.index2, output)
                if sym.size2 is not None and SemanticAnalyzer.constant_int(expr.index2) is None:
                    output.append(BoundsCheck(expr.name, index2, sym.size2, expr.line))
            dest = self.temp(sym.dtype)
            suffix = f'[{index.text}]' + (f'[{index2.text}]' if index2 is not None else '')
            output.append(Let(dest, Atom(expr.name + suffix, sym.dtype), 'COPY', line=expr.line))
            return dest
        if isinstance(expr, n.Unary):
            value = self.expr(expr.operand, output)
            result = self.temp(value.dtype)
            output.append(Let(result, value, f'UNARY{expr.op}', line=expr.line))
            return result
        if isinstance(expr, n.Binary):
            left = self.expr(expr.left, output)
            right = self.expr(expr.right, output)
            dtype = 'REAL' if 'REAL' in (left.dtype, right.dtype) else 'INTEGER'
            dest = self.temp(dtype)
            output.append(Let(dest, left, expr.op, right, expr.line))
            return dest
        raise AssertionError('unexpected expression')

    def place(self, node: n.Place, output: list[Instruction]) -> Place:
        dtype = self.lookup(node.name).dtype
        if isinstance(node, n.ArrayAccess):
            idx = self.expr(node.index, output)
            sym = self.lookup(node.name)
            if sym.size is not None and SemanticAnalyzer.constant_int(node.index) is None:
                output.append(BoundsCheck(node.name, idx, sym.size, node.line))
            idx2 = None
            if node.index2 is not None:
                idx2 = self.expr(node.index2, output)
                if sym.size2 is not None and SemanticAnalyzer.constant_int(node.index2) is None:
                    output.append(BoundsCheck(node.name, idx2, sym.size2, node.line))
            return Place(node.name, dtype, idx, idx2)
        return Place(node.name, dtype)

    def condition(self, node: n.ConditionExpr, setup: list[Instruction]) -> Atom:
        inline = self.inline_condition(node)
        if inline is not None:
            return Atom(inline, 'INTEGER', inline=True)
        if isinstance(node, n.BoolNot):
            operand = self.condition(node.operand, setup)
            result = self.temp('INTEGER')
            setup.append(Let(result, operand, 'UNARY!', line=node.line))
            return result
        if isinstance(node, n.BoolOp):
            left = self.condition(node.left, setup)
            result = self.temp('INTEGER')
            setup.append(Declare(result.text, 'INTEGER', None))
            right_setup: list[Instruction] = []
            right = self.condition(node.right, right_setup)
            rhs = Block(tuple(right_setup + [Assign(Place(result.text, 'INTEGER'), right, node.line)]))
            literal = Atom('0' if node.op == 'AND' else '1', 'INTEGER', True)
            shortcut = Block((Assign(Place(result.text, 'INTEGER'), literal, node.line),))
            setup.append(If((), left, rhs if node.op == 'AND' else shortcut,
                            shortcut if node.op == 'AND' else rhs))
            return result
        left = self.expr(node.left, setup)
        right = self.expr(node.right, setup)
        result = self.temp('INTEGER')
        setup.append(Let(result, left, node.op, right, node.line))
        return result

    def inline_condition(self, node: n.ConditionExpr) -> str | None:
        """Use a C condition directly only when no operand needs IR setup or guards."""
        if isinstance(node, n.BoolNot):
            operand = self.inline_condition(node.operand)
            return f'(!({operand}))' if operand is not None else None
        if isinstance(node, n.BoolOp):
            left = self.inline_condition(node.left)
            right = self.inline_condition(node.right)
            if left is None or right is None:
                return None
            op = '&&' if node.op == 'AND' else '||'
            return f'({left} {op} {right})'
        operands = []
        for expr in (node.left, node.right):
            if isinstance(expr, n.Variable):
                symbol = self.lookup(expr.name)
                if symbol.size is not None or symbol.dtype == 'STRING':
                    return None
                operands.append(expr.name)
            elif isinstance(expr, n.Literal) and expr.kind != 'STRING':
                operands.append(expr.text)
            else:
                return None
        return f'{operands[0]} {node.op} {operands[1]}'

    def block(self, source: tuple[n.Stmt, ...]) -> Block:
        self.scopes.append({})
        instructions: list[Instruction] = []
        for statement in source:
            self.statement(statement, instructions)
        self.scopes.pop()
        return Block(tuple(instructions))

    def statement(self, s: n.Stmt, out: list[Instruction]) -> None:
        if isinstance(s, n.Declaration):
            self.scopes[-1][s.name] = Symbol(s.name, s.dtype, s.size, '', s.line, s.size2)
            out.append(Declare(s.name, s.dtype, s.size, s.size2))
        elif isinstance(s, n.Assignment):
            target = self.place(s.target, out)
            value = self.expr(s.value, out)
            out.append(Assign(target, value, s.line))
        elif isinstance(s, n.Read):
            out.append(Read(self.place(s.target, out), s.line))
        elif isinstance(s, n.Print):
            out.append(Print(self.expr(s.value, out)))
        elif isinstance(s, (n.Require, n.Ensure)):
            setup: list[Instruction] = []
            condition = self.condition(s.condition, setup)
            out.extend(setup)
            out.append(Contract('REQUIRE' if isinstance(s, n.Require) else 'ENSURE', condition, s.line))
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
            out.append(For(s.iterator, tuple(start_setup), start, tuple(end_setup), end, s.step, body, s.line))
        elif isinstance(s, n.Break):
            out.append(Break())
        elif isinstance(s, n.Continue):
            out.append(Continue())
        elif isinstance(s, n.Return):
            out.append(Return(self.expr(s.value, out)))
        else:
            raise AssertionError('unexpected statement')

    def build(self, program: n.Program) -> Block:
        self.function_types = {fn.name: fn.return_type for fn in program.functions}
        self.reserved.update(self.function_types)
        functions = []
        for fn in program.functions:
            self.scopes.append({p.name: Symbol(p.name, p.dtype, None, fn.name, p.line) for p in fn.parameters})
            body = self.block(fn.body)
            self.scopes.pop()
            functions.append(Function(fn.name, fn.parameters, fn.return_type, body))
        result: list[Instruction] = []
        for statement in program.statements:
            self.statement(statement, result)
        return Block(tuple(result), tuple(functions))


def _p(place: Place) -> str:
    if place.index is None:
        return place.name
    return f'{place.name}[{place.index.text}]' + (f'[{place.index2.text}]' if place.index2 is not None else '')

def _render(instr: Instruction, level: int, output: list[str]):
    pre = '    ' * level
    if isinstance(instr, Declare):
        suffix = '' if instr.size is None else f'[{instr.size}]'
        if instr.size2 is not None:
            suffix += f'[{instr.size2}]'
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
    elif isinstance(instr, BoundsCheck):
        output.append(f'{pre}BOUNDS_CHECK {instr.array}[{instr.index.text}] IN 0..{instr.size - 1}  # source line {instr.line}')
    elif isinstance(instr, Print):
        output.append(f'{pre}PRINT {instr.value.text}')
    elif isinstance(instr, Contract):
        output.append(f'{pre}{instr.kind} {instr.condition.text}  # source line {instr.line}')
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
    elif isinstance(instr, Break):
        output.append(f'{pre}BREAK')
    elif isinstance(instr, Continue):
        output.append(f'{pre}CONTINUE')
    elif isinstance(instr, Call):
        output.append(f'{pre}{instr.target.text} = CALL {instr.name}({", ".join(arg.text for arg in instr.arguments)})')
    elif isinstance(instr, Return):
        output.append(f'{pre}RETURN {instr.value.text}')


def render(block: Block) -> str:
    lines: list[str] = []
    for fn in block.functions:
        signature = ', '.join(f'{p.name}: {p.dtype}' for p in fn.parameters)
        lines.append(f'FUNCTION {fn.name}({signature}) RETURNS {fn.return_type}')
        for instr in fn.body.instructions:
            _render(instr, 1, lines)
        lines.append('ENDFUNCTION')
    for instr in block.instructions:
        _render(instr, 0, lines)
    return '\n'.join(lines)
