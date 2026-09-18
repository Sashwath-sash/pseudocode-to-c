"""C99 generator from the optimized intermediate representation."""
from .ir import Block, Let, Declare, Assign, Read, Print, If, While, For, Place

TYPES = {'INTEGER':'int', 'REAL':'double', 'CHAR':'char'}
FMT_OUT = {'INTEGER':'%d\\n', 'REAL':'%g\\n', 'CHAR':'%c\\n'}
FMT_IN = {'INTEGER':'%d', 'REAL':'%lf', 'CHAR':' %c'}

class CGenerator:
    def __init__(self):
        self.lines: list[str] = ['#include <stdio.h>', '', 'int main(void) {']
        self.depth = 1

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
            self.emit(f'{TYPES[ins.target.dtype]} {ins.target.text} = {expr};')
        elif isinstance(ins, Assign):
            self.emit(f'{self._place(ins.target)} = {ins.value.text};')
        elif isinstance(ins, Read):
            self.emit(f'if (scanf("{FMT_IN[ins.target.dtype]}", &{self._place(ins.target)}) != 1) return 1;')
        elif isinstance(ins, Print):
            self.emit(f'printf("{FMT_OUT[ins.value.dtype]}", {ins.value.text});')
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
            self.emit(f'for ({ins.iterator} = {ins.start.text}; {ins.iterator} {op} {ins.end.text}; {ins.iterator} += ({ins.step})) {{')
            self.depth += 1
            self._block(ins.body)
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
