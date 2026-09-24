"""Conservative IR optimizer: 32-bit integer constant folding and safe identities.

Only compiler-created temporary values are propagated. Source variables are never
assumed constant, which prevents incorrect transformations across branches/loops.
"""
from dataclasses import replace
from .ir import Atom, Block, Let, Declare, Assign, Read, Print, Contract, If, While, For, Place
from .semantic import INT_MIN, INT_MAX


def _int(atom: Atom) -> int | None:
    if atom.literal and atom.dtype == 'INTEGER':
        try:
            value = int(atom.text)
            return value if INT_MIN <= value <= INT_MAX else None
        except ValueError:
            return None
    return None


def _fold(op: str, a: int, b: int) -> int | None:
    try:
        if op == '+': val = a + b
        elif op == '-': val = a - b
        elif op == '*': val = a * b
        elif op in ('/', '%'):
            if b == 0: return None
            q = abs(a) // abs(b) * (1 if (a >= 0) == (b >= 0) else -1)
            val = q if op == '/' else a - q*b
        elif op == '<': val = int(a < b)
        elif op == '>': val = int(a > b)
        elif op == '<=': val = int(a <= b)
        elif op == '>=': val = int(a >= b)
        elif op == '==': val = int(a == b)
        elif op == '!=': val = int(a != b)
        else: return None
        return val if INT_MIN <= val <= INT_MAX else None
    except (OverflowError, ZeroDivisionError):
        return None


def _sequence(instructions, inherited=None):
    env = dict(inherited or {})
    result = []

    def get(atom: Atom) -> Atom:
        # Only generated tN references exist in env, never user variables.
        return env.get(atom.text, atom) if not atom.literal else atom

    def place(p: Place) -> Place:
        return replace(p, index=get(p.index)) if p.index is not None else p

    for ins in instructions:
        if isinstance(ins, Let):
            a = get(ins.left)
            b = get(ins.right) if ins.right is not None else None
            substitute = None
            if ins.op == 'COPY' and a.literal is False and '[' in a.text:
                # C array access is an expression, not a pure variable atom.
                # Its index was evaluated in its own temp, so substitution
                # must also work inside the bracketed expression.
                base, suffix = a.text.split('[', 1)
                index_name = suffix[:-1]
                sub = env.get(index_name)
                if sub is not None:
                    a = replace(a, text=f'{base}[{sub.text}]')
            if ins.op == 'COPY':
                substitute = a if a.literal else None
            elif ins.op in ('UNARY+', 'UNARY-'):
                av = _int(a)
                if av is not None:
                    val = av if ins.op == 'UNARY+' else -av
                    if INT_MIN <= val <= INT_MAX:
                        substitute = Atom(str(val), 'INTEGER', True)
                elif ins.op == 'UNARY+':
                    substitute = a
            elif b is not None:
                av, bv = _int(a), _int(b)
                if av is not None and bv is not None and ins.target.dtype == 'INTEGER':
                    val = _fold(ins.op, av, bv)
                    if val is not None:
                        substitute = Atom(str(val), 'INTEGER', True)
                # Identity simplifications are used only for INTEGER.
                if substitute is None and ins.target.dtype == 'INTEGER':
                    if ins.op == '+' and av == 0: substitute = b
                    elif ins.op == '+' and bv == 0: substitute = a
                    elif ins.op == '-' and bv == 0: substitute = a
                    elif ins.op == '*' and (av == 1 or bv == 1): substitute = b if av == 1 else a
                    elif ins.op == '/' and bv == 1: substitute = a
            if substitute is not None:
                env[ins.target.text] = substitute
            else:
                result.append(replace(ins, left=a, right=b))
                # do not give an unknown temp an assumed value
        elif isinstance(ins, Assign):
            result.append(replace(ins, target=place(ins.target), value=get(ins.value)))
        elif isinstance(ins, Read):
            result.append(replace(ins, target=place(ins.target)))
        elif isinstance(ins, Print):
            result.append(replace(ins, value=get(ins.value)))
        elif isinstance(ins, Contract):
            result.append(replace(ins, condition=get(ins.condition)))
        elif isinstance(ins, If):
            setup, e = _sequence(ins.setup, env)
            cond = e.get(ins.condition.text, ins.condition)
            yes, _ = _sequence(ins.yes.instructions, env)
            no = None
            if ins.no is not None:
                no_seq, _ = _sequence(ins.no.instructions, env)
                no = Block(tuple(no_seq))
            result.append(replace(ins, setup=tuple(setup), condition=cond, yes=Block(tuple(yes)), no=no))
        elif isinstance(ins, While):
            setup, e = _sequence(ins.setup, env)
            cond = e.get(ins.condition.text, ins.condition)
            body, _ = _sequence(ins.body.instructions, env)
            result.append(replace(ins, setup=tuple(setup), condition=cond, body=Block(tuple(body))))
        elif isinstance(ins, For):
            start_setup, st = _sequence(ins.start_setup, env)
            end_setup, en = _sequence(ins.end_setup, env)
            body, _ = _sequence(ins.body.instructions, env)
            result.append(replace(ins,
                start_setup=tuple(start_setup), start=st.get(ins.start.text, ins.start),
                end_setup=tuple(end_setup), end=en.get(ins.end.text, ins.end),
                body=Block(tuple(body))))
        else:
            result.append(ins)
    return result, env


def optimize(block: Block) -> Block:
    output, _ = _sequence(block.instructions)
    return Block(tuple(output))
