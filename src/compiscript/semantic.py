"""Visitor semántico de Compiscript.

La implementación recorre el árbol producido por YAPar. Cada expresión
se evalúa a un tipo estático y cada declaración se registra en la tabla de
símbolos del entorno actual.
"""

from dataclasses import dataclass, field

from .parser import Diagnostic
from .symbols import Environment, Symbol, SymbolTable
from .tree import Token, Tree


ERROR = "<error>"
UNKNOWN = "<desconocido>"
VOID = "void"
NUMERIC = {"integer", "float"}


@dataclass
class ExpressionInfo:
    type_name: str
    symbol: Symbol | None = None
    assignable: bool = False


@dataclass
class SemanticResult:
    tree: Tree
    symbol_table: SymbolTable
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def errors(self):
        return [item for item in self.diagnostics if item.severity == "error"]

    @property
    def warnings(self):
        return [item for item in self.diagnostics if item.severity == "aviso"]

    @property
    def ok(self):
        return not self.errors


def _data(node) -> str:
    return str(node.data) if isinstance(node, Tree) else ""


def _location(node) -> tuple[int, int]:
    if isinstance(node, Tree):
        return getattr(node.meta, "line", 0), getattr(node.meta, "column", 0)
    if isinstance(node, Token):
        return node.line or 0, node.column or 0
    return 0, 0


