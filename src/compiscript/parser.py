"""Frontend de Compiscript generado con YALex y YAPar propios."""

from dataclasses import dataclass, field
import hashlib
import importlib.util
from pathlib import Path
import pickle
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SHARED = SRC / "shared"
for candidate in (SRC, SHARED):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from yalex.yalex_gen import YALexEngine  # noqa: E402
from yapar.first_follow import compute_first, compute_follow  # noqa: E402
from yapar.lr0_automaton import LR0Automaton  # noqa: E402
from yapar.slr1_table import SLRTable  # noqa: E402
from yapar.yapar_parser import YAParParser  # noqa: E402
from .tree import Token, Tree, make_tree

YAL_PATH = ROOT / "grammar" / "Compiscript.yal"
YALP_PATH = ROOT / "grammar" / "Compiscript.yalp"
GENERATED = ROOT / "generated"


@dataclass
class Diagnostic:
    phase: str
    message: str
    line: int = 0
    column: int = 0
    severity: str = "error"

    def __str__(self):
        location = f" línea {self.line}, columna {self.column}" if self.line else ""
        return f"[{self.phase}] {self.severity}{location}: {self.message}"


@dataclass
class ParseResult:
    tree: Tree | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def ok(self):
        return self.tree is not None and not self.diagnostics


