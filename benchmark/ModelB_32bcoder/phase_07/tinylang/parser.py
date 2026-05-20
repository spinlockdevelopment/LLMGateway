from tinylang.lexer import Token
from tinylang.ast import Program, FnDecl, FnLit, Call, ReturnStmt, Expression, BinaryOp, Identifier, Literal
from tinylang.errors import TinylangError, RuntimeError as TinyRuntimeError
import re

def parse(tokens):
    pos = 0
    def consume(type):
        nonlocal pos
        if pos < len(tokens) and tokens[pos].type == type:
            pos += 1
            return tokens[pos - 1]
        else:
            raise TinylangError(f'Expected {type}, got {tokens[pos].type} at line {tokens[pos].line}, column {tokens[pos].column}')

    def parse_program():
        statements = []
        while pos < len(tokens):
            statements.append(parse_statement())
        return Program(statements)

    def parse_statement():
        if tokens[pos].type == 'IDENT' and tokens[pos + 1].type == 'DELIM' and tokens[pos + 1].value == '=':
            return parse_let_stmt()
        elif tokens[pos].type == 'IDENT' and tokens[pos].value == 'if':
            return parse_if_stmt()
        elif tokens[pos].type == 'IDENT' and tokens[pos].value == 'while':
            return parse_while_stmt()
        elif tokens[pos].type == 'IDENT' and tokens[pos].value == 'for':
            return parse_for_stmt()
        elif tokens[pos].type == 'IDENT' and tokens[pos].value == 'fn':
            return parse_fn_decl()
        elif tokens[pos].type == 'IDENT' and tokens[pos].value == 'return':
            return parse_return_stmt()
        elif tokens[pos].type == 'DELIM' and tokens[pos].value == '{':
            return parse_block()
        else:
            return parse_expr_stmt()

    def parse_let_stmt():
        consume('IDENT')
        name = consume('IDENT').value
        consume('DELIM')
        value = parse_expression()
        consume('DELIM')
        return LetStmt(name, value)

    def parse_if_stmt():
        consume('IDENT')
        consume('DELIM')
        condition = parse_expression()
        consume('DELIM')
        then_block = parse_block()
        if tokens[pos].type == 'IDENT' and tokens[pos].value == 'else':
            consume('IDENT')
            else_block = parse_statement()
            return IfStmt(condition, then_block, else_block)
        else:
            return IfStmt(condition, then_block)

    def parse_while_stmt():
        consume('IDENT')
        consume('DELIM')
        condition = parse_expression()
        consume('DELIM')
        body = parse_block()
        return WhileStmt(condition, body)

    def parse_for_stmt():
        consume('IDENT')
        consume('DELIM')
        var = consume('IDENT').value
        index_var = None
        if tokens[pos].type == 'DELIM' and tokens[pos].value == ',':
            consume('DELIM')
            index_var = consume('IDENT').value
        consume('IDENT')
        iterable = parse_expression()
        consume('DELIM')
        body = parse_block()
        return ForStmt(var, index_var, iterable, body)

    def parse_fn_decl():
        consume('IDENT')
        name = consume('IDENT').value
        consume('DELIM')
        params = parse_params()
        consume('DELIM')
        body = parse_block()
        return FnDecl(name, params, body)

    def parse_return_stmt():
        consume('IDENT')
        value = parse_expression() if tokens[pos].type != 'DELIM' or tokens[pos].value != ';' else None
        consume('DELIM')
        return ReturnStmt(value)

    def parse_block():
        consume('DELIM')
        statements = []
        while tokens[pos].type != 'DELIM' or tokens[pos].value != '}':
            statements.append(parse_statement())
        consume('DELIM')
        return Block(statements)

    def parse_expr_stmt():
        expr = parse_expression()
        consume('DELIM')
        return ExprStmt(expr)

    def parse_expression():
        return parse_assignment()

    def parse_assignment():
        expr = parse_logic_or()
        if tokens[pos].type == 'DELIM' and tokens[pos].value == '=':
            consume('DELIM')
            value = parse_assignment()
            return Assignment(expr, value)
        return expr

    def parse_logic_or():
        expr = parse_logic_and()
        while tokens[pos].type == 'OP' and tokens[pos].value == '||':
            consume('OP')
            right = parse_logic_and()
            expr = BinaryOp(expr, '||', right)
        return expr

    def parse_logic_and():
        expr = parse_equality()
        while tokens[pos].type == 'OP' and tokens[pos].value == '&&':
            consume('OP')
            right = parse_equality()
            expr = BinaryOp(expr, '&&', right)
        return expr

    def parse_equality():
        expr = parse_comparison()
        while tokens[pos].type == 'OP' and tokens[pos].value in ('==', '!='):
            consume('OP')
            right = parse_comparison()
            expr = BinaryOp(expr, tokens[pos - 1].value, right)
        return expr

    def parse_comparison():
        expr = parse_term()
        while tokens[pos].type == 'OP' and tokens[pos].value in ('<', '>', '<=', '>='):
            consume('OP')
            right = parse_term()
            expr = BinaryOp(expr, tokens[pos - 1].value, right)
        return expr

    def parse_term():
        expr = parse_factor()
        while tokens[pos].type == 'OP' and tokens[pos].value in ('+', '-'):
            consume('OP')
            right = parse_factor()
            expr = BinaryOp(expr, tokens[pos - 1].value, right)
        return expr

    def parse_factor():
        expr = parse_unary()
        while tokens[pos].type == 'OP' and tokens[pos].value in ('*', '/', '%'):
            consume('OP')
            right = parse_unary()
            expr = BinaryOp(expr, tokens[pos - 1].value, right)
        return expr

    def parse_unary():
        if tokens[pos].type == 'OP' and tokens[pos].value in ('!', '-'):
            op = consume('OP').value
            right = parse_unary()
            return UnaryOp(op, right)
        else:
            return parse_call()

    def parse_call():
        expr = parse_primary()
        while tokens[pos].type == 'DELIM' and tokens[pos].value == '(': 
            consume('DELIM')
            args = []
            if tokens[pos].type != 'DELIM' or tokens[pos].value != ')':
                args.append(parse_expression())
                while tokens[pos].type == 'DELIM' and tokens[pos].value == ',':
                    consume('DELIM')
                    args.append(parse_expression())
            consume('DELIM')
            expr = Call(expr, args)
        return expr

    def parse_primary():
        if tokens[pos].type == 'NUMBER':
            return Literal(consume('NUMBER').value)
        elif tokens[pos].type == 'STRING':
            return Literal(consume('STRING').value)
        elif tokens[pos].type == 'IDENT' and tokens[pos + 1].type == 'DELIM' and tokens[pos + 1].value == '(': 
            return parse_fn_lit()
        elif tokens[pos].type == 'IDENT':
            return Identifier(consume('IDENT').value)
        elif tokens[pos].type == 'DELIM' and tokens[pos].value == '(': 
            consume('DELIM')
            expr = parse_expression()
            consume('DELIM')
            return expr
        else:
            raise TinylangError(f'Unexpected token {tokens[pos].value} at line {tokens[pos].line}, column {tokens[pos].column}')

    def parse_params():
        params = []
        if tokens[pos].type == 'IDENT':
            params.append(consume('IDENT').value)
            while tokens[pos].type == 'DELIM' and tokens[pos].value == ',':
                consume('DELIM')
                params.append(consume('IDENT').value)
        return params

    def parse_fn_lit():
        consume('IDENT')
        consume('DELIM')
        params = parse_params()
        consume('DELIM')
        body = parse_block()
        return FnLit(params, body)

    return parse_program()
