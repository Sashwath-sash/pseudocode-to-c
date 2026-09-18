"""Public translation API; no external Python dependencies."""
from dataclasses import dataclass
from .lexer import tokenize, Token
from .parser import parse
from .semantic import SemanticAnalyzer, Symbol
from .ir import IRBuilder, Block, render
from .optimizer import optimize
from .cgen import generate
from . import nodes

@dataclass(frozen=True)
class Compilation:
    tokens: list[Token]
    ast: nodes.Program
    symbols: list[Symbol]
    ir_before: Block
    ir_after: Block
    c_source: str

    def ir_text(self) -> str:
        return render(self.ir_before)

    def optimized_ir_text(self) -> str:
        return render(self.ir_after)


def compile_pseudocode(source: str, *, optimize_ir: bool = True) -> Compilation:
    tokens = tokenize(source)
    ast = parse(tokens)
    symbols = SemanticAnalyzer().analyze(ast)
    ir_before = IRBuilder(symbols).build(ast)
    ir_after = optimize(ir_before) if optimize_ir else ir_before
    c_source = generate(ir_after)
    return Compilation(tokens, ast, symbols, ir_before, ir_after, c_source)
