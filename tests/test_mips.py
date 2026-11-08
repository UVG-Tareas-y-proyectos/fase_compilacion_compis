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


# Mismos casos de comportamiento de fase 2, ejecutados ahora en MARS.
from test_execution import test_generated_tac_preserves_behavior as _behavior_spec
BEHAVIOR_CASES=next(m.args[1] for m in _behavior_spec.pytestmark if m.name=='parametrize')


@pytest.mark.parametrize(('source','expected'),BEHAVIOR_CASES)
def test_existing_language_behaviors_run_as_real_mips(source,expected):
    compiled=compile_source(source)
    assert compiled.ok
    execution=run_mars(MIPSGenerator(compiled.tac).generate().text())
    assert execution.ok,execution.stderr+execution.stdout
    assert execution.stdout.splitlines()==expected


@pytest.mark.parametrize('name',['basico','clases_listas','fase2_expresiones','fase2_control',
    'fase2_funciones_closures','fase2_objetos_listas','fase2_error_ejecucion'])
def test_previous_examples_match_tac_in_mars(name):
    compare((Path(__file__).resolve().parents[1]/'examples'/f'{name}.cps').read_text(encoding='utf-8'))


@pytest.mark.parametrize('source',[
    'let xs=[[1,2],[3,4]]; print(xs);',
    'function f(x:integer):integer {return 1/x;} try {print(f(0));} catch(e){print(e);} print(f(2));',
    'function f():integer {try {return 5;} catch(e){return 2;}} print(f()); try{print(1/0);} catch(e){print(e);}',
    'function f():Closure { function g(x:float):float{return x;} return g;} print(f()(2));',
    'let xs=[1]; try{print(xs[-1]);}catch(e){print(e);} print(xs[0]);',
    'class A {let x=1; function m():integer{return this.x;}} class B:A {function m():integer{return this.x+2;}} let b=new B(); print(b.m()); print(b);',
    'function f():integer{return 1;} print(f); print(10000000000.0%3.0);',
    'print(-0.0%2.0); print(-9.5%2.0); let minimo=-2147483647-1; print(minimo%-1);',
])
def test_advanced_values_exceptions_and_capture(source):
    compare(source,delayed=True)


@pytest.mark.parametrize('expr',['2147483647+1','50000*50000','-2147483647-2'])
def test_integer_overflow_reports_error_instead_of_silent_wrap(expr):
    result=compile_source('print('+expr+');')
    execution=run_mars(MIPSGenerator(result.tac).generate().text())
    assert not execution.ok and 'desbordamiento' in execution.stdout


@pytest.mark.parametrize(('name','expected'),[
    ('fase3_llamadas',['720','15','25']),
    ('fase3_memoria',['11','12','21','24']),
    ('fase3_control',['8','3','3.5','false','índice fuera de rango: 5','continuamos']),
])
def test_phase3_demonstrations(name,expected):
    source=(Path(__file__).resolve().parents[1]/'examples'/f'{name}.cps').read_text(encoding='utf-8')
    result=compile_source(source)
    assert result.ok
    execution=run_mars(MIPSGenerator(result.tac).generate().text())
    assert execution.ok,execution.stderr
    assert execution.stdout.splitlines()==expected
