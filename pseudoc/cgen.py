"""C99 generator from the optimized intermediate representation."""
from .ir import Block, Let, Declare, Assign, Read, Print, Contract, BoundsCheck, If, While, For, Break, Continue, Place
from .semantic import STRING_CAPACITY

TYPES = {'INTEGER':'int', 'REAL':'double', 'CHAR':'char'}
FMT_OUT = {'INTEGER':'%d\\n', 'REAL':'%g\\n', 'CHAR':'%c\\n', 'STRING':'%s\\n'}
FMT_IN = {'INTEGER':'%d', 'REAL':'%lf', 'CHAR':' %c'}

class CGenerator:
    def __init__(self):
        self.lines: list[str] = ['#include <stdio.h>', '#include <limits.h>', '', 'int main(void) {']
        self.depth = 1
        self.for_count = 0
        self.string_read_count = 0
        self.loop_continue_labels: list[str | None] = []

    def emit(self, line: str):
        self.lines.append('    ' * self.depth + line)

    def _block(self, block: Block):
        for ins in block.instructions:
            self._instruction(ins)

    def _uses_strings(self, block: Block) -> bool:
        for ins in block.instructions:
            if isinstance(ins, Declare) and ins.dtype == 'STRING':
                return True
            if isinstance(ins, Let) and (ins.left.dtype == 'STRING' or (ins.right and ins.right.dtype == 'STRING')):
                return True
            if isinstance(ins, Assign) and ins.target.dtype == 'STRING':
                return True
            if isinstance(ins, Read) and ins.target.dtype == 'STRING':
                return True
            if isinstance(ins, Print) and ins.value.dtype == 'STRING':
                return True
            if isinstance(ins, If) and (self._uses_strings(ins.yes) or (ins.no and self._uses_strings(ins.no))):
                return True
            if isinstance(ins, (If, While, For)):
                if isinstance(ins, (If, While)) and any(getattr(step, 'left', None) and step.left.dtype == 'STRING' for step in ins.setup):
                    return True
                if isinstance(ins, For) and self._uses_strings(ins.body):
                    return True
                if isinstance(ins, While) and self._uses_strings(ins.body):
                    return True
        return False

    @staticmethod
    def _place(place: Place):
        return place.name if place.index is None else f'{place.name}[{place.index.text}]'

    @staticmethod
    def _simple_while_condition(ins: While) -> str | None:
        """Inline a pure scalar comparison in a C while header.

        Conditions that need setup statements (for example, a dynamic array
        access with a bounds check) keep the statement-based loop lowering so
        those checks still run on every iteration.
        """
        if not ins.setup:
            if ins.condition.literal and ins.condition.dtype == 'INTEGER':
                return ins.condition.text
            return None
        if len(ins.setup) != 1:
            return None
        condition = ins.setup[0]
        if not isinstance(condition, Let):
            return None
        if condition.target.text != ins.condition.text or condition.op not in {
            '<', '>', '<=', '>=', '==', '!='
        }:
            return None
        if condition.left.dtype == 'STRING':
            return f'(strcmp({condition.left.text}, {condition.right.text}) {condition.op} 0)'
        return f'({condition.left.text} {condition.op} {condition.right.text})'

    def _instruction(self, ins):
        if isinstance(ins, Declare):
            size = f'[{ins.size}]' if ins.size is not None else ''
            if ins.dtype == 'STRING':
                self.emit(f'char {ins.name}[{STRING_CAPACITY}] = "";')
            else:
                self.emit(f'{TYPES[ins.dtype]} {ins.name}{size};')
        elif isinstance(ins, Let):
            if ins.op == 'COPY':
                expr = ins.left.text
            elif ins.op.startswith('UNARY'):
                expr = f'({ins.op[-1]}{ins.left.text})'
            elif ins.left.dtype == 'STRING' and ins.op in ('==', '!='):
                expr = f'(strcmp({ins.left.text}, {ins.right.text}) {ins.op} 0)'
            elif ins.op in ('<<', '>>'):
                self.emit(f'if ({ins.right.text} < 0 || {ins.right.text} >= (int)(sizeof(unsigned int) * CHAR_BIT)) {{')
                self.depth += 1
                self.emit(f'fprintf(stderr, "Invalid shift count at pseudocode line {ins.line}\\n");')
                self.emit('return 1;')
                self.depth -= 1
                self.emit('}')
                op = '<<' if ins.op == '<<' else '>>'
                expr = f'((int)((unsigned int){ins.left.text} {op} {ins.right.text}))'
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
            if ins.target.dtype == 'STRING':
                target = self._place(ins.target)
                if target != ins.value.text:
                    self.emit(f'strcpy({target}, {ins.value.text});')
            else:
                self.emit(f'{self._place(ins.target)} = {ins.value.text};')
        elif isinstance(ins, Read):
            if ins.target.dtype == 'STRING':
                self.string_read_count += 1
                token = f'__pseudoc_string_input_{self.string_read_count}'
                self.emit(f'char {token}[{STRING_CAPACITY + 1}];')
                self.emit(f'if (scanf("%{STRING_CAPACITY}s", {token}) != 1) {{')
                self.depth += 1
                self.emit(f'fprintf(stderr, "Input could not be read at pseudocode line {ins.line}\\n");')
                self.emit('return 1;')
                self.depth -= 1
                self.emit('}')
                self.emit(f'if (strlen({token}) >= {STRING_CAPACITY}) {{')
                self.depth += 1
                self.emit(f'fprintf(stderr, "STRING input too long at pseudocode line {ins.line}\\n");')
                self.emit('return 1;')
                self.depth -= 1
                self.emit('}')
                self.emit(f'strcpy({self._place(ins.target)}, {token});')
                return
            self.emit(f'if (scanf("{FMT_IN[ins.target.dtype]}", &{self._place(ins.target)}) != 1) {{')
            self.depth += 1
            self.emit(f'fprintf(stderr, "Input could not be read at pseudocode line {ins.line}\\n");')
            self.emit('return 1;')
            self.depth -= 1
            self.emit('}')
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
            condition = self._simple_while_condition(ins)
            if condition is not None:
                # A direct, side-effect-free comparison belongs in the C
                # while header, so C reevaluates it after every iteration.
                self.emit(f'while ({condition}) {{')
                self.depth += 1
                self.loop_continue_labels.append(None)
                self._block(ins.body)
                self.loop_continue_labels.pop()
                self.depth -= 1
                self.emit('}')
            else:
                # Retain setup statements inside the loop for conditions that
                # need temporaries or runtime checks; they must be repeated.
                self.emit('while (1) {')
                self.depth += 1
                self.loop_continue_labels.append(None)
                self._block(Block(ins.setup))
                self.emit(f'if (!({ins.condition.text})) break;')
                self._block(ins.body)
                self.loop_continue_labels.pop()
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
            self.for_count += 1
            next_value = f'__pseudoc_for_next_{self.for_count}'
            continue_label = f'__pseudoc_for_continue_{self.for_count}'
            self.loop_continue_labels.append(continue_label)
            self._block(ins.body)
            self.loop_continue_labels.pop()
            self.emit(f'{continue_label}: ;')
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
        elif isinstance(ins, Break):
            self.emit('break;')
        elif isinstance(ins, Continue):
            if self.loop_continue_labels and self.loop_continue_labels[-1] is not None:
                self.emit(f'goto {self.loop_continue_labels[-1]};')
            else:
                self.emit('continue;')
        else:
            raise AssertionError(f'unknown IR instruction {ins}')

    def generate(self, block: Block) -> str:
        if self._uses_strings(block):
            self.lines.insert(2, '#include <string.h>')
        self._block(block)
        self.emit('return 0;')
        self.lines.append('}')
        return '\n'.join(self.lines) + '\n'


def generate(block: Block) -> str:
    return CGenerator().generate(block)
