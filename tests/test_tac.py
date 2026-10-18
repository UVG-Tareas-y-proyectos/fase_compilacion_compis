from compiscript.pipeline import compile_source
import pytest


def compile_ok(source):
    result = compile_source(source)
    assert result.ok, [str(d) for d in result.diagnostics]
    assert result.tac is not None
    return result


def test_precedence_and_recycling():
    result = compile_ok('let a = 2 + 3 * 4; let b = 5 + 6; print(a + b);')
    code = result.tac.functions['__main__']
    operations = [i.op for i in code.instructions if i.op in {'+', '*'}]
    assert operations[:2] == ['*', '+']
    assert code.temporary_count < 6
    assert not code.frame['tamano'] % 8


def test_semantic_error_never_produces_tac():
    result = compile_source('let x: integer = "incorrecto";')
    assert not result.ok and result.tac is None


def test_short_circuit_and_ternary_have_jumps():
    result = compile_ok('let a = true && false || true; let b = a ? 1 : 2; print(b);')
    ops = [i.op for i in result.tac.functions['__main__'].instructions]
    assert 'ifFalse' in ops and 'if' in ops and 'goto' in ops


@pytest.mark.parametrize('source', [
    'if (true) { print(1); } else { print(2); }',
    'while (true) { if (false) { continue; } break; }',
    'do { print(1); continue; } while (false);',
    'for (let i = 0; i < 3; i = i + 1) { print(i); }',
    'switch (true) { case true: print(1); break; default: print(2); }',
    'try { print(1 / 0); } catch (error) { print(error); }',
])
def test_control_flow_targets_exist(source):
    result = compile_ok(source)
    for function in result.tac.functions.values():
        labels = {i.result for i in function.instructions if i.op == 'label'}
        assert all(i.result in labels for i in function.instructions
                   if i.op in {'goto', 'if', 'ifFalse', 'try'})


def test_nested_function_cannot_break_its_defining_loop():
    result = compile_source('while (true) { function f() { break; } break; }')
    assert not result.ok and result.tac is None
