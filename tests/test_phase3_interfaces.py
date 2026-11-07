import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
import tkinter as tk
import pytest

from compiscript.pipeline import compile_mips,compile_source
from compiscript.mips_runner import run_mars,SimulatorError,simulator_paths

ROOT=Path(__file__).resolve().parents[1]


def command(*args):
    return subprocess.run([sys.executable,'scripts/compiscript.py',*map(str,args)],cwd=ROOT,
        capture_output=True,encoding='utf-8',env={**os.environ,'PYTHONUTF8':'1'})


@pytest.fixture
def mars():
    try:
        simulator_paths()
    except SimulatorError as exc:
        pytest.skip(str(exc))


def test_pipeline_blocks_mips_on_semantic_or_target_error():
    result=compile_mips('let x:integer="incorrecto";')
    assert not result.ok and result.mips is None and result.tac is None
    result=compile_mips('print(2147483648);')
    assert not result.ok and result.mips is None and result.errors[0].phase=='ensamblador'
    assert result.errors[0].line==1
    assert compile_source('print(2147483648);').ok


def test_cli_writes_assembly_and_physical_map(tmp_path):
    target=tmp_path/'programa.asm'
    process=command('examples/basico.cps','--salida-mips',target,'--mapa-mips')
    assert process.returncode==0,process.stderr
    assert '.globl main' in target.read_text(encoding='utf-8')
    assert 'Fase 3 completada' in process.stdout and 'fp_anterior' in process.stdout


def test_asm_extension_is_assembly_not_tac(tmp_path):
    target=tmp_path/'programa.asm'
    process=command('examples/basico.cps','--salida',target)
    assert process.returncode==0 and '.text' in target.read_text(encoding='utf-8')


def test_cli_invalid_program_does_not_export(tmp_path):
    target=tmp_path/'programa.asm'
    process=command('examples/errores.cps','--salida-mips',target)
    assert process.returncode==1 and not target.exists()


def test_cli_runs_the_external_simulator(mars):
    process=command('examples/fase2_funciones_closures.cps','--ejecutar-mips')
    assert process.returncode==0,process.stderr
    assert '120\n11\n12\n21' in process.stdout


def test_cli_runtime_failure_returns_nonzero(mars,tmp_path):
    source=tmp_path/'error.cps'
    source.write_text('print(1/0);',encoding='utf-8')
    process=command(source,'--ejecutar-mips')
    assert process.returncode==1 and 'división entre cero' in process.stdout


def test_simulator_step_limit_is_a_failure(mars):
    result=compile_mips('while(true){}')
    execution=run_mars(result.mips.text(),max_steps=1000)
    assert not execution.ok and 'step' in execution.stderr.lower()


def test_mirilla_preserves_observable_behavior(mars):
    source='let x=0; for(let i=0;i<5;i=i+1){x=x+i;} print(x);'
    outputs=[]
    for optimize in [False,True]:
        result=compile_mips(source,optimize=optimize)
        execution=run_mars(result.mips.text())
        assert execution.ok
        outputs.append(execution.stdout)
    assert outputs==['10\n','10\n']


def test_ide_generates_executes_and_clears_stale_mips(mars):
    spec=importlib.util.spec_from_file_location('phase3_ide',ROOT/'scripts/ide.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        app=module.CompiscriptIDE()
    except tk.TclError as exc:
        pytest.skip(str(exc))
    app.withdraw()
    try:
        app._load('function f(n:integer):integer {return n+1;} print(f(8));')
        app.execute_mips()
        deadline=time.monotonic()+15
        while 'Ejecutando' in app.mips_run_text.get('1.0','end') and time.monotonic()<deadline:
            app.update()
            time.sleep(0.02)
        assert '9\n' in app.mips_run_text.get('1.0','end')
        assert 'correctamente' in app.mips_run_text.get('1.0','end')
        assert 'MARCOS FÍSICOS' in app.frame_text.get('1.0','end')
        app._load('let x:integer="error";')
        app.analyze()
        assert app.result.mips is None
        assert '.globl main' not in app.mips_text.get('1.0','end')
        assert '9\n' not in app.mips_run_text.get('1.0','end')
    finally:
        app.destroy()
