"""What a Python file means, for comparing a rendered copy with its source (the
parts component): its syntax tree, docstrings included (the shared runner's usage
text is its module docstring, so a docstring is behaviour), with comments, blank
lines, layout and the shebang aside. Two files mean the same iff their trees dump
equal under this interpreter. Reads only; the hooks have their own comparator,
the hooks dependency's. Each function takes a path, or the file's bytes (the
source as its repo's HEAD holds it)."""
import ast
import hashlib
from pathlib import Path


def _tree(src):
    """The parsed tree of a path or of bytes, or None."""
    try:
        data = src if isinstance(src, bytes) else Path(src).read_bytes()
        return ast.parse(data, filename="<bytes>" if isinstance(src, bytes) else str(src))
    except (OSError, SyntaxError, ValueError):
        return None


def meaning(src):
    """sha256 of the file's syntax tree, or None when it cannot be read or does not
    parse (a caller treats None as differing, never as equal)."""
    tree = _tree(src)
    if tree is None:
        return None
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


def version(src):
    """The module-level `VERSION = "<str>"` literal, or None when there is none, or
    more than one, or the file does not parse. Read from the tree; never executed."""
    tree = _tree(src)
    if tree is None:
        return None
    found = [n.value.value for n in tree.body
             if isinstance(n, ast.Assign) and len(n.targets) == 1
             and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "VERSION"
             and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)]
    return found[0] if len(found) == 1 else None
