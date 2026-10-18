"""Pruebas de comportamiento: ejecutar el TAC generado y verificar resultados."""

import pytest
from compiscript.pipeline import compile_source
from compiscript.vm import TACMachine, RuntimeFault


def execute(source):
    compiled = compile_source(source)
    assert compiled.ok, [str(d) for d in compiled.diagnostics]
    return TACMachine(compiled.tac).run()


@pytest.mark.parametrize(('source', 'output'), [
    ('print(2 + 3 * 4); print((2 + 3) * 4); print(10 - 3 - 2);', ['14', '20', '5']),
    ('print(-7 / 2); print(7 / 2.0); print(!false);', ['-3', '3.5', 'true']),
    ('let a = 1; print(a + (a = 2)); print(a);', ['3', '2']),
    ('let x = 0; let a = false && ((x = 1) == 1); let b = true || ((x = 2) == 2); print(x);', ['0']),
    ('let x = 0; print(true ? (x = 1) : (x = 2)); print(x);', ['1', '1']),
    ('let x = 1; { let x = 2; print(x); } print(x);', ['2', '1']),
    ('let i = 0; while (i < 4) { i = i + 1; if (i == 2) { continue; } if (i == 4) { break; } print(i); }', ['1', '3']),
    ('let i = 0; do { i = i + 1; continue; } while (i < 2); print(i);', ['2']),
    ('for (let i = 0; i < 4; i = i + 1) { if (i == 1) { continue; } print(i); }', ['0', '2', '3']),
    ('switch (true) { case false: print(0); break; case true: print(1); break; default: print(2); }', ['1']),
    ('switch (true) { case true: print(1); default: print(2); }', ['1', '2']),
    ('let xs = [1, 2, 3]; xs[1] = 8; foreach (x in xs) { print(x); }', ['1', '8', '3']),
    ('let xs = [[1, 2], [3, 4]]; xs[1][0] = 9; print(xs[1][0]);', ['9']),
    ('function f(n: integer): integer { if (n <= 1) { return 1; } return n * f(n - 1); } print(f(6));', ['720']),
    ('function f(a: integer, b: integer): integer { return a * 10 + b; } print(f(f(1, 2), f(3, 4)));', ['154']),
    ('function f(x: integer): integer { function g(): integer { return x + 1; } return g(); } print(f(8));', ['9']),
    ('function contador(n: integer): Closure { function siguiente(): integer { n = n + 1; return n; } return siguiente; } let a = contador(10); let b = contador(20); print(a()); print(a()); print(b());', ['11', '12', '21']),
    ('class A { let x = 2; function constructor(n: integer) { this.x = n; } function doble(): integer { return this.x * 2; } } let a = new A(5); print(a.doble());', ['10']),
    ('class A { let x = 3; function valor(): integer { return this.x; } } class B: A { let y = 4; function total(): integer { return this.valor() + this.y; } } let b = new B(); print(b.total());', ['7']),
    ('try { print(1 / 0); } catch (error) { print("capturado"); } print(2);', ['capturado', '2']),
    ('while (true) { try { break; } catch (e) { print("no"); } } try { print(1 / 0); } catch (e) { print("si"); }', ['si']),
    ('class A { let x = 1; function valor(): integer { return this.x; } } let a = new A(); let f = a.valor; print(f());', ['1']),
    ('let xs = [1, 2.5]; print(xs[0]); print(xs[1]);', ['1.0', '2.5']),
    ('let xs = [1, 2, 3]; foreach (x in xs) { if (x == 2) { continue; } print(x); }', ['1', '3']),
    ('function par(n: integer): boolean { if (n == 0) { return true; } return impar(n - 1); } function impar(n: integer): boolean { if (n == 0) { return false; } return par(n - 1); } print(par(8));', ['true']),
    ('print(007); print(-7 % 2);', ['7', '-1']),
    ('let a = [1]; let b = [1]; print(a == b); let c = a; print(a == c);', ['false', 'true']),
])
def test_generated_tac_preserves_behavior(source, output):
    assert execute(source).output == output


def test_recursion_creates_distinct_activation_records():
    result = execute('function f(n: integer): integer { if (n == 0) { return 0; } return f(n - 1) + 1; } print(f(5));')
    assert result.output == ['5'] and result.max_call_depth == 7


def test_execution_limit_is_reported():
    result = compile_source('while (true) { print(1); }')
    with pytest.raises(RuntimeFault, match='límite de instrucciones'):
        TACMachine(result.tac, max_steps=50).run()


def test_invalid_index_does_not_use_python_negative_indexing():
    result = compile_source('let xs = [1]; print(xs[-1]);')
    with pytest.raises(RuntimeFault, match='fuera de rango'):
        TACMachine(result.tac).run()
