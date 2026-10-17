"""Cuádruplos TAC y asignación de temporales (presentación 06)."""

from dataclasses import dataclass, field, asdict
import json


@dataclass(frozen=True)
class Instruction:
    op: str
    arg1: str = ""
    arg2: str = ""
    result: str = ""
    line: int = 0
    column: int = 0

    def text(self):
        a, b, r = self.arg1, self.arg2, self.result
        if self.op == "label":
            return f"{r}:"
        if self.op == "copy":
            return f"{r} = {a}"
        if self.op in {"+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">="}:
            return f"{r} = {a} {self.op} {b}"
        if self.op in {"neg", "!", "i2f"}:
            return f"{r} = {self.op} {a}"
        if self.op == "goto":
            return f"goto {r}"
        if self.op in {"if", "ifFalse"}:
            return f"{self.op} {a} goto {r}"
        if self.op == "load_index":
            return f"{r} = {a}[{b}]"
        if self.op == "store_index":
            return f"{r}[{b}] = {a}"
        if self.op == "load_field":
            return f"{r} = {a}.{b}"
        if self.op == "store_field":
            return f"{r}.{b} = {a}"
        if self.op == "call":
            return f"{r + ' = ' if r else ''}call {a}, {b}"
        if self.op in {"param", "return", "print"}:
            return f"{self.op} {a}".rstrip()
        return f"{r + ' = ' if r else ''}{self.op} {a}{', ' + b if b else ''}".rstrip()


class TemporaryPool:
    """Un temporal se libera sólo después de emitir su último consumidor."""

    def __init__(self):
        self.free = []
        self.live = set()
        self.created = 0
        self.peak = 0

    def acquire(self):
        if self.free:
            name = self.free.pop()
        else:
            self.created += 1
            name = f"%t{self.created}"
        self.live.add(name)
        self.peak = max(self.peak, len(self.live))
        return name

    def release(self, name):
        if name in self.live:
            self.live.remove(name)
            self.free.append(name)


@dataclass
class FunctionCode:
    label: str
    name: str
    parameters: list[str] = field(default_factory=list)
    instructions: list[Instruction] = field(default_factory=list)
    frame: dict = field(default_factory=dict)
    temporary_count: int = 0
    peak_live: int = 0


@dataclass
class TACProgram:
    functions: dict[str, FunctionCode] = field(default_factory=dict)
    classes: dict = field(default_factory=dict)
    entry: str = "__main__"

    def text(self):
        lines = []
        for function in self.functions.values():
            lines.append(f"function {function.label}({', '.join(function.parameters)})")
            lines.extend("  " + instruction.text() for instruction in function.instructions)
            lines.append(f"end {function.label}\n")
        return "\n".join(lines)

    def quadruples(self):
        return [(function.label, i, ins.op, ins.arg1, ins.arg2, ins.result)
                for function in self.functions.values()
                for i, ins in enumerate(function.instructions)]

    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)
