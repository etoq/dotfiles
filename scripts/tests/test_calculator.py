"""Expression formatting and qalc output; never read the user's history/clipboard."""
import importlib.machinery
import importlib.util
from pathlib import Path
import shutil
import subprocess
import unittest

path = Path(__file__).resolve().parents[1] / 'local-bin/tiffany-calculator'
loader = importlib.machinery.SourceFileLoader('calculator_test', str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
calc = importlib.util.module_from_spec(spec)
loader.exec_module(calc)


class Formatting(unittest.TestCase):
    def test_two_hex_operands_use_hex_output(self):
        for expression in ('0x100 + 0x20', '0x100 - 0x20', '0X100 ^ 0X10',
                           '(0xff & 0x0f) + 0x10'):
            self.assertEqual(calc.output_expression(expression), '('+expression+') to hex')

    def test_explicit_output_wins(self):
        for expression in ('0x100+0x20 to dec', '(0x100-0x20) to bin',
                           '0x100+0x20 to base 8', '0x100+0x20 -> dec'):
            self.assertEqual(calc.output_expression(expression), expression)

    def test_regular_expressions_and_quoted_text_unchanged(self):
        for expression in ('21*2', '0xff+1', '10 km to m', 'hex(1)+(2)',
                           '"0x10 0x20"', '0x10 + "0x20"', 'my0x10 + my0x20'):
            self.assertEqual(calc.output_expression(expression), expression)

    def test_outer_hex_keeps_python_style_meaning(self):
        self.assertEqual(calc.output_expression('hex(0x10 - 0x20)'), '(0x10 - 0x20) to hex')
        self.assertEqual(calc.output_expression('hex(16)'), '(16) to hex')
        self.assertEqual(calc.output_expression('hex(16'), 'hex(16')

    def test_plain_clipboard_values(self):
        self.assertEqual(calc.clipboard_text('−0x10'), '-0x10')
        self.assertEqual(calc.clipboard_text(' 0x5641F7476000\n'), '0x5641F7476000')

    @unittest.skipUnless(shutil.which('qalc'), 'qalc not installed')
    def test_real_backend_hex_and_conversion_regressions(self):
        for expression, expected in [
                ('0x5641f74a5000 - 0x2f000', '0x5641F7476000'),
                ('0x10 + 0x20', '0x30'), ('0x10 - 0x20', '−0x10'),
                ('0X100 - 0X10', '0xF0'), ('0x10+0x20 to dec', '48'),
                ('hex(16)', '0x10'), ('21*2', '42')]:
            with self.subTest(expression=expression):
                actual = subprocess.check_output(
                    ['qalc', '-t', '-m', '3000', '--', calc.output_expression(expression)],
                    text=True, timeout=8).strip()
                self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
