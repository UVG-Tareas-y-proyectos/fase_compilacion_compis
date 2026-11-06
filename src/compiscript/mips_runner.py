"""Ejecución del ensamblador en el simulador externo MARS, sin usar TACMachine."""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


class SimulatorError(Exception):
    pass


@dataclass
class MARSResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self):
        return self.returncode==0


def simulator_paths():
    jar=Path(os.environ.get('MARS_JAR',ROOT/'tools/Mars4_5.jar'))
    portable=ROOT/'tools/jre/bin'/('java.exe' if os.name=='nt' else 'java')
    java=os.environ.get('COMPISCRIPT_JAVA')
    if not java and portable.exists():
        java=str(portable)
    if not java:
        java=shutil.which('java')
    if not java or not jar.is_file():
        raise SimulatorError('Falta Java o MARS. Ejecute: python scripts/preparar_mips.py')
    return java,jar


def run_mars(assembly, *, timeout=15, max_steps=2000000, assemble_only=False, delayed=False):
    if timeout<=0 or max_steps<=0:
        raise ValueError('los límites del simulador deben ser positivos')
    java,jar=simulator_paths()
    with tempfile.TemporaryDirectory(prefix='compiscript_mips_') as directory:
        source=Path(directory)/'programa.asm'
        source.write_text(assembly,encoding='utf-8')
        command=[str(java),'-Dfile.encoding=UTF-8','-Djava.awt.headless=true','-jar',str(jar),
                 'nc','me','ae2','se3','sm',str(max_steps)]
        if assemble_only:
            command.append('a')
        if delayed:
            command.append('db')
        command.append(str(source))
        try:
            result=subprocess.run(command,capture_output=True,encoding='utf-8',errors='replace',
                timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(f'MARS excedió el límite de {timeout} segundos') from exc
        except OSError as exc:
            raise SimulatorError(f'No se pudo iniciar Java/MARS: {exc}') from exc
        code=result.returncode
        if 'maximum' in result.stderr.lower() and 'step' in result.stderr.lower():
            code=1
        return MARSResult(result.stdout,result.stderr,code)
