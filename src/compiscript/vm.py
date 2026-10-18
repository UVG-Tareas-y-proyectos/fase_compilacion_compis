"""Intérprete de cuádruplos para comprobar el TAC sin ejecutar código Python.

Cada llamada crea un registro de activación. Su padre léxico es el entorno
capturado por la closure, no el entorno del llamador. Los entornos capturados
permanecen vivos mientras alguna closure los referencia.
"""

from dataclasses import dataclass, field
import json
import operator


class RuntimeFault(Exception):
    def __init__(self, message, line=0, column=0):
        super().__init__(message)
        self.line, self.column = line, column


@dataclass
class RuntimeEnvironment:
    parent: object = None
    cells: dict = field(default_factory=dict)

    def read(self, name):
        env = self
        while env is not None:
            if name in env.cells:
                return env.cells[name]
            env = env.parent
        raise RuntimeFault(f'valor no inicializado: {name}')

    def write(self, name, value):
        env = self
        while env is not None:
            if name in env.cells:
                env.cells[name] = value
                return
            env = env.parent
        self.cells[name] = value


@dataclass
class Closure:
    label: str
    environment: RuntimeEnvironment
    receiver: object = None


@dataclass
class ClassValue:
    descriptor: dict
    environment: RuntimeEnvironment


@dataclass
class Instance:
    class_value: ClassValue
    fields: dict = field(default_factory=dict)


@dataclass
class ExecutionResult:
    output: list[str]
    steps: int
    max_call_depth: int


def display(value):
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if value is None:
        return 'null'
    if isinstance(value, list):
        return '[' + ', '.join(display(v) for v in value) + ']'
    if isinstance(value, Instance):
        return '<' + value.class_value.descriptor['name'] + '>'
    if isinstance(value, Closure):
        return '<closure ' + value.label + '>'
    return str(value)


