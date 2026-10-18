import os
import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([sys.executable, 'scripts/compiscript.py', *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                          env={**os.environ, 'PYTHONUTF8': '1'})


def test_cli_generates_executes_and_exports(tmp_path):
    path = tmp_path / 'salida.json'
    result = run('examples/fase2_funciones_closures.cps', '--tac', '--ejecutar', '--salida', path)
    assert result.returncode == 0, result.stderr
    assert '120\n11\n12\n21' in result.stdout
    assert json.loads(path.read_text(encoding='utf-8'))['entry'] == '__main__'


def test_invalid_source_never_writes_output(tmp_path):
    path = tmp_path / 'salida.tac'
    result = run('examples/errores.cps', '--tac', '--salida', path)
    assert result.returncode == 1 and not path.exists()


def test_runtime_limit_returns_nonzero(tmp_path):
    path = tmp_path / 'infinito.cps'
    path.write_text('while (true) { print(1); }', encoding='utf-8')
    result = run(path, '--ejecutar', '--limite', '20')
    assert result.returncode == 1 and 'límite' in result.stderr


def test_missing_source_reports_readable_error():
    result = run('no_existe.cps', '--tac')
    assert result.returncode == 2 and 'No se pudo leer' in result.stderr
