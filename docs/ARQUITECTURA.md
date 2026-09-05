# Arquitectura de la Fase 1

## Flujo completo

```text
código .cps
   ↓
Compiscript.yal → regex → NFA de Thompson → DFA → tokens
   ↓
Compiscript.yalp → FIRST/FOLLOW → LR(0) → tabla SLR → árbol
   ↓
tabla de símbolos + ámbitos anidados + comprobación de tipos
   ↓
árbol, símbolos, errores y avisos en CLI o IDE
```

## Qué hace cada parte

### YALex

La especificación `.yal` describe patrones como identificadores, números,
palabras reservadas y operadores. El generador convierte cada expresión regular
en un NFA mediante Thompson; luego aplica construcción de subconjuntos para
obtener un DFA. El DFA recorre el texto carácter por carácter, usa coincidencia
más larga y produce tokens con tipo, lexema, línea y columna.

### YAPar

La especificación `.yalp` define cómo pueden combinarse los tokens. YAPar
calcula FIRST y FOLLOW, crea los estados LR(0) y llena ACTION/GOTO. Durante el
análisis, **shift** consume un token y **reduce** reconoce una producción. La
única colisión SLR restante aparece ante `=`; se resuelve con shift para permitir
que `x = valor` continúe como asignación en vez de reducir `x` antes de tiempo.

### Árbol

Cada reducción crea un nodo. El árbol conserva la estructura relevante del
programa: declaraciones, expresiones, bloques, funciones y clases. La interfaz
lo muestra para comprobar qué entendió el parser.

### Tabla de símbolos y ámbitos

Un símbolo guarda nombre, clase (variable, constante, función, parámetro,
método o clase), tipo, mutabilidad y ubicación. Cada bloque, función, clase,
bucle, `catch` o `switch` puede crear un entorno hijo. La resolución comienza
en el entorno actual y sube por sus padres, lo cual permite usar variables
externas y también hacer sombreado.

### Análisis semántico

El analizador recorre el árbol y verifica, entre otras reglas:

- nombres declarados y duplicados;
- compatibilidad de tipos y operadores;
- firmas, argumentos y retornos de funciones;
- condiciones booleanas;
- mutabilidad de constantes;
- uso correcto de `break`, `continue`, `return` y `this`;
- clases, herencia, constructores y miembros;
- tipos e índices de listas;
- código inalcanzable y variables no utilizadas como avisos.

## Relación con TAC

TAC pertenece a una fase posterior. Este proyecto deja lista la información que
esa fase necesitará: árbol ya validado, tipos resueltos y nombres asociados a su
símbolo y ámbito. Un futuro recorrido podría traducir expresiones a temporales y
saltos, pero aquí deliberadamente no se genera TAC.
