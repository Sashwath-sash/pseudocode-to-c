"""End-to-end checks for compound conditions and two-dimensional arrays."""
import shutil
import unittest

from main import compile_and_run
from pseudoc.compiler import compile_pseudocode
from pseudoc.errors import TranslationError


class NewFeaturesTests(unittest.TestCase):
    def run_source(self, source: str):
        result = compile_pseudocode(source)
        self.assertIn('int main(void)', result.c_source)
        if shutil.which('gcc'):
            return compile_and_run(result.c_source)
        self.skipTest('GCC is required to execute generated C')

    def test_short_circuit_and_or_not(self):
        source = '''BEGIN
DECLARE a AS INTEGER
DECLARE b AS INTEGER
SET a = 0
SET b = 0
IF a != 0 AND 10 / a > 1 THEN
    PRINT 99
ELSE
    PRINT 1
ENDIF
IF a == 0 OR 10 / a > 1 THEN
    PRINT 2
ENDIF
IF NOT (a == 1 OR b == 1) THEN
    PRINT 3
ENDIF
END
'''
        out, err, code = self.run_source(source)
        self.assertEqual((out, err, code), ('1\n2\n3\n', '', 0))

    def test_condition_precedence_and_parentheses(self):
        source = '''BEGIN
DECLARE a AS INTEGER
SET a = 2
IF (a + 1) == 3 AND NOT a == 0 OR a == 4 THEN
    PRINT 7
ENDIF
END
'''
        self.assertEqual(self.run_source(source)[0], '7\n')

    def test_two_dimensional_array(self):
        source = '''BEGIN
DECLARE grid[2][3] AS INTEGER
DECLARE row AS INTEGER
DECLARE col AS INTEGER
SET row = 1
SET col = 2
SET grid[row][col] = 7
PRINT grid[row][col]
END
'''
        result = compile_pseudocode(source)
        self.assertIn('int grid[2][3];', result.c_source)
        self.assertEqual(self.run_source(source), ('7\n', '', 0))

    def test_second_dimension_runtime_bounds(self):
        source = '''BEGIN
DECLARE grid[2][3] AS INTEGER
DECLARE row AS INTEGER
DECLARE col AS INTEGER
SET row = 1
SET col = 3
PRINT grid[row][col]
END
'''
        out, err, code = self.run_source(source)
        self.assertEqual(out, '')
        self.assertNotEqual(code, 0)
        self.assertIn('Array index out of bounds', err)

    def test_missing_second_index_is_error(self):
        source = 'BEGIN\nDECLARE grid[2][3] AS INTEGER\nPRINT grid[1]\nEND\n'
        with self.assertRaisesRegex(TranslationError, 'requires two indices'):
            compile_pseudocode(source)

    def test_typed_function_with_call_and_return(self):
        source = '''FUNCTION larger(a AS INTEGER, b AS INTEGER) RETURNS INTEGER
IF a > b THEN
    RETURN a
ELSE
    RETURN b
ENDIF
ENDFUNCTION
BEGIN
DECLARE answer AS INTEGER
SET answer = larger(5, 8)
PRINT answer
END
'''
        result = compile_pseudocode(source)
        self.assertIn('int larger(int a, int b)', result.c_source)
        self.assertEqual(self.run_source(source), ('8\n', '', 0))

    def test_function_argument_type_error(self):
        source = '''FUNCTION twice(x AS INTEGER) RETURNS INTEGER
RETURN x * 2
ENDFUNCTION
BEGIN
PRINT twice(1.5)
END
'''
        with self.assertRaisesRegex(TranslationError, 'requires INTEGER'):
            compile_pseudocode(source)

    def test_function_must_return_on_all_paths(self):
        source = '''FUNCTION maybe(x AS INTEGER) RETURNS INTEGER
IF x > 0 THEN
    RETURN x
ENDIF
ENDFUNCTION
BEGIN
PRINT maybe(2)
END
'''
        with self.assertRaisesRegex(TranslationError, 'RETURN on every path'):
            compile_pseudocode(source)

    def test_recursive_function(self):
        source = '''FUNCTION factorial(n AS INTEGER) RETURNS INTEGER
IF n <= 1 THEN
    RETURN 1
ELSE
    RETURN n * factorial(n - 1)
ENDIF
ENDFUNCTION
BEGIN
PRINT factorial(5)
END
'''
        self.assertEqual(self.run_source(source), ('120\n', '', 0))


if __name__ == '__main__':
    unittest.main()
