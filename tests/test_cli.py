import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(example):
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, "scripts/compiscript.py", example, "--simbolos"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        env=environment,
    )


def test_cli_accepts_valid_example():
    result = run_cli("examples/basico.cps")
    assert result.returncode == 0
    assert "Fase 1 completada correctamente" in result.stdout
    assert "Tabla de símbolos" in result.stdout


def test_cli_rejects_invalid_example():
    result = run_cli("examples/errores.cps")
    assert result.returncode == 1
    assert "semántico" in result.stderr