class SemanticAnalyzer:
    def __init__(self):
        self.table = SymbolTable()
        self.diagnostics: list[Diagnostic] = []
        self._declarations: dict[int, Symbol | None] = {}
        self.function_stack: list[Symbol] = []
        self.class_stack: list[Symbol] = []
        self.loop_depth = 0

    def analyze(self, tree: Tree) -> SemanticResult:
        program = tree.children[0] if _data(tree) == "start" else tree
        self._predeclare(program.children)
        self._visit_statements(program.children)
        self._emit_unused_warnings()
        return SemanticResult(tree, self.table, self.diagnostics)

    # ------------------------------------------------------------------
    # Diagnósticos y tipos
    # ------------------------------------------------------------------

    def error(self, node, message):
        line, column = _location(node)
        self.diagnostics.append(Diagnostic(
            "semántico", message, line, column, "error"
        ))

    def warning(self, node, message):
        line, column = _location(node)
        self.diagnostics.append(Diagnostic(
            "semántico", message, line, column, "aviso"
        ))

    def _type_from_tree(self, node: Tree | None) -> str:
        if node is None:
            return UNKNOWN
        if _data(node) == "type_annotation":
            node = node.children[0]
        if _data(node) != "type":
            return UNKNOWN
        base = node.children[0]
        base_kind = _data(base)
        if base_kind.endswith("_type") and base_kind != "named_type":
            result = base_kind.removesuffix("_type")
        elif base_kind == "named_type":
            result = str(base.children[0])
        else:
            result = UNKNOWN
        dimensions = sum(_data(child) == "array_suffix"
                         for child in node.children[1:])
        return result + "[]" * dimensions

    def _compatible(self, expected: str, actual: str) -> bool:
        if ERROR in {expected, actual} or UNKNOWN in {expected, actual}:
            return True
        if expected == actual:
            return True
        if actual == UNKNOWN + "[]" and expected.endswith("[]"):
            return True
        if actual == "null" and self._is_reference_type(expected):
            return True
        return expected == "float" and actual == "integer"

    def _is_reference_type(self, type_name):
        if type_name.endswith("[]"):
            return True
        return any(symbol.kind == "clase" and symbol.name == type_name
                   for environment in self.table.environments()
                   for symbol in environment.symbols.values())

    def _common_type(self, left: str, right: str) -> str:
        if left == right:
            return left
        if left in NUMERIC and right in NUMERIC:
            return "float"
        return ERROR

    def _validate_type_name(self, type_name, node):
        base = type_name
        while base.endswith("[]"):
            base = base[:-2]
        if base in {"integer", "float", "boolean", "string", VOID,
                    UNKNOWN, ERROR, "null"}:
            return
        if self._find_class(base) is None:
            self.error(node, f"tipo '{base}' no declarado")

    # ------------------------------------------------------------------
    # Declaraciones y ámbitos
    # ------------------------------------------------------------------

    def _predeclare(self, statements):
        for statement in statements:
            kind = _data(statement)
            if kind == "function_declaration":
                self._predeclare_function(statement)
            elif kind == "class_declaration":
                self._predeclare_class(statement)

    def _function_parts(self, node):
        name = str(node.children[0])
        parameters = next((child for child in node.children
                           if _data(child) == "parameters"), None)
        return_tree = next((child for child in node.children
                            if _data(child) == "type"), None)
        block = next(child for child in node.children
                     if _data(child) == "block")
        return name, parameters, return_tree, block

    def _parameter_specs(self, parameters):
        specs = []
        if parameters is None:
            return specs
        for parameter in parameters.children:
            name = str(parameter.children[0])
            annotation = next((child for child in parameter.children
                               if _data(child) == "type_annotation"), None)
            specs.append((name, self._type_from_tree(annotation), parameter))
        return specs

    def _predeclare_function(self, node, method=False):
        name, parameters, return_tree, _ = self._function_parts(node)
        parameter_types = [spec[1] for spec in self._parameter_specs(parameters)]
        symbol = Symbol(
            name=name,
            kind="método" if method else "función",
            type_name="función",
            parameters=parameter_types,
            return_type=self._type_from_tree(return_tree)
            if return_tree is not None else VOID,
            line=_location(node)[0],
            column=_location(node)[1],
            mutable=False,
            metadata={"node": node},
        )
        if not self.table.declare(symbol):
            self.error(node, f"'{name}' ya fue declarado en este ámbito")
            self._declarations[id(node)] = None
        else:
            self._declarations[id(node)] = symbol
        return symbol

    def _predeclare_class(self, node):
        name = str(node.children[0])
        symbol = Symbol(
            name=name,
            kind="clase",
            type_name=name,
            line=_location(node)[0],
            column=_location(node)[1],
            mutable=False,
            metadata={"node": node},
        )
        if not self.table.declare(symbol):
            self.error(node, f"'{name}' ya fue declarado en este ámbito")
            self._declarations[id(node)] = None
        else:
            self._declarations[id(node)] = symbol
        return symbol

    def _visit_statements(self, statements):
        terminated = False
        for statement in statements:
            if terminated:
                self.warning(statement, "código inalcanzable")
            self._visit_statement(statement)
            if self._guarantees_exit(statement):
                terminated = True

    def _visit_statement(self, node):
        kind = _data(node)
        handler = getattr(self, f"_visit_{kind}", None)
        if handler is None:
            self.error(node, f"sentencia no soportada: {kind}")
            return
        handler(node)

    def _declare_variable(self, node, constant=False):
        name = str(node.children[0])
        annotation = next((child for child in node.children
                           if _data(child) == "type_annotation"), None)
        initializer = next((child for child in node.children
                            if _data(child) == "initializer"), None)
        value_node = initializer.children[0] if initializer is not None else None
        if constant and value_node is None:
            value_node = next((child for child in node.children[1:]
                               if isinstance(child, Tree)
                               and _data(child) != "type_annotation"), None)
        declared_type = self._type_from_tree(annotation)
        if annotation is not None:
            self._validate_type_name(declared_type, annotation)
        value_type = (self._eval(value_node).type_name
                      if value_node is not None else UNKNOWN)

        if constant and value_node is None:
            self.error(node, f"la constante '{name}' debe inicializarse")
        if annotation is None and value_node is None:
            self.error(node, f"no se puede inferir el tipo de '{name}'")
        final_type = declared_type if annotation is not None else value_type
        if annotation is not None and value_node is not None \
                and not self._compatible(declared_type, value_type):
            self.error(node, f"no se puede inicializar '{name}' de tipo "
                       f"{declared_type} con {value_type}")

        symbol = Symbol(
            name=name,
            kind="constante" if constant else "variable",
            type_name=final_type,
            line=_location(node)[0],
            column=_location(node)[1],
            mutable=not constant,
        )
        if not self.table.declare(symbol):
            self.error(node, f"'{name}' ya fue declarado en este ámbito")

    def _visit_variable_declaration(self, node):
        self._declare_variable(node)

    def _visit_variable_declaration_no_semi(self, node):
        self._declare_variable(node)

    def _visit_constant_declaration(self, node):
        self._declare_variable(node, constant=True)

    def _visit_function_declaration(self, node):
        symbol = self._declarations.get(id(node))
        if symbol is None and id(node) not in self._declarations:
            symbol = self._predeclare_function(node,
                                               method=bool(self.class_stack))
        if symbol is None:
            return

        name, parameters, _, block = self._function_parts(node)
        environment = self.table.enter(f"función {name}", "función")
        symbol.environment = environment
        self.function_stack.append(symbol)
        self._validate_type_name(symbol.return_type, node)

        for parameter_name, parameter_type, parameter_node in \
                self._parameter_specs(parameters):
            if parameter_type == UNKNOWN:
                self.error(parameter_node,
                           f"el parámetro '{parameter_name}' necesita tipo")
            else:
                self._validate_type_name(parameter_type, parameter_node)
            parameter_symbol = Symbol(
                parameter_name, "parámetro", parameter_type,
                _location(parameter_node)[0], _location(parameter_node)[1]
            )
            if not self.table.declare(parameter_symbol):
                self.error(parameter_node,
                           f"parámetro duplicado '{parameter_name}'")

        self._visit_block(block)
        if symbol.return_type != VOID and not self._guarantees_return(block):
            self.error(node, f"la función '{name}' no retorna {symbol.return_type} "
                       "en todos los caminos")

        self.function_stack.pop()
        self.table.exit()

    def _visit_class_declaration(self, node):
        symbol = self._declarations.get(id(node))
        if symbol is None:
            return

        name_tokens = [child for child in node.children
                       if isinstance(child, Token)]
        parent_name = str(name_tokens[1]) if len(name_tokens) > 1 else None
        if parent_name:
            parent = self.table.resolve(parent_name)
            if parent is None or parent.kind != "clase":
                self.error(node, f"la clase base '{parent_name}' no existe")
            elif parent.name == symbol.name:
                self.error(node, "una clase no puede heredarse a sí misma")
            else:
                symbol.metadata["parent"] = parent_name

        environment = self.table.enter(f"clase {symbol.name}", "clase")
        symbol.environment = environment
        self.class_stack.append(symbol)
        members = [child for child in node.children[1:]
                   if isinstance(child, Tree)]

        # Las firmas se registran antes de los cuerpos para permitir métodos
        # recursivos y llamadas a métodos declarados posteriormente.
        for member in members:
            if _data(member) == "function_declaration":
                self._predeclare_function(member, method=True)

        # Las propiedades se registran antes de analizar los métodos para que
        # `this.propiedad` funcione sin depender del orden textual.
        for member in members:
            if _data(member) == "variable_declaration":
                self._declare_variable(member)
            elif _data(member) == "constant_declaration":
                self._declare_variable(member, constant=True)

        for member in members:
            if _data(member) == "function_declaration":
                self._visit_function_declaration(member)
        self.class_stack.pop()
        self.table.exit()

    def _visit_block(self, node):
        self.table.enter("", "bloque")
        self._predeclare(node.children)
        self._visit_statements(node.children)
        self.table.exit()

    # ------------------------------------------------------------------
    # Control de flujo
    # ------------------------------------------------------------------

    def _require_boolean(self, expression, context):
        actual = self._eval(expression).type_name
        if actual not in {"boolean", ERROR}:
            self.error(expression, f"la condición de {context} debe ser "
                       f"boolean, no {actual}")

    def _visit_if_statement(self, node):
        self._require_boolean(node.children[0], "if")
        self._visit_block(node.children[1])
        if len(node.children) > 2:
            self._visit_block(node.children[2])

    def _visit_while_statement(self, node):
        self._require_boolean(node.children[0], "while")
        self.loop_depth += 1
        self._visit_block(node.children[1])
        self.loop_depth -= 1

    def _visit_do_while_statement(self, node):
        self.loop_depth += 1
        self._visit_block(node.children[0])
        self.loop_depth -= 1
        self._require_boolean(node.children[1], "do-while")

    def _visit_for_statement(self, node):
        block = next(child for child in node.children if _data(child) == "block")
        self.table.enter("", "bucle")
        for child in node.children:
            kind = _data(child)
            if kind == "variable_declaration_no_semi":
                self._declare_variable(child)
            elif kind == "for_condition":
                self._require_boolean(child.children[0], "for")
            elif kind == "for_update":
                self._eval(child.children[0])
            elif child is not block:
                self._eval(child)
        self.loop_depth += 1
        self._visit_block(block)
        self.loop_depth -= 1
        self.table.exit()

    def _visit_foreach_statement(self, node):
        name = str(node.children[0])
        collection = self._eval(node.children[1]).type_name
        item_type = collection[:-2] if collection.endswith("[]") else ERROR
        if item_type == ERROR and collection != ERROR:
            self.error(node.children[1], "foreach requiere una lista")
        self.table.enter("", "bucle")
        self.table.declare(Symbol(name, "variable", item_type,
                                  *_location(node.children[0])))
        self.loop_depth += 1
        self._visit_block(node.children[2])
        self.loop_depth -= 1
        self.table.exit()

    def _visit_switch_statement(self, node):
        condition_type = self._eval(node.children[0]).type_name
        if condition_type not in {"boolean", ERROR}:
            self.error(node.children[0], f"la condición de switch debe ser "
                       f"boolean, no {condition_type}")
        self.table.enter("", "switch")
        for child in node.children[1:]:
            if _data(child) == "switch_case":
                case_type = self._eval(child.children[0]).type_name
                if not (self._compatible(condition_type, case_type) or
                        self._compatible(case_type, condition_type)):
                    self.error(child.children[0], "el tipo del case no coincide "
                               "con la expresión de switch")
                self._predeclare(child.children[1:])
                self._visit_statements(child.children[1:])
            elif _data(child) == "default_case":
                self._predeclare(child.children)
                self._visit_statements(child.children)
        self.table.exit()

    def _visit_try_catch_statement(self, node):
        self._visit_block(node.children[0])
        error_name = str(node.children[1])
        self.table.enter("", "catch")
        self.table.declare(Symbol(error_name, "variable", "string",
                                  *_location(node.children[1])))
        self._visit_block(node.children[2])
        self.table.exit()

    def _visit_break_statement(self, node):
        if self.loop_depth == 0:
            self.error(node, "break solo puede utilizarse dentro de un bucle")

    def _visit_continue_statement(self, node):
        if self.loop_depth == 0:
            self.error(node,
                       "continue solo puede utilizarse dentro de un bucle")

    def _visit_return_statement(self, node):
        if not self.function_stack:
            self.error(node, "return solo puede utilizarse dentro de una función")
            return
        function = self.function_stack[-1]
        actual = self._eval(node.children[0]).type_name if node.children else VOID
        if not self._compatible(function.return_type, actual):
            self.error(node, f"return de tipo {actual}; la función "
                       f"'{function.name}' declara {function.return_type}")

    def _visit_print_statement(self, node):
        actual = self._eval(node.children[0]).type_name
        if actual == VOID:
            self.error(node, "print no acepta una expresión void")

    def _visit_expression_statement(self, node):
        self._eval(node.children[0])

    # ------------------------------------------------------------------
    # Expresiones
    # ------------------------------------------------------------------

    def _eval(self, node) -> ExpressionInfo:
        if isinstance(node, Token):
            return ExpressionInfo(ERROR)
        handler = getattr(self, f"_eval_{_data(node)}", None)
        if handler is None:
            if len(node.children) == 1 and isinstance(node.children[0], Tree):
                return self._eval(node.children[0])
            self.error(node, f"expresión no soportada: {_data(node)}")
            return ExpressionInfo(ERROR)
        return handler(node)

    def _eval_integer_literal(self, node):
        return ExpressionInfo("integer")

    def _eval_float_literal(self, node):
        return ExpressionInfo("float")

    def _eval_string_literal(self, node):
        return ExpressionInfo("string")

    def _eval_true_literal(self, node):
        return ExpressionInfo("boolean")

    def _eval_false_literal(self, node):
        return ExpressionInfo("boolean")

    def _eval_null_literal(self, node):
        return ExpressionInfo("null")

    def _eval_identifier_expr(self, node):
        name = str(node.children[0])
        symbol = self.table.resolve(name)
        if symbol is None:
            self.error(node, f"identificador '{name}' no declarado")
            return ExpressionInfo(ERROR)
        symbol.used = True
        if symbol.kind in {"función", "método"}:
            return ExpressionInfo("función", symbol)
        if symbol.kind == "clase":
            return ExpressionInfo("clase", symbol)
        return ExpressionInfo(symbol.type_name, symbol, True)

    def _eval_left_hand_side(self, node):
        result = self._eval(node.children[0])
        for suffix in node.children[1:]:
            if _data(suffix) == "call_suffix":
                args = suffix.children[0].children if suffix.children else []
                result = self._call(result, args, suffix)
            elif _data(suffix) == "index_suffix":
                index_type = self._eval(suffix.children[0]).type_name
                if index_type not in {"integer", ERROR}:
                    self.error(suffix, f"el índice debe ser integer, no {index_type}")
                if result.type_name.endswith("[]"):
                    result = ExpressionInfo(result.type_name[:-2],
                                            assignable=result.assignable)
                elif result.type_name != ERROR:
                    self.error(suffix, "solo se puede indexar una lista")
                    result = ExpressionInfo(ERROR)
            elif _data(suffix) == "property_suffix":
                name = str(suffix.children[0])
                member = self._resolve_member(result.type_name, name)
                if member is None:
                    if result.type_name != ERROR:
                        self.error(suffix, f"'{result.type_name}' no contiene "
                                   f"el miembro '{name}'")
                    result = ExpressionInfo(ERROR)
                elif member.kind in {"función", "método"}:
                    member.used = True
                    result = ExpressionInfo("función", member)
                else:
                    member.used = True
                    result = ExpressionInfo(member.type_name, member, True)
        return result

    def _resolve_member(self, type_name, member_name):
        class_symbol = self._find_class(type_name)
        visited = set()
        while class_symbol is not None and class_symbol.name not in visited:
            visited.add(class_symbol.name)
            if class_symbol.environment is not None:
                member = class_symbol.environment.resolve_local(member_name)
                if member is not None:
                    return member
            parent_name = class_symbol.metadata.get("parent")
            class_symbol = self._find_class(parent_name) if parent_name else None
        return None

    def _find_class(self, name):
        if not name:
            return None
        for environment in self.table.environments():
            symbol = environment.symbols.get(name)
            if symbol is not None and symbol.kind == "clase":
                return symbol
        return None

    def _eval_direct_call(self, node):
        name = str(node.children[0])
        symbol = self.table.resolve(name)
        if symbol is None:
            self.error(node, f"función '{name}' no declarada")
            return ExpressionInfo(ERROR)
        symbol.used = True
        args = node.children[1].children if len(node.children) > 1 else []
        return self._call(ExpressionInfo("función", symbol), args, node)

    def _call(self, callee, arguments, node):
        symbol = callee.symbol
        if symbol is None or symbol.kind not in {"función", "método"}:
            self.error(node, "se intentó llamar un valor que no es función")
            for argument in arguments:
                self._eval(argument)
            return ExpressionInfo(ERROR)
        actual_types = [self._eval(argument).type_name for argument in arguments]
        if len(actual_types) != len(symbol.parameters):
            self.error(node, f"'{symbol.name}' espera {len(symbol.parameters)} "
                       f"argumentos y recibió {len(actual_types)}")
        for index, (expected, actual) in enumerate(
                zip(symbol.parameters, actual_types), 1):
            if not self._compatible(expected, actual):
                self.error(node, f"argumento {index} de '{symbol.name}': "
                           f"se esperaba {expected} y llegó {actual}")
        return ExpressionInfo(symbol.return_type)

    def _eval_new_expr(self, node):
        name = str(node.children[0])
        class_symbol = self.table.resolve(name)
        arguments = node.children[1].children if len(node.children) > 1 else []
        if class_symbol is None or class_symbol.kind != "clase":
            self.error(node, f"clase '{name}' no declarada")
            for argument in arguments:
                self._eval(argument)
            return ExpressionInfo(ERROR)
        class_symbol.used = True
        constructor = self._resolve_member(name, "constructor")
        if constructor is None:
            if arguments:
                self.error(node, f"la clase '{name}' no declara constructor")
                for argument in arguments:
                    self._eval(argument)
        else:
            constructor.used = True
            self._call(ExpressionInfo("función", constructor), arguments, node)
        return ExpressionInfo(name)

    def _eval_this_expr(self, node):
        if not self.class_stack:
            self.error(node, "this solo puede utilizarse dentro de una clase")
            return ExpressionInfo(ERROR)
        return ExpressionInfo(self.class_stack[-1].name)

    def _eval_assign_expr(self, node):
        target = self._eval(node.children[0])
        value = self._eval(node.children[1])
        if target.type_name == ERROR:
            return ExpressionInfo(ERROR)
        if not target.assignable:
            self.error(node.children[0], "el lado izquierdo no es asignable")
        elif target.symbol is not None and not target.symbol.mutable:
            self.error(node.children[0],
                       f"no se puede reasignar la constante '{target.symbol.name}'")
        if not self._compatible(target.type_name, value.type_name):
            self.error(node, f"asignación incompatible: {target.type_name} = "
                       f"{value.type_name}")
        return ExpressionInfo(target.type_name)

    def _eval_ternary_expr(self, node):
        if len(node.children) == 1:
            return self._eval(node.children[0])
        condition = self._eval(node.children[0]).type_name
        if condition not in {"boolean", ERROR}:
            self.error(node.children[0], "la condición ternaria debe ser boolean")
        left = self._eval(node.children[1]).type_name
        right = self._eval(node.children[2]).type_name
        result = self._common_type(left, right)
        if result == ERROR:
            self.error(node, f"ramas ternarias incompatibles: {left} y {right}")
        return ExpressionInfo(result)

    def _eval_unary_expr(self, node):
        operator = str(node.children[0])
        operand = self._eval(node.children[1]).type_name
        expected = "boolean" if operator == "!" else "numeric"
        valid = operand == "boolean" if operator == "!" else operand in NUMERIC
        if not valid and operand != ERROR:
            self.error(node, f"'{operator}' requiere {expected}, no {operand}")
        return ExpressionInfo("boolean" if operator == "!" else operand)

    def _eval_binary(self, node, family):
        result = self._eval(node.children[0]).type_name
        for index in range(1, len(node.children), 2):
            operator = str(node.children[index])
            right = self._eval(node.children[index + 1]).type_name
            if ERROR in {result, right}:
                result = ERROR
                continue
            if family == "logical":
                if result != "boolean" or right != "boolean":
                    self.error(node, f"'{operator}' requiere operandos boolean")
                    result = ERROR
                else:
                    result = "boolean"
            elif family == "arithmetic":
                if operator == "+" and result == right == "string":
                    result = "string"
                elif result in NUMERIC and right in NUMERIC:
                    result = self._common_type(result, right)
                else:
                    self.error(node, f"'{operator}' no aplica entre {result} y {right}")
                    result = ERROR
            elif family == "relational":
                if result in NUMERIC and right in NUMERIC:
                    result = "boolean"
                else:
                    self.error(node, f"'{operator}' requiere operandos numéricos")
                    result = ERROR
            elif family == "equality":
                if self._compatible(result, right) or self._compatible(right, result):
                    result = "boolean"
                else:
                    self.error(node, f"no se puede comparar {result} con {right}")
                    result = ERROR
        return ExpressionInfo(result)

    def _eval_logical_or_expr(self, node):
        return self._eval_binary(node, "logical")

    def _eval_logical_and_expr(self, node):
        return self._eval_binary(node, "logical")

    def _eval_equality_expr(self, node):
        return self._eval_binary(node, "equality")

    def _eval_relational_expr(self, node):
        return self._eval_binary(node, "relational")

    def _eval_additive_expr(self, node):
        return self._eval_binary(node, "arithmetic")

    def _eval_multiplicative_expr(self, node):
        return self._eval_binary(node, "arithmetic")

    def _eval_array_literal(self, node):
        if not node.children:
            return ExpressionInfo(UNKNOWN + "[]")
        result = self._eval(node.children[0]).type_name
        for child in node.children[1:]:
            current = self._eval(child).type_name
            result = self._common_type(result, current)
            if result == ERROR:
                self.error(node, "todos los elementos de una lista deben tener "
                           "un tipo compatible")
                break
        return ExpressionInfo(result + "[]" if result != ERROR else ERROR)

    # ------------------------------------------------------------------
    # Flujo y reportes
    # ------------------------------------------------------------------

    def _guarantees_exit(self, node):
        return _data(node) in {"return_statement", "break_statement",
                               "continue_statement"} or \
            self._guarantees_return(node)

    def _guarantees_return(self, node):
        kind = _data(node)
        if kind == "return_statement":
            return True
        if kind == "block":
            return any(self._guarantees_return(child) for child in node.children)
        if kind == "if_statement" and len(node.children) == 3:
            return (self._guarantees_return(node.children[1]) and
                    self._guarantees_return(node.children[2]))
        if kind == "try_catch_statement":
            return (self._guarantees_return(node.children[0]) and
                    self._guarantees_return(node.children[2]))
        return False

    def _emit_unused_warnings(self):
        for environment in self.table.environments():
            for symbol in environment.symbols.values():
                if symbol.kind in {"variable", "constante"} and not symbol.used:
                    self.diagnostics.append(Diagnostic(
                        "semántico",
                        f"{symbol.kind} '{symbol.name}' declarada pero no utilizada",
                        symbol.line,
                        symbol.column,
                        "aviso",
                    ))
