"""Recursive-descent parser; synchronizes at statement boundaries after syntax errors."""
from .lexer import Token
from .errors import Issue, TranslationError
from . import nodes as n

CLOSERS = frozenset({'END', 'ELSE', 'ENDIF', 'ENDWHILE', 'ENDFOR'})
REL_OPS = frozenset({'<','>','<=','>=','==','!='})
TYPE_KINDS = frozenset({'INTEGER','REAL','CHAR'})

class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0
        self.issues: list[Issue] = []

    @property
    def cur(self) -> Token:
        return self.tokens[self.i]

    def at(self, *kinds: str) -> bool:
        return self.cur.kind in kinds

    def accept(self, kind: str) -> Token | None:
        if self.at(kind):
            token = self.cur
            self.i += 1
            return token
        return None

    def fail(self, message: str) -> None:
        t = self.cur
        raise TranslationError(Issue('Syntax', message, t.line, t.column))

    def expect(self, kind: str) -> Token:
        token = self.accept(kind)
        if token is None:
            self.fail(f'expected {kind}, found {self.cur.kind} {self.cur.text!r}')
        return token

    def consume_line(self):
        if self.at('EOF'):
            self.fail('expected end of line')
        self.expect('NEWLINE')

    def skip_empty(self):
        while self.accept('NEWLINE'):
            pass

    def synchronize(self):
        # Skip the rest of an invalid statement, retaining the next statement.
        while not self.at('EOF', 'NEWLINE'):
            self.i += 1
        self.accept('NEWLINE')

    def parse(self) -> n.Program:
        self.skip_empty()
        self.expect('BEGIN')
        self.consume_line()
        body = self.block({'END'})
        self.expect('END')
        if not self.at('NEWLINE', 'EOF'):
            self.fail('unexpected text after END')
        self.skip_empty()
        self.expect('EOF')
        if self.issues:
            raise TranslationError(self.issues)
        return n.Program(tuple(body))

    def block(self, stops: set[str]) -> list[n.Stmt]:
        body: list[n.Stmt] = []
        while True:
            self.skip_empty()
            if self.at('EOF'):
                self.fail(f'unclosed block: expected {" or ".join(sorted(stops))}')
            if self.cur.kind in stops:
                return body
            if self.cur.kind in CLOSERS:
                self.issues.append(Issue('Syntax', f'unexpected {self.cur.kind} in this block', self.cur.line, self.cur.column))
                self.synchronize()
                continue
            try:
                body.append(self.statement())
            except TranslationError as e:
                self.issues.extend(e.issues)
                self.synchronize()

    def statement(self) -> n.Stmt:
        t = self.cur
        if self.accept('DECLARE'):
            name = self.expect('IDENT').text
            size = None
            if self.accept('['):
                tok = self.expect('INT_LITERAL')
                size = int(tok.text)
                self.expect(']')
            self.expect('AS')
            if self.cur.kind not in TYPE_KINDS:
                self.fail('expected INTEGER, REAL, or CHAR after AS')
            dtype = self.cur.kind
            self.i += 1
            self.consume_line()
            return n.Declaration(name, dtype, size, t.line)
        if self.accept('SET'):
            target = self.place()
            self.expect('=')
            value = self.expression()
            self.consume_line()
            return n.Assignment(target, value, t.line)
        if self.accept('READ'):
            target = self.place()
            self.consume_line()
            return n.Read(target, t.line)
        if self.accept('PRINT'):
            value = self.expression()
            self.consume_line()
            return n.Print(value, t.line)
        if self.accept('IF'):
            cond = self.condition()
            self.expect('THEN')
            self.consume_line()
            yes = self.block({'ELSE', 'ENDIF'})
            no = []
            if self.accept('ELSE'):
                self.consume_line()
                no = self.block({'ENDIF'})
            self.expect('ENDIF')
            self.consume_line()
            return n.If(cond, tuple(yes), tuple(no), t.line)
        if self.accept('WHILE'):
            cond = self.condition()
            self.expect('DO')
            self.consume_line()
            body = self.block({'ENDWHILE'})
            self.expect('ENDWHILE')
            self.consume_line()
            return n.While(cond, tuple(body), t.line)
        if self.accept('FOR'):
            iterator = self.expect('IDENT').text
            self.expect('=')
            start = self.expression()
            self.expect('TO')
            stop = self.expression()
            step = 1
            if self.accept('STEP'):
                sign = -1 if self.accept('-') else 1
                if sign == 1:
                    self.accept('+')
                step = sign * int(self.expect('INT_LITERAL').text)
            self.expect('DO')
            self.consume_line()
            body = self.block({'ENDFOR'})
            self.expect('ENDFOR')
            self.consume_line()
            return n.For(iterator, start, stop, step, tuple(body), t.line)
        self.fail(f'unknown statement beginning with {t.kind} {t.text!r}')

    def place(self) -> n.Place:
        tok = self.expect('IDENT')
        if self.accept('['):
            index = self.expression()
            self.expect(']')
            return n.ArrayAccess(tok.text, index, tok.line)
        return n.Variable(tok.text, tok.line)

    def condition(self) -> n.Condition:
        left = self.expression()
        if not self.at(*REL_OPS):
            self.fail('expected a comparison operator (<, >, <=, >=, ==, !=)')
        op = self.cur.kind
        line = self.cur.line
        self.i += 1
        right = self.expression()
        return n.Condition(left, op, right, line)

    def expression(self) -> n.Expr:
        expr = self.term()
        while self.at('+', '-'):
            op = self.cur.kind
            line = self.cur.line
            self.i += 1
            expr = n.Binary(expr, op, self.term(), line)
        return expr

    def term(self) -> n.Expr:
        expr = self.factor()
        while self.at('*', '/', '%'):
            op = self.cur.kind
            line = self.cur.line
            self.i += 1
            expr = n.Binary(expr, op, self.factor(), line)
        return expr

    def factor(self) -> n.Expr:
        tok = self.cur
        if self.at('+', '-'):
            self.i += 1
            return n.Unary(tok.kind, self.factor(), tok.line)
        if self.accept('('):
            expr = self.expression()
            self.expect(')')
            return expr
        if self.accept('INT_LITERAL'):
            return n.Literal(str(int(tok.text)), 'INTEGER', tok.line)
        if self.accept('REAL_LITERAL'):
            return n.Literal(tok.text, 'REAL', tok.line)
        if self.accept('CHAR_LITERAL'):
            return n.Literal(tok.text, 'CHAR', tok.line)
        if self.at('IDENT'):
            return self.place()
        self.fail(f'expected expression, found {tok.kind} {tok.text!r}')


def parse(tokens: list[Token]) -> n.Program:
    return Parser(tokens).parse()
