#!/usr/bin/env python3
"""Black-box tests for rpn.py, derived from README.md and CLAUDE.md.

Each test runs rpn.py as a subprocess, feeds it input lines on stdin, and
checks what it prints.  Nothing here imports rpn.py, so the internals can be
rewritten freely.

Run:   python3 -m unittest -v test_rpn
One:   python3 -m unittest -v test_rpn.Arithmetic.test_subtract_is_y_minus_x
"""

import os
import re
import select
import signal
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RPN = os.path.join(HERE, "rpn.py")
TIMEOUT = 10  # seconds per run; guards against hangs (e.g. infinite include)

# A display line: a register label (t, z, y, x), then a currency value
# right-aligned in 20 columns: "x:             1,234.50".
DISPLAY_RE = re.compile(r"^[tzyx]: ( *-?\d{1,3}(?:,\d{3})*\.\d\d)$")
PROMPT_RE = re.compile(r"^(?:> ?)+")


def run(*lines, cwd=None, env=None):
    """Run rpn.py with the given input lines. Returns CompletedProcess."""
    data = "".join(line + "\n" for line in lines)
    return subprocess.run(
        [sys.executable, RPN],
        input=data,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=TIMEOUT,
    )


def display_lines(out):
    """All stack-display lines in the output, with any '> ' prompts removed."""
    lines = (PROMPT_RE.sub("", line) for line in out.splitlines())
    return [line for line in lines if DISPLAY_RE.match(line)]


def write(path, *lines):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write("".join(line + "\n" for line in lines))


class RpnTestCase(unittest.TestCase):
    def last_display(self, result):
        """The last 4-row stack display, as stripped strings (top is last)."""
        lines = display_lines(result.stdout)
        self.assertGreaterEqual(
            len(lines), 4,
            f"expected a 4-row stack display\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}")
        return [DISPLAY_RE.match(line).group(1).strip()
                for line in lines[-4:]]

    def assertStack(self, result, expected):
        self.assertEqual(self.last_display(result), expected)

    def assertTop(self, result, expected):
        self.assertEqual(self.last_display(result)[-1], expected)

    def assertClean(self, result):
        """Exited normally, with no Python traceback."""
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)

    def assertError(self, result, text="Error"):
        self.assertIn(text, result.stdout + result.stderr)


# ---------------------------------------------------------------- display

class Display(RpnTestCase):
    def test_push_shows_four_rows_top_last(self):
        self.assertStack(run("1"), ["0.00", "0.00", "0.00", "1.00"])

    def test_top_of_stack_printed_last(self):
        self.assertStack(run("1", "2", "3", "4", "5"),
                         ["2.00", "3.00", "4.00", "5.00"])

    def test_rows_labeled_t_z_y_x(self):
        lines = display_lines(run("1", "2", "3", "4").stdout)[-4:]
        self.assertEqual(lines, ["t:" + "1.00".rjust(21),
                                 "z:" + "2.00".rjust(21),
                                 "y:" + "3.00".rjust(21),
                                 "x:" + "4.00".rjust(21)])

    def test_rows_right_aligned_in_20_columns(self):
        result = run("1234.5")
        lines = display_lines(result.stdout)[-4:]
        self.assertEqual(len(lines), 4)
        for line in lines:
            self.assertEqual(len(line), len("x: ") + 20, repr(line))
        self.assertEqual(lines[-1], "x: " + "1,234.50".rjust(20))

    def test_display_after_each_entry(self):
        self.assertEqual(len(display_lines(run("1", "2", "3").stdout)), 12)

    def test_comma_separators(self):
        self.assertTop(run("1234567.5"), "1,234,567.50")

    def test_negative_with_commas(self):
        self.assertTop(run("0", "1234.5", "-"), "-1,234.50")

    def test_display_rounds_half_up(self):
        self.assertTop(run("2.665"), "2.67")
        self.assertTop(run("0.005"), "0.01")

    def test_negative_display_rounds_half_up_away_from_zero(self):
        self.assertTop(run("0", "2.665", "-"), "-2.67")


