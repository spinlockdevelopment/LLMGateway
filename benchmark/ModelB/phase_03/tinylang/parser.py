from tinylang.ast import *
from tinylang.lexer import tokenize, Token
from typing import List, Optional
import sys

class ParseError(Exception):
    def __init__(self, message: str, line: int, col: int):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(f"Parse error at line {line}, column {col}: {message}")

    def __str__(self):
        return f"Parse error at line {self.line}, column {self.col}: {self.message}"

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
    
    def peek(self) -> Token:
        if self.pos >= len(self.tokens):
            # Return a fake EOF token
            return Token("EOF", None, 0, 0)
        return self.tokens[self.pos]
    
    def advance(self) -> Token:
        if self.pos >= len(self.tokens):
            raise ParseError("Unexpected end of file", 0, 0)
        token = self.tokens[self.pos]
        self.pos += 1
        return token
    
    def match(self, expected_kind: str) -> Token:
        token = self.peek()
        if token.kind == expected_kind:
            return self.advance()
        else:
            raise ParseError(f"Expected {expected_kind}, got {token.kind}", token.line, token.col)
    
    def match_value(self, expected_value: str) -> Token:
        token = self.peek()
        if token.kind == "KEYWORD" and token.value == expected_value:
            return self.advance()
        else:
            raise ParseError(f"Expected '{expected_value}', got {token.value}", token.line, token.col)
    
    def parse_program(self) -> Program:
        stmts = []
        while self.peek().kind != "EOF":
            stmts.append(self.parse_statement())
        return Program(stmts)
    
    def parse_statement(self) -> Statement:
        token = self.peek()
        if token.kind == "KEYWORD":
            keyword = token.value
            if keyword == "let":
                return self.parse_let_stmt()
            elif keyword == "if":
                return self.parse_if_stmt()
            elif keyword == "while":
                return self.parse_while_stmt()
            elif keyword == "for":
                return self.parse_for_stmt()
            elif keyword == "fn":
                return self.parse_fn_decl()
            elif keyword == "return":
                return self.parse_return_stmt()
            elif keyword == "break":
                return self.parse_break_stmt()
            elif keyword == "continue":
                return self.parse_continue_stmt()
            elif keyword == "{":
                return self.parse_block()
            else:
                raise ParseError(f"Unexpected keyword '{keyword}'", token.line, token.col)
        elif token.kind == "{":
            return self.parse_block()
        else:
            return self.parse_expr_stmt()
    
    def parse_let_stmt(self) -> LetStmt:
        self.match_value("let")
        name = self.match("IDENT").value
        self.match("PUNCT")  # =
        value = self.parse_expression()
        self.match("PUNCT")  # ;
        return LetStmt(name, value)
    
    def parse_if_stmt(self) -> IfStmt:
        self.match_value("if")
        self.match("PUNCT")  # (
        cond = self.parse_expression()
        self.match("PUNCT")  # )
        then_block = self.parse_block()
        else_block = None
        if self.peek().value == "else":
            self.advance()  # consume "else"
            if self.peek().value == "if":
                else_block = self.parse_if_stmt()
            else:
                else_block = self.parse_block()
        return IfStmt(cond, then_block, else_block)
    
    def parse_while_stmt(self) -> WhileStmt:
        self.match_value("while")
        self.match("PUNCT")  # (
        cond = self.parse_expression()
        self.match("PUNCT")  # )
        body = self.parse_block()
        return WhileStmt(cond, body)
    
    def parse_for_stmt(self) -> ForStmt:
        self.match_value("for")
        self.match("PUNCT")  # (
        # Parse names (could be 1 or 2)
        names = []
        first_name = self.match("IDENT").value
        names.append(first_name)
        if self.peek().value == ",":
            self.advance()  # consume comma
            second_name = self.match("IDENT").value
            names.append(second_name)
        self.match("PUNCT")  # )
        self.match_value("in")
        iterable = self.parse_expression()
        body = self.parse_block()
        return ForStmt(names, iterable, body)
    
    def parse_fn_decl(self) -> FnDecl:
        self.match_value("fn")
        name = self.match("IDENT").value
        self.match("PUNCT")  # (
        params = []
        if self.peek().value != ")":
            while True:
                param = self.match("IDENT").value
                params.append(param)
                if self.peek().value == ",":
                    self.advance()  # consume comma
                else:
                    break
        self.match("PUNCT")  # )
        body = self.parse_block()
        return FnDecl(name, params, body)
    
    def parse_return_stmt(self) -> ReturnStmt:
        self.match_value("return")
        if self.peek().value != ";":
            value = self.parse_expression()
            self.match("PUNCT")  # ;
            return ReturnStmt(value)
        else:
            self.match("PUNCT")  # ;
            return ReturnStmt(None)
    
    def parse_break_stmt(self) -> BreakStmt:
        self.match_value("break")
        self.match("PUNCT")  # ;
        return BreakStmt()
    
    def parse_continue_stmt(self) -> ContinueStmt:
        self.match_value("continue")
        self.match("PUNCT")  # ;
        return ContinueStmt()
    
    def parse_block(self) -> Block:
        self.match("PUNCT")  # {
        stmts = []
        while self.peek().value != "}":
            stmts.append(self.parse_statement())
        self.match("PUNCT")  # }
        return Block(stmts)
    
    def parse_expr_stmt(self) -> ExprStmt:
        expr = self.parse_expression()
        self.match("PUNCT")  # ;
        return ExprStmt(expr)
    
    def parse_expression(self) -> Expression:
        return self.parse_assignment()
    
    def parse_assignment(self) -> Expression:
        left = self.parse_logic_or()
        if self.peek().value == "=":
            self.advance()  # consume =
            right = self.parse_assignment()
            # Check if left is a valid assignment target
            if not isinstance(left, (Identifier, Index)):
                token = self.peek()
                raise ParseError("Invalid assignment target", token.line, token.col)
            return Assign(left, right)
        return left
    
    def parse_logic_or(self) -> Expression:
        left = self.parse_logic_and()
        if self.peek().value == "||":
            self.advance()  # consume ||
            right = self.parse_logic_or()
            return BinaryOp("||", left, right)
        return left
    
    def parse_logic_and(self) -> Expression:
        left = self.parse_equality()
        if self.peek().value == "&&":
            self.advance()  # consume &&
            right = self.parse_logic_and()
            return BinaryOp("&&", left, right)
        return left
    
    def parse_equality(self) -> Expression:
        left = self.parse_comparison()
        if self.peek().value in ("==", "!="):
            op = self.advance().value
            right = self.parse_equality()
            return BinaryOp(op, left, right)
        return left
    
    def parse_comparison(self) -> Expression:
        left = self.parse_term()
        if self.peek().value in ("<", ">", "<=", ">="):
            op = self.advance().value
            right = self.parse_comparison()
            return BinaryOp(op, left, right)
        return left
    
    def parse_term(self) -> Expression:
        left = self.parse_factor()
        while self.peek().value in ("+", "-"):
            op = self.advance().value
            right = self.parse_term()
            left = BinaryOp(op, left, right)
        return left
    
    def parse_factor(self) -> Expression:
        left = self.parse_unary()
        while self.peek().value in ("*", "/", "%"):
            op = self.advance().value
            right = self.parse_factor()
            left = BinaryOp(op, left, right)
        return left
    
    def parse_unary(self) -> Expression:
        if self.peek().value in ("!", "-"):
            op = self.advance().value
            operand = self.parse_unary()
            return UnaryOp(op, operand)
        return self.parse_call()
    
    def parse_call(self) -> Expression:
        callee = self.parse_primary()
        while self.peek().value in ("(", "["):
            if self.peek().value == "(":
                self.advance()  # consume (
                args = []
                if self.peek().value != ")":
                    while True:
                        args.append(self.parse_expression())
                        if self.peek().value == ",":
                            self.advance()  # consume comma
                        else:
                            break
                self.match("PUNCT")  # )
                callee = Call(callee, args)
            elif self.peek().value == "[":
                self.advance()  # consume [
                key = self.parse_expression()
                self.match("PUNCT")  # ]
                callee = Index(callee, key)
        return callee
    
    def parse_primary(self) -> Expression:
        token = self.peek()
        if token.kind == "NUMBER":
            self.advance()
            return NumberLit(token.value)
        elif token.kind == "STRING":
            self.advance()
            return StringLit(token.value)
        elif token.kind == "KEYWORD":
            keyword = token.value
            if keyword == "true":
                self.advance()
                return BoolLit(True)
            elif keyword == "false":
                self.advance()
                return BoolLit(False)
            elif keyword == "nil":
                self.advance()
                return NilLit()
            elif keyword == "fn":
                return self.parse_fn_lit()
            else:
                raise ParseError(f"Unexpected keyword '{keyword}'", token.line, token.col)
        elif token.kind == "IDENT":
            self.advance()
            return Identifier(token.value)
        elif token.kind == "PUNCT" and token.value == "(":
            self.advance()  # consume (
            expr = self.parse_expression()
            self.match("PUNCT")  # )
            return expr
        elif token.kind == "PUNCT" and token.value == "[":
            return self.parse_list_lit()
        elif token.kind == "PUNCT" and token.value == "{":
            return self.parse_dict_lit()
        else:
            raise ParseError(f"Unexpected token {token.kind} with value {token.value}", token.line, token.col)
    
    def parse_list_lit(self) -> ListLit:
        self.match("PUNCT")  # [
        items = []
        if self.peek().value != "]":
            while True:
                items.append(self.parse_expression())
                if self.peek().value == ",":
                    self.advance()  # consume comma
                    if self.peek().value == "]":  # trailing comma
                        break
                else:
                    break
        self.match("PUNCT")  # ]
        return ListLit(items)
    
    def parse_dict_lit(self) -> DictLit:
        self.match("PUNCT")  # {
        pairs = []
        if self.peek().value != "}":
            while True:
                key = self.parse_expression()
                self.match("PUNCT")  # :
                value = self.parse_expression()
                pairs.append((key, value))
                if self.peek().value == ",":
                    self.advance()  # consume comma
                    if self.peek().value == "}":  # trailing comma
                        break
                else:
                    break
        self.match("PUNCT")  # }
        return DictLit(pairs)
    
    def parse_fn_lit(self) -> FnLit:
        self.match_value("fn")
        self.match("PUNCT")  # (
        params = []
        if self.peek().value != ")":
            while True:
                param = self.match("IDENT").value
                params.append(param)
                if self.peek().value == ",":
                    self.advance()  # consume comma
                else:
                    break
        self.match("PUNCT")  # )
        body = self.parse_block()
        return FnLit(params, body)

def parse(source_or_tokens) -> Program:
    if isinstance(source_or_tokens, str):
        tokens = tokenize(source_or_tokens)
    else:
        tokens = source_or_tokens
    parser = Parser(tokens)
    return parser.parse_program()