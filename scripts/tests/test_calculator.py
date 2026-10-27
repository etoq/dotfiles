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

class ReverseEngineering(unittest.TestCase):
    def test_exact_size_conversions(self):
        for expression, answer in [
            ('1 byte to bits', '8 bits'), ('1 MiB to bits', '8388608 bits'),
            ('32 bits to bytes', '4 bytes'), ('1 bit to bytes', '0.125 bytes'),
            ('1 MB to KiB', '976.5625 KiB'), ('1 MiB to MB', '1.048576 MB'),
            ('1.5 KiB to B', '1536 B'), ('1,5 KiB to B', '1536 B'),
            ('8 Mb to MB', '1 MB'), ('1 B -> b', '8 b'),
            ('4096 байт в KiB', '4 KiB'), ('0x100 bytes to bits', '2048 bits'),
            ('(0x200 - 0x100) B to bits', '2048 bits')]:
            with self.subTest(expression=expression):
                self.assertEqual(calc.calculate_re(expression), answer)

    def test_integer_semantics(self):
        for expression, answer in [
            ('hex(255)', '0xff'), ('bin(10)', '0b1010'), ('oct(64)', '0o100'),
            ('u8(0x1234)', '0x34'), ('u32(-1)', '4294967295'),
            ('i32(0xffffffff)', '-1'), ('i8(128)', '-128'), ('i64(1 << 63)', '-9223372036854775808'),
            ('0x81 << 1', '0x102'), ('0b1010 ^ 0b0011', '9'),
            ('0xff & 0x0f', '0xf'), ('~0', '-1'), ('u32(~0)', '4294967295'),
            ('rol(0x81, 1, 8)', '0x3'), ('ror(0x81, 1, 8)', '0xc0'),
            ('rol(0x81, 8, 8)', '0x81'), ('rol(1, 63)', '9223372036854775808'),
            ('mask(12)', '4095'), ('popcount(u32(-1))', '32'),
            ('align(0x1001, 0x1000)', '0x2000'), ('align(20, 6)', '24'),
            ('i32(0xffffffff) to dec', '-1'), ('u8(-1) to hex', '0xff')]:
            with self.subTest(expression=expression):
                self.assertEqual(calc.calculate_re(expression), answer)

    def test_endian_and_strings(self):
        for expression, answer in [
            ('le(0x12345678, 4)', '78 56 34 12'), ('be(0x12345678, 4)', '12 34 56 78'),
            ('le(1, 4)', '01 00 00 00'), ('bswap32(0x12345678)', '0x78563412'),
            ('fromle("78 56 34 12") to hex', '0x12345678'),
            ('frombe("12 34 56 78") to hex', '0x12345678'),
            ('ascii("48 69 00 ff")', r'Hi\x00\xff'), ('utf8("Я")', 'd0 af')]:
            with self.subTest(expression=expression):
                self.assertEqual(calc.calculate_re(expression), answer)

    def test_reject_unsafe_or_ambiguous_input(self):
        for expression in ('u8(__import__("os"))', 'u8((1).__class__)', 'u8(True)',
                           'le(256, 1)', 'le(-1, 4)', 'bswap16(65536)', 'le(1, 1000)',
                           'rol(1, -1, 8)', 'ror(1, 1, 0)', 'rol(1, 1, 65)',
                           'mask(100000)', 'u8(1 << 100000)', 'u8(2 ** 4096)',
                           'fromle("0g")', 'popcount(-1)', '-1 byte to bits',
                           'align(1, 0)', 'u8(1 / 0)'):
            with self.subTest(expression=expression):
                with self.assertRaises((ValueError, SyntaxError, ArithmeticError)):
                    calc.calculate_re(expression)

    def test_qalc_fallback_and_integer_summary(self):
        for expression in ('2+2', '10 km to m', '1/3', 'sin(1)', '0xff+0x10'):
            self.assertIsNone(calc.calculate_re(expression))
        self.assertIn('DEC 255', calc.number_summary('0xff'))
        self.assertIn('BIN -0b1', calc.number_summary('−0x1'))
        self.assertEqual(calc.number_summary('78 56 34 12'), '')

    def test_rotations_exhaustively_for_8_bits(self):
        for value in range(256):
            for shift in range(9):
                rotated = calc.re_call('rol', [value, shift, 8])
                self.assertEqual(calc.re_call('ror', [rotated, shift, 8]), value)

    def test_endian_roundtrip(self):
        for width in (1, 2, 4, 8):
            for number in (0, 1, (1 << (width*8))-1):
                for order in ('le', 'be'):
                    encoded = calc.re_call(order, [number, width])
                    self.assertEqual(calc.re_call('from'+order, [encoded]), number)


if __name__ == '__main__':
    unittest.main()