# ---------------------------------------------------------------- input

class Input(RpnTestCase):
    def test_integer(self):
        self.assertTop(run("42"), "42.00")

    def test_decimal(self):
        self.assertTop(run("3.14159"), "3.14")

    def test_negative_number(self):
        self.assertTop(run("-5"), "-5.00")

    def test_dollar_and_commas(self):
        self.assertTop(run("$1,234.56"), "1,234.56")

    def test_comma_placement_not_validated(self):
        self.assertTop(run("1,2,3"), "123.00")

    def test_unrecognized_input_is_error(self):
        result = run("1", "bogus")
        self.assertError(result)
        self.assertClean(result)

    def test_unrecognized_input_suggests_help(self):
        result = run("bogus")
        self.assertError(result, "unrecognized input: bogus")
        self.assertError(result, "enter 'h' for help")


# ---------------------------------------------------------------- stack

class Stack(RpnTestCase):
    def test_starts_filled_with_zeros(self):
        # Drop the one pushed value; everything left must be zero.
        self.assertStack(run("1", "d"), ["0.00"] * 4)

    def test_holds_32_entries_and_discards_bottom(self):
        # Push 1..33: the 1 falls off the bottom. Adding the whole stack
        # (32 entries plus the zero that pops in) gives 2+...+33 = 560.
        # An unlimited stack would give 561.
        lines = [str(i) for i in range(1, 34)] + ["+"] * 32
        self.assertTop(run(*lines), "560.00")

    def test_holds_all_32(self):
        lines = [str(i) for i in range(1, 33)] + ["+"] * 31
        self.assertTop(run(*lines), "528.00")  # 1+...+32

    def test_pop_brings_zeros_in_from_bottom(self):
        lines = [str(i) for i in range(1, 33)] + ["d"] * 31
        self.assertStack(run(*lines), ["0.00", "0.00", "0.00", "1.00"])


# ---------------------------------------------------------------- arithmetic

class Arithmetic(RpnTestCase):
    def test_add(self):
        self.assertStack(run("1", "2", "3", "+"),
                         ["0.00", "0.00", "1.00", "5.00"])

    def test_subtract_is_y_minus_x(self):
        self.assertTop(run("10", "4", "-"), "6.00")

    def test_multiply(self):
        self.assertTop(run("6", "7", "*"), "42.00")

    def test_divide_is_y_over_x(self):
        self.assertTop(run("10", "4", "/"), "2.50")

    def test_exact_decimal_not_float(self):
        # With floats, 0.1+0.2-0.3 is ~5.55e-17; scaled up it would show.
        self.assertTop(run("0.1", "0.2", "+", "0.3", "-",
                           "100000000000000000000", "*"), "0.00")

    def test_stack_keeps_full_precision(self):
        self.assertTop(run("1", "3", "/", "3", "*"), "1.00")

    def test_input_keeps_full_precision(self):
        self.assertTop(run("1.004", "1000", "*"), "1,004.00")

    def test_divide_by_zero_is_error(self):
        result = run("5", "0", "/")
        self.assertError(result)
        self.assertIn("divide by zero", result.stdout + result.stderr)
        self.assertClean(result)

    def test_divide_by_zero_leaves_stack_unchanged(self):
        # If "/" had popped anything, the swap would show something else.
        self.assertStack(run("1", "6", "0", "/", "swap"),
                         ["0.00", "1.00", "0.00", "6.00"])


# ---------------------------------------------------------------- commands

