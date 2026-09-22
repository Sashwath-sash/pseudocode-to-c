"""Boundary, command-line and optimized/unoptimized execution regressions."""
import contextlib
import io
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from main import cli, compile_and_run
from pseudoc.compiler import compile_pseudocode
from pseudoc.errors import TranslationError
from pseudoc.optimizer_check import generate_case


def program(body):
    return f'BEGIN\n{body}\nEND\n'


class BoundaryTests(unittest.TestCase):
    def test_optimizer_generated_case_is_seed_reproducible(self):
        first = generate_case(20260923, 4)
        self.assertEqual(first, generate_case(20260923, 4))
        self.assertNotEqual(first, generate_case(20260923, 5))
        self.assertIn('x * 1', first)
        self.assertIn('STEP +1', first)
        compile_pseudocode(first)

    def test_non_ascii_numeric_literal(self):
        with self.assertRaisesRegex(TranslationError, 'Lexical error'):
            compile_pseudocode(program('PRINT \u0661.\u0665'))

    def test_excessively_long_integer_is_diagnostic(self):
        with self.assertRaisesRegex(TranslationError, 'numeric literal exceeds'):
            compile_pseudocode(program('PRINT ' + '9' * 5000))

    def test_nonfinite_real_literal(self):
        with self.assertRaisesRegex(TranslationError, 'finite double range'):
            compile_pseudocode(program('PRINT ' + '9' * 400 + '.0'))

    def test_no_optimization_preserves_ir(self):
        result = compile_pseudocode(program('PRINT 2 + 3'), optimize_ir=False)
        self.assertIs(result.ir_before, result.ir_after)
        self.assertIn('2 + 3', result.c_source)

    def test_explicit_positive_step(self):
        compile_pseudocode(program('DECLARE i AS INTEGER\nFOR i = 1 TO 3 STEP +2 DO\nPRINT i\nENDFOR'))

    def test_rejects_trailing_source(self):
        with self.assertRaises(TranslationError):
            compile_pseudocode('BEGIN\nEND\nPRINT 2\n')

    def test_rejects_expression_step(self):
        with self.assertRaises(TranslationError):
            compile_pseudocode(program('DECLARE i AS INTEGER\nFOR i = 1 TO 3 STEP 1+1 DO\nENDFOR'))


class CLITests(unittest.TestCase):
    def invoke(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli(args)
        return code, out.getvalue(), err.getvalue()

    def test_preserves_source_when_output_aliases_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'source.pseudo'
            text = program('PRINT 5')
            src.write_text(text)
            code, _, err = self.invoke([str(src), '--out', str(src)])
            self.assertEqual(code, 1)
            self.assertIn('must differ', err)
            self.assertEqual(src.read_text(), text)

    def test_preserves_runtime_input_when_output_aliases_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, data = Path(tmp) / 'source.pseudo', Path(tmp) / 'input.txt'
            src.write_text(program('PRINT 5'))
            data.write_text('17\n')
            code, _, err = self.invoke([str(src), '--out', str(data), '--input', str(data), '--run'])
            self.assertEqual(code, 1)
            self.assertIn('runtime input', err)
            self.assertEqual(data.read_text(), '17\n')

    def test_invalid_utf8_is_readable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'bad.pseudo'
            src.write_bytes(b'\xff')
            code, _, err = self.invoke([str(src)])
            self.assertEqual(code, 1)
            self.assertIn('ERROR:', err)
            self.assertFalse(src.with_suffix('.c').exists())

    def test_semantic_error_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'bad.pseudo'
            src.write_text(program('PRINT missing'))
            code, _, err = self.invoke([str(src)])
            self.assertEqual(code, 1)
            self.assertIn('undeclared', err)
            self.assertFalse(src.with_suffix('.c').exists())

    def test_show_all_and_no_optimize(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'source.pseudo'
            src.write_text(program('PRINT 2 + 3'))
            code, out, err = self.invoke([str(src), '--show-all', '--no-optimize'])
            self.assertEqual((code, err), (0, ''))
            for label in ('TOKENS', 'AST', 'SYMBOL TABLE', 'INTERMEDIATE REPRESENTATION', 'GENERATED C'):
                self.assertIn(label, out)
            self.assertIn('2 + 3', src.with_suffix('.c').read_text())

    def test_interactive_displays_every_compiler_stage(self):
        typed = iter(('BEGIN', 'DECLARE x AS INTEGER', 'SET x = 2 + 3', 'PRINT x', 'END'))
        with patch('builtins.input', side_effect=typed):
            code, out, err = self.invoke(['--interactive'])
        self.assertEqual((code, err), (0, ''))
        for label in (
            'SOURCE PSEUDOCODE', 'TOKENS', 'AST', 'SYMBOL TABLE',
            'INTERMEDIATE REPRESENTATION', 'OPTIMIZED IR', 'GENERATED C'
        ):
            self.assertIn(f'=== {label} ===', out)
        self.assertIn('x = 5;', out)


@unittest.skipUnless(shutil.which('gcc'), 'GCC is required')
class ExecutionRegressions(unittest.TestCase):
    def assert_execution(self, body, expected, stdin=''):
        # Both pipelines must agree with an independently specified result.
        for enabled in (True, False):
            with self.subTest(optimized=enabled):
                result = compile_pseudocode(program(body), optimize_ir=enabled)
                self.assertEqual(compile_and_run(result.c_source, stdin), (expected, '', 0))

    def test_while_condition_recomputed(self):
        self.assert_execution('DECLARE x AS INTEGER\nSET x = 0\nWHILE x + 1 < 4 DO\nPRINT x\nSET x = x + 1\nENDWHILE', '0\n1\n2\n')

    def test_computed_array_indices(self):
        self.assert_execution('DECLARE a[3] AS INTEGER\nSET a[1+1] = 9\nPRINT a[3-1]', '9\n')

    def test_real_arithmetic_and_widening(self):
        self.assert_execution('DECLARE x AS REAL\nSET x = 2\nPRINT x / 4\nPRINT -(2.5 + 1.0)', '0.5\n-3.5\n')

    def test_shadowing_inside_while(self):
        self.assert_execution('DECLARE x AS INTEGER\nSET x = 0\nWHILE x < 1 DO\nSET x = x + 1\nDECLARE x AS CHAR\nSET x = \'A\'\nPRINT x\nENDWHILE\nPRINT x', 'A\n1\n')

    def test_for_bound_identity_snapshot(self):
        self.assert_execution('DECLARE i AS INTEGER\nDECLARE n AS INTEGER\nSET n = 3\nFOR i = 1 TO n + 0 STEP +1 DO\nSET n = 0\nPRINT i\nENDFOR', '1\n2\n3\n')

    def test_negative_remainder_signs(self):
        self.assert_execution('PRINT 7 / -3\nPRINT 7 % -3\nPRINT -7 / -3\nPRINT -7 % -3', '-2\n1\n2\n-1\n')

    def test_invalid_read_returns_failure(self):
        result = compile_pseudocode(program('DECLARE x AS INTEGER\nREAD x\nPRINT x'))
        self.assertEqual(compile_and_run(result.c_source, 'hello'), ('', '', 1))

    def test_empty_program(self):
        self.assert_execution('', '')
