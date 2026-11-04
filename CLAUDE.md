# CLAUDE.md

Maintenance notes for `rpn.py`, a single-file, dependency-free Python 3 RPN
calculator. `README.md` is the user-facing doc; keep its command table (and `HELP`
in `rpn.py`) in sync when commands change.

## Design

- **Stack**: module-level list `stack` of exactly `STACK_SIZE` (32) `Decimal`s.
  The length never changes:
  - `push(v)` drops `stack[0]` (bottom) and appends.
  - `pop()` removes the top and inserts `Decimal(0)` at the bottom.
- **Names**: HP convention, used everywhere (code comments, `HELP`, docs):
  x = `stack[-1]` (top), y = `stack[-2]`, z = `stack[-3]`, t = `stack[-4]`.
  Two-number ops are y op x. In user-facing text (`HELP`, README) say "x"
  or "most recent", never "top"/"bottom": x is *displayed* at the bottom, so
  "top" is ambiguous. "Older" is the other direction. In code comments and
  here, "top" (= `stack[-1]`) is fine.
- **Levels**: beyond the names, entries are numbered 1-based from x (HP 48
  "stack levels"): level *n* is `stack[-n]`, so x = 1, t = 4, oldest = 32.
  Chosen over 0-based to follow HP prior art (e.g. RPL's `1 PICK` = copy x).
  Any future random-access command (pick, roll, etc.) should use the same
  numbering.
- **Display**: `show()` prints the last `DISPLAY_ROWS` (4) entries, labeled
  from `REGISTERS` (`"tzyx"`), so x prints last: `x: ` then the value
  right-aligned in 20 columns (wider values just print wider).
- **Currency mode** (currently the only mode):
  - All values are `decimal.Decimal`, context precision 34. Never use float
    (the one exception: `&module.func` results, see "Functions").
  - `fmt()` rounds to `CENT` with `ROUND_HALF_UP` (via `round_cents()`) and
    adds `,` separators for display only. `round_cents()` widens the context
    precision for the quantize, so values of 1e32 and up don't raise. The
    stack keeps full precision (HP-12C behavior).
  - `r` is the only command that changes a stored value's precision.
- **Line editing**: `import readline` (optional, skipped on `ImportError`)
  is all it takes: `input()` then uses it. Session history only; no history
  file (not requested). Readline isn't used when stdin isn't a terminal, so
  piped input and the tests are unaffected.
- **Input parsing**: commas and a leading `$` are stripped before
  `Decimal(...)`. Comma placement is not validated (`1,2,3` → 123).
  Non-finite values (`inf`, `nan`) are rejected; the stack only ever holds
  finite Decimals (`fmt()` can't format the others).

## Commands

| Input | Implementation notes |
|-------|----------------------|
| `+ - * / **` | In the `OPS` dict as `f(a, b)` with `a` = y, `b` = x. Computed from `stack[-2]`, `stack[-1]` *before* popping; `DecimalException` (e.g. `Overflow`, `0 ** 0`, `(-8) ** 0.5`) and non-finite results (`0 ** -1` gives `Infinity` without raising) become `CmdError`. Then pops both, pushes result. |
| `swap` | Swap x and y (`stack[-1]`, `stack[-2]`). Was `x`; renamed to avoid clashing with the register name. |
| `%` | HP-12C style: `x = y * x / 100`, y is **kept** (so `+`/`-` then do markup/discount). |
| `r` | `round_cents()`: quantize x to cents, `ROUND_HALF_UP` (matches display rounding). |
| `&mod.f[:n]`, `&f[:n]` | `call_function()`. See "Functions". |
| `d` | `pop()`. |
| `c` | Reset all entries to 0. |
| `u` | `undo()`: `stack[:] = history.pop()`. Only accepted as the only word on a prompt line, handled by `main()`; anywhere else (with other words, or in a file) `execute_one()` raises `CmdError`. Never recorded (no redo). |
| `@file` | `include()`: runs each line through `execute()`. See "Command files". A word starting with `@` takes the rest of the line (`split_line()`), internal spaces kept, ends stripped, `#` not special. `@ file` works; bare `@` is an error. |
| `#...` | A word starting with `#` ends the line (`split_line()`); `1#2` is not a comment. |
| `stack` | `show_stack()`: all `STACK_SIZE` entries, oldest first, labeled by level (1 = x; see "Names"), with the `REGISTERS` letters for levels 1-4. Labels right-aligned to the width of `STACK_SIZE`. Like `h`: a line of only `h`/`stack` is not recorded for undo or followed by `show()`. |
| `h` | Print `HELP`. |
| `q`, `quit`, EOF, Ctrl-C | Exit. |

A `q` inside a command file raises `Quit` and exits the program.

Structure:
- `split_line(line)` splits on whitespace (via `re.finditer`, to keep
  positions), stops at a word starting with `#`, and makes a word starting
  with `@` plus the rest of the line one word.
- `execute(line, base_dir, depth)` runs each word through
  `execute_one(cmd, base_dir, depth)`, stopping at the first `CmdError`
  (earlier words stay done; `main()` rolls back). `Quit` for `q`/`quit`.
- `main()` handles the prompt and owns rollback and undo (see "Lines").

Error handling: a failing command raises *before* modifying the stack.
Divide-by-zero is checked explicitly (for a clearer message); other `OPS`
errors are caught from the computation, which runs before popping.

## Lines

The unit of rollback and undo is one line read by `main()` (a prompt line, or
a stdin line when piped; no difference). `main()` takes `saved = stack[:]`
before the line. On `CmdError` it restores `stack[:] = saved`, prints
`Error: <msg>`, and doesn't redisplay (the stack is as it was). This covers
earlier words on the line and everything run by nested includes. On success
it appends `saved` to `history` and calls `show()` once, unless the line was
only `h`/`stack` (or blank/comment). `history` changes only after a line
succeeds, so rollback never needs to touch it; that's also why `u` must be
alone on its line.

## Functions

`&name[:n]` (parsed by `FUNC_RE`) calls a function by introspection, not by
a list of known names:

- Dotted name: `importlib.import_module()` on everything before the last dot,
  then `getattr` the function. Modules are imported on demand, so nothing
  (e.g. `math`) is imported at startup.
- No dot: `getattr(Decimal, name)`, called unbound with x as `self`
  (`Decimal.ln(x)`), so it uses the module context (precision 34).
- `n` defaults to 1, may be 0, max `STACK_SIZE`. Arguments are
  `stack[len(stack) - n:]` (not `stack[-n:]`, which is wrong for 0), so y
  comes before x. They're read before popping; any exception from the call
  becomes a `CmdError`, so the stack is untouched on failure. A `TypeError`
  mentioning "argument" gets a hint to use `:n` (forgetting it is the usual
  mistake). The message is stripped because CPython's for Decimal methods
  omits the name and starts with a space.
- `to_decimal()` accepts `int`, `float` (via `repr` → shortest decimal) and
  `Decimal` results, and only finite ones. `bool` (an int subclass), tuples,
  complex, `None`, etc. are errors.
- Security is deliberately not a concern: anyone who can run this can
  run arbitrary Python anyway.
- `&` exists to reach advanced functions without adding code to `rpn.py`.
  Dunder methods (`&__mod__:2`) still work, but the docs don't mention
  them: they point to built-in operators (`**`) or `operator.*`
  (`&operator.mod:2`) instead.
- `%` stays percent (HP-12C), not modulo; most users of a currency
  calculator want percent. `divmod` and other tuple-returning functions are
  deliberately unsupported.

## Command files

- `include()` resolves the path relative to `base_dir`: cwd (`"."`) at the
  prompt, or the including file's directory for nested includes (like C's
  `#include "file"`). `~` is expanded.
- Nesting is limited to `MAX_INCLUDE_DEPTH` (16), which catches self-includes.
- On the first error, `include()` re-raises `CmdError` prefixed with
  `path:lineno:`. Only the innermost location is added (the `located`
  attribute), so the message names the line that actually failed. The error
  aborts the whole include chain, and `main()` rolls the stack back to before
  the prompt line (see "Lines").
- No display during a file. `main()` shows the stack once at the end.

## Undo

Snapshot-based, per line (see "Lines"). Decimals are immutable, so the
shallow copy is safe. `history` is capped at `UNDO_LEVELS` (1000), oldest
dropped. New commands get undo and rollback for free.

## Adding a command

- Binary op that consumes x and y: add it to `OPS`.
- Anything else: add an `elif` branch in `execute_one()`, before the final
  `else` (which handles number parsing). Report failures with
  `raise CmdError(msg)` before touching the stack.
- Command names can't contain whitespace or start with `#`.
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

- Other modes besides currency (e.g. more decimals, scientific or
  engineering display, possibly non-Decimal internals). `&` functions
  make this more pressing: `2 &math.log` shows only `0.69`.
- Optional banker's rounding (`ROUND_HALF_EVEN`) for `r`.
- Validating comma placement in input.
- Random-access commands (pick, roll, etc.), using the 1-based levels
  described under "Levels".
- `^` as another name for `**` (offered, not decided).
- Saving readline history between sessions (left out on purpose for now).