class Commands(RpnTestCase):
    def test_swap(self):
        self.assertStack(run("1", "2", "swap"),
                         ["0.00", "0.00", "2.00", "1.00"])

    def test_x_is_not_a_command(self):
        result = run("1", "2", "x", "d")
        self.assertError(result)
        self.assertStack(result, ["0.00", "0.00", "0.00", "1.00"])

    def test_percent_keeps_y(self):
        self.assertStack(run("200", "15", "%"),
                         ["0.00", "0.00", "200.00", "30.00"])

    def test_percent_markup(self):
        self.assertTop(run("200", "15", "%", "+"), "230.00")

    def test_percent_discount(self):
        self.assertStack(run("200", "15", "%", "-"),
                         ["0.00", "0.00", "0.00", "170.00"])

    def test_round_to_cents(self):
        self.assertTop(run("10", "3", "/", "r", "3", "*"), "9.99")

    def test_round_is_half_up_not_bankers(self):
        # 2.665 -> 2.67 (half-up); banker's rounding would give 2.66.
        self.assertTop(run("2.665", "r", "1000", "*"), "2,670.00")

    def test_round_negative_half_up(self):
        self.assertTop(run("0", "2.665", "-", "r", "1000", "*"), "-2,670.00")

    def test_drop(self):
        self.assertStack(run("1", "2", "d"), ["0.00", "0.00", "0.00", "1.00"])

    def test_clear(self):
        self.assertStack(run("1", "2", "3", "c"), ["0.00"] * 4)

    def test_clear_reaches_whole_stack(self):
        lines = [str(i) for i in range(1, 11)] + ["c"] + ["d"] * 6
        self.assertStack(run(*lines), ["0.00"] * 4)

    def test_comment_ignored(self):
        result = run("1", "# just a comment", "2", "+")
        self.assertTop(result, "3.00")
        self.assertNotIn("Error", result.stdout + result.stderr)

    def test_help_prints_something(self):
        result = run("h")
        self.assertClean(result)
        self.assertNotIn("Error", result.stdout + result.stderr)
        text = PROMPT_RE.sub("", result.stdout).strip()
        self.assertTrue(text, "help printed nothing")

    def test_help_does_not_change_stack(self):
        self.assertTop(run("1", "2", "h", "+"), "3.00")


# ---------------------------------------------------------------- quitting

