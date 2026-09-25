"""Generate valid, optimization-focused programs and compare both pipelines."""
from __future__ import annotations

from dataclasses import dataclass
import random
import shutil
import os
import subprocess
import tempfile
from pathlib import Path

from .compiler import compile_pseudocode


@dataclass(frozen=True)
class CheckResult:
    cases: int
    comparisons: int
    mismatches: tuple[str, ...]


def _signed(value: int) -> str:
    return f"(-{abs(value)})" if value < 0 else str(value)


def _expression(rng: random.Random, depth: int) -> str:
    if depth <= 0 or rng.random() < 0.28:
        return rng.choice(("x", "y", _signed(rng.randint(-9, 9))))
    op = rng.choice(("+", "-", "*", "/", "%"))
    left = _expression(rng, depth - 1)
    if op in ("/", "%"):
        # A nonzero literal denominator avoids generating undefined behavior.
        right = _signed(rng.choice(tuple(range(-7, 0)) + tuple(range(1, 8))))
    else:
        right = _expression(rng, depth - 1)
    return f"({left} {op} {right})"


def generate_case(seed: int, case_index: int) -> str:
    """Make a repeatable, bounded program that exercises each current IR rule."""
    rng = random.Random((seed << 32) ^ case_index)
    x_value, y_value = rng.randint(-12, 12), rng.randint(-12, 12)
    a, b = rng.randint(1, 9), rng.choice(tuple(range(-9, 0)) + tuple(range(1, 10)))
    expressions = [
        f"{a} + {b}", f"{a} - {b}", f"{a} * {b}", f"{a} / {b}", f"{a} % {b}",
        f"(-{a})", f"(+{b})", "x + 0", "0 + x", "x - 0", "x * 1", "1 * x", "x / 1",
        f"{a} & {b}", f"{a} | {b}", f"{a} ^ {b}", f"~{a}", f"{a} << 2", f"{a} >> 2",
        f"((x + {a}) * (y - {b}))", f"(({a} + {b}) * ({a} - {b}))",
    ]
    expressions.extend(_expression(rng, 2) for _ in range(8))

    lines = [
        "BEGIN",
        "DECLARE x AS INTEGER",
        "DECLARE y AS INTEGER",
        "DECLARE i AS INTEGER",
        f"SET x = {_signed(x_value)}",
        f"SET y = {_signed(y_value)}",
    ]
    lines.extend(f"PRINT {expr}" for expr in expressions)
    lines.extend((
        "IF x < y THEN", "PRINT x + 0", "ELSE", "PRINT y * 1", "ENDIF",
        "WHILE x < " + str(x_value + 2) + " DO", "SET x = x + 1", "PRINT x", "ENDWHILE",
        "FOR i = 1 TO 2 STEP +1 DO", "PRINT i * (1 + 0)", "ENDFOR", "END",
    ))
    return "\n".join(lines) + "\n"


def _run_c(c_source: str, timeout: int) -> tuple[str, str, int]:
    gcc = shutil.which("gcc")
    if gcc is None:
        raise RuntimeError("GCC is required for optimizer differential checking")
    with tempfile.TemporaryDirectory(prefix="pseudoc_check_") as tmp:
        source = Path(tmp) / "case.c"
        executable = Path(tmp) / ("case.exe" if os.name == "nt" else "case")
        source.write_text(c_source, encoding="utf-8")
        built = subprocess.run(
            [gcc, "-std=c99", "-Wall", "-Wextra", str(source), "-o", str(executable)],
            capture_output=True, text=True, timeout=timeout,
        )
        if built.returncode:
            raise RuntimeError(f"generated C did not compile:\n{built.stderr}")
        ran = subprocess.run(
            [str(executable)], capture_output=True, text=True, timeout=timeout,
        )
        return ran.stdout, ran.stderr, ran.returncode


def check_optimizer(cases: int = 50, seed: int = 20260923, timeout: int = 3) -> CheckResult:
    if cases < 1 or cases > 10000:
        raise ValueError("case count must be between 1 and 10000")
    mismatches: list[str] = []
    for index in range(cases):
        program = generate_case(seed, index)
        baseline = compile_pseudocode(program, optimize_ir=False)
        optimized = compile_pseudocode(program, optimize_ir=True)
        before = _run_c(baseline.c_source, timeout)
        after = _run_c(optimized.c_source, timeout)
        if before != after:
            mismatches.append(
                f"Case {index} (seed {seed}):\n"
                f"Unoptimized result: {before!r}\nOptimized result: {after!r}\n"
                f"Reproduce with --fuzz-optimizer --cases {index + 1} --seed {seed}\n"
                f"Program:\n{program}"
            )
    return CheckResult(cases, cases * 2, tuple(mismatches))
