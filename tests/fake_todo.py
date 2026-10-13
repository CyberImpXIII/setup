#!/usr/bin/env python3
"""A stand-in store CLI for tests/test_steps.py: `fake_todo.py -C <dir> get <id>`
reads <dir>/fake-store.json ({id: closed}) and prints the item as JSON with its
`closed` boolean. No such file, or no such id: exit 1 with the reason on stderr,
as the real CLI does for both."""
import json
import sys
from pathlib import Path


def main(argv):
    if len(argv) != 4 or argv[0] != "-C" or argv[2] != "get":
        print("usage: fake_todo.py -C DIR get ID", file=sys.stderr)
        return 2
    store = Path(argv[1]) / "fake-store.json"
    try:
        items = json.loads(store.read_text())
    except OSError:
        print(f"no todo.json in {argv[1]}", file=sys.stderr)
        return 1
    if argv[3] not in items:
        print(f"{argv[3]}: a dangling id", file=sys.stderr)
        return 1
    print(json.dumps({"id": argv[3], "closed": items[argv[3]]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