class Quit(RpnTestCase):
    def test_q_quits(self):
        result = run("1", "q", "2")
        self.assertClean(result)
        self.assertTop(result, "1.00")
        self.assertNotIn("2.00", result.stdout)

    def test_quit_quits(self):
        result = run("1", "quit", "2")
        self.assertClean(result)
        self.assertTop(result, "1.00")
        self.assertNotIn("2.00", result.stdout)

    def test_eof_quits(self):
        result = run("1")
        self.assertClean(result)
        self.assertTop(result, "1.00")

    def test_empty_input_quits(self):
        result = run()
        self.assertClean(result)
        self.assertTrue(result.stdout.startswith(">"), "no prompt shown")

    def test_ctrl_c_quits(self):
        proc = subprocess.Popen([sys.executable, RPN], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            # Wait for the prompt so Python is up and waiting for input.
            ready, _, _ = select.select([proc.stdout], [], [], TIMEOUT)
            self.assertTrue(ready, "no prompt appeared")
            self.assertTrue(os.read(proc.stdout.fileno(), 1), "no prompt")
            proc.send_signal(signal.SIGINT)
            _, err = proc.communicate(timeout=TIMEOUT)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
        self.assertNotIn(b"Traceback", err)
        self.assertEqual(proc.returncode, 0)


# ---------------------------------------------------------------- errors

class Errors(RpnTestCase):
    def test_error_does_not_redisplay(self):
        # Displays after "5" and "0" only: 2 x 4 rows.
        result = run("5", "0", "/")
        self.assertError(result)
        self.assertEqual(len(display_lines(result.stdout)), 8)

    def test_error_then_continue(self):
        result = run("1", "bogus", "2", "+")
        self.assertError(result)
        self.assertTop(result, "3.00")


# ---------------------------------------------------------------- undo

class Undo(RpnTestCase):
    def test_undo_push(self):
        self.assertStack(run("1", "2", "u"), ["0.00", "0.00", "0.00", "1.00"])

    def test_undo_operation(self):
        self.assertStack(run("1", "2", "+", "u"),
                         ["0.00", "0.00", "1.00", "2.00"])

    def test_undo_is_repeatable(self):
        self.assertStack(run("1", "2", "3", "u", "u"),
                         ["0.00", "0.00", "0.00", "1.00"])

    def test_undo_clear(self):
        self.assertStack(run("1", "2", "c", "u"),
                         ["0.00", "0.00", "1.00", "2.00"])

    def test_undo_each_command_type(self):
        cases = {
            "swap": ["1", "2", "swap"],
            "%": ["1", "2", "%"],
            "r": ["1", "2.345", "r"],
            "d": ["1", "2", "d"],
            "-": ["1", "2", "-"],
            "*": ["1", "2", "*"],
            "/": ["1", "2", "/"],
        }
        for cmd, lines in cases.items():
            with self.subTest(cmd=cmd):
                before = self.last_display(run(*lines[:-1]))
                self.assertStack(run(*lines, "u"), before)

    def test_undo_skips_failed_command(self):
        self.assertStack(run("1", "2", "bogus", "u"),
                         ["0.00", "0.00", "0.00", "1.00"])

    def test_undo_skips_divide_by_zero(self):
        self.assertStack(run("1", "0", "/", "u"),
                         ["0.00", "0.00", "0.00", "1.00"])

    def test_undo_is_not_itself_undoable(self):
        # No redo: the second u undoes "2", not the first u.
        self.assertStack(run("1", "2", "3", "u", "u"),
                         ["0.00", "0.00", "0.00", "1.00"])

    def test_help_not_recorded(self):
        self.assertStack(run("1", "2", "h", "u"),
                         ["0.00", "0.00", "0.00", "1.00"])

    def test_undo_with_nothing_to_undo(self):
        result = run("u", "1")
        self.assertClean(result)
        self.assertStack(result, ["0.00", "0.00", "0.00", "1.00"])

    def test_1000_levels(self):
        # 1001 pushes; only the last 1000 can be undone, so "1" survives
        # even after extra undos.
        lines = [str(i) for i in range(1, 1002)] + ["u"] * 1005
        result = run(*lines)
        self.assertClean(result)
        self.assertStack(result, ["0.00", "0.00", "0.00", "1.00"])


# ---------------------------------------------------------------- @file

class Include(RpnTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)

    def run_here(self, *lines, env=None):
        return run(*lines, cwd=self.dir, env=env)

    def test_readme_markup_example(self):
        write(self.path("markup.rpn"),
              "# markup.rpn: add 15% to whatever is on top of the stack",
              "15", "%", "+")
        self.assertTop(self.run_here("200", "@markup.rpn"), "230.00")

    def test_blank_lines_and_comments_ignored(self):
        write(self.path("f.rpn"), "", "# comment", "1", "", "  ", "# x", "2",
              "+", "")
        result = self.run_here("@f.rpn")
        self.assertNotIn("Error", result.stdout + result.stderr)
        self.assertTop(result, "3.00")

    def test_display_once_at_end(self):
        write(self.path("f.rpn"), "1", "2", "3", "4")
        result = self.run_here("@f.rpn")
        self.assertEqual(len(display_lines(result.stdout)), 4)
        self.assertStack(result, ["1.00", "2.00", "3.00", "4.00"])

    def test_absolute_path(self):
        write(self.path("f.rpn"), "7")
        self.assertTop(run("@" + self.path("f.rpn")), "7.00")

    def test_relative_to_cwd_at_prompt(self):
        write(self.path("sub/f.rpn"), "7")
        self.assertTop(self.run_here("@sub/f.rpn"), "7.00")

    def test_nested_relative_to_including_file(self):
        write(self.path("sub/a.rpn"), "@b.rpn", "1", "+")
        write(self.path("sub/b.rpn"), "7")
        write(self.path("b.rpn"), "99")  # decoy in cwd: must not be used
        self.assertTop(self.run_here("@sub/a.rpn"), "8.00")

    def test_tilde_expanded(self):
        write(self.path("f.rpn"), "7")
        env = dict(os.environ, HOME=self.dir)
        self.assertTop(run("@~/f.rpn", env=env), "7.00")

    def test_deep_nesting_allowed(self):
        for i in range(10):
            write(self.path(f"f{i}.rpn"), f"@f{i + 1}.rpn")
        write(self.path("f10.rpn"), "7")
        self.assertTop(self.run_here("@f0.rpn"), "7.00")

    def test_self_include_is_error_not_hang(self):
        write(self.path("self.rpn"), "@self.rpn")
        result = self.run_here("@self.rpn")
        self.assertError(result)
        self.assertClean(result)

    def test_missing_file_is_error(self):
        result = self.run_here("1", "@nope.rpn")
        self.assertError(result)
        self.assertClean(result)
        self.assertTop(result, "1.00")

    def test_error_names_file_and_line(self):
        write(self.path("bad.rpn"), "# comment", "1", "0", "/")
        result = self.run_here("@bad.rpn")
        self.assertIn("bad.rpn:4: divide by zero",
                      result.stdout + result.stderr)
        self.assertClean(result)

    def test_error_names_innermost_location_only(self):
        write(self.path("outer.rpn"), "1", "@inner.rpn")
        write(self.path("inner.rpn"), "2", "bogus")
        result = self.run_here("@outer.rpn")
        output = result.stdout + result.stderr
        self.assertIn("inner.rpn:2:", output)
        self.assertNotIn("outer.rpn:2:", output)

    def test_error_aborts_whole_chain_without_rollback(self):
        write(self.path("outer.rpn"), "1", "@inner.rpn", "5")
        write(self.path("inner.rpn"), "2", "0", "/", "3")
        result = self.run_here("@outer.rpn")
        self.assertError(result)
        # 1, 2, 0 stay pushed; neither 3 nor 5 ran. Stack changed, so the
        # display is shown even though there was an error.
        self.assertStack(result, ["0.00", "1.00", "2.00", "0.00"])

    def test_each_included_command_undoable(self):
        write(self.path("markup.rpn"), "15", "%", "+")
        result = self.run_here("200", "@markup.rpn", "u")
        self.assertStack(result, ["0.00", "0.00", "200.00", "30.00"])
        result = self.run_here("200", "@markup.rpn", "u", "u")
        self.assertStack(result, ["0.00", "0.00", "200.00", "15.00"])
        result = self.run_here("200", "@markup.rpn", "u", "u", "u")
        self.assertStack(result, ["0.00", "0.00", "0.00", "200.00"])

    def test_q_in_file_quits(self):
        write(self.path("f.rpn"), "5", "q", "6")
        result = self.run_here("1", "@f.rpn", "7")
        self.assertClean(result)
        self.assertTop(result, "1.00")  # shown before the include
        self.assertNotIn("6.00", result.stdout)
        self.assertNotIn("7.00", result.stdout)


# ---------------------------------------------------------------- &function

class Functions(RpnTestCase):
    """&module.func[:n] calls a Python function; &name[:n] a Decimal method.

    n (default 1) values are taken from the stack, y before x, and replaced
    by the result.
    """

    def assertErrorUnchanged(self, *lines):
        """The last line is an error and the stack is left as it was."""
        before = self.last_display(run(*lines[:-1]))
        # Errors don't redisplay, so swap twice to show the stack again.
        result = run(*lines, "swap", "swap")
        self.assertError(result)
        self.assertClean(result)
        self.assertEqual(self.last_display(result), before)
        # Also not recorded for undo: u undoes the line before.
        if len(lines) >= 2:
            before_prev = self.last_display(run(*lines[:-2], "0"))
            self.assertEqual(
                self.last_display(run(*lines, "u", "0")), before_prev)

    def test_module_function(self):
        self.assertStack(run("7", "16", "&math.sqrt"),
                         ["0.00", "0.00", "7.00", "4.00"])

    def test_arity_suffix_y_before_x(self):
        self.assertStack(run("5", "2", "10", "&math.pow:2"),
                         ["0.00", "0.00", "5.00", "1,024.00"])

    def test_arity_zero(self):
        result = run("5", "&random.random:0")
        self.assertNotIn("Error", result.stdout + result.stderr)
        display = self.last_display(result)
        self.assertEqual(display[-2], "5.00")
        self.assertIn(display[-1], [f"{i / 100:.2f}" for i in range(101)])

    def test_int_result(self):
        self.assertTop(run("7.9", "&math.floor"), "7.00")

    def test_float_result_converted(self):
        # repr-based conversion: 0.1 stays 0.1, not 0.1000000000000000055...
        self.assertTop(run("1", "10", "&operator.truediv:2",
                           "1000000000000000000", "*"),
                       "100,000,000,000,000,000.00")

    def test_decimal_method(self):
        self.assertTop(run("100", "&log10"), "2.00")
        self.assertTop(run("1", "&exp", "&ln"), "1.00")

    def test_decimal_method_full_precision(self):
        # Decimal sqrt keeps 34 digits; a float would give ...095,100.00
        self.assertTop(run("2", "&sqrt", "1000000000000000000", "*"),
                       "1,414,213,562,373,095,048.80")

    def test_decimal_method_with_arity_order(self):
        # fma(self, other, third) = self * other + third
        self.assertStack(run("2", "3", "4", "&fma:3"),
                         ["0.00", "0.00", "0.00", "10.00"])

    def test_undo(self):
        self.assertStack(run("7", "16", "&math.sqrt", "u"),
                         ["0.00", "0.00", "7.00", "16.00"])

    def test_domain_error(self):
        self.assertErrorUnchanged("1", "-1", "&math.sqrt")

    def test_decimal_domain_error(self):
        self.assertErrorUnchanged("1", "-1", "&ln")

    def test_overflow_error(self):
        self.assertErrorUnchanged("1", "1000", "&math.exp")

    def test_infinite_result_is_error(self):
        self.assertErrorUnchanged("1", "0", "&ln")  # Decimal ln(0) = -inf

    def test_wrong_argument_count(self):
        self.assertErrorUnchanged("1", "2", "&math.pow")

    def test_unknown_module(self):
        self.assertErrorUnchanged("1", "2", "&nosuchmodule.f")

    def test_unknown_function(self):
        self.assertErrorUnchanged("1", "2", "&math.nosuch")

    def test_unknown_decimal_method(self):
        self.assertErrorUnchanged("1", "2", "&nosuch")

    def test_not_callable(self):
        self.assertErrorUnchanged("1", "2", "&math.pi")

    def test_bool_result_is_error(self):
        self.assertErrorUnchanged("1", "2", "&math.isfinite")

    def test_tuple_result_is_error(self):
        self.assertErrorUnchanged("1", "2", "&math.frexp")

    def test_complex_result_is_error(self):
        self.assertErrorUnchanged("1", "-1", "&cmath.sqrt")

    def test_bad_syntax(self):
        for cmd in ["&", "&:2", "&math.", "&math.sqrt:", "&math.sqrt:x",
                    "&math.sqrt:-1", "&math.sqrt:33", "&math..sqrt"]:
            with self.subTest(cmd=cmd):
                self.assertErrorUnchanged("1", "2", cmd)

    def test_in_command_file(self):
        with tempfile.TemporaryDirectory() as d:
            write(os.path.join(d, "f.rpn"), "2", "10", "&math.pow:2")
            self.assertTop(run("@f.rpn", cwd=d), "1,024.00")


# ---------------------------------------------------------------- big values

class BigValues(RpnTestCase):
    def test_huge_value_displays(self):
        result = run("1e40")
        self.assertClean(result)
        self.assertTop(result, "10,000,000,000,000,000,000,000,000,000,000,"
                               "000,000,000.00")

    def test_round_huge_value(self):
        result = run("1e40", "r")
        self.assertClean(result)
        self.assertNotIn("Error", result.stdout + result.stderr)

    def test_inf_and_nan_rejected(self):
        for text in ["inf", "-Infinity", "nan", "sNaN"]:
            with self.subTest(text=text):
                result = run("1", text, "2", "+")
                self.assertError(result)
                self.assertClean(result)
                self.assertTop(result, "3.00")


if __name__ == "__main__":
    unittest.main()
