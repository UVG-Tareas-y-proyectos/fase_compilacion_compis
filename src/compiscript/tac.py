"""Traducción dirigida por la sintaxis sobre los atributos de la fase 1.

Cada _expr_* devuelve el atributo sintetizado (tipo, lugar). Los ámbitos,
destinos de salto y función actual son el contexto heredado del recorrido.
"""

from dataclasses import dataclass
import json

from .ir import FunctionCode, Instruction, TACProgram, TemporaryPool
from .layout import WORD, extend_symbols
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

    def generate(self):
        extend_symbols(self.table)
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
        for node in statements:
            self._statement(node)

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

    def _literal(self, node):
        return Value(str(node.children[0]), self._type(node))

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
        self.emit('copy', symbol.address, result=value.place, node=node)
        return value

    def _expr_left_hand_side(self, node):
        if len(node.children) == 1:
            return self._expr(node.children[0])
        raise GenerationError(node, 'los accesos y llamadas necesitan su regla TAC')

    def _expr_assign_expr(self, node):
        target = node.children[0]
        while _data(target) in {'left_hand_side', 'ternary_expr'} and len(target.children) == 1:
            target = target.children[0]
        if _data(target) != 'identifier_expr':
            raise GenerationError(node, 'destino de asignación todavía no traducido')
        symbol = self.attributes[id(target)].symbol
        value = self._cast(self._expr(node.children[1]), symbol.type_name)
        self.emit('copy', value.place, result=symbol.address, node=node)
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
