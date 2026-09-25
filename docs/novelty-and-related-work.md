# Phase 2 improvement and related work

## Automatic rule-based runtime safety checks

Generated C now inserts guards based on the operations found in the source, without requiring the pseudocode author to write conditions: variable `/` and `%` divisors are checked for zero (including the `INT_MIN / -1` integer overflow case); dynamic array indices are checked before reads and writes; and the next FOR-iterator value is checked before incrementing. A failed check prints a pseudocode line diagnostic and returns status 1. READ uses direct typed conversion without separate input-range checks. These are targeted rules, not a general proof of program safety: arbitrary INTEGER addition, subtraction or multiplication overflow and uninitialized reads remain unchecked.

## Optional contracts and contextual diagnostic hints

The restricted language now supports `REQUIRE condition` and `ENSURE condition`. These statements check a precondition or postcondition at their source position. Conditions the analyzer can prove false from bounded numeric constants are rejected before C generation; value-dependent conditions become C runtime guards that report the contract kind and pseudocode line, then exit with status 1. Conditions use the language's existing one-comparison grammar, and checks must be placed after values are initialized and before any operation they protect.

For an undeclared name, semantic analysis compares it with identifiers visible in the current lexical scopes and includes a similar-name suggestion when the match is strong enough. The compiler never edits the source automatically. This is a small deterministic heuristic, not machine learning or an intent-recovery system.

Runnable examples cover automatic safety checks that need no contract, optional guarded integer division, a bounded factorial, and a misspelled identifier suggestion in [docs/examples.md](examples.md). These checks use explicit rules over known operations rather than generalized dataflow range analysis. Their contribution is a practical extension to this restricted pseudocode-to-C compiler, not a claim that runtime guards or compiler instrumentation are new concepts. Limits include no Boolean AND/OR, no general automatic range analysis, no definite-assignment analysis, and no inferred repairs for arbitrary logic errors.

## Project contribution

The project adds a repeatable, optimization-focused differential check for its pseudocode compiler. A seeded generator creates valid, bounded programs containing expressions that exercise the current integer constant-folding, bitwise-folding and identity rules, along with branches and short loops. The harness translates each input twice, compiles both generated C programs with GCC, runs them, and compares standard output, standard error and exit status. A mismatch prints the seed, case number and pseudocode so the example can be reproduced.

This makes it easier to check whether the current optimizer changes a program's observed behavior as its rules evolve. It extends the project's existing hand-written examples and tests with generated cases aimed at the implemented optimization patterns.

## Related research

Kwon, J., Jang, B., Lee, J., and Heo, K. (2025). “Optimization-Directed Compiler Fuzzing for Continuous Translation Validation.” *Proceedings of the ACM on Programming Languages*, 9 (PLDI), Article 172. [https://doi.org/10.1145/3729275](https://doi.org/10.1145/3729275). The paper presents Optimuzz, which combines optimization-directed fuzzing with translation validation for LLVM and TurboFan.

Yang, X., Chen, Y., Eide, E., and Regehr, J. (2011). “Finding and Understanding Bugs in C Compilers.” *Proceedings of the 32nd ACM SIGPLAN Conference on Programming Language Design and Implementation*, 283-294. [https://doi.org/10.1145/1993498.1993532](https://doi.org/10.1145/1993498.1993532). Csmith generates C programs for compiler differential testing while avoiding undefined behavior.

## How this project relates

The implementation is a small educational adaptation of the testing idea: its generated inputs target this project's own optimization rules, and it compares the actual GCC-run results of optimized and unoptimized output. It does not implement Optimuzz's directed grey-box search, coverage-guided mutation, or formal translation validation. Differentially equal runs provide evidence for the tested inputs; they do not prove optimizer correctness.

## Initial result

With seed `20260925`, 30 generated programs produced 60 optimized/unoptimized executions. All observed outputs, errors and exit statuses matched. This result applies to the included generator and local compiler setup; it does not establish correctness for all inputs or compiler environments.

## Accurate novelty statement

Describe the contribution as an implemented project-specific improvement in optimizer validation, inspired by established compiler-testing research. Do not claim that differential testing or optimization-directed fuzzing was invented here, that this is a new research algorithm, or that the preliminary run proves correctness. Any paper or report should follow the course's authorship and AI-assistance disclosure requirements.
