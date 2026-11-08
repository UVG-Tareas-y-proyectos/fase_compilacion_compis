# Compiscript — Fases 1, 2 y 3

Compilador académico de Ihan Marroquin y Diego Patzan. Analiza Compiscript, genera código de tres direcciones (TAC) y lo traduce a ensamblador MIPS32 ejecutable en MARS. Conserva funciones, recursión, ámbitos, closures, clases, herencia, listas y manejo de errores.

## Preparación

Requiere Python 3.10 o posterior con Tkinter. Desde la carpeta del repositorio, en PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\preparar_mips.py
```

El último comando descarga MARS oficial y comprueba su SHA-256. Si falta Java, prepara un JRE 17 portátil. Las herramientas quedan en `tools/`, fuera de Git. La preparación requiere Internet una vez; después puede ejecutarse sin conexión. Generar `.asm` solamente requiere Python; ejecutarlo requiere Java y MARS.

## Interfaz gráfica

```powershell
.\.venv\Scripts\python.exe scripts\ide.py
```

Elegir `fase3_llamadas` y presionar **Compilar (F5)**. Las pestañas **Árbol**, **Símbolos**, **Errores** y **TAC** muestran las etapas previas. **MIPS** muestra el ensamblador y **Memoria** compara los registros abstractos con los marcos físicos MIPS32.

**Ejecutar MIPS (F6)** inicia MARS y muestra `720`, `15` y `25` en **Salida MIPS**. **Exportar MIPS** guarda un `.asm` completo, con sus rutinas de apoyo. **Ejecutar TAC** y **Exportar TAC** conservan la fase 2.

La simulación se ejecuta en segundo plano con límites de tiempo e instrucciones. Una nueva compilación limpia las salidas anteriores y descarta resultados de simulaciones anteriores pendientes.

## Terminal

```powershell
.\.venv\Scripts\python.exe scripts\compiscript.py examples\fase3_llamadas.cps --salida-mips programa.asm
.\.venv\Scripts\python.exe scripts\compiscript.py examples\fase3_llamadas.cps --ejecutar-mips
.\.venv\Scripts\python.exe scripts\compiscript.py examples\fase3_memoria.cps --ejecutar-mips
.\.venv\Scripts\python.exe scripts\compiscript.py examples\fase3_control.cps --ejecutar-mips
.\.venv\Scripts\python.exe scripts\compiscript.py examples\basico.cps --mips --mapa-mips
```

`--salida programa.asm` también exporta ensamblador; `.tac` y `.json` conservan la exportación anterior. `--sin-mirilla` desactiva la optimización local. `--tiempo-mips` limita segundos (15 por defecto) y `--limite-mips` instrucciones simuladas (2 000 000 por defecto). Este límite es diferente de `--limite`, que controla instrucciones TAC.

Se puede configurar `MARS_JAR` y, opcionalmente, `COMPISCRIPT_JAVA`; también se reconoce Java en PATH. Para ejecutar el archivo exportado directamente:

```powershell
.\tools\jre\bin\java.exe -jar tools\Mars4_5.jar nc me sm programa.asm
```

Si se utiliza Java de PATH, reemplazar la ruta del ejecutable por `java`. En la interfaz de MARS, abrir el `.asm`, usar **Run → Assemble** y después **Run → Go**. Se incluyen NOP después de saltos y llamadas y se prueba también delayed branching activado. [Comandos de MARS](https://dpetersanderson.github.io/Help/MarsHelpCommand.html).

Las fases anteriores siguen disponibles:

```powershell
.\.venv\Scripts\python.exe scripts\compiscript.py examples\basico.cps --arbol --simbolos
.\.venv\Scripts\python.exe scripts\compiscript.py examples\fase2_funciones_closures.cps --tac --registros --ejecutar
```

## Arquitectura

```text
.cps → YALex/YAPar → árbol → semántica y símbolos → TAC → MIPS → MARS
```

YALex construye un lexer DFA desde `grammar/Compiscript.yal` y YAPar genera las tablas SLR de `grammar/Compiscript.yalp`. Conservamos `Compiscript.g4` como referencia. Continuamos con los generadores propios del proyecto anterior. El backend recibe TAC validado; no ejecuta el programa para fabricar el ensamblador.

| Componente | Responsabilidad |
| --- | --- |
| `parser.py`, `semantic.py`, `symbols.py` | Árbol, tipos, símbolos y ámbitos |
| `ir.py`, `layout.py`, `tac.py` | Cuádruplos, memoria abstracta y generación de TAC |
| `vm.py` | Intérprete TAC utilizado como referencia en las pruebas |
| `mips_model.py` | Marcos físicos, descriptores, `getReg()` y mirilla |
| `mips.py` | Traducción de cuádruplos e instrucciones destino |
| `mips_runtime.asm` | Rutinas MIPS para valores, entornos, objetos y errores |
| `mips_runner.py` | Ejecución externa en MARS con límites |
| `pipeline.py` | Coordinación de las fases y diagnósticos |

El llamador guarda los argumentos en su marco. La convención interna pasa la closure en `$a0`, la dirección del vector de argumentos en `$a1` y su cantidad en `$a2`; devuelve una referencia en `$v0`. Es una convención propia, diferente de la ABI o32 de C.

Cada procedimiento reserva un marco alineado a ocho bytes mediante `$sp`, guarda `$ra`, `$fp` y `$s0`–`$s3`, y restaura el estado al retornar. `$fp` permite localizar temporales y argumentos. Cada llamada recursiva dispone de su propio marco. El modelo abstracto de fase 2 usaba palabras de ocho bytes; el backend calcula una distribución física independiente con referencias de cuatro bytes.

`getReg()` utiliza `$t0`–`$t7` y asigna registros libres. Si todos están ocupados, derrama el menos recientemente usado a su hogar en la pila. Los descriptores se vacían antes de etiquetas, saltos y llamadas. `$t8` y `$t9` se reservan para apoyo. La mirilla elimina movimientos propios, cargas consecutivas idénticas y saltos a la etiqueta inmediatamente siguiente.

Los entornos capturados permanecen en el heap. Una closure conserva código, entorno de definición y receptor; una instancia conserva su clase y campos. La búsqueda de métodos comienza en la clase hija y continúa hacia sus padres. Cada operación TAC se convierte en instrucciones o llamadas a rutinas MIPS; no se interpreta una tabla de cuádruplos dentro de MARS.

Los enteros tienen signo y 32 bits, con desbordamientos detectados. Los `float` utilizan precisión double y se rechazan resultados no finitos. La división entera trunca hacia cero y el residuo conserva el signo del dividendo. La notación de salida de punto flotante puede diferir de Python. Las cadenas usan bytes Latin-1 y terminador NUL; caracteres fuera de ese conjunto o NUL internos producen un diagnóstico. El heap dura hasta terminar la simulación; no implementamos recolección de basura MIPS.

`try/catch` conserva el punto de recuperación, la pila y el entorno, incluso para errores originados en una llamada interna. Los errores no capturados muestran línea y columna y terminan con código distinto de cero. Se controlan división entre cero, índices, desbordamiento y profundidad de llamadas (256 activaciones).

La CLI devuelve 0 al completar, 1 ante errores de compilación o ejecución y 2 ante errores de lectura o escritura. Las fases anteriores con errores impiden generar MIPS.

## Pruebas y ejemplos

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

La batería conserva las pruebas anteriores y ejecuta en MARS sus casos de comportamiento. Cubre recursión, más de cuatro parámetros, closures independientes, herencia, listas anidadas, cortocircuito, excepciones, generación inválida, errores del ensamblador, CLI, IDE y límites de simulación. Requiere preparar MARS; si falta, pytest identifica las pruebas dependientes como omitidas. GitHub Actions prepara el simulador antes de probar.

| Ejemplo | Resultado |
| --- | --- |
| `fase3_llamadas.cps` | `720`, `15`, `25` |
| `fase3_memoria.cps` | `11`, `12`, `21`, `24` |
| `fase3_control.cps` | `8`, `3`, `3.5`, `false`, error de índice capturado y `continuamos` |
| `fase3_error_generacion.cps` | Diagnóstico de literal fuera del rango MIPS32 |
| `fase3_error_ejecucion.cps` | Error de división entre cero en MARS |

## Documentación

- [Fase 3](docs/fase3.pdf): arquitectura, llamadas, registros, traducción y ejecución.
- [Fase 2](docs/fase2.pdf): lenguaje intermedio y diseño anterior.
