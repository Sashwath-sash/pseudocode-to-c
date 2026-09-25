# Validation

Local validation on 25 September 2026 used Windows, Python 3.13.2 and MinGW GCC 6.3.0.

```text
python -m unittest discover -s tests -v
OK
```

The local suite completed without failures. With GCC available, its checks include translation and selected generated-C cases for strings, bitwise operations, loop control, contracts and existing compiler behavior. The result applies to these checks; it is not a claim that every possible program has been tested.

## Reproduce

```sh
python --version
gcc --version
python -m unittest discover -s tests -v
python main.py examples/review1.pseudo --show-all --run
python main.py examples/sum_for.pseudo --run --input examples/input5.txt
python main.py examples/phase2_features.pseudo --show-all
python main.py examples/automatic_division.pseudo --run --input examples/division_valid.txt
python main.py examples/invalid.pseudo
```

The Review 1, sum, and automatic division examples print 5, 15, and 5 respectively when run. The Phase 2 command translates to C without running it. The invalid example must fail translation with status 1.

GitHub Actions runs the suite with GCC on Linux using Python 3.10 and 3.13. The README badge links to current remote results. Local GCC-dependent cases are skipped if GCC is missing; inspect the skipped count.

The Phase 2 example is translated with `python main.py examples/phase2_features.pseudo --show-all`. The command displays the compiler stages and generated C; it does not execute that C program.

## Optimizer comparison

Command: `python main.py --fuzz-optimizer --cases 30 --seed 20260925`

Result: 30 generated programs and 60 optimized/unoptimized executions; no output, error or exit-status differences were observed. Cases include bounded arithmetic, bitwise operators, branches and short loops. The result applies only to this generated input set and local compiler environment; it is not a proof of correctness for every valid program.

Uninitialized reads and overflow in general arithmetic expressions remain outside validated program conditions. Compilation warnings are not treated as test failures.
