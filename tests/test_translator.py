"""Executable integration tests; gcc output verifies semantics of generated C."""
import shutil
import unittest
from pathlib import Path

from pseudoc.compiler import compile_pseudocode
from pseudoc.errors import TranslationError
from pseudoc.astview import render as render_ast
from main import compile_and_run

ROOT = Path(__file__).resolve().parents[1]


def program(lines: str):
    return 'BEGIN\n' + lines.strip() + '\nEND\n'


class FrontendTests(unittest.TestCase):
    def test_review1_pipeline_has_actual_intermediate_results(self):
        result = compile_pseudocode((ROOT / 'examples/review1.pseudo').read_text())
        self.assertTrue(any(t.kind == 'DECLARE' for t in result.tokens))
        self.assertIn('Program(statements=', repr(result.ast))
        self.assertEqual([(s.name, s.dtype) for s in result.symbols], [('x', 'INTEGER')])
        self.assertIn('t1 = 2 + 3', result.ir_text())
        self.assertIn('x = t1', result.ir_text())
        self.assertIn('x = 5', result.optimized_ir_text())
        self.assertNotIn('t1 =', result.optimized_ir_text())
        self.assertIn('x = 5;', result.c_source)

    def test_keywords_case_insensitive(self):
        c = compile_pseudocode('begin\ndeclare X as integer\nset X = 9\nprint X\nend\n').c_source
        self.assertIn('int X;', c)
        self.assertIn('printf("%d\\n", X);', c)

    def test_comment_and_blank_lines(self):
        src = 'BEGIN\n# comment\n\nDECLARE a AS INTEGER // comment\nSET a = 2\nPRINT a\nEND\n'
        self.assertIn('a = 2;', compile_pseudocode(src).c_source)

    def test_precedence_and_parentheses(self):
        c = compile_pseudocode(program('DECLARE x AS INTEGER\nSET x = (2 + 3) * 4\nPRINT x')).c_source
        self.assertIn('x = 20;', c)

    def test_syntax_recovery_collects_multiple_errors(self):
        src = program('DECLARE a AS INTEGER\nSET a =\nPRINT\nSET a = 1')
        with self.assertRaises(TranslationError) as context:
            compile_pseudocode(src)
        self.assertGreaterEqual(len(context.exception.issues), 2)
        self.assertTrue(all(x.stage == 'Syntax' for x in context.exception.issues))

    def test_rejects_unexpected_character(self):
        with self.assertRaisesRegex(TranslationError, 'Lexical error at line 2'):
            compile_pseudocode(program('PRINT @'))

    def test_rejects_bad_char_literal(self):
        with self.assertRaisesRegex(TranslationError, 'invalid character literal'):
            compile_pseudocode(program("PRINT 'abc'"))

    def test_rejects_python_only_char_escape(self):
        with self.assertRaisesRegex(TranslationError, 'unsupported C character escape'):
            compile_pseudocode(program("PRINT '\\u0041'"))

    def test_rejects_missing_endif(self):
        with self.assertRaisesRegex(TranslationError, 'unclosed block'):
            compile_pseudocode(program('IF 1 == 1 THEN\nPRINT 1'))

    def test_rejects_undeclared_variable(self):
        with self.assertRaisesRegex(TranslationError, "undeclared identifier 'x'"):
            compile_pseudocode(program('PRINT x'))

    def test_undeclared_variable_suggests_similar_visible_name(self):
        with self.assertRaisesRegex(TranslationError, "did you mean 'total'"):
            compile_pseudocode(program('DECLARE total AS INTEGER\nSET totl = 4'))

    def test_constant_false_precondition_is_rejected(self):
        with self.assertRaisesRegex(TranslationError, 'REQUIRE condition is always false'):
            compile_pseudocode(program('REQUIRE 1 == 2'))

    def test_constant_false_postcondition_is_rejected(self):
        with self.assertRaisesRegex(TranslationError, 'ENSURE condition is always false'):
            compile_pseudocode(program('ENSURE 3 < 2'))

    def test_contracts_appear_in_ast_and_ir(self):
        result = compile_pseudocode(program('DECLARE x AS INTEGER\nREAD x\nREQUIRE x >= 0\nENSURE x < 10'))
        self.assertIn('Precondition: x >= 0', render_ast(result.ast))
        self.assertIn('REQUIRE', result.ir_text())
        self.assertIn('ENSURE', result.ir_text())

    def test_rejects_duplicate_in_same_scope(self):
        with self.assertRaisesRegex(TranslationError, 'duplicate declaration'):
            compile_pseudocode(program('DECLARE a AS INTEGER\nDECLARE a AS CHAR'))

    def test_rejects_char_to_int_assignment(self):
        with self.assertRaisesRegex(TranslationError, 'cannot assign CHAR to INTEGER'):
            compile_pseudocode(program("DECLARE x AS INTEGER\nSET x = 'A'"))

    def test_rejects_real_to_integer_assignment(self):
        with self.assertRaisesRegex(TranslationError, 'cannot assign REAL to INTEGER'):
            compile_pseudocode(program('DECLARE x AS INTEGER\nSET x = 1.5'))

    def test_rejects_array_without_index(self):
        with self.assertRaisesRegex(TranslationError, 'requires an index'):
            compile_pseudocode(program('DECLARE a[2] AS INTEGER\nPRINT a'))

    def test_rejects_indexing_scalar(self):
        with self.assertRaisesRegex(TranslationError, 'is not an array'):
            compile_pseudocode(program('DECLARE a AS INTEGER\nPRINT a[0]'))

    def test_rejects_real_array_index(self):
        with self.assertRaisesRegex(TranslationError, 'array index must be INTEGER'):
            compile_pseudocode(program('DECLARE a[2] AS INTEGER\nPRINT a[1.5]'))

    def test_rejects_literal_array_out_of_bounds(self):
        with self.assertRaisesRegex(TranslationError, 'outside 0..1'):
            compile_pseudocode(program('DECLARE a[2] AS INTEGER\nPRINT a[2]'))

    def test_rejects_zero_sized_array(self):
        with self.assertRaisesRegex(TranslationError, 'array size must be'):
            compile_pseudocode(program('DECLARE a[0] AS INTEGER'))

    def test_rejects_bad_for_iterator(self):
        with self.assertRaisesRegex(TranslationError, 'FOR iterator must'):
            compile_pseudocode(program('DECLARE i AS REAL\nFOR i = 1 TO 3 DO\nPRINT i\nENDFOR'))

    def test_rejects_zero_for_step(self):
        with self.assertRaisesRegex(TranslationError, 'STEP cannot be zero'):
            compile_pseudocode(program('DECLARE i AS INTEGER\nFOR i = 1 TO 3 STEP 0 DO\nPRINT i\nENDFOR'))

    def test_rejects_non_integer_for_bound(self):
        with self.assertRaisesRegex(TranslationError, 'FOR bounds must be INTEGER'):
            compile_pseudocode(program('DECLARE i AS INTEGER\nFOR i = 1.5 TO 3 DO\nPRINT i\nENDFOR'))

    def test_rejects_modulo_with_real(self):
        with self.assertRaisesRegex(TranslationError, 'remainder % requires'):
            compile_pseudocode(program('DECLARE x AS REAL\nSET x = 2.5 % 2'))

    def test_rejects_constant_zero_denominator(self):
        with self.assertRaisesRegex(TranslationError, 'division or remainder by zero'):
            compile_pseudocode(program('PRINT 8 / (3 - 3)'))

    def test_rejects_reserved_C_identifier(self):
        for name in ('int', 'main', 'printf', 'scanf', 'EOF', '__hidden'):
            with self.subTest(name=name), self.assertRaisesRegex(TranslationError, 'reserved'):
                compile_pseudocode(program(f'DECLARE {name} AS INTEGER'))

    def test_nested_scope_allows_shadowing(self):
        src = program('DECLARE x AS INTEGER\nSET x = 1\nIF x == 1 THEN\nDECLARE x AS CHAR\nSET x = \'Z\'\nPRINT x\nENDIF\nPRINT x')
        result = compile_pseudocode(src)
        self.assertEqual(len(result.symbols), 2)
        self.assertNotEqual(result.symbols[0].scope, result.symbols[1].scope)

    def test_rejects_reference_after_scope_exit(self):
        src = program('IF 1 == 1 THEN\nDECLARE local AS INTEGER\nSET local = 1\nENDIF\nPRINT local')
        with self.assertRaisesRegex(TranslationError, 'undeclared identifier'):
            compile_pseudocode(src)

    def test_user_variable_t1_does_not_collide_with_generated_temp(self):
        src = program('DECLARE t1 AS INTEGER\nSET t1 = 5\nPRINT t1 + 2')
        result = compile_pseudocode(src)
        self.assertIn('t2 = t1 + 2', result.ir_text())


