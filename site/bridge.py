"""Browser adapter for the same Python translation pipeline as the local app."""
import json
from pseudoc.astview import render as render_ast
from pseudoc.compiler import compile_pseudocode
from pseudoc.errors import TranslationError
from webapp.ast_tree import program as render_ast_tree


def compile_json(source):
    try:
        result = compile_pseudocode(source)
    except TranslationError as exc:
        return json.dumps({"error": str(exc), "stage": "Source diagnostic"})
    symbols = [
        f"{s.name}{f'[{s.size}]' if s.size is not None else ''}{f'[{s.size2}]' if s.size2 is not None else ''} : "
        f"{s.dtype}    scope={s.scope}    line={s.declared_line}"
        for s in result.symbols
    ]
    return json.dumps({
        "stages": {
            "tokens": "\n".join(map(str, result.tokens)),
            "ast": render_ast(result.ast),
            "symbols": "\n".join(symbols) or "(no declarations)",
            "ir": result.ir_text(),
            "optimized_ir": result.optimized_ir_text(),
            "c": result.c_source,
        },
        "ast_tree": render_ast_tree(result.ast),
        "execution": None,
    })
