"""Backend TAC -> MIPS32 para MARS. No ejecuta el programa al compilarlo.

Cada cuádruplo emite instrucciones y llamadas a rutinas MIPS de apoyo.
Las etiquetas y llamadas son código destino, no un intérprete de TAC.
"""

from dataclasses import asdict
import json
import math
from pathlib import Path

from .mips_model import FrameLayout, RegisterAllocator, MIPSError, MIPSProgram, peephole


BINARY = {'+':'add','-':'sub','*':'mul','/':'div','%':'mod',
          '==':'eq','!=':'ne','<':'lt','<=':'le','>':'gt','>=':'ge'}


class MIPSGenerator:
    def __init__(self, program, *, optimize=True):
        self.program, self.optimize = program, optimize
        self.lines, self.data = [], []
        self.constants, self.names, self.frames, self.stats = {}, {}, {}, {}
        self.functions={label:f'cs_fn_{n}' for n,label in enumerate(program.functions)}

    def emit(self, line):
        self.lines.append(line)

    def call(self, label):
        self.emit('jal '+label)
        self.emit('nop')

    def ident(self, name):
        if name not in self.names:
            self.names[name]=len(self.names)+1
        return self.names[name]

    def string(self, text):
        try:
            data=text.encode('latin-1')
        except UnicodeEncodeError as exc:
            raise MIPSError('MARS utiliza cadenas de un byte: carácter fuera de Latin-1') from exc
        if 0 in data:
            raise MIPSError('las cadenas MIPS no admiten el carácter NUL')
        label=f'cs_str_{len(self.data)}'
        self.data.extend([label+':', '.byte '+','.join(map(str,[*data,0]))])
        return label

    def constant(self, operand):
        if operand=='':
            return '__cs_null'
        if operand in self.constants:
            return self.constants[operand]
        try:
            value=json.loads(operand)
        except ValueError as exc:
            raise MIPSError(f'operando TAC inválido: {operand}') from exc
        if value is None:
            return '__cs_null'
        if type(value) is bool:
            return '__cs_true' if value else '__cs_false'
        label=f'cs_const_{len(self.constants)}'
        if type(value) is int:
            if not -2147483648<=value<=2147483647:
                raise MIPSError('literal integer fuera del rango MIPS32 con signo')
            body=[f'.word 1, {value}, 0, 0']
        elif type(value) is float:
            if not math.isfinite(value):
                raise MIPSError('literal float no finito')
            body=['.word 3, 0',f'.double {value!r}']
        elif isinstance(value,str):
            body=[f'.word 4, {self.string(value)}, 0, 0']
        else:
            raise MIPSError('literal TAC no traducible a MIPS')
        self.constants[operand]=label
        self.data.extend(['.align 3',label+':',*body])
        return label

    def read(self, place, target):
        if place.startswith('%'):
            self.emit(f'move {target}, {self.reg.getReg(place)}')
        elif place.startswith('v'):
            self.reg.flush()
            self.emit('move $a0, $s0')
            self.emit(f'li $a1, {self.ident(place)}')
            self.call('__cs_get')
            self.emit(f'move {target}, $v0')
        elif place=='@this':
            self.emit(f'lw {target}, 12($s1)')
            self.emit(f'beq {target}, $zero, __cs_err_this')
            self.emit('nop')
        else:
            self.emit(f'la {target}, {self.constant(place)}')

    def arguments(self, places):
        # Materializar en la pila antes de resolver otro nombre, porque las
        # rutinas de búsqueda pueden modificar los registros de argumentos.
        self.reg.flush()
        if places:
            self.emit('addiu $sp, $sp, -16')
            for i,place in enumerate(places):
                self.read(place,'$v1')
                self.emit(f'sw $v1, {4*i}($sp)')
            for i in range(len(places)):
                self.emit(f'lw $a{i}, {4*i}($sp)')
            self.emit('addiu $sp, $sp, 16')

    def write(self, place):
        if place.startswith('%'):
            self.emit(f'move {self.reg.getReg(place,write=True)}, $v0')
        elif place:
            self.reg.flush()
            self.emit('move $a2, $v0')
            self.emit('move $a0, $s0')
            self.emit(f'li $a1, {self.ident(place)}')
            self.call('__cs_set')

    def generate(self):
        if self.program.entry not in self.functions:
            raise MIPSError('el TAC no contiene el punto de entrada')
        self.emit('.text')
        self.emit('.globl main')
        self.emit('main:')
        self.emit('li $t0, -8')
        self.emit('and $sp, $sp, $t0')
        self.emit('move $a0, $zero')
        self.call('__cs_env_new')
        self.emit('move $a1, $v0')
        self.emit('move $a2, $zero')
        self.emit('la $a0, '+self.functions[self.program.entry])
        self.call('__cs_closure')
        self.emit('move $a0, $v0')
        self.emit('move $a1, $zero')
        self.emit('move $a2, $zero')
        self.call(self.functions[self.program.entry])
        self.emit('li $v0, 10')
        self.emit('syscall')
        for label,function in self.program.functions.items():
            self.function(label,function)
        for label,desc in self.program.classes.items():
            if desc['initializer'] not in self.functions or any(v not in self.functions for v in desc['methods'].values()):
                raise MIPSError('descriptor de clase con función inexistente')
            self.data.extend(['.align 2',self.class_label(label)+':',
                              f'.word {self.functions[desc["initializer"]]}, {len(desc["methods"])}, {self.string(desc["name"])}'])
            # string() agrega datos: el descriptor tiene que ser contiguo.
            # El nombre ya se emitió al evaluar la lista anterior.
            for name,method in desc['methods'].items():
                self.data.append(f'.word {self.ident(name)}, {self.functions[method]}')
        runtime=Path(__file__).with_name('mips_runtime.asm').read_text(encoding='utf-8')
        # NOP explícito permite ejecutar también con delayed branching de MARS.
        runtime_lines=runtime.splitlines()
        padded=[]
        branches={'j','jal','jr','jalr','beq','bne','blt','bgt','ble','bge','bltz','bgez','bgtz','blez','bc1t','bc1f'}
        for n,line in enumerate(runtime_lines):
            padded.append(line)
            words=line.strip().split()
            if words and words[0] in branches and (n+1==len(runtime_lines) or runtime_lines[n+1].strip()!='nop'):
                padded.append('    nop')
        runtime='\n'.join(padded)+'\n'
        lines=peephole(self.lines) if self.optimize else self.lines
        assembly='# Compiscript - MIPS32 para MARS 4.5\n.data\n'+ '\n'.join(self.data)+'\n'+ '\n'.join(lines)+'\n'+runtime
        return MIPSProgram(assembly,self.frames,self.stats,self.optimize)

    def class_label(self, label):
        return 'cs_class_'+str(list(self.program.classes).index(label))

    def function(self, label, function):
        frame=FrameLayout.build(function)
        self.frames[label]=asdict(frame)
        self.frame, self.prefix=frame,self.functions[label]
        self.reg=RegisterAllocator(frame.temporaries,self.emit)
        self.pending=0
        self.emit('\n# Procedimiento '+function.name)
        self.emit(self.prefix+':')
        self.emit(f'li $t0, {len(function.parameters)}')
        self.emit('bne $a2, $t0, __cs_err_arity')
        self.emit('nop')
        self.emit(f'addiu $sp, $sp, -{frame.size}')
        for reg,offset in [('$ra',0),('$fp',4),('$s0',8),('$s1',12),('$s2',24),('$s3',28)]:
            self.emit(f'sw {reg}, {offset}($sp)')
        self.emit('move $fp, $sp')
        self.emit('sw $a1, 20($fp)')
        self.emit('lw $t0, __cs_handler')
        self.emit('sw $t0, 16($fp)')
        self.emit('move $s1, $a0')
        self.emit('lw $t0, __cs_depth')
        self.emit('addiu $t0, $t0, 1')
        self.emit('sw $t0, __cs_depth')
        self.emit('bgt $t0, 256, __cs_err_depth')
        self.emit('nop')
        self.emit('lw $a0, 8($s1)')
        self.call('__cs_env_new')
        self.emit('move $s0, $v0')
        for n,param in enumerate(function.parameters):
            self.emit('move $a0, $s0')
            self.emit(f'li $a1, {self.ident(param)}')
            self.call('__cs_declare')
            self.emit('lw $t0, 20($fp)')
            self.emit(f'lw $a2, {4*n}($t0)')
            self.emit('move $a0, $s0')
            self.emit(f'li $a1, {self.ident(param)}')
            self.call('__cs_set')
        targets={i.result for i in function.instructions if i.op=='label'}
        for ins in function.instructions:
            try:
                if ins.op in {'goto','if','ifFalse','try'} and ins.result not in targets:
                    raise MIPSError('salto TAC a etiqueta inexistente')
                self.instruction(ins)
            except MIPSError as exc:
                if not exc.line:
                    exc.line,exc.column=ins.line,ins.column
                raise
        self.reg.flush()
        self.emit('la $v0, __cs_null')
        self.emit(self.prefix+'_return:')
        self.emit('lw $t8, 16($fp)')
        self.emit('sw $t8, __cs_handler')
        self.emit('lw $t8, __cs_depth')
        self.emit('addiu $t8, $t8, -1')
        self.emit('sw $t8, __cs_depth')
        self.emit('move $sp, $fp')
        for reg,offset in [('$ra',0),('$s0',8),('$s1',12),('$s2',24),('$s3',28)]:
            self.emit(f'lw {reg}, {offset}($sp)')
        self.emit('lw $fp, 4($sp)')
        self.emit(f'addiu $sp, $sp, {frame.size}')
        self.emit('jr $ra')
        self.emit('nop')
        self.stats[label]={'derrames':self.reg.spills,'cargas':self.reg.loads,'almacenamientos':self.reg.stores}

    def instruction(self, ins):
        op,a,b,r=ins.op,ins.arg1,ins.arg2,ins.result
        self.emit(f'# TAC L{ins.line}:C{ins.column}: {ins.text()}')
        if op=='label':
            self.reg.flush()
            self.emit(self.prefix+'_'+r+':')
            return
        self.emit(f'li $t8, {ins.line}')
        self.emit('sw $t8, __cs_line')
        self.emit(f'li $t8, {ins.column}')
        self.emit('sw $t8, __cs_column')
        if op=='declare':
            self.reg.flush()
            self.emit('move $a0, $s0')
            self.emit(f'li $a1, {self.ident(a)}')
            self.call('__cs_declare')
        elif op=='copy':
            self.read(a,'$v0')
            self.write(r)
        elif op in BINARY:
            self.arguments([a,b])
            self.call('__cs_'+BINARY[op])
            self.write(r)
        elif op in {'neg','!','i2f','print','length','newobj'}:
            self.arguments([a])
            self.call('__cs_'+{'!':'not','newobj':'new'}.get(op,op))
            if op!='print':
                self.write(r)
        elif op in {'goto','if','ifFalse'}:
            self.reg.flush()
            if op=='goto':
                self.emit('j '+self.prefix+'_'+r)
            else:
                self.arguments([a])
                self.call('__cs_truth')
                self.emit(f'{"bne" if op=="if" else "beq"} $v0, $zero, {self.prefix}_{r}')
            self.emit('nop')
        elif op=='enter':
            self.reg.flush()
            self.emit('move $a0, $s0')
            self.call('__cs_env_new')
            self.emit('move $s0, $v0')
        elif op=='leave':
            self.reg.flush()
            self.emit('lw $s0, 0($s0)')
        elif op=='closure':
            if a not in self.functions:
                raise MIPSError('closure TAC con función inexistente')
            self.reg.flush()
            self.emit('la $a0, '+self.functions[a])
            self.emit('move $a1, $s0')
            self.emit('lw $a2, 12($s1)')
            self.call('__cs_closure')
            self.write(r)
        elif op=='param':
            self.read(a,'$v1')
            self.emit(f'sw $v1, {self.frame.arguments[self.pending]}($fp)')
            self.pending+=1
        elif op=='call':
            self.reg.flush()
            self.read(a,'$a0')
            count=int(b)
            start=self.pending-count
            self.emit(f'addiu $a1, $fp, {self.frame.arguments[start]}' if count else 'move $a1, $zero')
            self.emit(f'li $a2, {count}')
            self.emit('lw $t8, 0($a0)')
            self.emit('bne $t8, 6, __cs_err_callable')
            self.emit('nop')
            self.emit('lw $t9, 4($a0)')
            self.emit('jalr $t9')
            self.emit('nop')
            self.pending=start
            self.write(r)
        elif op=='return':
            self.reg.flush()
            self.read(a,'$v0')
            self.emit('j '+self.prefix+'_return')
            self.emit('nop')
        elif op=='newlist':
            self.reg.flush()
            self.emit('li $a0, '+a)
            self.call('__cs_newlist')
            self.write(r)
        elif op in {'load_index','store_index'}:
            self.arguments([a,b] if op=='load_index' else [r,b,a])
            self.call('__cs_'+op)
            if op=='load_index':
                self.write(r)
        elif op in {'load_field','store_field','method'}:
            self.arguments([a] if op!='store_field' else [r,a])
            if op=='store_field':
                self.emit('move $a2, $a1')
            self.emit(f'li $a1, {self.ident(b)}')
            self.call('__cs_'+op)
            if op!='store_field':
                self.write(r)
        elif op=='class':
            if a not in self.program.classes:
                raise MIPSError('clase TAC inexistente')
            parent=self.program.classes[a]['parent_address']
            self.arguments([parent] if parent else ['null'])
            self.emit('move $a2, $a0')
            self.emit('move $a1, $s0')
            self.emit('la $a0, '+self.class_label(a))
            self.call('__cs_class')
            self.write(r)
        elif op=='try':
            self.reg.flush()
            self.emit('la $a0, '+self.prefix+'_'+r)
            self.call('__cs_try')
        elif op=='endtry':
            self.reg.flush()
            self.emit('lw $t8, __cs_handler')
            self.emit('lw $t8, 0($t8)')
            self.emit('sw $t8, __cs_handler')
        elif op=='exception':
            self.emit('lw $v0, __cs_exception')
            self.write(r)
        else:
            raise MIPSError(f'instrucción TAC no soportada por MIPS: {op}')
