from pathlib import Path
import pytest
from compiscript.pipeline import compile_source
from compiscript.vm import TACMachine


@pytest.mark.parametrize(('name', 'expected'), [
    ('basico', ['7']),
    ('clases_listas', ['Toby ladra', '11', '90']),
    ('fase2_expresiones', ['14', '14.0', 'correcto']),
    ('fase2_control', ['total correcto', '8']),
    ('fase2_funciones_closures', ['120', '11', '12', '21']),
    ('fase2_objetos_listas', ['24', '29']),
])
def test_demonstration_examples(name, expected):
    path = Path(__file__).resolve().parents[1] / 'examples' / f'{name}.cps'
    result = compile_source(path.read_text(encoding='utf-8'))
    assert result.ok, [str(d) for d in result.diagnostics]
    assert TACMachine(result.tac).run().output == expected


def test_rebuilds_own_frontend_without_preexisting_cache(tmp_path, monkeypatch):
    import compiscript.parser as parser
    monkeypatch.setattr(parser, 'GENERATED', tmp_path)
    frontend = parser.CompiscriptParser()
    assert frontend.parse('let x = 1; print(x);').ok
    assert (tmp_path / 'compiscript_lexer.py').exists()
    assert (tmp_path / 'compiscript_slr.pkl').exists()


def test_callable_return_can_be_called_directly():
    result = compile_source('function f(): Closure { function g(x: float): float { return x; } return g; } print(f()(2));')
    assert result.ok, [str(d) for d in result.diagnostics]
    assert TACMachine(result.tac).run().output == ['2.0']
