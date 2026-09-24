"""Hand-written scanner. NEWLINE is significant: one statement per line."""
from dataclasses import dataclass
import ast
import re
from .errors import Issue, TranslationError

KEYWORDS = frozenset('BEGIN END DECLARE AS SET READ PRINT REQUIRE ENSURE IF THEN ELSE ENDIF WHILE DO ENDWHILE FOR TO STEP ENDFOR INTEGER REAL CHAR'.split())
TOKEN_RE = re.compile(r'[A-Za-z_][A-Za-z_0-9]*|[0-9]+\.[0-9]+|[0-9]+|<=|>=|==|!=|[+*/%\-<>=()\[\]]')

@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.kind:<11} {self.text!r:<15} ({self.line}:{self.column})"

def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    for line_no, line in enumerate(source.splitlines(), 1):
        i = 0
        while i < len(line):
            ch = line[i]
            if ch in ' \t\r':
                i += 1
                continue
            if ch == '#' or line.startswith('//', i):
                break
            if ch == "'":
                start = i
                i += 1
                while i < len(line):
                    if line[i] == '\\':
                        i += 2
                        continue
                    if line[i] == "'":
                        i += 1
                        break
                    i += 1
                word = line[start:i]
                # Accept only portable single-character C escapes; Python has
                # escapes (e.g. \uXXXX) that are not C character-literal syntax.
                if '\\' in word and (len(word) != 4 or word[1] != '\\' or word[2] not in ('n', 't', 'r', '0', '\\', "'", '"')):
                    raise TranslationError(Issue('Lexical', f'unsupported C character escape {word!r}', line_no, start + 1))
                try:
                    value = ast.literal_eval(word)
                    if not isinstance(value, str) or len(value) != 1 or ord(value) > 127:
                        raise ValueError('CHAR must contain exactly one ASCII character')
                except (ValueError, SyntaxError, UnicodeError) as exc:
                    raise TranslationError(Issue('Lexical', f'invalid character literal {word!r}: {exc}', line_no, start + 1)) from exc
                tokens.append(Token('CHAR_LITERAL', word, line_no, start + 1))
                continue
            match = TOKEN_RE.match(line, i)
            if not match:
                raise TranslationError(Issue('Lexical', f'unexpected character {ch!r}', line_no, i + 1))
            word = match.group()
            if word[0].isalpha() or word[0] == '_':
                upper = word.upper()
                kind = upper if upper in KEYWORDS else 'IDENT'
            elif word[0].isdigit():
                if len(word) > 1024:
                    raise TranslationError(Issue('Lexical', 'numeric literal exceeds 1024 characters', line_no, i + 1))
                kind = 'REAL_LITERAL' if '.' in word else 'INT_LITERAL'
            else:
                kind = word
            tokens.append(Token(kind, word, line_no, i + 1))
            i = match.end()
        tokens.append(Token('NEWLINE', '\\n', line_no, len(line) + 1))
    tokens.append(Token('EOF', '', max(1, len(source.splitlines()) + 1), 1))
    return tokens
