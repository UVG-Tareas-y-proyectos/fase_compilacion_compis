"""Tabla de símbolos con entornos anidados de Compiscript."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Symbol:
    name: str
    kind: str
    type_name: str
    line: int = 0
    column: int = 0
    mutable: bool = True
    parameters: list[str] = field(default_factory=list)
    return_type: str = "void"
    environment: "Environment | None" = None
    metadata: dict[str, Any] = field(default_factory=dict)
    used: bool = False

    @property
    def signature(self):
        if self.kind in {"función", "método"}:
            return f"({', '.join(self.parameters)}) -> {self.return_type}"
        return self.type_name


class Environment:
    def __init__(self, name: str, kind: str, level: int,
                 parent: "Environment | None" = None):
        self.name = name
        self.kind = kind
        self.level = level
        self.parent = parent
        self.symbols: dict[str, Symbol] = {}
        self.children: list[Environment] = []
        if parent is not None:
            parent.children.append(self)

    def declare(self, symbol: Symbol) -> bool:
        if symbol.name in self.symbols:
            return False
        self.symbols[symbol.name] = symbol
        return True

    def resolve_local(self, name: str) -> Symbol | None:
        return self.symbols.get(name)

    def resolve(self, name: str) -> Symbol | None:
        environment: Environment | None = self
        while environment is not None:
            symbol = environment.resolve_local(name)
            if symbol is not None:
                return symbol
            environment = environment.parent
        return None


class SymbolTable:
    """Árbol de entornos; conserva ámbitos cerrados para el reporte final."""

    def __init__(self):
        self.global_environment = Environment("global", "global", 0)
        self.current = self.global_environment
        self._counters = {"bloque": 0, "función": 0, "clase": 0,
                          "catch": 0, "bucle": 0, "switch": 0}

    def enter(self, name: str, kind: str) -> Environment:
        if not name:
            self._counters[kind] = self._counters.get(kind, 0) + 1
            name = f"{kind} {self._counters[kind]}"
        self.current = Environment(name, kind, self.current.level + 1,
                                   self.current)
        return self.current

    def exit(self) -> Environment:
        if self.current.parent is None:
            raise RuntimeError("no se puede salir del ámbito global")
        closed = self.current
        self.current = self.current.parent
        return closed

    def declare(self, symbol: Symbol) -> bool:
        return self.current.declare(symbol)

    def resolve(self, name: str) -> Symbol | None:
        return self.current.resolve(name)

    def environments(self) -> list[Environment]:
        result: list[Environment] = []

        def walk(environment):
            result.append(environment)
            for child in environment.children:
                walk(child)

        walk(self.global_environment)
        return result

    def rows(self) -> list[tuple]:
        rows = []
        for environment in self.environments():
            for symbol in environment.symbols.values():
                rows.append((
                    environment.name,
                    environment.kind,
                    environment.level,
                    symbol.name,
                    symbol.kind,
                    symbol.signature,
                    "sí" if symbol.mutable else "no",
                    symbol.line,
                    symbol.column,
                ))
        return rows