class TACMachine:
    def __init__(self, program, *, max_steps=100000, max_depth=120):
        self.program = program
        self.max_steps, self.max_depth = max_steps, max_depth
        self.steps = self.depth = self.peak_depth = 0
        self.output = []
        self.classes = {}

    def run(self):
        self._call(Closure(self.program.entry, RuntimeEnvironment()), [])
        return ExecutionResult(self.output, self.steps, self.peak_depth)

    def _parent(self, cls):
        address = cls.descriptor.get('parent_address')
        return cls.environment.read(address) if address else None

    def _method(self, instance, name):
        if not isinstance(instance, Instance):
            raise RuntimeFault('el receptor no es un objeto')
        cls = instance.class_value
        while cls:
            label = cls.descriptor['methods'].get(name)
            if label:
                return Closure(label, cls.environment, instance)
            cls = self._parent(cls)
        raise RuntimeFault(f'método inexistente: {name}')

    def _new(self, cls):
        if not isinstance(cls, ClassValue):
            raise RuntimeFault('new requiere una clase')
        obj = Instance(cls)
        lineage = []
        current = cls
        while current:
            lineage.append(current)
            current = self._parent(current)
        for base in reversed(lineage):
            self._call(Closure(base.descriptor['initializer'], base.environment, obj), [])
        return obj

    def _call(self, closure, args):
        if not isinstance(closure, Closure):
            raise RuntimeFault('se intentó ejecutar un valor que no es una closure')
        if self.depth >= self.max_depth:
            raise RuntimeFault('se excedió el límite de profundidad de llamadas')
        function = self.program.functions[closure.label]
        if len(args) != len(function.parameters):
            raise RuntimeFault(f'cantidad de argumentos inválida para {function.name}')
        self.depth += 1
        self.peak_depth = max(self.peak_depth, self.depth)
        try:
            return self._execute(function, closure, args)
        finally:
            self.depth -= 1

    def _execute(self, function, closure, args):
        env = RuntimeEnvironment(closure.environment)
        for name, value in zip(function.parameters, args):
            env.cells[name] = value
        temporaries = {}
        labels = {i.result: n for n, i in enumerate(function.instructions) if i.op == 'label'}
        pending = []
        handlers = []
        exception = ''
        pc = 0

        def read(place):
            if place == '@this':
                if closure.receiver is None:
                    raise RuntimeFault('this no tiene receptor')
                return closure.receiver
            if place.startswith('%'):
                if place not in temporaries:
                    raise RuntimeFault(f'temporal no inicializado: {place}')
                return temporaries[place]
            if place.startswith('v'):
                return env.read(place)
            if place == '':
                return None
            try:
                return json.loads(place)
            except (ValueError, TypeError) as exc:
                raise RuntimeFault(f'operando TAC inválido: {place}') from exc

        def write(place, value):
            if place.startswith('%'):
                temporaries[place] = value
            else:
                env.write(place, value)

        def checked_index(container, index):
            if not isinstance(container, list) or type(index) is not int:
                raise RuntimeFault('acceso indexado requiere lista e índice entero')
            if index < 0 or index >= len(container):
                raise RuntimeFault(f'índice fuera de rango: {index}')
            return index

        def equal(x, y):
            return x is y if isinstance(x, (Instance, Closure, ClassValue, list)) else x == y

        binary = {'+': operator.add, '-': operator.sub, '*': operator.mul,
                  '==': equal, '!=': lambda x, y: not equal(x, y),
                  '<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge}
        while pc < len(function.instructions):
            ins = function.instructions[pc]
            self.steps += 1
            if self.steps > self.max_steps:
                raise RuntimeFault('se excedió el límite de instrucciones', ins.line, ins.column)
            pc += 1
            op, a, b, r = ins.op, ins.arg1, ins.arg2, ins.result
            try:
                if op == 'label':
                    continue
                if op == 'declare':
                    env.cells[a] = None
                elif op == 'copy':
                    write(r, read(a))
                elif op in binary:
                    write(r, binary[op](read(a), read(b)))
                elif op in {'/', '%'}:
                    x, y = read(a), read(b)
                    if y == 0:
                        raise RuntimeFault('división entre cero')
                    # División entera truncada hacia cero, sin convertir a float.
                    value = (abs(x) // abs(y)) * (-1 if (x < 0) != (y < 0) else 1) if type(x) is type(y) is int else x / y
                    write(r, value if op == '/' else x - value * y)
                elif op in {'neg', '!', 'i2f'}:
                    x = read(a)
                    write(r, -x if op == 'neg' else not x if op == '!' else float(x))
                elif op == 'goto':
                    pc = labels[r]
                elif op in {'if', 'ifFalse'}:
                    if bool(read(a)) == (op == 'if'):
                        pc = labels[r]
                elif op == 'enter':
                    env = RuntimeEnvironment(env)
                elif op == 'leave':
                    env = env.parent
                elif op == 'closure':
                    write(r, Closure(a, env, closure.receiver))
                elif op == 'param':
                    pending.append(read(a))
                elif op == 'call':
                    count = int(b)
                    arguments = pending[-count:] if count else []
                    if count:
                        del pending[-count:]
                    write(r, self._call(read(a), arguments))
                elif op == 'return':
                    return read(a)
                elif op == 'print':
                    self.output.append(display(read(a)))
                elif op == 'newlist':
                    write(r, [None] * int(a))
                elif op == 'length':
                    write(r, len(read(a)))
                elif op == 'load_index':
                    sequence, index = read(a), read(b)
                    write(r, sequence[checked_index(sequence, index)])
                elif op == 'store_index':
                    sequence, index = read(r), read(b)
                    sequence[checked_index(sequence, index)] = read(a)
                elif op == 'class':
                    cls = ClassValue(self.program.classes[a], env)
                    self.classes[cls.descriptor['name']] = cls
                    write(r, cls)
                elif op == 'newobj':
                    write(r, self._new(read(a)))
                elif op == 'method':
                    write(r, self._method(read(a), b))
                elif op == 'load_field':
                    write(r, read(a).fields[b])
                elif op == 'store_field':
                    read(r).fields[b] = read(a)
                elif op == 'try':
                    handlers.append((r, env))
                elif op == 'endtry':
                    handlers.pop()
                elif op == 'exception':
                    write(r, exception)
                else:
                    raise RuntimeFault(f'instrucción desconocida: {op}')
            except (RuntimeFault, ArithmeticError, IndexError, KeyError, TypeError, AttributeError) as exc:
                if handlers:
                    target, env = handlers.pop()
                    exception = str(exc)
                    pending.clear()
                    pc = labels[target]
                else:
                    if isinstance(exc, RuntimeFault) and exc.line:
                        raise
                    raise RuntimeFault(str(exc), ins.line, ins.column) from exc
        return None
