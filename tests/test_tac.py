from compiscript.pipeline import compile_source


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
