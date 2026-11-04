# rpn

A small command-line RPN (Reverse Polish Notation) calculator for currency math.

```
python3 rpn.py
```

## How it works

Type a number or a command and press Enter. After each entry the calculator
shows the top four stack entries, with the **top of the stack printed last**:

```
> 1
                0.00
                0.00
                0.00
                1.00
```

The stack holds 32 entries and starts out filled with zeros. Pushing onto a
full stack discards the bottom entry.

## Commands

| Input        | Action                                                        |
|--------------|---------------------------------------------------------------|
| *number*     | Push onto the stack. Commas and a leading `$` are ignored (`$1,234.56`). |
| `+ - * /`    | Replace the top two entries with the result (`y op x`).       |
| `x`          | Exchange the top two entries.                                 |
| `%`          | Percent: replaces the top with `y × x / 100`, keeping `y`.    |
| `r`          | Round the top entry to the nearest cent.                      |
| `d`          | Drop the top entry.                                           |
| `c`          | Clear the whole stack.                                        |
| `u`          | Undo the last command (repeatable, up to 1000 levels).        |
| `&`*mod.f*[`:`*n*] | Call a Python function on the top *n* entries (default 1), e.g. `&math.log`, `&math.pow:2` (see below). |
| `&`*f*[`:`*n*] | Call a `Decimal` method, e.g. `&sqrt`, `&ln`, `&log10`, `&exp`. |
| `@`*file*    | Run the commands in *file*, then return to the prompt (see below). |
| `#` ...      | Comment; ignored.                                             |
| `h`          | Show a summary of the commands.                               |
| `q`, Ctrl-D  | Quit.                                                         |

## Currency mode

Numbers are exact decimals (no floating-point surprises like
`0.1 + 0.2 = 0.30000000000000004`).

The display rounds to cents (half-up) and adds comma separators, but the
stack keeps full precision, like a financial calculator. So
`1 3 / 3 *` shows `1.00`, not `0.99`. Use `r` when you want the value
itself rounded to cents, e.g. for an amount that will actually be paid:
`10 3 / r 3 *` shows `9.99`.

## Percent examples

`%` leaves the base amount on the stack, so markups and discounts take one
more keystroke:

| Keys              | Result   |
|-------------------|----------|
| `200 15 %`        | `30.00` (15% of 200; 200 is still below it) |
| `200 15 % +`      | `230.00` (200 plus 15%)  |
| `200 15 % -`      | `170.00` (200 less 15%)  |

## Functions

`&` calls a Python function by name, so any function that takes and returns
numbers works without being built in:

| Keys                 | Result |
|----------------------|--------|
| `16 &math.sqrt`      | `4.00` |
| `2 10 &math.pow:2`   | `1,024.00` (2¹⁰: *y* is the first argument, *x* the second) |
| `&random.random:0`   | a random number between 0 and 1 |
| `2 &sqrt`            | `1.41` (a `Decimal` method: no module name) |

- `&module.func` imports *module* (as needed) and calls *func*. The module
  can be dotted (`&os.path.func`).
- `&name` with no dot calls the `Decimal` method *name* with *x* as `self`.
  These keep full precision; `math` functions work in floating point
  (about 16 digits), and their result is converted back to a decimal.
- `:`*n* takes *n* entries from the stack (default 1, may be 0), *y* before
  *x*, and replaces them with the result.
- The result must be a finite number. Anything else (true/false, a tuple, a
  complex number, infinity) is an error, as is an error raised by the
  function (`&math.sqrt` of a negative number). Errors leave the stack
  unchanged.

### Useful `Decimal` methods

One argument (`&name`, applied to *x*): `sqrt` (square root), `ln` (natural
log), `log10` (common log), `exp` (*e* to the *x*), `copy_abs` (absolute
value), `copy_negate` (change sign), `to_integral_value` (round to a whole
number), and `logb` (the power of ten of *x*, e.g. 3 for 1000).

Two arguments (`&name:2`, *y* then *x*): `__pow__` (*y* to the *x*, at full
precision, unlike `&math.pow:2`), `max` and `min`, `__mod__` (remainder of
*y* ÷ *x*), `__floordiv__` (whole-number quotient of *y* ÷ *x*),
`remainder_near` (remainder, using the nearest whole quotient), `copy_sign`
(*y* with the sign of *x*), `quantize` (round *y* to as many decimal places
as *x* has: `1.2346 0.001 &quantize:2` gives 1.235), and `scaleb` (*y* × 10
to the *x*).

Three arguments: `fma` (`a b c &fma:3` gives *a* × *b* + *c* in one exact
step).

Note that `to_integral_value` and `quantize` use banker's rounding (halves go
to the even neighbor, so 2.5 becomes 2 and 3.5 becomes 4), unlike `r` and the
display, which round halves up. `__mod__` and `__floordiv__` truncate toward
zero rather than rounding down, so `7 -2 &__floordiv__:2` is −3, not −4, and
the remainder takes the sign of *y*.

## Command files

`@file` reads *file* and runs each line as if you had typed it. The stack is
displayed once, when the file is done. Blank lines and lines starting with `#`
are ignored, so a file can document itself:

```
# markup.rpn: add 15% to whatever is on top of the stack
15
%
+
```

```
> 200
> @markup.rpn        (shows 230.00)
```

Files can include other files. A relative path inside a file is relative to
that file's directory; at the prompt it is relative to the current directory.
`~` is expanded.

If a line in a file fails, the error shows the file and line number
(`markup.rpn:3: divide by zero`) and the rest of the file (and of any file
that included it) is skipped. Commands that already ran stay done; each can be
undone with `u` one at a time. A `q` in a file quits the calculator.

## Errors

Dividing by zero, typing something unrecognized (including `inf` and
`nan`), or a failing `&` function prints an error and leaves
the stack unchanged (except for a command file that fails partway; see above). A failed entry is not recorded, so `u` skips it.
