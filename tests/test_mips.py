from pathlib import Path
import pytest
from compiscript.pipeline import compile_source
from compiscript.mips import MIPSGenerator
from compiscript.mips_model import MIPSError
from compiscript.mips_runner import run_mars, simulator_paths, SimulatorError
from compiscript.vm import TACMachine


@pytest.fixture(scope='module',autouse=True)
def require_mars():
    try:
        simulator_paths()
    except SimulatorError as exc:
        pytest.skip(str(exc))


def compare(source, *, delayed=False):
    result=compile_source(source)
    assert result.ok,[str(d) for d in result.diagnostics]
    assembly=MIPSGenerator(result.tac).generate()
    execution=run_mars(assembly.text(),delayed=delayed)
    assert execution.ok,execution.stderr+execution.stdout
    assert execution.stdout.splitlines()==TACMachine(result.tac).run().output
    return assembly


@pytest.mark.parametrize('source',[
    'print(2+3*4); print(19/4); print(-19/4); print(-19%4);',
    'print(2+3.5); print(7.5/2); print(9.0%2.0); print(-2.5);',
    'print(true); print(!false); print(null); print("José"+" Pérez");',
    'print(1<2); print("igual"=="igual"); print(2.0>=2); print(1!=2);',
    'let x=0; print(false && (1/0>0)); print(true || (1/0>0)); print(true ? 7 : 1/0);',
    'function f(a:integer,b:integer,c:integer,d:integer,e:integer):integer{return a+b+c+d+e;} print(f(1,2,3,4,5));',
    'function f(n:integer):integer{if(n<=1){return 1;}return n*f(n-1);} print(f(6));',
    'let x=1; {let x=2;print(x);} print(x);',
    'try {print(5/0);} catch(e){print(e);} print(42);',
])
def test_primitives_and_calls_match_tac(source):
    compare(source)


def test_runs_with_delayed_branches_enabled():
    compare('function f(x:integer):integer {if(x<2){return x;} return f(x-1)+f(x-2);} print(f(7));',delayed=True)


def test_uncaught_error_is_nonzero_and_located():
    result=compile_source('let x=0;\nprint(10/x);')
    execution=run_mars(MIPSGenerator(result.tac).generate().text())
    assert not execution.ok and 'Error MIPS L2:C' in execution.stdout
    assert 'división entre cero' in execution.stdout


def test_literals_outside_mips_word_are_rejected():
    result=compile_source('print(2147483648);')
    with pytest.raises(MIPSError,match='rango MIPS32'):
        MIPSGenerator(result.tac).generate()


def test_assembler_failure_is_not_reported_as_success():
    assert not run_mars('.text\n.globl main\nmain: instruccion_inexistente\n',assemble_only=True).ok
