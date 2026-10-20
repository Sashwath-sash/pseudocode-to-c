"""Convert the compiler's typed AST into a browser-friendly node tree."""

from pseudoc import nodes as n


def edge(role: str, node: dict) -> dict:
    return {"role": role, "node": node}


def expression(value: n.Expr) -> dict:
    if isinstance(value, n.Literal):
        return {"kind": "Literal", "detail": f"{value.kind} {value.text}", "children": []}
    if isinstance(value, n.Variable):
        return {"kind": "Variable", "detail": value.name, "children": []}
    if isinstance(value, n.ArrayAccess):
        return {"kind": "Array access", "detail": value.name,
                "children": [edge("index", expression(value.index))]}
    if isinstance(value, n.Unary):
        return {"kind": "Unary", "detail": value.op,
                "children": [edge("operand", expression(value.operand))]}
    if isinstance(value, n.Binary):
        return {"kind": "Binary", "detail": value.op,
                "children": [edge("left", expression(value.left)),
                             edge("right", expression(value.right))]}
    raise TypeError(f"Unexpected expression: {type(value).__name__}")


def condition(value: n.Condition) -> dict:
    return {"kind": "Condition", "detail": value.op,
            "children": [edge("left", expression(value.left)),
                         edge("right", expression(value.right))]}


def statement(value: n.Stmt) -> dict:
    if isinstance(value, n.Declaration):
        suffix = f"[{value.size}]" if value.size is not None else ""
        return {"kind": "Declaration", "detail": f"{value.name}{suffix}: {value.dtype}",
                "children": []}
    if isinstance(value, n.Assignment):
        return {"kind": "Assignment", "detail": "=",
                "children": [edge("target", expression(value.target)),
                             edge("value", expression(value.value))]}
    if isinstance(value, n.Read):
        return {"kind": "Read", "detail": "",
                "children": [edge("target", expression(value.target))]}
    if isinstance(value, n.Print):
        return {"kind": "Print", "detail": "",
                "children": [edge("value", expression(value.value))]}
    if isinstance(value, (n.Require, n.Ensure)):
        return {"kind": "Require" if isinstance(value, n.Require) else "Ensure",
                "detail": "", "children": [edge("condition", condition(value.condition))]}
    if isinstance(value, n.If):
        children = [edge("condition", condition(value.condition))]
        children.extend(edge("then", statement(item)) for item in value.yes)
        children.extend(edge("else", statement(item)) for item in value.no)
        return {"kind": "If", "detail": "", "children": children}
    if isinstance(value, n.While):
        return {"kind": "While", "detail": "",
                "children": [edge("condition", condition(value.condition)),
                             *(edge("body", statement(item)) for item in value.body)]}
    if isinstance(value, n.For):
        return {"kind": "For", "detail": f"{value.iterator}, step {value.step}",
                "children": [edge("start", expression(value.start)),
                             edge("stop", expression(value.stop)),
                             *(edge("body", statement(item)) for item in value.body)]}
    if isinstance(value, (n.Break, n.Continue)):
        return {"kind": type(value).__name__, "detail": "", "children": []}
    raise TypeError(f"Unexpected statement: {type(value).__name__}")


def program(value: n.Program) -> dict:
    return {"kind": "Program", "detail": "",
            "children": [edge("statement", statement(item)) for item in value.statements]}
