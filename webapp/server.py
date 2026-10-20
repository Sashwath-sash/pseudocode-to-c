"""Local website for exploring the existing pseudocode-to-C compiler."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
sys.path.insert(0, str(ROOT))

from main import compile_and_run  # noqa: E402
from pseudoc.astview import render as render_ast  # noqa: E402
from pseudoc.compiler import compile_pseudocode  # noqa: E402
from pseudoc.errors import TranslationError  # noqa: E402
from webapp.ast_tree import program as render_ast_tree  # noqa: E402

MAX_REQUEST_BYTES = 256_000
MAX_SOURCE_CHARS = 40_000
MAX_INPUT_CHARS = 4_000
EXAMPLE_DIR = ROOT / "examples"
EXAMPLE_INPUTS = {
    "sum_for": "input5.txt",
    "contracts_division": "division_valid.txt",
    "automatic_division": "division_valid.txt",
    "contracts_array": "array_valid.txt",
    "automatic_array_bounds": "array_valid.txt",
}
EXAMPLE_NAMES = {
    "review1": "Arithmetic (Review 1)",
    "sum_for": "Read and sum with FOR",
    "phase2_features": "STRING, bitwise and loop control",
    "automatic_division": "Automatic division guard",
    "automatic_array_bounds": "Automatic array bounds guard",
    "logic_matrix": "AND / OR with a 2D array",
    "function_larger": "Typed function and RETURN",
    "invalid": "Invalid source and diagnostics",
}
FEATURED = ("review1", "sum_for", "logic_matrix", "function_larger",
            "phase2_features", "automatic_division", "automatic_array_bounds", "invalid")


def project_examples() -> list[dict]:
    files = {path.stem: path for path in EXAMPLE_DIR.glob("*.pseudo")}
    order = [name for name in FEATURED if name in files]
    order.extend(sorted(set(files) - set(order)))
    examples = []
    for name in order:
        input_file = EXAMPLE_INPUTS.get(name)
        examples.append({
            "id": name,
            "name": EXAMPLE_NAMES.get(name, name.replace("_", " ").title()),
            "source": files[name].read_text(encoding="utf-8"),
            "input": (EXAMPLE_DIR / input_file).read_text(encoding="utf-8").strip()
            if input_file else "",
        })
    return examples


def compile_request(payload: object) -> tuple[int, dict]:
    if not isinstance(payload, dict):
        return 400, {"error": "Send a JSON object."}
    source = payload.get("source")
    user_input = payload.get("input", "")
    run = payload.get("run", False)
    if not isinstance(source, str) or not source.strip():
        return 400, {"error": "Enter pseudocode before compiling."}
    if not isinstance(user_input, str) or not isinstance(run, bool):
        return 400, {"error": "Input must be text and run must be true or false."}
    if len(source) > MAX_SOURCE_CHARS or len(user_input) > MAX_INPUT_CHARS:
        return 413, {"error": "Program or runtime input is too long for this local demo."}

    try:
        result = compile_pseudocode(source)
    except TranslationError as exc:
        return 422, {"error": str(exc), "stage": "Source diagnostic"}

    symbols = [
        f"{s.name}{f'[{s.size}]' if s.size is not None else ''}{f'[{s.size2}]' if s.size2 is not None else ''} : "
        f"{s.dtype}    scope={s.scope}    line={s.declared_line}"
        for s in result.symbols
    ]
    stages = {
        "tokens": "\n".join(map(str, result.tokens)),
        "ast": render_ast(result.ast),
        "symbols": "\n".join(symbols) or "(no declarations)",
        "ir": result.ir_text(),
        "optimized_ir": result.optimized_ir_text(),
        "c": result.c_source,
    }
    response = {"stages": stages, "ast_tree": render_ast_tree(result.ast),
                "execution": None}
    if run:
        try:
            stdout, stderr, returncode = compile_and_run(result.c_source, user_input)
            response["execution"] = {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": returncode,
            }
        except RuntimeError as exc:
            response["execution"] = {"error": str(exc)}
    return 200, response


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/examples":
            self.send_json(200, {"examples": project_examples()})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/compile":
            self.send_error(404, "Not found")
            return
        host = self.headers.get("Host", "")
        if host not in {f"127.0.0.1:{self.server.server_port}",
                        f"localhost:{self.server.server_port}"}:
            self.send_json(403, {"error": "This local server only accepts localhost requests."})
            return
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{host}":
            self.send_json(403, {"error": "Cross-origin requests are not accepted."})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self.send_json(415, {"error": "Content-Type must be application/json."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self.send_json(413, {"error": "Request is empty or too large."})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "Request must contain valid UTF-8 JSON."})
            return
        status, response = compile_request(payload)
        self.send_json(status, response)

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local pseudocode-to-C website")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Pseudocode-to-C website: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
