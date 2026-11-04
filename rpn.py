#!/usr/bin/env python3
"""A small command-line RPN calculator for currency math.

See README.md for usage and CLAUDE.md for design notes.
"""

import importlib
import os
import re
try:
    import readline  # noqa: F401  (just importing it gives input() editing)
except ImportError:  # e.g. Windows
    pass
from decimal import (Context, Decimal, DecimalException, InvalidOperation,
                     ROUND_HALF_UP, getcontext)

getcontext().prec = 34

STACK_SIZE = 32
REGISTERS = "tzyx"  # HP names for the displayed entries; x is most recent
DISPLAY_ROWS = len(REGISTERS)
DISPLAY_WIDTH = 20
UNDO_LEVELS = 1000
MAX_INCLUDE_DEPTH = 16
CENT = Decimal("0.01")

HELP = """\
The display shows the 4 most recent stack entries (x is most recent).

number     Push onto the stack ($ and commas are ignored: $1,234.56)
+ - * /    Replace y and x with y op x
**         Power: replace y and x with y to the power x
swap       Exchange x and y
%          Percent: replace x with y * x / 100, keeping y
r          Round x to the nearest cent
stack      Show all 32 entries, numbered from x = 1 (as on an HP 48)
d          Drop x
c          Clear the whole stack
u          Undo the last command (up to 1000 levels)
&mod.f[:n] Call Python funct mod.f on the n most recent stack entries [deflt 1]
           For n>1, x is passed last. E.g. &math.pow:2 calls math.pow(y, x)
&f[:n]     Same as &mod.f[:n] with mod=Decimal. E.g. &sqrt, &ln, &log10, &exp
@file      Run the commands in file
# ...      Comment; ignored
h          Show this help
q, Ctrl-D  Quit

For details, see https://github.com/fordsfords/rpn"""

stack = [Decimal(0)] * STACK_SIZE
history = []


class CmdError(Exception):
    """A command failed. Raised before the stack is modified."""


class Quit(Exception):
    """q or quit was entered (at the prompt or in a command file)."""


def push(value):
    del stack[0]
    stack.append(value)


def pop():
    value = stack.pop()
    stack.insert(0, Decimal(0))
    return value


def round_cents(value):
    """Round to cents, half-up. Widens precision so huge values don't fail."""
    prec = max(getcontext().prec, value.adjusted() + 3)
    return value.quantize(CENT, rounding=ROUND_HALF_UP,
                          context=Context(prec=prec))


def fmt(value):
    """Round to cents, half-up, with comma separators. Display only."""
    return "{:,}".format(round_cents(value))


def show():
    for name, value in zip(REGISTERS, stack[-DISPLAY_ROWS:]):
        print(f"{name}: {fmt(value).rjust(DISPLAY_WIDTH)}")


def show_stack():
    """All entries, oldest first. Level 1 is x (HP 48 numbering)."""
    width = len(str(STACK_SIZE))
    for level in range(STACK_SIZE, 0, -1):
        name = REGISTERS[-level] if level <= DISPLAY_ROWS else str(level)
        print(f"{name.rjust(width)}: "
              f"{fmt(stack[-level]).rjust(DISPLAY_WIDTH)}")


OPS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b,
    "**": lambda a, b: a ** b,
}


def parse_number(text):
    text = text.replace(",", "")
    if text.startswith("$"):
        text = text[1:]
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None  # no inf or nan


FUNC_RE = re.compile(r"&((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*)(?::(\d+))?")


def to_decimal(result, name):
    """Convert a function's result for the stack. Only finite numbers."""
    if isinstance(result, bool):  # bool is an int subclass; reject it
        value = None
    elif isinstance(result, Decimal):
        value = result
    elif isinstance(result, int):
        value = Decimal(result)
    elif isinstance(result, float):
        value = Decimal(repr(result))  # shortest form: 0.1, not 0.1000...055
    else:
        value = None
    if value is None:
        raise CmdError(f"{name}: result is not a number: {result!r}")
    if not value.is_finite():
        raise CmdError(f"{name}: result is not finite: {value}")
    return value


