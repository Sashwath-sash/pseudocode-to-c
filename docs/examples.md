# Runnable examples

Run these from the project root. Each `--out` path keeps generated C under `build/`.

## Automatic safety checks (no written conditions required)

The compiler inserts checks from the operations in the pseudocode. These examples contain no `REQUIRE` or `ENSURE` statements.

```sh
python main.py examples/automatic_division.pseudo --run --input examples/division_valid.txt
```

Input `20 4` prints `5`. With `20 0`, the generated guard reports division/remainder by zero and exits with status 1 before C evaluates the operation.

```sh
python main.py examples/automatic_array_bounds.pseudo --run --input examples/array_valid.txt
```

Input `2 42` prints `42`. Try index `3` or `-1` to see the automatic bounds diagnostic. Both array reads and writes are guarded.

`automatic_for_overflow.pseudo` demonstrates a FOR iterator that reaches the maximum signed 32-bit INTEGER value. The loop body prints that value; the compiler-generated check then reports that the next increment would overflow and exits with status 1.

## Contract-checked division

`REQUIRE` is a precondition checked where it appears. The zero check comes before the remainder and division operations; the second condition restricts this example to exact integer division. `ENSURE` checks the result after the assignment.

```text
BEGIN
DECLARE dividend AS INTEGER
DECLARE divisor AS INTEGER
DECLARE quotient AS INTEGER
READ dividend
READ divisor
REQUIRE divisor != 0
REQUIRE dividend % divisor == 0
SET quotient = dividend / divisor
ENSURE quotient * divisor == dividend
PRINT quotient
END
```

Valid input `20 4` prints `5`:

```sh
python main.py examples/contracts_division.pseudo --out build/contracts_division.c --run --input examples/division_valid.txt
```

Input `20 0` fails the first precondition before `%` or `/` is evaluated. The program prints a precondition diagnostic to standard error and exits with status 1:

```sh
python main.py examples/contracts_division.pseudo --out build/contracts_division.c --run --input examples/division_zero.txt
```

## Factorial with a bounded input contract

The preconditions reject negative input and values above 12, keeping the result within the supported signed 32-bit INTEGER range. The postcondition checks the result after the loop.

```sh
python main.py examples/contracts_factorial.pseudo --out build/factorial.c --run --input examples/factorial_5.txt
```

Input `5` prints `120`.

## Optional runtime array-index contract

The fixed array has three elements. The two preconditions are separate because the language does not support Boolean AND. They guard a variable index before the generated C reads or writes the array.

```sh
python main.py examples/contracts_array.pseudo --out build/contracts_array.c --run --input examples/array_valid.txt
```

Input `2 42` prints `42`. Replacing the index input with `3` causes the second precondition to fail before the array access.

## Contextual typo suggestion

Phase 1 already reports undeclared identifiers. The semantic diagnostic now also suggests a similar name when one is visible in the current scope. It never edits the source automatically.

```sh
python main.py examples/suggest_typo.pseudo --out build/typo.c
```

Expected diagnostic includes: `undeclared identifier 'totl'; did you mean 'total'?`

## Contract diagnostics

A contract that is provably false from constants is rejected before C generation:

```text
BEGIN
REQUIRE 1 == 2
END
```

Value-dependent contracts become runtime checks. Keep each condition to one comparison, initialize values before checking them, and place each contract at the point where it should be enforced.
