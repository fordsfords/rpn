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
| `u` | Undo. Restores `stack[:] = history.pop()`. Handled before `saved` is taken, so `u` itself is never recorded (no redo). |
| `@file` | `include()`: runs each line through `execute()`. See "Command files". Not itself recorded for undo; each command it runs is. |
| `#...` | Comment, skipped at the prompt and in files. |
| `stack` | `show_stack()`: all `STACK_SIZE` entries, oldest first, labeled by level (1 = x; see "Names"), with the `REGISTERS` letters for levels 1-4. Labels right-aligned to the width of `STACK_SIZE`. Like `h`: not recorded for undo, and `main()` doesn't call `show()` after it. |
| `h` | Print `HELP`. Not recorded for undo. |
| `q`, `quit`, EOF, Ctrl-C | Exit. |

A `q` inside a command file raises `Quit` and exits the program.

Structure: `execute(line, base_dir, depth)` runs one command and raises
`CmdError(msg)` on failure or `Quit` for `q`/`quit`. `main()` handles the
prompt, prints `Error: <msg>`, and calls `show()` after each successful line.

Error handling: a failing command raises *before* modifying the stack, so the
stack is unchanged. `main()` doesn't redisplay after an error unless the stack
changed, which only happens when an include fails partway. Divide-by-zero is
checked explicitly (for a clearer message); other `OPS` errors are caught
from the computation, which runs before popping.

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

- Other modes besides currency (e.g. more decimals, scientific or
  engineering display, possibly non-Decimal internals). `&` functions
  make this more pressing: `2 &math.log` shows only `0.69`.
- Optional banker's rounding (`ROUND_HALF_EVEN`) for `r`.
- Validating comma placement in input.
- Random-access commands (pick, roll, etc.), using the 1-based levels
  described under "Levels".
- `^` as another name for `**` (offered, not decided).
- Saving readline history between sessions (left out on purpose for now).
