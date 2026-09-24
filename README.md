# Pseudocode to C

[![Compiler tests](https://github.com/Sashwath-sash/pseudocode-to-c/actions/workflows/tests.yml/badge.svg)](https://github.com/Sashwath-sash/pseudocode-to-c/actions/workflows/tests.yml)

A compiler project that translates a restricted pseudocode language into readable C. It demonstrates lexical analysis, recursive-descent parsing, an abstract syntax tree, scoped symbol tables, semantic checks, intermediate code, and simple optimization.

The compiler uses Python's standard library. GCC compiles and runs generated programs during validation.

## Quick start

Requirements: **Python 3.10+**; **GCC** on PATH for execution and integration tests. Translation alone does not require GCC.

```sh
git clone https://github.com/Sashwath-sash/pseudocode-to-c.git
cd pseudocode-to-c
python main.py examples/review1.pseudo --show-all --run
```

This example prints `5` after showing every compiler stage:

```text
BEGIN
DECLARE x AS INTEGER
SET x = 2 + 3
PRINT x
END
```

```text
Original IR      Optimized IR
t1 = 2 + 3      x = 5
x = t1          PRINT x
PRINT x
```

Generate C without running it:

```sh
python main.py examples/review1.pseudo --out build/review1.c
gcc build/review1.c -o build/review1
```

Run `./build/review1` on Linux/macOS, or `.\build\review1.exe` in Windows PowerShell. `RUN_REVIEW1.bat` also runs the stage-by-stage demo on Windows.

## Supported features

| Area | Implemented behavior |
| --- | --- |
| Types | INTEGER, REAL, CHAR; INTEGER-to-REAL widening |
| Statements | DECLARE, SET, READ, PRINT, REQUIRE, ENSURE |
| Expressions | Arithmetic, unary signs, parentheses and comparison conditions |
| Control flow | Nested IF/ELSE, WHILE, inclusive FOR with signed literal STEP |
| Arrays | Fixed-size, zero-based, one-dimensional arrays |
| Scope | Block-local declarations and shadowing |
| Diagnostics | Source locations, declaration/type checks, constant index checks, similar-name suggestions, constant-false contract checks and basic parser recovery |
| Automatic runtime guards | Variable `/` and `%` zero checks, dynamic array bounds, typed input validation and FOR iterator overflow |
| Contracts | Optional REQUIRE / ENSURE conditions checked statically when constant and at runtime otherwise |
| Optimization | Bounded integer constant folding and selected integer identities |
| Optimization validation | Seeded program generation and optimized/unoptimized execution comparison |
| Inspection | Tokens, AST, symbols, original IR, optimized IR and generated C |

Keywords are case-insensitive; identifiers are case-sensitive. Write one statement per line. REQUIRE checks a precondition at its position; ENSURE checks a postcondition at its position. See the [language reference](docs/language.md) for exact rules.

## Examples and commands

| Example | Command | Program output |
| --- | --- | --- |
| Constant folding | `python main.py examples/review1.pseudo --run` | `5` |
| Read and sum | `python main.py examples/sum_for.pseudo --run --input examples/input5.txt` | `15` |
| Arrays and nested blocks | `python main.py examples/nested.pseudo --run` | `12` |
| Real and character values | `python main.py examples/real_char.pseudo --run` | `3.5`, `A` |
| Descending loop | `python main.py examples/negative_step.pseudo --run` | `3`, `2`, `1` |
| Invalid source | `python main.py examples/invalid.pseudo` | Diagnostics; exit status 1 |
| Contract-checked division | `python main.py examples/contracts_division.pseudo --run --input examples/division_valid.txt` | `5` |
| Failed contract | `python main.py examples/contracts_division.pseudo --run --input examples/division_zero.txt` | Precondition diagnostic; exit status 1 |
| Contract-checked array access | `python main.py examples/contracts_array.pseudo --run --input examples/array_valid.txt` | `42` |
| Automatic division guard (no REQUIRE) | `python main.py examples/automatic_division.pseudo --run --input examples/division_valid.txt` | `5` |
| Automatic array guard (no REQUIRE) | `python main.py examples/automatic_array_bounds.pseudo --run --input examples/array_valid.txt` | `42` |
| Invalid typed input | `python main.py examples/read_integer.pseudo --run --input examples/input_not_number.txt` | Diagnostic; exit status 1 |

`--show-all` displays intermediate stages. `--out` chooses the output path; by default it is the source path with a `.c` extension. `--no-optimize` generates C directly from the original IR for comparison.

Run `python main.py --fuzz-optimizer --cases 30 --seed 20260923` to generate bounded test programs that target the current optimizer's rules, compile each both ways, and compare outputs and exit statuses. Matching runs are evidence for those generated inputs only, not a proof of correctness.

For a live demonstration, run `python main.py --interactive`, enter the pseudocode line by line, and finish with `END`. Interactive mode automatically displays the source, tokens, AST, symbol table, original IR, optimized IR, and generated C.

`--run` captures output and supplies the contents of `--input` as standard input. Without `--input`, standard input is empty; this mode does not prompt interactively. Compile and launch the C program separately for interactive input. Compilation and execution each have a three-second timeout.

## How it works

```text
Pseudocode -> Tokens -> AST -> Semantic analysis and symbols
           -> Structured IR -> Optimized IR -> C -> GCC compile/run
```

| Module | Responsibility |
| --- | --- |
| `pseudoc/lexer.py` | Token scanning and source locations |
| `pseudoc/parser.py`, `nodes.py` | Precedence parsing, block structure and AST |
| `pseudoc/semantic.py` | Lexical scopes, types and static diagnostics |
| `pseudoc/ir.py` | Typed three-address temporaries and structured control flow |
| `pseudoc/optimizer.py` | Integer folding and algebraic simplification |
| `pseudoc/cgen.py` | C generation from IR |
| `pseudoc/compiler.py`, `main.py` | Translation API, CLI and GCC execution |

The backend consumes IR. Loop conditions are reevaluated each iteration; FOR bounds are evaluated before the loop. Optimization does not assume mutable source variables are constants.

## Tests

```sh
python -m unittest discover -s tests -v
```

The current local suite contains 93 passing tests with no skips on Windows using Python 3.13.2 and MinGW GCC 6.3.0. Tests cover translation stages, rejected programs, automatic runtime guards, contracts, generated C execution, file handling, reproducible generation, and optimized/unoptimized equivalence against expected outputs. See [validation details](docs/validation.md).

GitHub Actions runs the same suite on Linux with Python 3.10 and 3.13. Without GCC locally, integration tests are explicitly skipped; a frontend-only run is not full execution validation.

## Scope and remaining work

This is a working educational prototype for a defined language subset. It does not accept arbitrary English. Functions, strings, logical AND/OR, multidimensional arrays, pointers, structures, dynamic allocation, a GUI, an interpreter and machine-code generation are not implemented. Contract conditions use the existing single-comparison grammar; combine checks as separate REQUIRE statements instead of using AND/OR.

The compiler automatically guards variable division/remainder by zero, dynamic array indices, invalid or out-of-range typed input, and overflow of the FOR iterator's next value. These checks require no REQUIRE/ENSURE statements. Explicit contracts remain optional for program-specific conditions. General arithmetic overflow (for example, `x * y` or `x + y`) and uninitialized variables are not automatically detected; very deep expressions or blocks may exceed Python's recursion limit.

The [Phase 1 comparison](docs/phase1-alignment.md) separates the report's design from the implemented subset. See the [runnable examples](docs/examples.md) for contracts, runtime checks and contextual typo suggestions. The [novelty and research note](docs/novelty-and-related-work.md) describes the implemented extensions and their limits. This repository continues the existing Review 1 prototype with validation fixes, regression tests and project documentation.
