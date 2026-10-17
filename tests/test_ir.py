from compiscript.ir import Instruction, TemporaryPool
from compiscript.layout import extend_symbols
from compiscript.pipeline import analyze_source


def test_temporary_is_reused_only_after_consumption():
    pool = TemporaryPool()
    a, b = pool.acquire(), pool.acquire()
    assert a != b
    pool.release(a)
    assert pool.acquire() == a
    assert pool.created == pool.peak == 2


def test_extended_symbols_have_distinct_addresses_and_frame_header():
    result = analyze_source('let x = 1; { let x = 2; print(x); } print(x);')
    extend_symbols(result.symbol_table)
    rows = result.symbol_table.code_rows()
    assert len({row[9] for row in rows}) == len(rows)
    assert all(row[10] >= 32 and row[11] == 8 for row in rows)
    assert result.symbol_table.global_environment.frame['cabecera']['enlace_acceso'] == 8


def test_quadruple_rendering():
    assert Instruction('+', 'a', 'b', '%t1').text() == '%t1 = a + b'
    assert Instruction('ifFalse', '%t1', result='L1').text() == 'ifFalse %t1 goto L1'
