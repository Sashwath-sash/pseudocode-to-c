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
            | IF condition THEN NL { statement }
                [ ELSE NL { statement } ] ENDIF NL
            | WHILE condition DO NL { statement } ENDWHILE NL
            | FOR identifier "=" expression TO expression
                [ STEP [ "+" | "-" ] integer ] DO NL
                { statement } ENDFOR NL
type        = INTEGER | REAL | CHAR
location    = identifier [ "[" expression "]" ]
condition   = expression ( "<" | ">" | "<=" | ">=" | "==" | "!=" ) expression
expression  = term { ( "+" | "-" ) term }
term        = factor { ( "*" | "/" | "%" ) factor }
factor      = ( "+" | "-" ) factor | "(" expression ")"
            | integer | real | character | location
```

The final physical newline is optional. Conditions require exactly one comparison; Boolean combinations are unsupported. Arithmetic associates left to right, with multiplication/division/remainder before addition/subtraction.

## Types and values

- INTEGER maps to C `int` and assumes a 32-bit target. Unsigned literal magnitudes are decimal `0..2147483647`; unary minus supplies negative values. The spelling `-2147483648` is currently rejected because its literal operand exceeds that range. Leading zeros remain decimal. Division truncates toward zero; remainder has the dividend's sign.
- REAL maps to `double`. Literals require digits on both sides of a decimal point, such as `2.5`. Exponents, NaN and infinity are not source literals. Nonfinite literal conversions are rejected. Very small literals can underflow to zero; runtime floating-point behavior and `%g` output follow C.
- CHAR is one ASCII character in single quotes. Accepted escapes are `\n`, `\t`, `\r`, `\0`, `\\`, `\'`, and `\"`. Character arithmetic is rejected. Character comparisons support equality/inequality only.
- Numeric tokens are limited to 1024 characters so excessive literals produce a diagnostic rather than a Python conversion failure.

Mixed INTEGER/REAL arithmetic produces REAL. INTEGER may be assigned to REAL; narrowing REAL to INTEGER and numeric/CHAR assignment are rejected. `%` requires two INTEGER operands.

## Declarations and arrays

Declarations take effect from their position in the block. Inner blocks may shadow outer names. Same-scope duplicate declarations are errors. Declarations do not initialize values.

Array sizes are literal integers from 1 through 100000. Indices are zero-based INTEGER expressions. Statically evaluable integer indices are checked; dynamic indices are not checked at runtime. Whole-array assignment/printing is unsupported.

## Loops

WHILE reevaluates its condition before each iteration. FOR requires an already-declared scalar INTEGER iterator and INTEGER start/end expressions. Bounds are evaluated before assigning the iterator, and the end is snapshotted even if the body changes its source variable. The end is inclusive. STEP defaults to 1 and must be a nonzero signed integer literal. Positive steps count upward and negative steps downward.

The iterator is incremented after every iteration, including the last. Keep that increment within the C int range. Assignment to the iterator in the body affects subsequent iterations. BREAK and CONTINUE are unsupported.

## Input, output and errors

PRINT emits one value and a newline using `%d`, `%g` or `%c`. READ uses typed C input conversion; character input skips whitespace. Invalid input or end of input makes the generated program return status 1. Out-of-range numeric input is not validated by a separate parser; provide values within the target type's range.

Lexical, syntax and semantic failures prevent C generation. Parser recovery can collect multiple errors at statement boundaries but does not guarantee a complete list. The CLI leaves any preexisting output file untouched on translation failure; check its exit status before using an old `.c` file.
