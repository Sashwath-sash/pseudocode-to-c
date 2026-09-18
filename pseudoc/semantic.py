"""Lexically-scoped symbol table and basic static type checking."""
from dataclasses import dataclass
import math
from . import nodes as n
from .errors import Issue, TranslationError

INT_MIN, INT_MAX = -(2**31), 2**31 - 1
# These spellings must not become C identifiers or hide functions emitted by the backend.
C_RESERVED = frozenset(('auto break case char const continue default do double else enum '
    'extern float for goto if inline int long register restrict return short signed '
    'sizeof static struct switch typedef union unsigned void volatile while '
    '_Bool _Complex _Imaginary main printf scanf EOF NULL BUFSIZ FILENAME_MAX ' 'FOPEN_MAX TMP_MAX L_tmpnam SEEK_SET SEEK_CUR SEEK_END stdin stdout stderr ' 'FILE size_t fpos_t').split())

@dataclass(frozen=True)
class Symbol:
    name: str
    dtype: str
    size: int | None
    scope: str
    declared_line: int

class SemanticAnalyzer:
    def __init__(self):
        self.scopes: list[dict[str, Symbol]] = [{}]
        self.scope_names: list[str] = ['main']
        self.symbols: list[Symbol] = []
        self.issues: list[Issue] = []
        self.counter = 0

    def error(self, line: int, message: str):
        self.issues.append(Issue('Semantic', message, line))

    def lookup(self, name: str, line: int) -> Symbol | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        self.error(line, f'undeclared identifier {name!r}')
        return None

    def begin_scope(self, kind: str):
        self.counter += 1
        self.scope_names.append(f'{self.scope_names[-1]}/{kind}_{self.counter}')
        self.scopes.append({})

    def end_scope(self):
        self.scopes.pop()
        self.scope_names.pop()

    def block(self, statements: tuple[n.Stmt, ...], kind: str):
        self.begin_scope(kind)
        for stmt in statements:
            self.statement(stmt)
        self.end_scope()

    def place_type(self, place: n.Place) -> str | None:
        sym = self.lookup(place.name, place.line)
        if sym is None:
            if isinstance(place, n.ArrayAccess):
                self.expr_type(place.index)
            return None
        if isinstance(place, n.ArrayAccess):
            if sym.size is None:
                self.error(place.line, f'{sym.name!r} is not an array')
            if self.expr_type(place.index) not in (None, 'INTEGER'):
                self.error(place.line, 'array index must be INTEGER')
            index = self.constant_int(place.index)
            if index is not None and sym.size is not None and not (0 <= index < sym.size):
                self.error(place.line, f'constant array index {index} is outside 0..{sym.size - 1}')
        elif sym.size is not None:
            self.error(place.line, f'array {sym.name!r} requires an index')
        return sym.dtype

    @staticmethod
    def constant_int(expr: n.Expr) -> int | None:
        """Evaluate *simple* integer-only constant expressions for static diagnostics."""
        if isinstance(expr, n.Literal) and expr.kind == 'INTEGER':
            val = int(expr.text)
            return val if INT_MIN <= val <= INT_MAX else None
        if isinstance(expr, n.Unary):
            value = SemanticAnalyzer.constant_int(expr.operand)
            if value is None:
                return None
            val = -value if expr.op == '-' else value
            return val if INT_MIN <= val <= INT_MAX else None
        if isinstance(expr, n.Binary):
            left = SemanticAnalyzer.constant_int(expr.left)
            right = SemanticAnalyzer.constant_int(expr.right)
            if left is None or right is None:
                return None
            if expr.op == '+': val = left + right
            elif expr.op == '-': val = left - right
            elif expr.op == '*': val = left * right
            elif expr.op in ('/', '%') and right != 0:
                quotient = abs(left) // abs(right) * (1 if (left >= 0) == (right >= 0) else -1)
                val = quotient if expr.op == '/' else left - quotient * right
            else: return None
            return val if INT_MIN <= val <= INT_MAX else None
        return None

    def expr_type(self, expr: n.Expr) -> str | None:
        if isinstance(expr, n.Literal):
            if expr.kind == 'REAL' and not math.isfinite(float(expr.text)):
                self.error(expr.line, 'REAL literal exceeds supported finite double range')
            if expr.kind == 'INTEGER' and int(expr.text) > INT_MAX:
                self.error(expr.line, 'integer literal exceeds supported 32-bit C int range')
            return expr.kind
        if isinstance(expr, (n.Variable, n.ArrayAccess)):
            return self.place_type(expr)
        if isinstance(expr, n.Unary):
            dtype = self.expr_type(expr.operand)
            if dtype not in (None, 'INTEGER', 'REAL'):
                self.error(expr.line, 'unary +/- requires a numeric operand')
            return dtype
        assert isinstance(expr, n.Binary)
        ltype = self.expr_type(expr.left)
        rtype = self.expr_type(expr.right)
        if ltype is None or rtype is None:
            return None
        if ltype not in ('INTEGER','REAL') or rtype not in ('INTEGER','REAL'):
            self.error(expr.line, f'operator {expr.op} requires numeric operands')
            return None
        if expr.op == '%' and (ltype != 'INTEGER' or rtype != 'INTEGER'):
            self.error(expr.line, 'remainder % requires two INTEGER operands')
        if expr.op in ('/', '%') and (
            self.constant_int(expr.right) == 0 or
            (isinstance(expr.right, n.Literal) and expr.right.kind == 'REAL' and float(expr.right.text) == 0)
        ):
            self.error(expr.line, 'division or remainder by zero')
        return 'REAL' if 'REAL' in (ltype, rtype) else 'INTEGER'

    def condition(self, cond: n.Condition):
        left = self.expr_type(cond.left)
        right = self.expr_type(cond.right)
        if left is None or right is None:
            return
        if left == 'CHAR' or right == 'CHAR':
            if left != 'CHAR' or right != 'CHAR' or cond.op not in ('==','!='):
                self.error(cond.line, 'CHAR comparisons require CHAR == CHAR or CHAR != CHAR')
        elif left not in ('INTEGER','REAL') or right not in ('INTEGER','REAL'):
            self.error(cond.line, 'comparison requires compatible operands')

    def statement(self, stmt: n.Stmt):
        if isinstance(stmt, n.Declaration):
            if stmt.name in C_RESERVED or stmt.name.startswith('__') or (len(stmt.name) > 1 and stmt.name[0] == '_' and stmt.name[1].isupper()):
                self.error(stmt.line, f'identifier {stmt.name!r} is reserved in generated C')
            elif stmt.name in self.scopes[-1]:
                self.error(stmt.line, f'duplicate declaration of {stmt.name!r} in same scope')
            elif stmt.size is not None and (stmt.size <= 0 or stmt.size > 100000):
                self.error(stmt.line, 'array size must be between 1 and 100000')
            else:
                sym = Symbol(stmt.name, stmt.dtype, stmt.size, self.scope_names[-1], stmt.line)
                self.scopes[-1][stmt.name] = sym
                self.symbols.append(sym)
        elif isinstance(stmt, n.Assignment):
            target = self.place_type(stmt.target)
            value = self.expr_type(stmt.value)
            if target and value and target != value and not (target == 'REAL' and value == 'INTEGER'):
                self.error(stmt.line, f'cannot assign {value} to {target}')
        elif isinstance(stmt, n.Read):
            self.place_type(stmt.target)
        elif isinstance(stmt, n.Print):
            self.expr_type(stmt.value)
        elif isinstance(stmt, n.If):
            self.condition(stmt.condition)
            self.block(stmt.yes, 'if')
            if stmt.no:
                self.block(stmt.no, 'else')
        elif isinstance(stmt, n.While):
            self.condition(stmt.condition)
            self.block(stmt.body, 'while')
        elif isinstance(stmt, n.For):
            iterator = self.lookup(stmt.iterator, stmt.line)
            if iterator is not None and (iterator.dtype != 'INTEGER' or iterator.size is not None):
                self.error(stmt.line, 'FOR iterator must be a scalar INTEGER variable')
            for bound in (stmt.start, stmt.stop):
                dtype = self.expr_type(bound)
                if dtype and dtype != 'INTEGER':
                    self.error(stmt.line, 'FOR bounds must be INTEGER')
            if stmt.step == 0:
                self.error(stmt.line, 'FOR STEP cannot be zero')
            if not (INT_MIN <= stmt.step <= INT_MAX):
                self.error(stmt.line, 'FOR STEP exceeds supported 32-bit integer range')
            self.block(stmt.body, 'for')

    def analyze(self, program: n.Program) -> list[Symbol]:
        for stmt in program.statements:
            self.statement(stmt)
        if self.issues:
            raise TranslationError(self.issues)
        return self.symbols
