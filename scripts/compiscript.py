"""CLI del frontend de Compiscript."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from compiscript.parser import tree_lines  # noqa: E402
from compiscript.pipeline import analyze_source  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analizador de Compiscript")
    parser.add_argument("archivo", help="archivo fuente con extensión .cps")
    parser.add_argument("--arbol", action="store_true",
                        help="mostrar el árbol sintáctico")
    parser.add_argument("--simbolos", action="store_true",
                        help="mostrar la tabla de símbolos")
    args = parser.parse_args(argv)

    path = Path(args.archivo)
    if path.suffix.lower() != ".cps":
        parser.error("el archivo debe tener extensión .cps")

    result = analyze_source(path.read_text(encoding="utf-8"))
    for diagnostic in result.diagnostics:
        print(diagnostic, file=sys.stderr)
    if args.arbol and result.tree is not None:
        print("\n=== Árbol sintáctico ===")
        print("\n".join(tree_lines(result.tree)))
    if args.simbolos and result.symbol_table is not None:
        print("\n=== Tabla de símbolos ===")
        for row in result.symbol_table.rows():
            scope, kind, level, name, symbol_kind, type_name, mutable, line, col = row
            print(f"{scope:<22} N{level}  {name:<15} {symbol_kind:<10} "
                  f"{type_name:<24} mutable={mutable}  L{line}:C{col}")
    if not result.ok:
        return 1

    print("\nFase 1 completada correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
