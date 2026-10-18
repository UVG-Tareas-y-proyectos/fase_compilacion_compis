"""CLI del frontend de Compiscript."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from compiscript.parser import tree_lines  # noqa: E402
from compiscript.pipeline import analyze_source  # noqa: E402
from compiscript.vm import TACMachine, RuntimeFault  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compilador de Compiscript: semántica y TAC")
    parser.add_argument("archivo", help="archivo fuente con extensión .cps")
    parser.add_argument("--arbol", action="store_true",
                        help="mostrar el árbol sintáctico")
    parser.add_argument("--simbolos", action="store_true",
                        help="mostrar la tabla de símbolos")
    parser.add_argument('--tac', action='store_true', help='generar y mostrar código de tres direcciones')
    parser.add_argument('--cuadruplos', action='store_true', help='mostrar operador, argumentos y resultado')
    parser.add_argument('--registros', action='store_true', help='mostrar registros de activación')
    parser.add_argument('--salida', type=Path, help='guardar TAC (.tac) o cuádruplos y metadatos (.json)')
    parser.add_argument('--ejecutar', action='store_true', help='ejecutar el TAC con el intérprete de verificación')
    parser.add_argument('--limite', type=int, default=100000, help='máximo de instrucciones al ejecutar')
    args = parser.parse_args(argv)

    path = Path(args.archivo)
    if path.suffix.lower() != ".cps":
        parser.error("el archivo debe tener extensión .cps")

    generate = bool(args.tac or args.cuadruplos or args.registros or args.salida or args.ejecutar)
    try:
        result = analyze_source(path.read_text(encoding="utf-8"), generate_code=generate)
    except (OSError, UnicodeError) as exc:
        print(f'No se pudo leer el archivo: {exc}', file=sys.stderr)
        return 2
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
        if generate and result.tac:
            print('\n=== Direcciones y desplazamientos ===')
            for row in result.symbol_table.code_rows():
                print(f'{row[3]:<18} {row[9]:<24} offset={row[10]} tamaño={row[11]} '
                      f'etiqueta={row[12]} almacenamiento={row[13]}')
    if not result.ok:
        return 1

    if result.tac:
        if args.tac:
            print('\n=== Código de tres direcciones ===')
            print(result.tac.text())
        if args.cuadruplos:
            print('\n=== Cuádruplos: función, número, op, arg1, arg2, resultado ===')
            for row in result.tac.quadruples():
                print(' | '.join(map(str, row)))
        if args.registros:
            print('\n=== Registros de activación ===')
            print(json.dumps({f.label: f.frame for f in result.tac.functions.values()},
                             ensure_ascii=False, indent=2))
        if args.salida:
            content = result.tac.to_json() if args.salida.suffix == '.json' else result.tac.text()
            try:
                args.salida.write_text(content, encoding='utf-8')
            except OSError as exc:
                print(f'No se pudo guardar el TAC: {exc}', file=sys.stderr)
                return 2
            print(f'TAC guardado en {args.salida}')
        if args.ejecutar:
            print('\n=== Ejecución del TAC ===')
            try:
                execution = TACMachine(result.tac, max_steps=args.limite).run()
                print('\n'.join(execution.output))
            except RuntimeFault as exc:
                print(f'Error de ejecución L{exc.line}:C{exc.column}: {exc}', file=sys.stderr)
                return 1
        print('\nFase 2 completada correctamente.')
    else:
        print("\nFase 1 completada correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
