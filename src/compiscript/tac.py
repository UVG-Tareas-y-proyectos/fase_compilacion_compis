"""Traducción dirigida por la sintaxis sobre los atributos de la fase 1.

Cada _expr_* devuelve el atributo sintetizado (tipo, lugar). Los ámbitos,
destinos de salto y función actual son el contexto heredado del recorrido.
"""

from dataclasses import dataclass
import json

from .ir import FunctionCode, Instruction, TACProgram, TemporaryPool
from .layout import WORD, extend_symbols, layout_classes
from .semantic import SemanticAnalyzer, _data, _location
from .tree import Tree


@dataclass
class Value:
    place: str
    type_name: str
    symbol: object = None


class GenerationError(Exception):
    def __init__(self, node, message):
        super().__init__(message)
        self.line, self.column = _location(node)


class TACGenerator(SemanticAnalyzer):
    """Mismo patrón Visitor y helpers de tipos de SemanticAnalyzer, segunda pasada."""

    def __init__(self, semantic):
        super().__init__()
        self.semantic = semantic
        self.table = semantic.symbol_table
        self.attributes = semantic.expressions
        self.scopes = semantic.scopes
        self.declarations = semantic.declarations
        self.program = TACProgram()
        self.current_env = self.table.global_environment
        self.class_symbol = None
        self.label_count = 0
        self.depth = 0
        self.break_targets = []
        self.continue_targets = []
        self.try_depths = []

    def generate(self):
        extend_symbols(self.table)
        try:
            layout_classes(self.table)
        except ValueError as exc:
            raise GenerationError(self.semantic.tree, str(exc)) from exc
        tree = self.semantic.tree
        root = tree.children[0] if _data(tree) == 'start' else tree
        self.code = FunctionCode('__main__', 'programa', frame=self.current_env.frame)
        self.pool = TemporaryPool()
        self.program.functions[self.code.label] = self.code
        self._statements(root.children)
        self.emit('return')
        self._finish_frame()
        return self.program

    def _finish_frame(self):
        self.code.temporary_count = self.pool.created
        self.code.peak_live = self.pool.peak
        frame = self.code.frame
        start = frame['tamano']
        frame['temporales'] = [
            {'nombre': f'%t{i+1}', 'desplazamiento': start + i * WORD, 'tamano': WORD}
            for i in range(self.pool.created)]
        frame['tamano'] = start + self.pool.created * WORD

    def emit(self, op, a='', b='', result='', node=None):
        line, col = _location(node) if node is not None else (0, 0)
        self.code.instructions.append(Instruction(op, str(a), str(b), str(result), line, col))

    def label(self):
        self.label_count += 1
        return f'L{self.label_count}'

    def mark(self, label):
        self.emit('label', result=label)

    def release(self, *values):
        for value in values:
            if value is not None:
                self.pool.release(value.place)

    def temporary(self, type_name):
        return Value(self.pool.acquire(), type_name)

    def _type(self, node):
        info = self.attributes.get(id(node))
        return info.type_name if info else '<desconocido>'

    def _expr(self, node):
        kind = _data(node)
        handler = getattr(self, f'_expr_{kind}', None)
        if handler is None:
            raise GenerationError(node, f'no existe regla TAC para {kind}')
        return handler(node)

    def _statement(self, node):
        handler = getattr(self, f'_stmt_{_data(node)}', None)
        if handler is None:
            raise GenerationError(node, f'no existe regla TAC para {_data(node)}')
        handler(node)

    def _statements(self, statements):
        # Las firmas ya existen en fase 1. Crear closures antes de los cuerpos
        # permite recursión y llamadas a funciones declaradas posteriormente.
        for node in statements:
            if _data(node) == 'function_declaration':
                symbol = self.declarations[id(node)]
                self.emit('declare', symbol.address)
                self.emit('closure', symbol.label, result=symbol.address, node=node)
                self._compile_function(node)
            elif _data(node) == 'class_declaration':
                self._compile_class(node)
        for node in statements:
            self._statement(node)

    def _stmt_function_declaration(self, node):
        pass  # la definición se emite una vez, al entrar en su ámbito

    _stmt_class_declaration = _stmt_function_declaration

    def _compile_function(self, node, *, label=None, name=None, env=None, initializer=False):
        saved = (self.code, self.pool, self.current_env, self.depth,
                 self.break_targets, self.continue_targets, self.try_depths)
        symbol = self.declarations.get(id(node))
        environment = env or symbol.environment
        parameters = ([] if initializer else
                      [s.address for s in environment.symbols.values() if s.kind == 'parámetro'])
        self.code = FunctionCode(label or symbol.label, name or symbol.name,
                                 parameters, frame=environment.frame)
        self.program.functions[self.code.label] = self.code
        self.pool = TemporaryPool()
        self.current_env, self.depth = environment, 0
        self.break_targets, self.continue_targets = [], []
        self.try_depths = []
        if initializer:
            for member in node.children:
                if _data(member) in {'variable_declaration', 'constant_declaration'}:
                    self._stmt_variable_declaration(member)
        else:
            self._stmt_block(next(c for c in node.children if _data(c) == 'block'))
        self.emit('return')
        self._finish_frame()
        (self.code, self.pool, self.current_env, self.depth,
         self.break_targets, self.continue_targets, self.try_depths) = saved

    def _compile_class(self, node):
        symbol = self.declarations[id(node)]
        previous_class = self.class_symbol
        self.class_symbol = symbol
        descriptor = {'name': symbol.name, 'parent': symbol.metadata.get('parent'),
                      'size': symbol.size, 'methods': {}, 'fields': [],
                      'initializer': symbol.label + '_init'}
        parent = self.current_env.resolve(descriptor['parent']) if descriptor['parent'] else None
        descriptor['parent_address'] = parent.address if parent else ''
        for member in symbol.environment.symbols.values():
            if member.kind in {'función', 'método'}:
                descriptor['methods'][member.name] = member.label
            else:
                descriptor['fields'].append({'name': member.name, 'offset': member.offset,
                                             'size': member.size, 'type': member.type_name})
        self.program.classes[symbol.label] = descriptor
        self.emit('declare', symbol.address)
        self.emit('class', symbol.label, result=symbol.address, node=node)
        # El inicializador tiene su propio registro, separado del programa global.
        from .layout import HEADER
        init_env = type('InitEnvironment', (), {})()
        init_env.resolve = symbol.environment.resolve
        init_env.frame = {'entorno': 'inicializador ' + symbol.name,
                          'cabecera': dict(HEADER), 'parametros': [], 'locales': [],
                          'temporales': [], 'tamano': 32}
        self._compile_function(node, label=descriptor['initializer'],
                               name='inicializador ' + symbol.name, env=init_env, initializer=True)
        for member in node.children:
            if _data(member) == 'function_declaration':
                self._compile_function(member)
        self.class_symbol = previous_class

    def _stmt_return_statement(self, node):
        if node.children:
            value = self._expr(node.children[0])
            # Buscar la firma de la función actual sin depender del nombre.
            owner = next((s for e in self.table.environments() for s in e.symbols.values()
                          if s.label == self.code.label), None)
            if owner:
                value = self._cast(value, owner.return_type)
            self.emit('return', value.place, node=node)
            self.release(value)
        else:
            self.emit('return', node=node)

    def _enter(self, node):
        previous = self.current_env
        self.current_env = self.scopes[id(node)]
        self.emit('enter', self.current_env.code_id, node=node)
        self.depth += 1
        return previous

    def _leave(self, previous):
        self.emit('leave')
        self.depth -= 1
        self.current_env = previous

    def _stmt_block(self, node):
        previous = self._enter(node)
        self._statements(node.children)
        self._leave(previous)

    def _cast(self, value, expected):
        if value.type_name == 'integer' and expected == 'float':
            result = self.temporary('float')
            self.emit('i2f', value.place, result=result.place)
            self.release(value)
            return result
        return value

    def _stmt_variable_declaration(self, node):
        symbol = self.declarations[id(node)]
        init = next((c for c in node.children if _data(c) == 'initializer'), None)
        default = {'integer': '0', 'float': '0.0', 'boolean': 'false', 'string': '""'}
        value = (self._expr(init.children[0]) if init else
                 Value(default.get(symbol.type_name, 'null'), symbol.type_name))
        value = self._cast(value, symbol.type_name)
        if symbol.storage == 'atributo':
            self.emit('store_field', value.place, symbol.name, '@this', node)
        else:
            self.emit('declare', symbol.address, node=node)
            self.emit('copy', value.place, result=symbol.address, node=node)
        self.release(value)

    _stmt_variable_declaration_no_semi = _stmt_variable_declaration
    _stmt_constant_declaration = _stmt_variable_declaration

    def _stmt_expression_statement(self, node):
        self.release(self._expr(node.children[0]))

    def _stmt_print_statement(self, node):
        value = self._expr(node.children[0])
        self.emit('print', value.place, node=node)
        self.release(value)

    def _branch_false(self, expression, target):
        value = self._expr(expression)
        self.emit('ifFalse', value.place, result=target, node=expression)
        self.release(value)

    def _stmt_if_statement(self, node):
        other, end = self.label(), self.label()
        self._branch_false(node.children[0], other)
        self._stmt_block(node.children[1])
        self.emit('goto', result=end)
        self.mark(other)
        if len(node.children) > 2:
            self._stmt_block(node.children[2])
        self.mark(end)

    def _loop_body(self, block, end, step):
        self.break_targets.append((end, self.depth))
        self.continue_targets.append((step, self.depth))
        self._stmt_block(block)
        self.continue_targets.pop()
        self.break_targets.pop()

    def _stmt_while_statement(self, node):
        start, end = self.label(), self.label()
        self.mark(start)
        self._branch_false(node.children[0], end)
        self._loop_body(node.children[1], end, start)
        self.emit('goto', result=start)
        self.mark(end)

    def _stmt_do_while_statement(self, node):
        start, step, end = self.label(), self.label(), self.label()
        self.mark(start)
        self._loop_body(node.children[0], end, step)
        self.mark(step)
        self._branch_false(node.children[1], end)
        self.emit('goto', result=start)
        self.mark(end)

    def _stmt_for_statement(self, node):
        previous = self._enter(node)
        block = next(c for c in node.children if _data(c) == 'block')
        condition = next((c for c in node.children if _data(c) == 'for_condition'), None)
        update = next((c for c in node.children if _data(c) == 'for_update'), None)
        for child in node.children:
            if child is block or child is condition or child is update:
                continue
            if _data(child) == 'variable_declaration_no_semi':
                self._stmt_variable_declaration(child)
            else:
                self.release(self._expr(child))
        start, step, end = self.label(), self.label(), self.label()
        self.mark(start)
        if condition:
            self._branch_false(condition.children[0], end)
        self._loop_body(block, end, step)
        self.mark(step)
        if update:
            self.release(self._expr(update.children[0]))
        self.emit('goto', result=start)
        self.mark(end)
        self._leave(previous)

    def _stmt_foreach_statement(self, node):
        collection = self._expr(node.children[1])
        previous = self._enter(node)
        symbol = self.declarations[id(node)]
        self.emit('declare', symbol.address)
        index, length = self.temporary('integer'), self.temporary('integer')
        self.emit('copy', '0', result=index.place)
        self.emit('length', collection.place, result=length.place)
        start, step, end = self.label(), self.label(), self.label()
        self.mark(start)
        test = self.temporary('boolean')
        self.emit('<', index.place, length.place, test.place)
        self.emit('ifFalse', test.place, result=end)
        self.release(test)
        self.emit('load_index', collection.place, index.place, symbol.address, node)
        self._loop_body(node.children[2], end, step)
        self.mark(step)
        self.emit('+', index.place, '1', index.place)
        self.emit('goto', result=start)
        self.mark(end)
        self.release(collection, index, length)
        self._leave(previous)

    def _jump_context(self, node, targets):
        if not targets:
            raise GenerationError(node, 'salto sin contexto de destino')
        target, depth = targets[-1]
        for try_depth in reversed(self.try_depths):
            if depth <= try_depth:
                self.emit('endtry', node=node)
        for _ in range(self.depth - depth):
            self.emit('leave', node=node)
        self.emit('goto', result=target, node=node)

    def _stmt_break_statement(self, node):
        self._jump_context(node, self.break_targets)

    def _stmt_continue_statement(self, node):
        self._jump_context(node, self.continue_targets)

    def _stmt_switch_statement(self, node):
        previous = self._enter(node)
        value = self._expr(node.children[0])
        end = self.label()
        cases = [(child, self.label()) for child in node.children[1:]]
        fallback = end
        for child, label in cases:
            if _data(child) == 'default_case':
                fallback = label
            else:
                expected = self._expr(child.children[0])
                test = self.temporary('boolean')
                self.emit('==', value.place, expected.place, test.place, child)
                self.emit('if', test.place, result=label, node=child)
                self.release(expected, test)
        self.emit('goto', result=fallback)
        self.release(value)
        self.break_targets.append((end, self.depth))
        for child, label in cases:
            self.mark(label)
            statements = child.children[1:] if _data(child) == 'switch_case' else child.children
            self._statements(statements)
        self.break_targets.pop()
        self.mark(end)
        self._leave(previous)

    def _stmt_try_catch_statement(self, node):
        catch, end = self.label(), self.label()
        self.emit('try', result=catch, node=node)
        self.try_depths.append(self.depth)
        self._stmt_block(node.children[0])
        self.try_depths.pop()
        self.emit('endtry')
        self.emit('goto', result=end)
        self.mark(catch)
        previous = self._enter(node)
        error = self.declarations[id(node)]
        self.emit('declare', error.address)
        self.emit('exception', result=error.address)
        self._stmt_block(node.children[2])
        self._leave(previous)
        self.mark(end)

    def _literal(self, node):
        text = str(node.children[0])
        kind = _data(node)
        if kind == 'integer_literal':
            text = str(int(text))
        elif kind == 'float_literal':
            text = str(float(text))
        elif kind == 'string_literal':
            # La regla léxica conserva barras literalmente: serializar a JSON
            # no debe interpretarlas como escapes de Python o de JSON.
            text = json.dumps(text[1:-1], ensure_ascii=False)
        return Value(text, self._type(node))

    _expr_integer_literal = _literal
    _expr_float_literal = _literal
    _expr_string_literal = _literal
    _expr_null_literal = _literal
    _expr_true_literal = _literal
    _expr_false_literal = _literal

    def _expr_identifier_expr(self, node):
        symbol = self.attributes[id(node)].symbol
        value = self.temporary(self._type(node))
        value.symbol = symbol
        # Copia inmediata: a + (a = 2) utiliza el valor anterior de a.
        if symbol.storage == 'atributo':
            self.emit('load_field', '@this', symbol.name, value.place, node)
        elif symbol.kind == 'método':
            self.emit('method', '@this', symbol.name, value.place, node)
        else:
            self.emit('copy', symbol.address, result=value.place, node=node)
        return value

    def _expr_left_hand_side(self, node):
        value = self._expr(node.children[0])
        for suffix in node.children[1:]:
            kind = _data(suffix)
            if kind == 'call_suffix':
                args = suffix.children[0].children if suffix.children else []
                value = self._invoke(value, args, self._type(suffix), suffix)
            elif kind == 'index_suffix':
                index = self._expr(suffix.children[0])
                result = self.temporary(value.type_name[:-2])
                self.emit('load_index', value.place, index.place, result.place, suffix)
                self.release(value, index)
                value = result
            else:
                info = self.attributes[id(suffix)]
                member = info.symbol
                result = self.temporary(info.type_name)
                result.symbol = member
                self.emit('method' if member and member.kind == 'método' else 'load_field',
                          value.place, str(suffix.children[0]), result.place, suffix)
                self.release(value)
                value = result
        return value

    def _invoke(self, callee, args, type_name, node):
        values = [self._expr(arg) for arg in args]
        symbol = callee.symbol
        if symbol and symbol.kind not in {'función', 'método'}:
            symbol = symbol.metadata.get('callable')
        if symbol:
            values = [self._cast(v, t) for v, t in zip(values, symbol.parameters)]
        for value in values:
            self.emit('param', value.place, node=node)
        result = self.temporary(type_name)
        self.emit('call', callee.place, str(len(values)), result.place, node)
        self.release(callee, *values)
        return result

    def _expr_this_expr(self, node):
        value = self.temporary(self._type(node))
        self.emit('copy', '@this', result=value.place, node=node)
        return value

    def _expr_new_expr(self, node):
        symbol = self.current_env.resolve(str(node.children[0]))
        # El ámbito del inicializador puede ser sintético: usar la resolución de fase 1.
        if symbol is None:
            symbol = self._find_class(str(node.children[0]))
        instance = self.temporary(symbol.name)
        self.emit('newobj', symbol.address, result=instance.place, node=node)
        constructor = self._resolve_member(symbol.name, 'constructor')
        if constructor:
            method = self.temporary('función')
            method.symbol = constructor
            self.emit('method', instance.place, 'constructor', method.place, node)
            args = node.children[1].children if len(node.children) > 1 else []
            self.release(self._invoke(method, args, 'void', node))
        return instance

    def _expr_array_literal(self, node):
        result = self.temporary(self._type(node))
        self.emit('newlist', str(len(node.children)), result=result.place, node=node)
        for i, child in enumerate(node.children):
            value = self._cast(self._expr(child), result.type_name[:-2])
            self.emit('store_index', value.place, str(i), result.place, child)
            self.release(value)
        return result

    def _expr_assign_expr(self, node):
        target = node.children[0]
        while _data(target) in {'left_hand_side', 'ternary_expr'} and len(target.children) == 1:
            target = target.children[0]
        held = []
        if _data(target) == 'identifier_expr':
            symbol = self.attributes[id(target)].symbol
            field = symbol.storage == 'atributo'
            destination = ('store_field', '@this', symbol.name) if field else ('copy', symbol.address, '')
            expected = symbol.type_name
        elif _data(target) == 'left_hand_side':
            last = target.children[-1]
            prefix = Tree('left_hand_side', target.children[:-1])
            base = self._expr_left_hand_side(prefix)
            held.append(base)
            if _data(last) == 'index_suffix':
                index = self._expr(last.children[0])
                held.append(index)
                destination = ('store_index', base.place, index.place)
            else:
                destination = ('store_field', base.place, str(last.children[0]))
            expected = self._type(target)
        else:
            raise GenerationError(node, 'destino de asignación no traducible')
        value = self._cast(self._expr(node.children[1]), expected)
        op, address, selector = destination
        self.emit(op, value.place, selector, address, node)
        self.release(*held)
        return value

    def _binary(self, node):
        left = self._expr(node.children[0])
        for i in range(1, len(node.children), 2):
            op = str(node.children[i])
            right = self._expr(node.children[i+1])
            numeric = left.type_name in {'integer', 'float'} and right.type_name in {'integer', 'float'}
            if numeric and 'float' in {left.type_name, right.type_name}:
                left, right = self._cast(left, 'float'), self._cast(right, 'float')
            result_type = ('boolean' if op in {'==', '!=', '<', '<=', '>', '>='}
                           else self._common_type(left.type_name, right.type_name))
            result = self.temporary(result_type)
            self.emit(op, left.place, right.place, result.place, node)
            self.release(left, right)
            left = result
        return left

    _expr_additive_expr = _binary
    _expr_multiplicative_expr = _binary
    _expr_relational_expr = _binary
    _expr_equality_expr = _binary

    def _expr_unary_expr(self, node):
        value = self._expr(node.children[1])
        result = self.temporary(self._type(node))
        self.emit('neg' if str(node.children[0]) == '-' else '!', value.place,
                  result=result.place, node=node)
        self.release(value)
        return result

    def _logical(self, node, conjunction):
        result = self.temporary('boolean')
        end = self.label()
        self.emit('copy', 'false' if conjunction else 'true', result=result.place)
        for child in node.children[::2]:
            value = self._expr(child)
            self.emit('ifFalse' if conjunction else 'if', value.place, result=end, node=node)
            self.release(value)
        self.emit('copy', 'true' if conjunction else 'false', result=result.place)
        self.mark(end)
        return result

    def _expr_logical_and_expr(self, node):
        return self._logical(node, True)

    def _expr_logical_or_expr(self, node):
        return self._logical(node, False)

    def _expr_ternary_expr(self, node):
        if len(node.children) == 1:
            return self._expr(node.children[0])
        result = self.temporary(self._type(node))
        other, end = self.label(), self.label()
        condition = self._expr(node.children[0])
        self.emit('ifFalse', condition.place, result=other)
        self.release(condition)
        yes = self._cast(self._expr(node.children[1]), result.type_name)
        self.emit('copy', yes.place, result=result.place)
        self.release(yes)
        self.emit('goto', result=end)
        self.mark(other)
        no = self._cast(self._expr(node.children[2]), result.type_name)
        self.emit('copy', no.place, result=result.place)
        self.release(no)
        self.mark(end)
        return result
