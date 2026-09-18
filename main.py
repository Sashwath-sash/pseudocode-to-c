#!/usr/bin/env python3
"""Usage: python main.py examples/review1.pseudo --show-all --run"""
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from pseudoc.compiler import compile_pseudocode
from pseudoc.astview import render as render_ast
from pseudoc.errors import TranslationError


def compile_and_run(c_code: str, user_input: str = '', timeout: int = 3) -> tuple[str, str, int]:
    gcc = shutil.which('gcc')
    if gcc is None:
        raise RuntimeError('GCC is not installed. C generation works; install GCC for --run.')
    with tempfile.TemporaryDirectory(prefix='pseudoc_') as temp:
        src = Path(temp) / 'generated.c'
        exe = Path(temp) / ('generated.exe' if os.name == 'nt' else 'generated')
        src.write_text(c_code, encoding='utf-8')
        try:
            result = subprocess.run([gcc, '-std=c99', '-Wall', '-Wextra', str(src), '-o', str(exe)],
                                    text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError('GCC compilation timed out') from e
        if result.returncode:
            raise RuntimeError(f'generated C did not compile:\n{result.stderr}')
        try:
            run = subprocess.run([str(exe)], input=user_input, text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError('program execution timed out (possible infinite loop)') from e
        return run.stdout, run.stderr, run.returncode


def cli(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='Compiler-based restricted pseudocode to C translator')
    ap.add_argument('source', type=Path, help='pseudocode .pseudo source file')
    ap.add_argument('--out', type=Path, help='path for generated .c file; default: source filename.c')
    ap.add_argument('--show-all', action='store_true', help='display tokens, AST, symbol table, IR, optimized IR, and C')
    ap.add_argument('--run', action='store_true', help='compile with GCC and run locally (3-second timeout)')
    ap.add_argument('--no-optimize', action='store_true', help='generate C from the original IR for comparison')
    ap.add_argument('--input', type=Path, help='optional UTF-8 stdin text file, for --run')
    args = ap.parse_args(argv)
    try:
        source = args.source.read_text(encoding='utf-8')
        result = compile_pseudocode(source, optimize_ir=not args.no_optimize)
        target = args.out or args.source.with_suffix('.c')
        if target.resolve() == args.source.resolve():
            raise RuntimeError('output path must differ from pseudocode input path')
        if args.input and target.resolve() == args.input.resolve():
            raise RuntimeError('output path must differ from runtime input path')
        data = args.input.read_text(encoding='utf-8') if args.run and args.input else ''
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result.c_source, encoding='utf-8')
        print(f'Generated C: {target}')
        if args.show_all:
            print('\n=== TOKENS ===')
            print('\n'.join(map(str, result.tokens)))
            print('\n=== AST ===')
            print(render_ast(result.ast))
            print('\n=== SYMBOL TABLE ===')
            for symbol in result.symbols:
                suffix = '' if symbol.size is None else f'[{symbol.size}]'
                print(f'{symbol.name}{suffix:<15} {symbol.dtype:<8} scope={symbol.scope} line={symbol.declared_line}')
            print('\n=== INTERMEDIATE REPRESENTATION ===')
            print(result.ir_text())
            print('\n=== OPTIMIZED IR ===')
            print(result.optimized_ir_text())
            print('\n=== GENERATED C ===')
            print(result.c_source)
        if args.run:
            stdout, stderr, returncode = compile_and_run(result.c_source, data)
            print('=== PROGRAM OUTPUT ===')
            print(stdout, end='')
            if stderr:
                print(stderr, file=sys.stderr)
            print(f'\n[Exit status: {returncode}]')
            return 0 if returncode == 0 else 1
        return 0
    except (TranslationError, RuntimeError, OSError, UnicodeError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(cli())
