"""Integración del IDE con el pipeline real, sin diálogos interactivos."""

import importlib.util
from pathlib import Path
import tkinter as tk
import pytest


def test_ide_compiles_executes_and_clears_stale_tac():
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'ide.py'
    spec = importlib.util.spec_from_file_location('compiscript_ide', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        app = module.CompiscriptIDE()
    except tk.TclError as exc:
        pytest.skip(f'Tk no disponible: {exc}')
    app.withdraw()
    try:
        app._load_example('fase2_funciones_closures')
        assert app.result.ok and app.result.tac
        app.execute_tac()
        assert '120\n11\n12\n21' in app.run_text.get('1.0', 'end')
        app._load('let x: integer = "error";')
        app.analyze()
        assert not app.result.ok
        assert app.result.tac is None
        assert 'function __main__' not in app.tac_text.get('1.0', 'end')
        assert app.frame_text.get('1.0', 'end').strip() == ''
        app.update_idletasks()
    finally:
        app.destroy()
