# Compiscript - Fases 1 y 2

Compilador académico de Compiscript implementado en Python. La fase 1 realiza
análisis léxico, sintáctico y semántico. La fase 2 traduce el árbol validado a
código de tres direcciones (TAC), con cuádruplos, reciclaje de temporales y
registros de activación. Incluye un intérprete de TAC para verificar resultados.

El frontend reutiliza los generadores desarrollados en el proyecto anterior:

- **YALex** lee `grammar/Compiscript.yal`, construye un NFA con Thompson, lo
  convierte a DFA por subconjuntos y genera el lexer de Python.
- **YAPar** lee `grammar/Compiscript.yalp`, calcula FIRST/FOLLOW, construye el
  autómata LR(0) y produce la tabla SLR para el parser shift-reduce.
- Las reducciones forman el árbol que recibe el analizador semántico.

La gramática oficial entregada por el catedrático se conserva como referencia
en `grammar/Compiscript.g4`. La implementación no usa Lark ni otro parser ya
hecho.

## Instalación

Desde PowerShell, dentro del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

La primera ejecución genera los artefactos del lexer y del parser en
`generated/`; las siguientes ejecuciones reutilizan esa caché.

## Cómo correrlo

Interfaz gráfica recomendada para presentar:

```powershell
python scripts/ide.py
```

En el IDE se elige un ejemplo y se presiona **Compilar (F5)**. Se muestran:

1. el árbol sintáctico;
2. la tabla de símbolos separada por ámbitos;
3. los errores y avisos con línea y columna.
4. el TAC y sus cuádruplos;
5. los registros de activación y símbolos extendidos.

**Ejecutar TAC** verifica el resultado y **Exportar TAC** guarda `.tac` o `.json`.
Para comprobar el funcionamiento, seleccione `fase2_expresiones` y luego
`fase2_funciones_closures`.

También puede usarse la terminal:

```powershell
python scripts/compiscript.py examples/basico.cps --arbol --simbolos
python scripts/compiscript.py examples/clases_listas.cps --simbolos
python scripts/compiscript.py examples/errores.cps --simbolos
python scripts/compiscript.py examples/fase2_expresiones.cps --tac --ejecutar
python scripts/compiscript.py examples/fase2_funciones_closures.cps --tac --registros --ejecutar
python scripts/compiscript.py examples/fase2_objetos_listas.cps --tac --simbolos --ejecutar
python scripts/compiscript.py examples/fase2_control.cps --salida salida.tac
python scripts/compiscript.py examples/fase2_expresiones.cps --salida salida.json
```

Los dos primeros ejemplos deben terminar con `Fase 1 completada
correctamente`. El tercero devuelve código de salida 1 y demuestra las
validaciones semánticas.

Sin opciones de fase 2, la CLI conserva el comportamiento de la fase 1.
`--tac`, `--cuadruplos`, `--registros`, `--salida` o `--ejecutar` activan la fase 2.
El compilador no genera TAC si existen errores de las fases anteriores. Los
avisos no bloquean la compilación. No se genera assembler ni un ejecutable nativo.

## Pruebas

```powershell
python -m pytest -q
```

Las pruebas cubren el frontend propio, posiciones de tokens, errores léxicos y
sintácticos, ámbitos anidados, tipos, funciones, clases, herencia, listas,
control de flujo, diagnósticos y CLI.
Además ejecutan el TAC para comprobar precedencia, cortocircuito, efectos
laterales, saltos, recursión, closures con entornos independientes, métodos,
herencia, índices, límites de ejecución, IDE y exportación. También regeneran
el frontend sin depender de la caché. Resultado de la entrega: **107 pruebas**.

## Estructura

```text
grammar/                 gramáticas oficial, YALex y YAPar
src/yalex/               generador léxico propio
src/yapar/               generador sintáctico propio
src/compiscript/parser.py integración y construcción del árbol
src/compiscript/symbols.py tabla de símbolos y ámbitos
src/compiscript/semantic.py validaciones semánticas
src/compiscript/ir.py      cuádruplos y pool de temporales
src/compiscript/layout.py  direcciones y registros de activación
src/compiscript/tac.py     Visitor de traducción dirigido por la sintaxis
src/compiscript/vm.py      intérprete de TAC para verificación
scripts/compiscript.py    ejecución por terminal
scripts/ide.py            interfaz gráfica de demostración
examples/                 casos listos para presentar
tests/                    pruebas automatizadas
```

## Documentación de la fase 2

La documentación de entrega reúne la arquitectura, el lenguaje intermedio,
las reglas de traducción, la instalación y las pruebas:

- [Documentación de la fase 2](docs/fase2.pdf).

Se conserva YALex/YAPar de la fase anterior. El enunciado menciona ANTLR en su
flujo ilustrativo, pero esta implementación sigue utilizando los generadores
propios y la gramática oficial como referencia. `Closure` es una anotación
adicional documentada para funciones que retornan otra función.

