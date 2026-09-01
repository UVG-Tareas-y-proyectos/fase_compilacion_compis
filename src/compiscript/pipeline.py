"""Orquestador de la Fase 1 de Compiscript."""

from dataclasses import dataclass, field

from .parser import CompiscriptParser, Diagnostic
from .semantic import SemanticAnalyzer


@dataclass
class CompilationResult:
    tree: object = None
    symbol_table: object = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    phase_reached: str = "sintáctico"

    @property
    def errors(self):
        return [item for item in self.diagnostics if item.severity == "error"]

    @property
    def warnings(self):
        return [item for item in self.diagnostics if item.severity == "aviso"]

    @property
    def ok(self):
        return not self.errors


_parser = None


def analyze_source(source: str) -> CompilationResult:
    global _parser
    if _parser is None:
        _parser = CompiscriptParser()
    parsed = _parser.parse(source)
    if not parsed.ok:
        return CompilationResult(diagnostics=parsed.diagnostics)
    semantic = SemanticAnalyzer().analyze(parsed.tree)
    return CompilationResult(
        tree=parsed.tree,
        symbol_table=semantic.symbol_table,
        diagnostics=semantic.diagnostics,
        phase_reached="semántico",
    )

