#!/usr/bin/env python3
"""A small command-line RPN calculator for currency math.

See README.md for usage and CLAUDE.md for design notes.
"""

import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext

getcontext().prec = 34

STACK_SIZE = 32
DISPLAY_ROWS = 4
DISPLAY_WIDTH = 20
UNDO_LEVELS = 1000
MAX_INCLUDE_DEPTH = 16
CENT = Decimal("0.01")

HELP = """\
number     Push onto the stack ($ and commas are ignored: $1,234.56)
+ - * /    Replace the top two entries with y op x
x          Exchange the top two entries
%          Percent: replace the top with y * x / 100, keeping y
r          Round the top entry to the nearest cent
d          Drop the top entry
c          Clear the whole stack
u          Undo the last command (up to 1000 levels)
@file      Run the commands in file
# ...      Comment; ignored
h          Show this help
q, Ctrl-D  Quit"""

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


def fmt(value):
    """Round to cents, half-up, with comma separators. Display only."""
    return "{:,}".format(value.quantize(CENT, rounding=ROUND_HALF_UP))


def show():
    for value in stack[-DISPLAY_ROWS:]:
        print(fmt(value).rjust(DISPLAY_WIDTH))


OPS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b,
}


def parse_number(text):
    text = text.replace(",", "")
    if text.startswith("$"):
        text = text[1:]
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


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
        b = pop()
        a = pop()
        push(OPS[cmd](a, b))
    elif cmd == "x":
        stack[-1], stack[-2] = stack[-2], stack[-1]
    elif cmd == "%":
        push(stack[-2] * pop() / 100)
    elif cmd == "r":
        push(pop().quantize(CENT, rounding=ROUND_HALF_UP))
    elif cmd == "d":
        pop()
    elif cmd == "c":
        stack[:] = [Decimal(0)] * STACK_SIZE
    else:
        value = parse_number(cmd)
        if value is None:
            raise CmdError(f"unrecognized input: {cmd}")
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
        if cmd and not cmd.startswith("#") and cmd != "h":
            show()


if __name__ == "__main__":
    main()
