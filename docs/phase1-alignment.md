# Phase 1 design and implementation

This comparison uses `Pseudocode_to_C_Phase1_FINAL.docx` and the source from `Pseudocode_to_C_Review1_Code.zip`. The report is the design baseline; code and tests describe current behavior. The report itself is maintained separately.

| Report proposal | Current implementation |
| --- | --- |
| Lexing, parsing and AST | Implemented in Python |
| Symbol table and semantic checks | Implemented with lexical block scopes |
| Simple intermediate representation | Typed temporaries and structured blocks |
| Folding and algebraic simplification | Conservative INTEGER rules; no general floating-point folding |
| C generation and GCC validation | Implemented and exercised by executable tests |
| Declaration/assignment/PRINT prototype | Includes the report's `2 + 3` example |
| IF/ELSE, WHILE, FOR, READ and 1-D arrays | Present in the supplied Review 1 source and retained here |
| Expression after STEP in simplified grammar | Narrower implementation: signed integer literal only |
| Error detection and basic recovery | Stage-specific errors and statement-boundary synchronization |
| Optional functions after the core | Not implemented |

Runtime bounds checking, definite-assignment analysis, overflow protection, richer input validation and broader error recovery remain possible improvements. No GUI, interpreter, advanced optimizer or native-code backend is claimed.
