"""C99 generator from the optimized intermediate representation."""
from .ir import Block, Let, Declare, Assign, Read, Print, Contract, BoundsCheck, If, While, For, Place

TYPES = {'INTEGER':'int', 'REAL':'double', 'CHAR':'char'}
FMT_OUT = {'INTEGER':'%d\\n', 'REAL':'%g\\n', 'CHAR':'%c\\n'}

class CGenerator:
    def __init__(self):
        self.lines: list[str] = [
            '#include <stdio.h>', '#include <stdlib.h>', '#include <errno.h>',
            '#include <limits.h>', '#include <math.h>', '#include <string.h>', '',
            'int main(void) {'
        ]
        self.depth = 1
        self.read_count = 0
        self.for_count = 0

    def emit(self, line: str):
        self.lines.append('    ' * self.depth + line)

    def _block(self, block: Block):
        for ins in block.instructions:
            self._instruction(ins)

    @staticmethod
    def _place(place: Place):
        return place.name if place.index is None else f'{place.name}[{place.index.text}]'

    def _instruction(self, ins):
        if isinstance(ins, Declare):
            size = f'[{ins.size}]' if ins.size is not None else ''
            self.emit(f'{TYPES[ins.dtype]} {ins.name}{size};')
        elif isinstance(ins, Let):
            if ins.op == 'COPY':
                expr = ins.left.text
            elif ins.op.startswith('UNARY'):
                expr = f'({ins.op[-1]}{ins.left.text})'
            else:
                expr = f'({ins.left.text} {ins.op} {ins.right.text})'
                if ins.op in ('/', '%'):
                    self.emit(f'if ({ins.right.text} == 0) {{')
                    self.depth += 1
                    self.emit(f'fprintf(stderr, "Division or remainder by zero at pseudocode line {ins.line}\\n");')
                    self.emit('return 1;')
                    self.depth -= 1
                    self.emit('}')
                    if ins.target.dtype == 'INTEGER':
                        self.emit(f'if ({ins.left.text} == INT_MIN && {ins.right.text} == -1) {{')
                        self.depth += 1
                        self.emit(f'fprintf(stderr, "Integer division/remainder overflow at pseudocode line {ins.line}\\n");')
                        self.emit('return 1;')
                        self.depth -= 1
                        self.emit('}')
            self.emit(f'{TYPES[ins.target.dtype]} {ins.target.text} = {expr};')
        elif isinstance(ins, Assign):
            self.emit(f'{self._place(ins.target)} = {ins.value.text};')
        elif isinstance(ins, Read):
            self.read_count += 1
            serial = self.read_count
            token = f'__pseudoc_token_{serial}'
            end = f'__pseudoc_end_{serial}'
            value = f'__pseudoc_value_{serial}'
            if ins.target.dtype == 'CHAR':
                self.emit(f'if (scanf(" %c", &{self._place(ins.target)}) != 1 || (unsigned char){self._place(ins.target)} > 127) {{')
                self.depth += 1
                self.emit(f'fprintf(stderr, "Invalid CHAR input at pseudocode line {ins.line}\\n");')
                self.emit('return 1;')
                self.depth -= 1
                self.emit('}')
            else:
                self.emit(f'char {token}[129], *{end};')
                ctype, converter = ('long', 'strtol') if ins.target.dtype == 'INTEGER' else ('double', 'strtod')
                self.emit(f'{ctype} {value};')
                self.emit(f'if (scanf("%128s", {token}) != 1) {{')
                self.depth += 1
                self.emit(f'fprintf(stderr, "Invalid {ins.target.dtype} input at pseudocode line {ins.line}\\n");')
                self.emit('return 1;')
                self.depth -= 1
                self.emit('}')
                self.emit('errno = 0;')
                base = ', 10' if ins.target.dtype == 'INTEGER' else ''
                self.emit(f'{value} = {converter}({token}, &{end}{base});')
                checks = [f'{end} == {token}', f'*{end} != \'\\0\'', 'errno == ERANGE', f'strlen({token}) >= 128']
                if ins.target.dtype == 'INTEGER':
                    checks.extend((f'{value} < INT_MIN', f'{value} > INT_MAX'))
                else:
                    checks.append(f'!isfinite({value})')
                self.emit(f'if ({" || ".join(checks)}) {{')
                self.depth += 1
                self.emit(f'fprintf(stderr, "Invalid or out-of-range {ins.target.dtype} input at pseudocode line {ins.line}\\n");')
                self.emit('return 1;')
                self.depth -= 1
                self.emit('}')
                self.emit(f'{self._place(ins.target)} = ({TYPES[ins.target.dtype]}){value};')
        elif isinstance(ins, Print):
            self.emit(f'printf("{FMT_OUT[ins.value.dtype]}", {ins.value.text});')
        elif isinstance(ins, Contract):
            message = 'Precondition' if ins.kind == 'REQUIRE' else 'Postcondition'
            self.emit(f'if (!({ins.condition.text})) {{')
            self.depth += 1
            self.emit(f'fprintf(stderr, "{message} failed at pseudocode line {ins.line}\\n");')
            self.emit('return 1;')
            self.depth -= 1
            self.emit('}')
        elif isinstance(ins, BoundsCheck):
            self.emit(f'if ({ins.index.text} < 0 || {ins.index.text} >= {ins.size}) {{')
            self.depth += 1
            self.emit(f'fprintf(stderr, "Array index out of bounds at pseudocode line {ins.line}\\n");')
            self.emit('return 1;')
            self.depth -= 1
            self.emit('}')
        elif isinstance(ins, If):
            self._block(Block(ins.setup))
            self.emit(f'if ({ins.condition.text}) {{')
            self.depth += 1
            self._block(ins.yes)
            self.depth -= 1
            if ins.no is None:
                self.emit('}')
            else:
                self.emit('} else {')
                self.depth += 1
                self._block(ins.no)
                self.depth -= 1
                self.emit('}')
        elif isinstance(ins, While):
            self.emit('while (1) {')
            self.depth += 1
            self._block(Block(ins.setup))
            self.emit(f'if (!({ins.condition.text})) break;')
            self._block(ins.body)
            self.depth -= 1
            self.emit('}')
        elif isinstance(ins, For):
            # Group start/end temporary declarations into the loop's own scope.
            self.emit('{')
            self.depth += 1
            self._block(Block(ins.start_setup))
            self._block(Block(ins.end_setup))
            op = '<=' if ins.step > 0 else '>='
            self.emit(f'{ins.iterator} = {ins.start.text};')
            self.emit(f'while ({ins.iterator} {op} {ins.end.text}) {{')
            self.depth += 1
            self._block(ins.body)
            self.for_count += 1
            next_value = f'__pseudoc_for_next_{self.for_count}'
            self.emit(f'long long {next_value} = (long long){ins.iterator} + ({ins.step});')
            self.emit(f'if ({next_value} < INT_MIN || {next_value} > INT_MAX) {{')
            self.depth += 1
            self.emit(f'fprintf(stderr, "FOR iterator overflow at pseudocode line {ins.line}\\n");')
            self.emit('return 1;')
            self.depth -= 1
            self.emit('}')
            self.emit(f'{ins.iterator} = (int){next_value};')
            self.depth -= 1
            self.emit('}')
            self.depth -= 1
            self.emit('}')
        else:
            raise AssertionError(f'unknown IR instruction {ins}')

    def generate(self, block: Block) -> str:
        self._block(block)
        self.emit('return 0;')
        self.lines.append('}')
        return '\n'.join(self.lines) + '\n'


def generate(block: Block) -> str:
    return CGenerator().generate(block)
