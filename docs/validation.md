# Validation

Local validation on 24 September 2026 used Windows, Python 3.13.2 and MinGW GCC 6.3.0.

```text
python -m unittest discover -s tests -v
Ran 83 tests in 13.969s
OK
```

There were no failures or skips. Seven execution regressions compile both optimized and unoptimized IR and compare each run with a specified expected output. Another test confirms the optimizer-check generator is deterministic for a given seed and creates compilable input.

Tests check source diagnostics and similar-name suggestions, precedence, nesting, scope, arrays, types, inclusive loops, pre/postconditions, constant-false contract detection, input/output, constant folding, generated temporary names, and preservation of source/runtime input files. Executable tests compile C with warnings enabled and run with a timeout. Contract integration tests verify successful runs and that failed guards stop before division or out-of-range array access.

## Reproduce

```sh
python --version
gcc --version
python -m unittest discover -s tests -v
python main.py examples/review1.pseudo --show-all --run
python main.py examples/sum_for.pseudo --run --input examples/input5.txt
python main.py examples/contracts_division.pseudo --run --input examples/division_valid.txt
python main.py examples/invalid.pseudo
```

The valid examples print 5, 15, and 5 respectively. The invalid example must fail translation with status 1.

GitHub Actions runs the suite with GCC on Linux using Python 3.10 and 3.13. The README badge links to current remote results. Local GCC-dependent cases are skipped if GCC is missing; inspect the skipped count.

## Optimization differential run

Command: `python main.py --fuzz-optimizer --cases 30 --seed 20260923`

Result: 30 generated pseudocode programs, 60 executions compared (optimized and unoptimized for each), zero observed output or exit-status mismatches. The generator deliberately includes constant arithmetic, unary operations, integer identities, nested expressions, branches, a bounded while loop and a short for loop. Reusing the same seed reproduces the same programs.

This is an initial experiment, not a correctness proof. The generated domain is intentionally small and avoids many dangerous values; it does not establish equivalence for every valid source program or test memory safety, integer overflow, or all compiler/runtime environments.

These tests establish behavior for covered cases, not a proof for every input. Uninitialized reads, unguarded dynamic out-of-bounds accesses, arithmetic overflow and invalid runtime numeric ranges remain outside validated program conditions. Compilation warnings are not currently treated as failures.
