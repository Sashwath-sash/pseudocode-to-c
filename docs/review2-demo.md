# Review 2 live demo

Open Command Prompt and run:

```bat
cd /d "%USERPROFILE%\Desktop\Pseudocode-to-C"
python main.py --interactive
```

Type these lines, pressing Enter after each. The translator starts when you enter `END`:

```text
BEGIN
DECLARE x AS INTEGER
SET x = 2 + 3
PRINT x
END
```

Point out the source, tokens, AST, symbol table, original IR, optimized IR, and generated C. In this example, the optimizer folds `2 + 3` to `5`, and the C contains `printf` for the result. Interactive mode translates; it does not run the generated C.

To show the Phase 2 additions without typing a long program:

```bat
python main.py examples\phase2_features.pseudo --show-all
```

This example uses a STRING, INTEGER bitwise operations, a FOR loop, IF conditions, CONTINUE, and BREAK. The full input is in [phase2_features.pseudo](../examples/phase2_features.pseudo). For a shorter view of its generated C, omit `--show-all` and open `examples\phase2_features.c` after translation.

To demonstrate functional execution when GCC is available:

```bat
python main.py examples\phase2_features.pseudo --run
```

Expected program output:

```text
Student:
Mira
Combined mask:
7
Lowest two bits:
3
```

The translator handles the documented restricted grammar. It does not translate free-form English or support functions, multidimensional arrays, or logical AND/OR. See [language.md](language.md) for syntax and limits.