def call_function(cmd):
    """&module.func[:n] or &decimal_method[:n]. Returns (nargs, result)."""
    m = FUNC_RE.fullmatch(cmd)
    if not m:
        raise CmdError(f"bad function syntax: {cmd} (use &module.func[:n])")
    name, nargs = m.group(1), int(m.group(2) or 1)
    if nargs > STACK_SIZE:
        raise CmdError(f"{name}: at most {STACK_SIZE} arguments")

    modname, _, funcname = name.rpartition(".")
    try:
        if modname:
            func = getattr(importlib.import_module(modname), funcname)
        else:
            func = getattr(Decimal, funcname)  # called with x as self
    except (ImportError, AttributeError) as e:
        raise CmdError(f"{name}: {e}")
    if not callable(func):
        raise CmdError(f"{name}: not a function")

    args = stack[len(stack) - nargs:]  # oldest first: f(y, x); not popped yet
    try:
        result = func(*args)
    except DecimalException as e:  # str() is an unhelpful class list
        raise CmdError(f"{name}: {type(e).__name__}")
    except Exception as e:  # any function, so any error
        msg = str(e).strip() or type(e).__name__  # strip: some start with " "
        if isinstance(e, TypeError) and "argument" in msg:
            entries = "entry" if nargs == 1 else "entries"
            msg += f" (passed {nargs} stack {entries}; use &{name}:n for n)"
        raise CmdError(f"{name}: {msg}")
    return nargs, to_decimal(result, name)


def include(name, base_dir, depth):
    """Run each line of a command file through execute()."""
    if depth >= MAX_INCLUDE_DEPTH:
        raise CmdError(f"{name}: includes nested more than "
                       f"{MAX_INCLUDE_DEPTH} deep")
    path = os.path.normpath(os.path.join(base_dir, os.path.expanduser(name)))
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except OSError as e:
        raise CmdError(f"{path}: {e.strerror}")

    file_dir = os.path.dirname(path) or "."
    for lineno, line in enumerate(lines, 1):
        try:
            execute(line, file_dir, depth + 1)
        except CmdError as e:
            if getattr(e, "located", False):
                raise  # keep the innermost location only
            located = CmdError(f"{path}:{lineno}: {e}")
            located.located = True
            raise located from None


def execute(line, base_dir=".", depth=0):
    """Run one command. Raises CmdError on failure, Quit for q/quit."""
    cmd = line.strip()
    if not cmd or cmd.startswith("#"):
        return
    if cmd in ("q", "quit"):
        raise Quit
    if cmd == "h":
        print(HELP)
        return
    if cmd == "stack":
        show_stack()
        return
    if cmd.startswith("@"):
        include(cmd[1:].strip(), base_dir, depth)
        return
    if cmd == "u":
        if not history:
            raise CmdError("nothing to undo")
        stack[:] = history.pop()
        return

    saved = stack[:]

    if cmd in OPS:
        if cmd == "/" and stack[-1] == 0:
            raise CmdError("divide by zero")
        try:  # compute before popping, so an error leaves the stack alone
            result = OPS[cmd](stack[-2], stack[-1])
        except DecimalException as e:  # e.g. Overflow; 0 ** 0, (-8) ** 0.5
            raise CmdError(f"{cmd}: {type(e).__name__}")
        if not result.is_finite():  # 0 ** -1 gives Infinity, not an error
            raise CmdError(f"{cmd}: result is not finite")
        pop()
        pop()
        push(result)
    elif cmd == "swap":
        stack[-1], stack[-2] = stack[-2], stack[-1]
    elif cmd == "%":
        push(stack[-2] * pop() / 100)
    elif cmd.startswith("&"):
        nargs, result = call_function(cmd)
        for _ in range(nargs):
            pop()
        push(result)
    elif cmd == "r":
        push(round_cents(pop()))
    elif cmd == "d":
        pop()
    elif cmd == "c":
        stack[:] = [Decimal(0)] * STACK_SIZE
    else:
        value = parse_number(cmd)
        if value is None:
            raise CmdError(f"unrecognized input: {cmd} (enter 'h' for help)")
        push(value)

    history.append(saved)
    if len(history) > UNDO_LEVELS:
        del history[0]


def main():
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        cmd = line.strip()
        before = stack[:]
        try:
            execute(line)
        except Quit:
            return
        except CmdError as e:
            print(f"Error: {e}")
            if stack != before:  # an include failed partway
                show()
            continue
        if cmd and not cmd.startswith("#") and cmd not in ("h", "stack"):
            show()


if __name__ == "__main__":
    main()
