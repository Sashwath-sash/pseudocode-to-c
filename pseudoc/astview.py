"""Compact readable AST view for demonstrations; AST itself is in nodes.py."""
from . import nodes as n


def expression(e: n.Expr) -> str:
    if isinstance(e, n.Literal):
        return e.text
    if isinstance(e, n.Variable):
        return e.name
    if isinstance(e, n.ArrayAccess):
        return f'{e.name}[{expression(e.index)}]' + (f'[{expression(e.index2)}]' if e.index2 is not None else '')
    if isinstance(e, n.Unary):
        return f'({e.op}{expression(e.operand)})'
    if isinstance(e, n.Call):
        return f'{e.name}({", ".join(expression(arg) for arg in e.arguments)})'
    return f'({expression(e.left)} {e.op} {expression(e.right)})'


def condition(c: n.ConditionExpr) -> str:
    if isinstance(c, n.BoolNot):
        return f'NOT ({condition(c.operand)})'
    if isinstance(c, n.BoolOp):
        return f'({condition(c.left)} {c.op} {condition(c.right)})'
    return f'{expression(c.left)} {c.op} {expression(c.right)}'


def render(program: n.Program) -> str:
    lines = ['Program']

    def block(statements: tuple[n.Stmt, ...], depth: int):
        p = '  ' * depth
        for s in statements:
            if isinstance(s, n.Declaration):
                suffix = f'[{s.size}]' if s.size is not None else ''
                if s.size2 is not None:
                    suffix += f'[{s.size2}]'
                lines.append(f'{p}Declaration: {s.name}{suffix} : {s.dtype}')
            elif isinstance(s, n.Assignment):
                lines.append(f'{p}Assignment: {expression(s.target)} = {expression(s.value)}')
            elif isinstance(s, n.Read):
                lines.append(f'{p}Read: {expression(s.target)}')
            elif isinstance(s, n.Print):
                lines.append(f'{p}Print: {expression(s.value)}')
            elif isinstance(s, n.Require):
                lines.append(f'{p}Precondition: {condition(s.condition)}')
            elif isinstance(s, n.Ensure):
                lines.append(f'{p}Postcondition: {condition(s.condition)}')
            elif isinstance(s, n.If):
                lines.append(f'{p}If: {condition(s.condition)}')
                lines.append(f'{p}  THEN:')
                block(s.yes, depth + 2)
                if s.no:
                    lines.append(f'{p}  ELSE:')
                    block(s.no, depth + 2)
            elif isinstance(s, n.While):
                lines.append(f'{p}While: {condition(s.condition)}')
                block(s.body, depth + 1)
            elif isinstance(s, n.For):
                lines.append(f'{p}For: {s.iterator} = {expression(s.start)} TO {expression(s.stop)} STEP {s.step}')
                block(s.body, depth + 1)
            elif isinstance(s, n.Break):
                lines.append(f'{p}Break')
            elif isinstance(s, n.Continue):
                lines.append(f'{p}Continue')
            elif isinstance(s, n.Return):
                lines.append(f'{p}Return: {expression(s.value)}')

    for fn in program.functions:
        params = ', '.join(f'{p.name}: {p.dtype}' for p in fn.parameters)
        lines.append(f'  Function: {fn.name}({params}) -> {fn.return_type}')
        block(fn.body, 2)
    block(program.statements, 1)
    return '\n'.join(lines)
