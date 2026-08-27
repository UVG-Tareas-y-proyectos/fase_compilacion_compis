# Compiscript — Fase 1: análisis semántico

Este repositorio contiene únicamente la Fase 1 del proyecto: toma código
Compiscript, hace análisis léxico y sintáctico, construye el árbol, administra
la tabla de símbolos con ámbitos anidados y ejecuta las validaciones semánticas.
No contiene TAC ni generación de código.

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

En el IDE se elige un ejemplo, se presiona **Analizar (F5)** y se muestran:

1. el árbol sintáctico;
2. la tabla de símbolos separada por ámbitos;
3. los errores y avisos con línea y columna.

También puede usarse la terminal:

```powershell
python scripts/compiscript.py examples/basico.cps --arbol --simbolos
python scripts/compiscript.py examples/clases_listas.cps --simbolos
python scripts/compiscript.py examples/errores.cps --simbolos
```

Los dos primeros ejemplos deben terminar con `Fase 1 completada
correctamente`. El tercero devuelve código de salida 1 y demuestra las
validaciones semánticas.

## Pruebas

```powershell
python -m pytest -q
```

Las pruebas cubren el frontend propio, posiciones de tokens, errores léxicos y
sintácticos, ámbitos anidados, tipos, funciones, clases, herencia, listas,
control de flujo, diagnósticos y CLI.

## Estructura

```text
grammar/                 gramáticas oficial, YALex y YAPar
src/yalex/               generador léxico propio
src/yapar/               generador sintáctico propio
src/compiscript/parser.py integración y construcción del árbol
src/compiscript/symbols.py tabla de símbolos y ámbitos
src/compiscript/semantic.py validaciones semánticas
scripts/compiscript.py    ejecución por terminal
scripts/ide.py            interfaz gráfica de demostración
examples/                 casos listos para presentar
tests/                    pruebas automatizadas
```

Consulte `docs/ARQUITECTURA.md` para la explicación del flujo y
`docs/CUMPLIMIENTO.md` para el alcance exacto de la fase.
