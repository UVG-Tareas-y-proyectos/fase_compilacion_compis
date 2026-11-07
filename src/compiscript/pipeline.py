"""Orquestador de las fases semántica, TAC y MIPS de Compiscript."""

from dataclasses import dataclass, field

from .parser import CompiscriptParser, Diagnostic
from .semantic import SemanticAnalyzer


@dataclass
class CompilationResult:
    tree: object = None
    symbol_table: object = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    phase_reached: str = "sintáctico"
    tac: object = None
    mips: object = None

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


def analyze_source(source: str, *, generate_code=False, generate_mips=False, optimize_mips=True) -> CompilationResult:
    global _parser
    if _parser is None:
        _parser = CompiscriptParser()
    parsed = _parser.parse(source)
    if not parsed.ok:
        return CompilationResult(diagnostics=parsed.diagnostics)
    analyzer = SemanticAnalyzer()
    semantic = analyzer.analyze(parsed.tree)
    result = CompilationResult(
        tree=parsed.tree,
        symbol_table=semantic.symbol_table,
        diagnostics=semantic.diagnostics,
        phase_reached="semántico",
    )
    if (generate_code or generate_mips) and semantic.ok:
        from .tac import GenerationError
        try:
            result.tac = analyzer.generate_code(semantic)
            result.phase_reached = "intermedio"
        except GenerationError as exc:
            result.diagnostics.append(Diagnostic("intermedio", str(exc), exc.line, exc.column, "error"))
    if generate_mips and result.ok and result.tac:
        from .mips import MIPSGenerator
        from .mips_model import MIPSError
        try:
            result.mips=MIPSGenerator(result.tac,optimize=optimize_mips).generate()
            result.phase_reached='ensamblador'
        except MIPSError as exc:
            result.diagnostics.append(Diagnostic('ensamblador',str(exc),exc.line,exc.column,'error'))
    return result


def compile_source(source: str):
    return analyze_source(source, generate_code=True)


def compile_mips(source: str, *, optimize=True):
    return analyze_source(source,generate_mips=True,optimize_mips=optimize)

