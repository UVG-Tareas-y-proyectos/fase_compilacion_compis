from pathlib import Path

from compiscript.parser import CompiscriptParser, Tree


def test_frontend_is_generated_by_own_yalex_and_yapar():
    parser = CompiscriptParser()
    assert parser.table.states
    assert parser.grammar.start_symbol == "program"
    assert Path(parser.yal_path).suffix == ".yal"
    assert Path(parser.yalp_path).suffix == ".yalp"


def test_lexer_uses_longest_match_and_tracks_location():
    parser = CompiscriptParser()
    tokens = [token for token in parser.lexer.tokenize("let valor = 12.5;")
              if token.type != "$"]
    assert [token.type for token in tokens] == [
        "LET", "ID", "ASSIGN", "FLOAT_LITERAL", "SEMI"
    ]
    assert (tokens[1].value, tokens[1].line, tokens[1].col) == ("valor", 1, 5)


def test_lexer_ignores_both_comment_styles():
    parser = CompiscriptParser()
    result = parser.parse("/* comentario\n   largo */ let x = 1; // corto")
    assert result.ok


def test_parser_builds_tree_without_external_parser_library():
    result = CompiscriptParser().parse("let x: integer = 1;")
    assert result.ok
    assert isinstance(result.tree, Tree)
    assert result.tree.data == "start"


def test_lexical_and_syntax_errors_have_location():
    parser = CompiscriptParser()
    lexical = parser.parse("let x = @;")
    syntax = parser.parse("let x: integer = ;")
    assert lexical.diagnostics[0].phase == "léxico"
    assert lexical.diagnostics[0].line == 1
    assert syntax.diagnostics[0].phase == "sintáctico"
    assert syntax.diagnostics[0].column > 0
