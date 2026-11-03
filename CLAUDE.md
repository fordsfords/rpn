# CLAUDE.md

Maintenance notes for `rpn.py`, a single-file, dependency-free Python 3 RPN
calculator. `README.md` is the user-facing doc; keep its command table (and `HELP`
in `rpn.py`) in sync when commands change.

## Design

- **Stack**: module-level list `stack` of exactly `STACK_SIZE` (32) `Decimal`s.
  `stack[-1]` is the top (x), `stack[-2]` is y. The length never changes:
  - `push(v)` drops `stack[0]` (bottom) and appends.
  - `pop()` removes the top and inserts `Decimal(0)` at the bottom.
- **Display**: `show()` prints the last `DISPLAY_ROWS` (4) entries, so the top
  of the stack prints last. Right-aligned in 20 columns.
- **Currency mode** (currently the only mode):
  - All values are `decimal.Decimal`, context precision 34. Never use float.
  - `fmt()` rounds to `CENT` with `ROUND_HALF_UP` and adds `,` separators
    for display only. The stack keeps full precision (HP-12C behavior).
  - `r` is the only command that changes a stored value's precision.
- **Input parsing**: commas and a leading `$` are stripped before
  `Decimal(...)`. Comma placement is not validated (`1,2,3` → 123).

## Commands

| Input | Implementation notes |
|-------|----------------------|
| `+ - * /` | In the `OPS` dict as `f(a, b)` with `a` = y, `b` = x. Pops both, pushes result. |
| `x` | Swap `stack[-1]` and `stack[-2]`. |
| `%` | HP-12C style: `x = y * x / 100`, y is **kept** (so `+`/`-` then do markup/discount). |
| `r` | Quantize x to cents, `ROUND_HALF_UP` (matches display rounding). |
| `d` | `pop()`. |
| `c` | Reset all entries to 0. |
| `u` | Undo. Restores `stack[:] = history.pop()`. Handled before `saved` is taken, so `u` itself is never recorded (no redo). |
| `@file` | `include()`: runs each line through `execute()`. See "Command files". Not itself recorded for undo; each command it runs is. |
| `#...` | Comment, skipped at the prompt and in files. |
| `h` | Print `HELP`. Not recorded for undo. |
| `q`, `quit`, EOF, Ctrl-C | Exit. |

A `q` inside a command file raises `Quit` and exits the program.

Structure: `execute(line, base_dir, depth)` runs one command and raises
`CmdError(msg)` on failure or `Quit` for `q`/`quit`. `main()` handles the
prompt, prints `Error: <msg>`, and calls `show()` after each successful line.

Error handling: a failing command raises *before* modifying the stack, so the
stack is unchanged. `main()` doesn't redisplay after an error unless the stack
changed, which only happens when an include fails partway. Divide-by-zero is
checked before popping.

## Command files

- `include()` resolves the path relative to `base_dir`: cwd (`"."`) at the
  prompt, or the including file's directory for nested includes (like C's
  `#include "file"`). `~` is expanded.
- Nesting is limited to `MAX_INCLUDE_DEPTH` (16), which catches self-includes.
- On the first error, `include()` re-raises `CmdError` prefixed with
  `path:lineno:`. Only the innermost location is added (the `located`
  attribute), so the message names the line that actually failed. The error
  aborts the whole include chain. Commands that already ran are not rolled back.
- No display during a file. `main()` shows the stack once at the end.

## Undo

Snapshot-based: `execute()` takes `saved = stack[:]` before each command and
appends it to `history` only after the command succeeds (errors `raise`
before the append). Decimals are immutable, so the shallow copy is safe.
`history` is capped at `UNDO_LEVELS` (1000), oldest dropped. New commands get
undo for free as long as they fall through to the end of `execute()`; a command
that should *not* be undoable (like `u`) must `return` before `saved`.

## Adding a command

- Binary op that consumes x and y: add it to `OPS`.
- Anything else: add an `elif` branch in `execute()`, before the final
  `else` (which handles number parsing). Report failures with
  `raise CmdError(msg)` before touching the stack.
- Check that the new command name can't also parse as a `Decimal`.
  `Decimal` accepts `inf`, `nan`, `e` notation, etc., but command branches
  are checked first, so a command name wins.
- Update `HELP` in `rpn.py` and the tables in `README.md` and here.

## Testing

`test_rpn.py` holds black-box tests (stdlib `unittest`, no dependencies) that
run `rpn.py` as a subprocess and check its output. They don't import `rpn.py`,
so internals can change freely. Add tests there when commands change.

```
python3 -m unittest -v test_rpn
```

To try something by hand, pipe input and check the output, e.g.:

```
printf '200\n15\n%%\n+\n' | python3 rpn.py
```

(`%%` because of printf.) Expected final top of stack: `230.00`.

## Possible future work (discussed, not requested)

- Other modes besides currency (e.g. a general float/scientific mode).
- Optional banker's rounding (`ROUND_HALF_EVEN`) for `r`.
- Validating comma placement in input.
