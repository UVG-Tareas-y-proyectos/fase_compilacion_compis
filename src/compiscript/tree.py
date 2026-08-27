"""Nodos mínimos del árbol sintáctico, sin depender de bibliotecas externas."""

from dataclasses import dataclass, field
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "src" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from tok import Token  # noqa: E402


@dataclass
class Meta:
    line: int = 0
    column: int = 0


@dataclass
class Tree:
    data: str
    children: list = field(default_factory=list)
    meta: Meta = field(default_factory=Meta)

    def pretty(self) -> str:
        lines = []

        def visit(node, depth=0):
            prefix = "  " * depth
            if isinstance(node, Tree):
                lines.append(prefix + node.data)
                for child in node.children:
                    visit(child, depth + 1)
            elif isinstance(node, Token):
                lines.append(prefix + f"{node.type}\t{node.value}")
            else:
                lines.append(prefix + str(node))

        visit(self)
        return "\n".join(lines) + "\n"


def make_tree(data: str, children=None) -> Tree:
    children = [item for item in (children or []) if item is not None]
    line = column = 0
    for child in children:
        if isinstance(child, Token) and child.line > 0:
            line, column = child.line, child.col
            break
        if isinstance(child, Tree) and child.meta.line > 0:
            line, column = child.meta.line, child.meta.column
            break
    return Tree(data, children, Meta(line, column))
