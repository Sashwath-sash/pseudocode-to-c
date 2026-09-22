# Phase 2 improvement and related work

## Project contribution

The project adds a repeatable, optimization-focused differential check for its pseudocode compiler. A seeded generator creates valid, bounded programs containing expressions that exercise the current integer constant-folding and identity rules, along with branches and short loops. The harness translates each input twice, compiles both generated C programs with GCC, runs them, and compares standard output, standard error and exit status. A mismatch prints the seed, case number and pseudocode so the example can be reproduced.

This makes it easier to check whether the current optimizer changes a program's observed behavior as its rules evolve. It extends the project's existing hand-written examples and tests with generated cases aimed at the implemented optimization patterns.

## Related research

Kwon, J., Jang, B., Lee, J., and Heo, K. (2025). “Optimization-Directed Compiler Fuzzing for Continuous Translation Validation.” *Proceedings of the ACM on Programming Languages*, 9 (PLDI), Article 172. [https://doi.org/10.1145/3729275](https://doi.org/10.1145/3729275). The paper presents Optimuzz, which combines optimization-directed fuzzing with translation validation for LLVM and TurboFan.

Yang, X., Chen, Y., Eide, E., and Regehr, J. (2011). “Finding and Understanding Bugs in C Compilers.” *Proceedings of the 32nd ACM SIGPLAN Conference on Programming Language Design and Implementation*, 283-294. [https://doi.org/10.1145/1993498.1993532](https://doi.org/10.1145/1993498.1993532). Csmith generates C programs for compiler differential testing while avoiding undefined behavior.

## How this project relates

The implementation is a small educational adaptation of the testing idea: its generated inputs target this project's own optimization rules, and it compares the actual GCC-run results of optimized and unoptimized output. It does not implement Optimuzz's directed grey-box search, coverage-guided mutation, or formal translation validation. Differentially equal runs provide evidence for the tested inputs; they do not prove optimizer correctness.

## Initial result

With seed `20260923`, 30 generated programs produced 60 optimized/unoptimized executions. All observed outputs, errors and exit statuses matched. This is a preliminary result for the included generator and local compiler setup. Broader seeds, more cases, additional compiler versions and careful handling of C undefined behavior are needed before drawing stronger conclusions.

## Accurate novelty statement

Describe the contribution as an implemented project-specific improvement in optimizer validation, inspired by established compiler-testing research. Do not claim that differential testing or optimization-directed fuzzing was invented here, that this is a new research algorithm, or that the preliminary run proves correctness. Any paper or report should follow the course's authorship and AI-assistance disclosure requirements.
