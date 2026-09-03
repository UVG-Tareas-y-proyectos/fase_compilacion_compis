# Alcance y cumplimiento

## Incluido en la Fase 1

- Gramática oficial `Compiscript.g4` como referencia.
- Especificación léxica ejecutable `Compiscript.yal`.
- Especificación sintáctica ejecutable `Compiscript.yalp`.
- Generadores propios YALex y YAPar reutilizados del proyecto anterior.
- Árbol sintáctico con posiciones.
- Tabla de símbolos y ámbitos anidados.
- Validación de tipos, expresiones, funciones y control de flujo.
- Semántica de clases, herencia, `this`, `new` y listas.
- Errores y avisos con línea y columna.
- CLI, IDE, tres ejemplos y pruebas automatizadas.

## Deliberadamente fuera de alcance

- Código de tres direcciones (TAC).
- Optimizaciones.
- Código objeto, ensamblador o ejecución del programa.

## Decisión del frontend

La consigna permite ANTLR u otra herramienta similar y pide reutilizar o
extender la fase anterior. Por esa razón el proyecto ya no delega el parsing a
Lark: usa el mismo trabajo académico de generadores que el equipo construyó el
semestre anterior. La gramática entregada se tradujo a los formatos de esos
generadores y se añadió `float`, solicitado en las instrucciones semánticas.
