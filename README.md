# rpn

A small command-line RPN (Reverse Polish Notation) calculator for currency math.

Usage:
```
python3 rpn.py  # or ./rpn.py
```

## Introduction

If you're not already familiar with RPN, you probably don't want this
calculator. :-) Or you could get an HP calculator and
[learn how to use it](https://www.hpmuseum.org/forum/attachment.php?aid=4956).
Either way, this README is not intended to teach you RPN, but here's a very
brief introduction.

Enter `2 5` at the `>` prompt.
This first pushes 2 onto the stack in the *x* position. Then it pushes 5 onto
the stack in *x*, and the 2 gets pushed into *y*. You should see this:
```
t:                 0.00
z:                 0.00
y:                 2.00
x:                 5.00
>
```
The four most-recent entries are displayed.

Now enter an operation, say `+`.
The values in *y* and *x* are added, leaving the answer in *x*:
```
t:                 0.00
z:                 0.00
y:                 0.00
x:                 7.00
>
```

You could have entered all three on a single line: `2 5 +`.

NOTE: Where Python has `readline` (Linux, macOS), the prompt supports the
usual shell-style line editing and up-arrow history for the session, with
your `~/.inputrc` settings (e.g. `set editing-mode vi`).

### The Stack

Following HP calculator convention, the four most recent entries have the names
*x*, *y*, *z*, and *t*. This calculator also has 28 more stack entries, normally not
displayed, for a total of 32 stack entries. The `stack` command shows all 32.
Note that *x*, *y*, *z*, and *t* are implicitly numbered 1-4 respectively.

## Commands

A line can hold several commands separated by spaces. The stack is shown
once, after the whole line. A line is all-or-nothing: if any command on it
fails, the stack goes back to how it was before the line.

| Input        | Action                                                        |
|--------------|---------------------------------------------------------------|
| `h`          | Show a summary of the commands.                               |
| `q`, Ctrl-D  | Quit.                                                         |
| *number*     | Push onto the stack. Commas and a leading `$` are ignored (`$1,234.56`). |
| `+ - * /`    | Replace *y* and *x* with the result (*y* op *x*).             |
| `**`         | Power: replace *y* and *x* with *y*<sup>*x*</sup> (`yˣ` on an HP). |
| `%`          | Percent (*y* stays intact!). [See below](#percent).           |
| `r`          | Round *x* to the nearest cent.                                |
| `stack`      | Show all 32 entries, numbered. [See above](#the-stack).       |
| `swap`       | Exchange *x* and *y* (`x≷y` on an HP).                        |
| `d`          | Drop the stack, with *x* discarded.                           |
| `c`          | Clear the whole stack.                                        |
| `u`          | Undo the last line. Must be alone on its line. [See below](#undo). |
| `&`*mod.f*[`:`*n*] | Call a Python function on the *n* most recent entries (default 1, just *x*), e.g. `&math.log`, `&math.pow:2`. [See below](#functions). |
| `&`*f*[`:`*n*] | Same as `&`*mod.f*[`:`*n*] with *mod* = `Decimal`: call a `Decimal` method, e.g. `&sqrt`, `&ln`, `&log10`, `&exp`. |
| `@`*file*    | Run the commands in *file*; the rest of the line is the file name. [See below](#command-files). |
| `#` ...      | Comment; the rest of the line is ignored (`100 1.08 * # tax`). |

## Currency mode

Numbers are exact decimals (no floating-point surprises like
`0.1 + 0.2 = 0.30000000000000004`).

The display rounds to cents (half-up) and adds comma separators, but the
stack keeps full precision, like a financial calculator. So
`1 3 / 3 *` shows `1.00`, not `0.99`. Use `r` when you want the value
itself rounded to cents, e.g. for an amount that will actually be paid:
`10 3 / r 3 *` shows `9.99`.

## Undo

The undo command (`u`) is scoped to the `>` prompt. Note that `u` must be on
its own line, not part of a multi-command line. For example:
```
> 2 3
t:                 0.00
z:                 0.00
y:                 2.00
x:                 3.00
> + 1 -
t:                 0.00
z:                 0.00
y:                 0.00
x:                 4.00
> u
t:                 0.00
z:                 0.00
y:                 2.00
x:                 3.00
```
The `u` command undid the whole `+ 1 -` sequence, returning the stack to what
it was before you entered it. `u` can be repeated to go back further, up to
1000 lines. There is no redo.

Similarly, a `u` command after a `@file` command will return the stack to what
it was before the `@file` command, no matter how many operations it performed.

## Percent

`%` leaves the base amount on the stack, so markups and discounts take
only one more keystroke:

| Keys              | Result   |
|-------------------|----------|
| `200 15 %`        | `30.00` (15% of 200; 200 is kept in *y*) |
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
- `&name` with no dot calls the `Decimal` method *name*, with the first
  argument as `self` (*x* for one argument, *y* for `:2`, and so on).
  These keep full precision; `math` functions work in floating point
  (about 16 digits), and their result is converted back to a decimal.
- `:`*n* passes the *n* most recent entries (default 1, may be 0) as
  arguments, oldest first, and replaces them with the result. So
  `&math.pow:2` calls `math.pow(y, x)`, which is *y*<sup>*x*</sup>, and a
  three-argument call is `f(z, y, x)`. This is the same order
  as `-` and `/`.
- The result must be a finite number. Anything else (true/false, a tuple, a
  complex number, infinity) is an error, as is an error raised by the
  function (`&math.sqrt` of a negative number). Errors leave the stack
  unchanged. A common one is forgetting `:`*n*: `&math.pow` passes only
  *x*, so it fails with a hint to use `&math.pow:n`.

### Useful `Decimal` methods

One argument (`&name`, applied to *x*): `sqrt` (square root), `ln` (natural
log), `log10` (common log), `exp` (*e* to the *x*), `copy_abs` (absolute
value), `copy_negate` (change sign), `to_integral_value` (round to a whole
number), and `logb` (the power of ten of *x*, e.g. 3 for 1000).

Two arguments (`&name:2`, *y* then *x*): `max` and `min`,
`remainder_near` (remainder, using the nearest whole quotient), `copy_sign`
(*y* with the sign of *x*), `quantize` (round *y* to as many decimal places
as *x* has: `1.2346 0.001 &quantize:2` gives 1.235), and `scaleb` (*y* × 10
to the *x*).

Three arguments: `fma` (`a b c &fma:3` gives *a* * *b* + *c* in one exact
step).

Note that `to_integral_value` and `quantize` use banker's rounding (halves go
to the even neighbor, so 2.5 becomes 2 and 3.5 becomes 4), unlike `r` and the
display, which round halves up.

### Operators as functions

Python's `operator` module has a function for every operator, so operators
the calculator doesn't build in are still available, at full precision:
`&operator.mod:2` (remainder of *y* ÷ *x*) and `&operator.floordiv:2`
(whole-number quotient of *y* ÷ *x*). With decimals, both truncate toward
zero rather than rounding down, so `7 -2 &operator.floordiv:2` is −3, not
−4, and the remainder takes the sign of *y*. (For *y* to the *x*, use `**`.)

## Command files

`@file` reads *file* and runs each line in turn. The stack is
displayed once, when the file is done. Blank lines and comments are ignored,
so a file can document itself:

```
# markup.rpn: add 15% to x
15
%
+
```

```
> 200
> @markup.rpn        (shows 230.00)
```

`@file` can come after other commands on a line: `200 @markup.rpn` does the
same thing. The file name is the rest of the line, so it can contain spaces
(`@my taxes.rpn`), and nothing can follow it, not even a comment.

Files can include other files. A relative path inside a file is relative to
that file's directory; at the prompt it is relative to the current directory.
`~` is expanded.

If a line in a file fails, the error shows the file and line number
(`markup.rpn:3: divide by zero`), the rest of the file (and of any file that
included it) is skipped, and the stack goes back to how it was before the line
you typed. On success, a single `u` undoes everything the file did. `u` can't
be used in a file. A `q` in a file quits the calculator.

## Errors

Dividing by zero, typing something unrecognized (including `inf` and
`nan`), or a failing `&` function prints an error and leaves the stack as it
was before the line (including any earlier commands on the line, and any
command file the line ran). A failed line is not recorded, so `u` skips it.
