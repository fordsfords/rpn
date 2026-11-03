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

Dividing by zero or typing something unrecognized prints an error and leaves
the stack unchanged (except for a command file that fails partway; see above). A failed entry is not recorded, so `u` skips it.
