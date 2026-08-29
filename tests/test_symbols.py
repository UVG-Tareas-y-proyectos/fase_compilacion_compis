from compiscript.symbols import Symbol, SymbolTable


def test_nested_scope_resolves_parent_symbol():
    table = SymbolTable()
    outer = Symbol("dato", "variable", "integer")
    table.declare(outer)
    table.enter("interno", "bloque")
    assert table.resolve("dato") is outer


def test_shadowing_uses_nearest_declaration():
    table = SymbolTable()
    table.declare(Symbol("dato", "variable", "integer"))
    table.enter("interno", "bloque")
    inner = Symbol("dato", "variable", "string")
    table.declare(inner)
    assert table.resolve("dato") is inner


def test_duplicate_in_same_scope_is_rejected():
    table = SymbolTable()
    assert table.declare(Symbol("x", "variable", "integer"))
    assert not table.declare(Symbol("x", "variable", "integer"))