def _source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("compiscript_generated_lexer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _list_value(children):
    result = []
    for child in children:
        if isinstance(child, list):
            result.extend(child)
        elif not isinstance(child, Token) or child.type != "COMMA":
            result.append(child)
    return result


def _only(children):
    return next((child for child in children if isinstance(child, Tree)), None)


def _token(children, token_type):
    return next((child for child in children
                 if isinstance(child, Token) and child.type == token_type), None)


def _build_value(head: str, body: list[str], children: list):
    """Convierte cada reducción LALR en el árbol que consume la semántica."""
    if body == ["ε"]:
        children = []

    if head in {"statement_list", "class_member_list", "switch_case_list",
                "parameter_list", "argument_list", "array_items", "suffix_list",
                "array_suffix_list"}:
        return _list_value(children)

    if head in {"optional_type", "optional_initializer", "optional_else",
                "optional_for_initializer", "optional_return_expression",
                "optional_default", "optional_parameters", "optional_arguments"}:
        return _only(children) if children else None
    if head == "optional_for_condition":
        item = _only(children)
        return make_tree("for_condition", [item]) if item else None
    if head == "optional_for_update":
        item = _only(children)
        return make_tree("for_update", [item]) if item else None
    if head == "optional_return_type":
        return next((child for child in children
                     if isinstance(child, Tree) and child.data == "type"), None)
    if head == "optional_parent":
        return _token(children, "ID")

    if head in {"statement", "class_member", "expression", "for_initializer",
                "primary_atom", "suffix_op", "base_type", "var_keyword",
                "literal_expr"}:
        return next((child for child in children
                     if isinstance(child, (Tree, Token))), None)

    if head == "program":
        return make_tree("program", _list_value(children))
    if head == "block":
        return make_tree(head, next((child for child in children
                                     if isinstance(child, list)), []))

    if head in {"variable_declaration", "variable_declaration_no_semi",
                "constant_declaration"}:
        return make_tree(head, [_token(children, "ID"),
                                *[child for child in children if isinstance(child, Tree)]])
    if head == "type_annotation":
        return make_tree(head, [_only(children)])
    if head == "initializer":
        return make_tree(head, [_only(children)])
    if head in {"expression_statement", "print_statement"}:
        return make_tree(head, [_only(children)])

    if head in {"if_statement", "while_statement", "for_statement"}:
        return make_tree(head, [child for child in children if isinstance(child, Tree)])
    if head == "do_while_statement":
        trees = [child for child in children if isinstance(child, Tree)]
        block = next(child for child in trees if child.data == "block")
        return make_tree(head, [block, next(child for child in trees if child is not block)])
    if head == "foreach_statement":
        return make_tree(head, [_token(children, "ID"),
                                *[child for child in children if isinstance(child, Tree)]])
    if head in {"break_statement", "continue_statement"}:
        keyword = next((child for child in children if isinstance(child, Token)), None)
        return make_tree(head, [keyword] if keyword else [])
    if head == "return_statement":
        item = _only(children)
        return make_tree(head, [item] if item else [])
    if head == "try_catch_statement":
        blocks = [child for child in children
                  if isinstance(child, Tree) and child.data == "block"]
        return make_tree(head, [blocks[0], _token(children, "ID"), blocks[1]])
    if head == "switch_statement":
        trees = [child for child in children if isinstance(child, Tree)]
        expression = next(child for child in trees if child.data != "default_case")
        cases = next((child for child in children if isinstance(child, list)), [])
        default = next((child for child in trees if child.data == "default_case"), None)
        return make_tree(head, [expression, *cases, default])
    if head == "switch_case":
        statements = next((child for child in children if isinstance(child, list)), [])
        return make_tree(head, [_only(children), *statements])
    if head == "default_case":
        return make_tree(head, next((child for child in children
                                     if isinstance(child, list)), []))

    if head == "function_declaration":
        params = next((child for child in children
                       if isinstance(child, Tree) and child.data == "parameters"), None)
        return_type = next((child for child in children
                            if isinstance(child, Tree) and child.data == "type"), None)
        block = next(child for child in children
                     if isinstance(child, Tree) and child.data == "block")
        return make_tree(head, [_token(children, "ID"), params, return_type, block])
    if head == "parameters":
        return make_tree(head, next((child for child in children
                                     if isinstance(child, list)), []))
    if head == "parameter":
        return make_tree(head, [_token(children, "ID"), _only(children)])
    if head == "class_declaration":
        ids = [child for child in children
               if isinstance(child, Token) and child.type == "ID"]
        members = next((child for child in children if isinstance(child, list)), [])
        return make_tree(head, [ids[0], ids[1] if len(ids) > 1 else None, *members])

    if head == "assignment_expr":
        trees = [child for child in children if isinstance(child, Tree)]
        return make_tree("assign_expr", trees) if _token(children, "ASSIGN") else trees[0]
    if head == "conditional_expr":
        base = next(child for child in children if isinstance(child, Tree))
        tail = next((child for child in children if isinstance(child, list)), [])
        return make_tree("ternary_expr", [base, *tail])
    if head == "conditional_tail":
        return [child for child in children if isinstance(child, Tree)]

    if head in {"logical_or_expr", "logical_and_expr", "equality_expr",
                "relational_expr", "additive_expr", "multiplicative_expr"}:
        trees = [child for child in children if isinstance(child, Tree)]
        operator = next((child for child in children if isinstance(child, Token)), None)
        if operator is None:
            return trees[0]
        left, right = trees
        values = list(left.children) if left.data == head else [left]
        return make_tree(head, [*values, operator, right])
    if head == "unary_expr":
        operator = next((child for child in children if isinstance(child, Token)), None)
        expression = _only(children)
        return make_tree(head, [operator, expression]) if operator else expression
    if head == "primary_expr":
        return _only(children)

    if head in {"integer_literal", "float_literal", "string_literal",
                "null_literal", "true_literal", "false_literal"}:
        return make_tree(head, [next(child for child in children
                                     if isinstance(child, Token))])
    if head == "array_literal":
        values = next((child for child in children if isinstance(child, list)), [])
        return make_tree(head, values)
    if head == "optional_array_items":
        return next((child for child in children if isinstance(child, list)), [])

    if head == "left_hand_side":
        atom = _only(children)
        suffixes = next((child for child in children if isinstance(child, list)), [])
        return make_tree(head, [atom, *suffixes])
    if head == "identifier_expr":
        return make_tree(head, [_token(children, "ID")])
    if head == "new_expr":
        args = next((child for child in children
                     if isinstance(child, Tree) and child.data == "arguments"), None)
        return make_tree(head, [_token(children, "ID"), args])
    if head == "this_expr":
        return make_tree(head, [_token(children, "THIS")])
    if head == "call_suffix":
        args = next((child for child in children
                     if isinstance(child, Tree) and child.data == "arguments"), None)
        return make_tree(head, [args] if args else [])
    if head == "index_suffix":
        return make_tree(head, [_only(children)])
    if head == "property_suffix":
        return make_tree(head, [_token(children, "ID")])
    if head == "arguments":
        return make_tree(head, next((child for child in children
                                     if isinstance(child, list)), []))

    if head == "type":
        base = _only(children)
        suffixes = next((child for child in children if isinstance(child, list)), [])
        return make_tree(head, [base, *suffixes])
    if head in {"boolean_type", "integer_type", "float_type", "string_type"}:
        return make_tree(head)
    if head == "named_type":
        return make_tree(head, [_token(children, "ID")])
    if head == "array_suffix":
        return make_tree(head)

    return make_tree(head, [child for child in children
                            if isinstance(child, (Tree, Token))])


class CompiscriptParser:
    """Genera el lexer DFA y la tabla SLR, y analiza una entrada."""

    def __init__(self, yal_path=YAL_PATH, yalp_path=YALP_PATH):
        self.yal_path = Path(yal_path)
        self.yalp_path = Path(yalp_path)
        GENERATED.mkdir(exist_ok=True)
        self.lexer = self._prepare_lexer()
        self.grammar, self.table = self._prepare_parser()

    def _prepare_lexer(self):
        output = GENERATED / "compiscript_lexer.py"
        stamp = GENERATED / "compiscript_lexer.sha256"
        current = _source_hash(self.yal_path)
        if not output.exists() or not stamp.exists() \
                or stamp.read_text(encoding="utf-8") != current:
            YALexEngine().compile(str(self.yal_path), str(output))
            stamp.write_text(current, encoding="utf-8")
        return _load_module(output)

    def _prepare_parser(self):
        cache = GENERATED / "compiscript_slr.pkl"
        stamp = GENERATED / "compiscript_slr.sha256"
        current = _source_hash(self.yalp_path)
        if cache.exists() and stamp.exists() \
                and stamp.read_text(encoding="utf-8") == current:
            with cache.open("rb") as stream:
                return pickle.load(stream)
        grammar = YAParParser().parse_file(str(self.yalp_path))
        first = compute_first(grammar)
        follow = compute_follow(grammar, first)
        automaton = LR0Automaton(grammar)
        table = SLRTable(grammar)
        table.build_slr(automaton, first, follow)
        table.states = automaton.states
        with cache.open("wb") as stream:
            pickle.dump((grammar, table), stream)
        stamp.write_text(current, encoding="utf-8")
        return grammar, table

    def parse(self, source: str) -> ParseResult:
        try:
            tokens = [token for token in self.lexer.tokenize(source)
                      if token.type != "$" and token.type not in self.grammar.ignored_tokens]
        except SyntaxError as exc:
            match = re.search(r"linea (\d+) col (\d+)", str(exc))
            line, column = (int(match.group(1)), int(match.group(2))) if match else (0, 0)
            return ParseResult(diagnostics=[Diagnostic("léxico", str(exc), line, column)])

        states = [0]
        values = []
        position = 0
        while True:
            lookahead = tokens[position].type if position < len(tokens) else "$"
            action, value = self.table.get_action(states[-1], lookahead)
            if action == self.table.SHIFT:
                states.append(value)
                values.append(tokens[position])
                position += 1
            elif action == self.table.REDUCE:
                production = self.grammar.productions[value]
                count = 0 if production.body == ["ε"] else len(production.body)
                reduced = values[-count:] if count else []
                if count:
                    del states[-count:]
                    del values[-count:]
                node = _build_value(production.head, production.body, reduced)
                destination = self.table.get_goto(states[-1], production.head)
                if destination is None:
                    return ParseResult(diagnostics=[Diagnostic(
                        "sintáctico", f"transición GOTO ausente para {production.head}")])
                states.append(destination)
                values.append(node)
            elif action == self.table.ACCEPT:
                program = values[-1] if values else make_tree("program")
                return ParseResult(tree=make_tree("start", [program]))
            else:
                token = tokens[position] if position < len(tokens) else None
                expected = sorted(symbol for (state, symbol), candidate
                                  in self.table.action.items()
                                  if state == states[-1] and candidate[0] != self.table.ERROR)
                message = "entrada no válida"
                if expected:
                    message += "; se esperaba: " + ", ".join(expected)
                if token:
                    line, column = token.line, token.col
                elif tokens:
                    line = tokens[-1].line
                    column = tokens[-1].col + len(tokens[-1].value)
                else:
                    line = column = 1
                return ParseResult(diagnostics=[Diagnostic(
                    "sintáctico", message, line, column)])


def tree_lines(tree: Tree) -> list[str]:
    return tree.pretty().rstrip().splitlines()
