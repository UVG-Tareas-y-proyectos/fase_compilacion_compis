"""Memoria MIPS32 y descriptores de registros de la presentación 09.

El TAC de fase 2 usa palabras abstractas de 8 bytes. El backend asigna
posiciones físicas de 4 bytes para referencias a valores en MIPS32.
"""

from dataclasses import dataclass, field


class MIPSError(Exception):
    def __init__(self, message, line=0, column=0):
        super().__init__(message)
        self.line, self.column = line, column


@dataclass
class FrameLayout:
    name: str
    temporaries: dict
    arguments: list
    size: int
    header: dict = field(default_factory=lambda: {
        'ra': 0, 'fp_anterior': 4, 's0_entorno': 8, 's1_closure': 12,
        'manejador_anterior': 16, 'argumentos_entrada': 20,
        's2': 24, 's3': 28})

    @classmethod
    def build(cls, function):
        names = sorted({p for i in function.instructions for p in (i.arg1,i.arg2,i.result)
                        if p.startswith('%')})
        homes = {name: 32+4*n for n,name in enumerate(names)}
        pending = peak = 0
        for ins in function.instructions:
            if ins.op == 'param':
                pending += 1
                peak = max(peak,pending)
            elif ins.op == 'call':
                try:
                    count = int(ins.arg2)
                except ValueError as exc:
                    raise MIPSError('cantidad de argumentos TAC inválida',ins.line,ins.column) from exc
                if count < 0 or count > pending:
                    raise MIPSError('parámetros TAC insuficientes',ins.line,ins.column)
                pending -= count
        if pending:
            raise MIPSError('parámetros TAC sin llamada')
        arguments = [32+4*len(homes)+4*n for n in range(peak)]
        size = (32+4*(len(homes)+peak)+7)//8*8
        if size > 32760:
            raise MIPSError('registro de activación excede el desplazamiento MIPS de 16 bits')
        return cls(function.name,homes,arguments,size)


class RegisterAllocator:
    """getReg: registro libre o derrame del registro usado menos recientemente.

    Cada temporal tiene un hogar en la pila. Se vacían descriptores antes
    de saltos, etiquetas y llamadas para no mezclar caminos de control.
    """
    def __init__(self, homes, emit, registers=None):
        self.homes, self.emit = homes, emit
        self.registers = registers or [f'$t{i}' for i in range(8)]
        self.descriptors = {}
        self.dirty = set()
        self.spills = self.loads = self.stores = 0

    def spill(self, register):
        name = self.descriptors.pop(register, None)
        if name in self.dirty:
            self.emit(f'sw {register}, {self.homes[name]}($fp)')
            self.dirty.remove(name)
            self.stores += 1

    def getReg(self, name, *, write=False, pinned=()):
        if name not in self.homes:
            raise MIPSError(f'temporal TAC sin posición: {name}')
        found = next((r for r,n in self.descriptors.items() if n==name),None)
        if found:
            self.descriptors.pop(found)
            register = found
        else:
            register = next((r for r in self.registers if r not in self.descriptors),None)
            if register is None:
                register = next((r for r in self.descriptors if r not in pinned),None)
                if register is None:
                    raise MIPSError('no hay registro disponible para la instrucción')
                self.spill(register)
                self.spills += 1
            if not write:
                self.emit(f'lw {register}, {self.homes[name]}($fp)')
                self.loads += 1
        self.descriptors[register] = name
        if write:
            self.dirty.add(name)
        return register

    def flush(self):
        for register in list(self.descriptors):
            self.spill(register)


def peephole(lines):
    """Mirilla conservadora: movimientos propios, cargas repetidas y salto próximo."""
    import re
    result=[]
    for line in lines:
        stripped=line.strip()
        if re.fullmatch(r'move (\$\w+), \1',stripped):
            continue
        if result and stripped==result[-1].strip() and stripped.startswith('lw '):
            continue
        result.append(line)
    changed=True
    while changed:
        changed=False
        for i in range(len(result)-2):
            if result[i].startswith('j ') and result[i+1]=='nop' and result[i+2]==result[i][2:]+':':
                del result[i:i+2]
                changed=True
                break
    return result


@dataclass
class MIPSProgram:
    assembly: str
    frames: dict
    registers: dict
    optimized: bool

    def text(self):
        return self.assembly
