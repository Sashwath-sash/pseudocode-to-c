# Language reference

Programs begin with `BEGIN` and finish with `END`. Every statement and block opener/closer occupies its own line. Blank lines and `#` or `//` comments are allowed. Keywords are case-insensitive. Identifiers are case-sensitive ASCII letters, digits and underscores, cannot begin with a digit, and cannot be C-reserved names recognized by the checker.

## Grammar

`NL` denotes a newline, `[]` optional syntax, and `{}` repetition. Blank/comment lines are ignored between statements.

```text
program     = BEGIN NL { statement } END [NL]
statement   = DECLARE identifier [ "[" integer "]" ] AS type NL
            | SET location "=" expression NL
            | READ location NL
            | PRINT expression NL
            | REQUIRE condition NL
            | ENSURE condition NL
            | IF condition THEN NL { statement }
                [ ELSE NL { statement } ] ENDIF NL
            | WHILE condition DO NL { statement } ENDWHILE NL
            | FOR identifier "=" expression TO expression
                [ STEP [ "+" | "-" ] integer ] DO NL
                { statement } ENDFOR NL
            | BREAK NL | CONTINUE NL
type        = INTEGER | REAL | CHAR | STRING
location    = identifier [ "[" expression "]" ]
condition   = expression ( "<" | ">" | "<=" | ">=" | "==" | "!=" ) expression
expression  = bit_or
bit_or      = bit_xor { "|" bit_xor }
bit_xor     = bit_and { "^" bit_and }
bit_and     = shift { "&" shift }
shift       = additive { ( "<<" | ">>" ) additive }
additive    = term { ( "+" | "-" ) term }
term        = factor { ( "*" | "/" | "%" ) factor }
factor      = ( "+" | "-" | "~" ) factor | "(" expression ")"
            | integer | real | character | string | location
```

The final physical newline is optional. Conditions require exactly one comparison; Boolean combinations are unsupported. Operators follow the precedence shown by the grammar. Arithmetic and bitwise binary operators associate left to right.

`REQUIRE condition` checks a precondition at that point in execution. `ENSURE condition` checks a postcondition at that point. Both use the existing single-comparison condition grammar. Put a REQUIRE before the operation it protects and an ENSURE after the operation whose result it checks. Multiple checks can be written on separate lines; `AND` and `OR` are not supported. The compiler rejects a contract it can prove is always false and emits a runtime diagnostic for conditions that depend on values. A failed runtime contract prints its kind and source line to standard error and exits with status 1. Contracts do not initialize variables or automatically guard later operations; ensure every referenced value has already been assigned or read.

## Types and values

- INTEGER maps to C `int` and assumes a 32-bit target. Unsigned literal magnitudes are decimal `0..2147483647`; unary minus supplies negative values. The spelling `-2147483648` is currently rejected because its literal operand exceeds that range. Leading zeros remain decimal. Division truncates toward zero; remainder has the dividend's sign.
- REAL maps to `double`. Literals require digits on both sides of a decimal point, such as `2.5`. Exponents, NaN and infinity are not source literals. Nonfinite literal conversions are rejected. Very small literals can underflow to zero; runtime floating-point behavior and `%g` output follow C.
- CHAR is one ASCII character in single quotes. Accepted escapes are `\n`, `\t`, `\r`, `\0`, `\\`, `\'`, and `\"`. Character arithmetic is rejected. Character comparisons support equality/inequality only.
- STRING is an ASCII, double-quoted value stored in a fixed 256-byte buffer and initialized to the empty string. It can be assigned, read, printed and compared with `==` or `!=`. A string holds at most 255 characters; READ accepts one whitespace-delimited token. Supported escapes are `\n`, `\t`, `\r`, `\\` and `\"`. Concatenation, embedded NUL, Unicode text, and STRING arrays are unsupported.
- Numeric tokens are limited to 1024 characters so excessive literals produce a diagnostic rather than a Python conversion failure.

Mixed INTEGER/REAL arithmetic produces REAL. INTEGER may be assigned to REAL; narrowing REAL to INTEGER and numeric/CHAR assignment are rejected. `%` requires two INTEGER operands.

## Declarations and arrays

Declarations take effect from their position in the block. Inner blocks may shadow outer names. Same-scope duplicate declarations are errors. Declarations do not initialize values.

Array sizes are literal integers from 1 through 100000. Indices are zero-based INTEGER expressions. Statically evaluable integer indices are checked during translation; dynamic indices receive an automatic runtime bounds check before each read or write and stop the generated program with a source-line diagnostic if out of range. Whole-array assignment/printing is unsupported.

## Loops

A direct scalar `WHILE` comparison is placed in the generated C `while` header. Conditions needing setup, such as a dynamic array access with a bounds check, keep that setup at the top of the generated loop so it runs again on every iteration.

WHILE reevaluates its condition before each iteration. FOR requires an already-declared scalar INTEGER iterator and INTEGER start/end expressions. Bounds are evaluated before assigning the iterator, and the end is snapshotted even if the body changes its source variable. The end is inclusive. STEP defaults to 1 and must be a nonzero signed integer literal. Positive steps count upward and negative steps downward.

The iterator is incremented after every iteration, including the last. Before incrementing, generated C checks whether the next value fits the target C `int`; overflow produces a runtime diagnostic and status 1 instead of signed-overflow behavior. Assignment to the iterator in the body affects subsequent iterations. Other INTEGER arithmetic is not generally overflow-checked.

BREAK exits the nearest WHILE or FOR loop. CONTINUE skips the rest of the current iteration and tests the loop condition again. In a FOR loop, generated C advances the iterator before starting the next iteration. BREAK and CONTINUE outside a loop are semantic errors.

INTEGER bitwise operators are `&`, `|`, `^`, `~`, `<<`, and `>>`. Bitwise operations require INTEGER operands. Shift counts are checked at runtime and must be smaller than the target `unsigned int` bit width. Shifts operate on the unsigned integer representation and convert the result back to INTEGER; behavior is validated with GCC on the supported 32-bit-int target.

## Input, output and errors

PRINT emits one value and a newline using `%d`, `%g`, `%c` or `%s`. READ uses typed `scanf` conversion for INTEGER, REAL and CHAR. STRING input is read as one whitespace-delimited token into a temporary buffer and rejected if it exceeds 255 characters. Failed conversion or end of input reports a source-line diagnostic. Numeric READ does not perform separate range or token validation; provide a value that fits the declared type.

Variable `/` and `%` operations have automatic runtime checks for a zero divisor. INTEGER division/remainder also checks the `INT_MIN / -1` overflow case. These guards do not require explicit contracts. General arithmetic overflow, division precision concerns for REAL, and uninitialized variable use are not checked automatically.

Lexical, syntax and semantic failures prevent C generation. When an undeclared identifier closely resembles a name visible in the current scope, the semantic diagnostic suggests that name; it never changes source automatically. Parser recovery can collect multiple errors at statement boundaries but does not guarantee a complete list. The CLI leaves any preexisting output file untouched on translation failure; check its exit status before using an old `.c` file.
