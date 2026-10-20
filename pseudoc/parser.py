"""Recursive-descent parser; synchronizes at statement boundaries after syntax errors."""
from .lexer import Token
from .errors import Issue, TranslationError
from . import nodes as n

CLOSERS = frozenset({'END', 'ELSE', 'ENDIF', 'ENDWHILE', 'ENDFOR', 'ENDFUNCTION'})
REL_OPS = frozenset({'<','>','<=','>=','==','!='})
TYPE_KINDS = frozenset({'INTEGER','REAL','CHAR','STRING'})

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
        functions = []
        while self.at('FUNCTION'):
            functions.append(self.function())
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
        return n.Program(tuple(body), tuple(functions))

    def function(self) -> n.Function:
        start = self.expect('FUNCTION')
        name = self.expect('IDENT').text
        self.expect('(')
        parameters = []
        if not self.at(')'):
            while True:
                param = self.expect('IDENT')
                self.expect('AS')
                if not self.at('INTEGER', 'REAL', 'CHAR'):
                    self.fail('function parameters must be INTEGER, REAL, or CHAR')
                parameters.append(n.Parameter(param.text, self.cur.kind, param.line))
                self.i += 1
                if not self.accept(','):
                    break
        self.expect(')')
        self.expect('RETURNS')
        if not self.at('INTEGER', 'REAL', 'CHAR'):
            self.fail('function return type must be INTEGER, REAL, or CHAR')
        return_type = self.cur.kind
        self.i += 1
        self.consume_line()
        body = self.block({'ENDFUNCTION'})
        self.expect('ENDFUNCTION')
        self.consume_line()
        return n.Function(name, tuple(parameters), return_type, tuple(body), start.line)

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
            size2 = None
            if self.accept('['):
                if size is None:
                    self.fail('second array dimension requires a first dimension')
                size2 = int(self.expect('INT_LITERAL').text)
                self.expect(']')
            self.expect('AS')
            if self.cur.kind not in TYPE_KINDS:
                self.fail('expected INTEGER, REAL, CHAR, or STRING after AS')
            dtype = self.cur.kind
            self.i += 1
            self.consume_line()
            return n.Declaration(name, dtype, size, t.line, size2)
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
        if self.accept('REQUIRE'):
            condition = self.condition()
            self.consume_line()
            return n.Require(condition, t.line)
        if self.accept('ENSURE'):
            condition = self.condition()
            self.consume_line()
            return n.Ensure(condition, t.line)
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
        if self.accept('BREAK'):
            self.consume_line()
            return n.Break(t.line)
        if self.accept('CONTINUE'):
            self.consume_line()
            return n.Continue(t.line)
        if self.accept('RETURN'):
            value = self.expression()
            self.consume_line()
            return n.Return(value, t.line)
        self.fail(f'unknown statement beginning with {t.kind} {t.text!r}')

    def place(self) -> n.Place:
        tok = self.expect('IDENT')
        if self.accept('['):
            index = self.expression()
            self.expect(']')
            index2 = None
            if self.accept('['):
                index2 = self.expression()
                self.expect(']')
            return n.ArrayAccess(tok.text, index, tok.line, index2)
        return n.Variable(tok.text, tok.line)

    def condition(self) -> n.ConditionExpr:
        value = self.and_condition()
        while self.at('OR'):
            line = self.cur.line
            self.i += 1
            value = n.BoolOp(value, 'OR', self.and_condition(), line)
        return value

    def and_condition(self) -> n.ConditionExpr:
        value = self.not_condition()
        while self.at('AND'):
            line = self.cur.line
            self.i += 1
            value = n.BoolOp(value, 'AND', self.not_condition(), line)
        return value

    def not_condition(self) -> n.ConditionExpr:
        if self.at('NOT'):
            line = self.cur.line
            self.i += 1
            return n.BoolNot(self.not_condition(), line)
        if self.at('('):
            saved = self.i
            self.i += 1
            try:
                grouped = self.condition()
                self.expect(')')
                return grouped
            except TranslationError:
                # An arithmetic expression such as (x + 1) < y starts here too.
                self.i = saved
        left = self.expression()
        if not self.at(*REL_OPS):
            self.fail('expected a comparison operator (<, >, <=, >=, ==, !=)')
        op = self.cur.kind
        line = self.cur.line
        self.i += 1
        right = self.expression()
        return n.Condition(left, op, right, line)

    def expression(self) -> n.Expr:
        expr = self.bit_xor()
        while self.at('|'):
            op, line = self.cur.kind, self.cur.line
            self.i += 1
            expr = n.Binary(expr, op, self.bit_xor(), line)
        return expr

    def bit_xor(self) -> n.Expr:
        expr = self.bit_and()
        while self.at('^'):
            op, line = self.cur.kind, self.cur.line
            self.i += 1
            expr = n.Binary(expr, op, self.bit_and(), line)
        return expr

    def bit_and(self) -> n.Expr:
        expr = self.shift()
        while self.at('&'):
            op, line = self.cur.kind, self.cur.line
            self.i += 1
            expr = n.Binary(expr, op, self.shift(), line)
        return expr

    def shift(self) -> n.Expr:
        expr = self.additive()
        while self.at('<<', '>>'):
            op, line = self.cur.kind, self.cur.line
            self.i += 1
            expr = n.Binary(expr, op, self.additive(), line)
        return expr

    def additive(self) -> n.Expr:
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
        if self.at('+', '-', '~'):
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
        if self.accept('STRING_LITERAL'):
            return n.Literal(tok.text, 'STRING', tok.line)
        if self.at('IDENT'):
            if self.tokens[self.i + 1].kind == '(':
                name = self.expect('IDENT')
                self.expect('(')
                args = []
                if not self.at(')'):
                    while True:
                        args.append(self.expression())
                        if not self.accept(','):
                            break
                self.expect(')')
                return n.Call(name.text, tuple(args), name.line)
            return self.place()
        self.fail(f'expected expression, found {tok.kind} {tok.text!r}')


def parse(tokens: list[Token]) -> n.Program:
    return Parser(tokens).parse()