@unittest.skipUnless(shutil.which('gcc'), 'GCC is required to verify executable C')
class GCCIntegrationTests(unittest.TestCase):
    def run_pseudo(self, source: str, stdin: str = ''):
        result = compile_pseudocode(source)
        out, err, exit_code = compile_and_run(result.c_source, stdin)
        self.assertEqual(exit_code, 0, msg=err)
        self.assertFalse(err, msg=err)
        return out, result

    def test_review1_sample(self):
        out, _ = self.run_pseudo((ROOT / 'examples/review1.pseudo').read_text())
        self.assertEqual(out, '5\n')

    def test_contract_checked_division_valid_input(self):
        src = (ROOT / 'examples/contracts_division.pseudo').read_text()
        stdin = (ROOT / 'examples/division_valid.txt').read_text()
        for enabled in (True, False):
            with self.subTest(optimized=enabled):
                result = compile_pseudocode(src, optimize_ir=enabled)
                out, err, status = compile_and_run(result.c_source, stdin)
                self.assertEqual((out, err, status), ('5\n', '', 0))
                self.assertIn('Precondition failed at pseudocode line', result.c_source)
                self.assertIn('Postcondition failed at pseudocode line', result.c_source)

    def test_contract_checked_division_zero_divisor_stops_before_division(self):
        result = compile_pseudocode((ROOT / 'examples/contracts_division.pseudo').read_text())
        out, err, status = compile_and_run(result.c_source, (ROOT / 'examples/division_zero.txt').read_text())
        self.assertEqual(out, '')
        self.assertIn('Precondition failed at pseudocode line 7', err)
        self.assertEqual(status, 1)

    def test_contract_checked_factorial(self):
        out, _ = self.run_pseudo((ROOT / 'examples/contracts_factorial.pseudo').read_text(), '5\n')
        self.assertEqual(out, '120\n')

    def test_contract_checked_factorial_rejects_negative_input(self):
        result = compile_pseudocode((ROOT / 'examples/contracts_factorial.pseudo').read_text())
        out, err, status = compile_and_run(result.c_source, '-1\n')
        self.assertEqual(out, '')
        self.assertIn('Precondition failed at pseudocode line 6', err)
        self.assertEqual(status, 1)

    def test_contracts_guard_dynamic_array_access(self):
        out, _ = self.run_pseudo((ROOT / 'examples/contracts_array.pseudo').read_text(), '2 42\n')
        self.assertEqual(out, '42\n')

    def test_contracts_stop_out_of_range_dynamic_array_access(self):
        result = compile_pseudocode((ROOT / 'examples/contracts_array.pseudo').read_text())
        out, err, status = compile_and_run(result.c_source, '3 42\n')
        self.assertEqual(out, '')
        self.assertIn('Precondition failed at pseudocode line 8', err)
        self.assertEqual(status, 1)

    def test_variable_division_by_zero_is_guarded_automatically(self):
        src = program('DECLARE a AS INTEGER\nDECLARE b AS INTEGER\nREAD a\nREAD b\nPRINT a / b')
        out, err, status = compile_and_run(compile_pseudocode(src).c_source, '10 0')
        self.assertEqual(out, '')
        self.assertIn('Division or remainder by zero at pseudocode line 6', err)
        self.assertEqual(status, 1)

    def test_variable_division_without_written_contract_succeeds(self):
        src = (ROOT / 'examples/automatic_division.pseudo').read_text()
        result = compile_pseudocode(src)
        self.assertNotIn('REQUIRE', src)
        self.assertNotIn('ENSURE', src)
        self.assertEqual(compile_and_run(result.c_source, '20 4'), ('5\n', '', 0))

    def test_variable_remainder_by_zero_is_guarded_automatically(self):
        src = program('DECLARE a AS INTEGER\nDECLARE b AS INTEGER\nREAD a\nREAD b\nPRINT a % b')
        out, err, status = compile_and_run(compile_pseudocode(src).c_source, '10 0')
        self.assertEqual(out, '')
        self.assertIn('Division or remainder by zero at pseudocode line 6', err)
        self.assertEqual(status, 1)

    def test_integer_min_divided_by_negative_one_is_guarded(self):
        src = program('DECLARE a AS INTEGER\nDECLARE b AS INTEGER\nREAD a\nREAD b\nPRINT a / b')
        out, err, status = compile_and_run(compile_pseudocode(src).c_source, '-2147483648 -1')
        self.assertEqual(out, '')
        self.assertIn('Integer division/remainder overflow at pseudocode line 6', err)
        self.assertEqual(status, 1)

    def test_dynamic_array_read_has_automatic_bounds_guard(self):
        src = program('DECLARE a[3] AS INTEGER\nDECLARE i AS INTEGER\nREAD i\nPRINT a[i]')
        out, err, status = compile_and_run(compile_pseudocode(src).c_source, '3')
        self.assertEqual(out, '')
        self.assertIn('Array index out of bounds at pseudocode line 5', err)
        self.assertEqual(status, 1)

    def test_dynamic_array_read_and_write_without_written_contract_succeeds(self):
        src = (ROOT / 'examples/automatic_array_bounds.pseudo').read_text()
        result = compile_pseudocode(src)
        self.assertNotIn('REQUIRE', src)
        self.assertNotIn('ENSURE', src)
        self.assertEqual(compile_and_run(result.c_source, '2 42'), ('42\n', '', 0))

    def test_dynamic_array_write_has_automatic_bounds_guard(self):
        src = program('DECLARE a[3] AS INTEGER\nDECLARE i AS INTEGER\nREAD i\nSET a[i] = 42\nPRINT a[0]')
        out, err, status = compile_and_run(compile_pseudocode(src).c_source, '-1')
        self.assertEqual(out, '')
        self.assertIn('Array index out of bounds at pseudocode line 5', err)
        self.assertEqual(status, 1)

    def test_for_iterator_overflow_is_reported_instead_of_undefined_behavior(self):
        src = program('DECLARE i AS INTEGER\nFOR i = 2147483647 TO 2147483647 DO\nPRINT i\nENDFOR')
        out, err, status = compile_and_run(compile_pseudocode(src).c_source)
        self.assertEqual(out, '2147483647\n')
        self.assertIn('FOR iterator overflow at pseudocode line 3', err)
        self.assertEqual(status, 1)

    def test_sum_for_loop_and_read(self):
        out, _ = self.run_pseudo((ROOT / 'examples/sum_for.pseudo').read_text(), '5\n')
        self.assertEqual(out, '15\n')

    def test_sum_for_zero_iterations(self):
        out, _ = self.run_pseudo((ROOT / 'examples/sum_for.pseudo').read_text(), '0\n')
        self.assertEqual(out, '0\n')

    def test_nested_arrays_while_if(self):
        out, _ = self.run_pseudo((ROOT / 'examples/nested.pseudo').read_text())
        self.assertEqual(out, '12\n')

    def test_real_char(self):
        out, _ = self.run_pseudo((ROOT / 'examples/real_char.pseudo').read_text())
        self.assertEqual(out, '3.5\nA\n')

    def test_for_negative_step(self):
        out, _ = self.run_pseudo((ROOT / 'examples/negative_step.pseudo').read_text())
        self.assertEqual(out, '3\n2\n1\n')

    def test_if_else_true(self):
        src = program('DECLARE x AS INTEGER\nSET x = 8\nIF x > 5 THEN\nPRINT 1\nELSE\nPRINT 2\nENDIF')
        out, _ = self.run_pseudo(src)
        self.assertEqual(out, '1\n')

    def test_if_else_false(self):
        src = program('DECLARE x AS INTEGER\nSET x = 3\nIF x > 5 THEN\nPRINT 1\nELSE\nPRINT 2\nENDIF')
        out, _ = self.run_pseudo(src)
        self.assertEqual(out, '2\n')

    def test_nested_scoping(self):
        src = program("DECLARE x AS INTEGER\nSET x = 1\nIF x == 1 THEN\nDECLARE x AS CHAR\nSET x = 'Z'\nPRINT x\nENDIF\nPRINT x")
        out, _ = self.run_pseudo(src)
        self.assertEqual(out, 'Z\n1\n')

    def test_for_step_two(self):
        src = program('DECLARE i AS INTEGER\nFOR i = 1 TO 5 STEP 2 DO\nPRINT i\nENDFOR')
        out, _ = self.run_pseudo(src)
        self.assertEqual(out, '1\n3\n5\n')

    def test_for_no_iterations_negative(self):
        src = program('DECLARE i AS INTEGER\nFOR i = 1 TO 3 STEP -1 DO\nPRINT i\nENDFOR')
        out, _ = self.run_pseudo(src)
        self.assertEqual(out, '')

    def test_integer_division_truncates_toward_zero(self):
        src = program('PRINT -7 / 3\nPRINT -7 % 3')
        out, result = self.run_pseudo(src)
        self.assertEqual(out, '-2\n-1\n')
        self.assertIn('PRINT -2', result.optimized_ir_text())

    def test_int_algebraic_identity_does_not_assume_variable_constant(self):
        src = program('DECLARE x AS INTEGER\nREAD x\nPRINT x + 0\nPRINT x * 1\nPRINT x / 1')
        out, result = self.run_pseudo(src, '7\n')
        self.assertEqual(out, '7\n7\n7\n')
        self.assertNotIn('t1 = x + 0', result.optimized_ir_text())

    def test_real_read_and_print(self):
        src = program('DECLARE x AS REAL\nREAD x\nPRINT x')
        out, _ = self.run_pseudo(src, '2.5\n')
        self.assertEqual(out, '2.5\n')

    def test_char_read_print(self):
        src = program('DECLARE x AS CHAR\nREAD x\nPRINT x')
        out, _ = self.run_pseudo(src, ' Z\n')
        self.assertEqual(out, 'Z\n')

    def test_array_read(self):
        src = program('DECLARE a[2] AS INTEGER\nREAD a[1]\nPRINT a[1]')
        out, _ = self.run_pseudo(src, '42\n')
        self.assertEqual(out, '42\n')

    def test_comparison_on_char(self):
        src = program("DECLARE ch AS CHAR\nSET ch = 'A'\nIF ch == 'A' THEN\nPRINT 1\nELSE\nPRINT 0\nENDIF")
        out, _ = self.run_pseudo(src)
        self.assertEqual(out, '1\n')

    def test_constant_folding_not_copied_across_assignments(self):
        src = program('DECLARE x AS INTEGER\nSET x = 1\nSET x = 7\nPRINT x')
        out, _ = self.run_pseudo(src)
        self.assertEqual(out, '7\n')

    def test_bound_computed_once_before_loop(self):
        src = program('DECLARE i AS INTEGER\nDECLARE n AS INTEGER\nSET n = 3\nFOR i = 1 TO n DO\nSET n = 1\nPRINT i\nENDFOR')
        out, _ = self.run_pseudo(src)
        self.assertEqual(out, '1\n2\n3\n')

    def test_parentheses_change_order(self):
        out, _ = self.run_pseudo(program('PRINT 2 + 3 * 4\nPRINT (2 + 3) * 4'))
        self.assertEqual(out, '14\n20\n')

    def test_print_char_escape(self):
        out, _ = self.run_pseudo(program("PRINT '\\n'"))
        self.assertEqual(out, '\n\n')

    def test_print_array_with_variable_index(self):
        src = program('DECLARE a[2] AS INTEGER\nDECLARE i AS INTEGER\nSET i = 1\nSET a[i] = 17\nPRINT a[i]')
        out, _ = self.run_pseudo(src)
        self.assertEqual(out, '17\n')

    def test_decimal_literals_with_leading_zeros(self):
        # C normally interprets 010 as octal; pseudocode defines decimal literals.
        out, _ = self.run_pseudo(program('PRINT 010\nPRINT 09'))
        self.assertEqual(out, '10\n9\n')

    def test_int_max_constant_folding_does_not_overflow(self):
        # No incorrect compile-time folding into 2147483648, which C int cannot hold.
        result = compile_pseudocode(program('PRINT 2147483647 + 1'))
        self.assertNotIn('PRINT 2147483648', result.optimized_ir_text())


if __name__ == '__main__':
    unittest.main()
