import pytest

from compiscript.pipeline import analyze_source


VALID_PROGRAMS = [
    "let x: integer = 1; print(x);",
    "let x: float = 1; print(x);",
    "let x: integer = 1; { let x: string = \"a\"; print(x); } print(x);",
    "function doble(x: integer): integer { return x + x; } print(doble(2));",
    "class A { let x: integer; function constructor(x: integer) { this.x = x; } } let a: A = new A(1);",
    "let xs: integer[] = [1, 2, 3]; let x: integer = xs[0]; print(x);",
    "let b: boolean = true; while (b) { b = false; break; }",
    "for (let i: integer = 0; i < 3; i = i + 1) { print(i); }",
    "let xs: integer[] = [1]; foreach (x in xs) { print(x); }",
    "let b: boolean = true; switch (b) { case true: print(b); default: print(false); }",
    "try { print(1); } catch (error) { print(error); }",
    "let b: boolean = true; let x: integer = b ? 1 : 2; print(x);",
    "function factorial(n: integer): integer { if (n <= 1) { return 1; } return n * factorial(n - 1); } print(factorial(4));",
    "function exterior(x: integer): integer { function interior(): integer { return x; } return interior(); } print(exterior(2));",
    "let b: boolean = true; do { b = false; } while (b);",
]


@pytest.mark.parametrize("source", VALID_PROGRAMS)
def test_valid_programs(source):
    result = analyze_source(source)
    assert result.ok, [str(item) for item in result.diagnostics]
    assert result.phase_reached == "semántico"


INVALID_PROGRAMS = [
    ("let x = 1; let x = 2;", "ya fue declarado"),
    ("print(x);", "no declarado"),
    ("const x: integer = 1; x = 2;", "constante"),
    ("let x: integer = \"a\";", "no se puede inicializar"),
    ("if (1) { print(1); }", "debe ser boolean"),
    ("break;", "break solo"),
    ("continue;", "continue solo"),
    ("return 1;", "return solo"),
    ("function f(x) { print(x); }", "necesita tipo"),
    ("function f(): integer { if (true) { return 1; } }", "no retorna"),
    ("function f(x: integer) { print(x); } f();", "espera 1"),
    ("function f(x: integer) { print(x); } f(\"a\");", "argumento 1"),
    ("let xs = [1, \"a\"];", "tipo compatible"),
    ("let xs: integer[] = [1]; print(xs[false]);", "índice"),
    ("class A { let x: integer; } let a: A = new A(); print(a.y);", "no contiene"),
    ("let a: Fantasma = new Fantasma();", "no declarado"),
    ("print(this);", "this solo"),
    ("1 = 2;", "no es asignable"),
    ("const x: integer;", "debe inicializarse"),
    ("function f(x: integer, x: integer) { print(x); }", "parámetro duplicado"),
    ("function f(): integer { return \"a\"; }", "return de tipo"),
    ("function f() { return; } let x = f * 2;", "no aplica"),
    ("class A { let x: integer; } let a: A = new A(1);", "no declara constructor"),
]


@pytest.mark.parametrize(("source", "message"), INVALID_PROGRAMS)
def test_invalid_programs(source, message):
    result = analyze_source(source)
    assert not result.ok
    assert any(message in item.message for item in result.errors), [
        str(item) for item in result.diagnostics
    ]


def test_unused_variable_is_warning_not_error():
    result = analyze_source("let x: integer = 1;")
    assert result.ok
    assert any(item.severity == "aviso" for item in result.diagnostics)


def test_symbol_report_keeps_closed_scopes():
    result = analyze_source(
        "function f(x: integer): integer { let y = x; return y; } print(f(1));"
    )
    rows = result.symbol_table.rows()
    assert any(row[3] == "x" and row[4] == "parámetro" for row in rows)
    assert any(row[3] == "y" and row[2] > 0 for row in rows)


def test_dead_code_is_reported_as_warning():
    result = analyze_source("function f(): integer { return 1; print(2); } print(f());")
    assert result.ok
    assert any("inalcanzable" in item.message for item in result.warnings)
