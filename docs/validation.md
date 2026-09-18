# Validation

Local validation on 18 September 2026 used Windows, Python 3.13.2 and MinGW GCC 6.3.0.

```text
python -m unittest discover -s tests -v
Ran 71 tests in 13.151s
OK
```

There were no failures or skips. The original 51-test suite also passed before changes. The expanded suite adds 20 tests: 7 boundary tests, 5 CLI tests and 8 execution regressions. Seven execution regressions compile both optimized and unoptimized IR and compare each run with a specified expected output. The remaining execution regression checks invalid input handling.

Tests check source diagnostics, precedence, nesting, scope, arrays, types, inclusive loops, input/output, constant folding, generated temporary names, and preservation of source/runtime input files. Executable tests compile C with warnings enabled and run with a timeout.

## Reproduce

```sh
python --version
gcc --version
python -m unittest discover -s tests -v
python main.py examples/review1.pseudo --show-all --run
python main.py examples/sum_for.pseudo --run --input examples/input5.txt
python main.py examples/invalid.pseudo
```

The valid examples print 5 and 15 respectively. The invalid example must fail translation with status 1.

GitHub Actions runs the suite with GCC on Linux using Python 3.10 and 3.13. The README badge links to current remote results. Local GCC-dependent cases are skipped if GCC is missing; inspect the skipped count.

These tests establish behavior for covered cases, not a proof for every input. Uninitialized reads, dynamic out-of-bounds accesses, arithmetic overflow and invalid runtime numeric ranges remain outside validated program conditions. Compilation warnings are not currently treated as failures.
