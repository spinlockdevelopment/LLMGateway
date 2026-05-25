from typing import Union, List, Tuple
from tinylang.lexer import tokenize, Token
from tinylang.ast import *
from tinylang.errors import ParseError

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token("EOF", None, 0, 0)

    def consume(self) -> Token:
        token = self.peek()
        self.pos += 1
        return token

    def expect(self, kind: str, value: Union[str, None] = None):
        token = self.peek()
        if token.kind != kind or (value is not None and token.value != value):
            raise ParseError(
                f"Expected {kind} {value}, got {token.kind} {token.value}",
                token.line,
                token.col
            )
        return self.consume()

    def parse_program(self) -> Program:
        stmts = []
        while self.peek().kind != "EOF":
            stmts.append(self.parse_statement())
        return Program(stmts)

    def parse_statement(self) -> Stmt:
        token = self.peek()
        if token.kind == "KEYWORD":
            if token.value == "let":
                return self.parse_let_stmt()
            elif token.value == "if":
                return self.parse_if_stmt()
            elif token.value == "while":
                return self.parse_while_stmt()
            elif token.value == "for":
                return self.parse_for_stmt()
            elif token.value == "fn":
                return self.parse_fn_decl()
            elif token.value == "return":
                return self.parse_return_stmt()
            elif token.value == "break":
                self.expect("KEYWORD", "break")
                self.expect("PUNCT", ";")
                return BreakStmt()
            elif token.value == "continue":
                self.expect("KEYWORD", "continue")
                self.expect("PUNCT", ";")
                return ContinueStmt()
        
        # If it's not a keyword statement, it might be a block or an expression statement
        # But wait, a block is also a statement.
        # A block starts with '{'
        if token.kind == "PUNCT" and token.value == "{":
            return self.parse_block()
        
        # Otherwise, it's an expression statement
        expr = self.parse_expression()
        self.expect("PUNCT", ";")
        return ExprStmt(expr)

    def parse_let_stmt(self) -> LetStmt:
        self.expect("KEYWORD", "let")
        name_token = self.expect("IDENT")
        self.expect("PUNCT", "=")
        value = self.parse_expression()
        self.expect("PUNCT", ";")
        return LetStmt(name_token.value, value)

    def parse_if_stmt(self) -> IfStmt:
        self.expect("KEYWORD", "if")
        cond = self.parse_expression()
        then_block = self.parse_block()
        else_block = None
        if self.peek().kind == "KEYWORD" and self.peek().value == "else":
            self.consume()
            if self.peek().kind == "KEYWORD" and self.peek().value == "if":
                # else if
                else_block = self.parse_if_stmt()
            else:
                else_block = self.parse_block()
        return IfStmt(cond, then_block, else_block)

    def parse_while_stmt(self) -> WhileStmt:
        self.expect("KEYWORD", "while")
        cond = self.parse_expression()
        body = self.parse_block()
        return WhileStmt(cond, body)

    def parse_for_stmt(self) -> ForStmt:
        self.expect("KEYWORD", "for")
        names = []
        while True:
            name_token = self.expect("IDENT")
            names.append(name_token.value)
            if self.peek().kind == "PUNCT" and self.peek().value == ",":
                self.consume()
            else:
                break
        self.expect("KEYWORD", "in")
        iterable = self.parse_expression()
        body = self.parse_block()
        return ForStmt(names, iterable, body)

    def parse_fn_decl(self) -> FnDecl:
        self.expect("KEYWORD", "fn")
        name_token = self.expect("IDENT")
        self.expect("PUNCT", "(")
        params = []
        if self.peek().kind != "PUNCT" or self.peek().value != ")":
            while True:
                param_token = self.expect("IDENT")
                params.append(param_token.value)
                if self.peek().kind == "PUNCT" and self.peek().value == ",":
                    self.consume()
                else:
                    break
        self.expect("PUNCT", ")")
        body = self.parse_block()
        return FnDecl(name_token.value, params, body)

    def parse_return_stmt(self) -> ReturnStmt:
        self.expect("KEYWORD", "return")
        value = None
        if self.peek().kind != "PUNCT" or self.peek().value != ";":
            value = self.parse_expression()
        self.expect("PUNCT", ";")
        return ReturnStmt(value)

    def parse_block(self) -> Block:
        self.expect("PUNCT", "{")
        stmts = []
        while self.peek().kind != "PUNCT" or self.peek().value != "}":
            stmts.append(self.parse_statement())
        self.expect("PUNCT", "}")
        return Block(stmts)

    def parse_expression(self) -> Expr:
        return self.parse_assignment()

    def parse_assignment(self) -> Expr:
        # Assignment is right-associative
        # We need to check if the left side is an identifier or index
        # But we can't easily look ahead without parsing the expression.
        # However, the grammar says target is Identifier | Index.
        
        # Let's try to parse the left side as a primary expression.
        # If it's an identifier or index, and the next token is '=', then it's an assignment.
        
        # To handle right-associativity and precedence correctly:
        # assignment -> logical_or "=" assignment | logical_or
        
        # But we need to know if the logical_or is actually an assignment target.
        # This is tricky in recursive descent.
        
        # Let's use a different approach:
        # parse_assignment calls parse_logical_or.
        # If parse_logical_or returns an Identifier or Index, and the next token is '=',
        # then we treat it as an assignment.
        
        # Wait, the target of assignment can be an Index.
        # Index is postfix.
        
        # Let's try this:
        expr = self.parse_logical_or()
        if self.peek().kind == "PUNCT" and self.peek().value == "=":
            self.consume()
            value = self.parse_assignment()
            if isinstance(expr, Identifier):
                return Assign(expr, value)
            elif isinstance(expr, Index):
                return Assign(expr, value)
            else:
                raise ParseError("Invalid assignment target", self.peek().line, self.peek().col)
        return expr

    def parse_logical_or(self) -> Expr:
        expr = self.parse_logical_and()
        while self.peek().kind == "PUNCT" and self.peek().value == "||":
            self.consume()
            right = self.parse_logical_and()
            expr = BinaryOp("||", expr, right)
        return expr

    def parse_logical_and(self) -> Expr:
        expr = self.parse_equality()
        while self.peek().kind == "PUNCT" and self.peek().value == "&&":
            self.consume()
            right = self.parse_equality()
            expr = BinaryOp("&&", expr, right)
        return expr

    def parse_equality(self) -> Expr:
        expr = self.parse_comparison()
        while self.peek().kind == "PUNCT" and self.peek().value in ("==", "!="):
            op = self.consume().value
            right = self.parse_comparison()
            expr = BinaryOp(op, expr, right)
        return expr

    def parse_comparison(self) -> Expr:
        expr = self.parse_additive()
        while self.peek().kind == "PUNCT" and self.peek().value in ("<", ">", "<=", ">="):
            op = self.consume().value
            right = self.parse_additive()
            expr = BinaryOp(op, expr, right)
        return expr

    def parse_additive(self) -> Expr:
        expr = self.parse_multiplicative()
        while self.peek().kind == "PUNCT" and self.peek().value in ("+", "-"):
            op = self.consume().value
            right = self.parse_multiplicative()
            expr = BinaryOp(op, expr, right)
        return expr

    def parse_multiplicative(self) -> Expr:
        expr = self.parse_unary()
        while self.peek().kind == "PUNCT" and self.peek().value in ("*", "/", "%"):
            op = self.consume().value
            right = self.parse_unary()
            expr = BinaryOp(op, expr, right)
        return expr

    def parse_unary(self) -> Expr:
        if self.peek().kind == "PUNCT" and self.peek().value in ("!", "-"):
            op = self.consume().value
            operand = self.parse_unary()
            return UnaryOp(op, operand)
        return self.parse_postfix()

    def parse_postfix(self) -> Expr:
        expr = self.parse_primary()
        while True:
            if self.peek().kind == "PUNCT" and self.peek().value == "(":
                self.consume()
                args = []
                if self.peek().kind != "PUNCT" or self.peek().value != ")":
                    while True:
                        args.append(self.parse_expression())
                        if self.peek().kind == "PUNCT" and self.peek().value == ",":
                            self.consume()
                        else:
                            break
                self.expect("PUNCT", ")")
                expr = Call(expr, args)
            elif self.peek().kind == "PUNCT" and self.peek().value == "[":
                self.consume()
                key = self.parse_expression()
                self.expect("PUNCT", "]")
                expr = Index(expr, key)
            else:
                break
        return expr

    def parse_primary(self) -> Expr:
        token = self.peek()
        if token.kind == "KEYWORD":
            if token.value == "true":
                self.consume()
                return BoolLit(True)
            elif token.value == "false":
                self.consume()
                return BoolLit(False)
            elif token.value == "nil":
                self.consume()
                return NilLit()
            elif token.value == "fn":
                return self.parse_fn_lit()
        elif token.kind == "NUMBER":
            return NumberLit(self.consume().value)
        elif token.kind == "STRING":
            return StringLit(self.consume().value)
        elif token.kind == "IDENT":
            return Identifier(self.consume().value)
        elif token.kind == "PUNCT":
            if token.value == "(":
                self.consume()
                expr = self.parse_expression()
                self.expect("PUNCT", ")")
                return expr
            elif token.value == "[":
                self.consume()
                items = []
                if self.peek().kind != "PUNCT" or self.peek().value != "]":
                    while True:
                        items.append(self.parse_expression())
                        if self.peek().kind == "PUNCT" and self.peek().value == ",":
                            self.consume()
                        else:
                            break
                self.expect("PUNCT", "]")
                return ListLit(items)
            elif token.value == "{":
                return self.parse_dict_lit()
        
        raise ParseError(f"Unexpected token {token.kind} {token.value}", token.line, token.col)

    def parse_fn_lit(self) -> FnLit:
        self.expect("KEYWORD", "fn")
        self.expect("PUNCT", "(")
        params = []
        if self.peek().kind != "PUNCT" or self.peek().value != ")":
            while True:
                param_token = self.expect("IDENT")
                params.append(param_token.value)
                if self.peek().kind == "PUNCT" and self.peek().value == ",":
                    self.consume()
                else:
                    break
        self.expect("PUNCT", ")")
        body = self.parse_block()
        return FnLit(params, body)

    def parse_dict_lit(self) -> DictLit:
        self.expect("PUNCT", "{")
        pairs = []
        if self.peek().kind != "PUNCT" or self.peek().value != "}":
            while True:
                key = self.parse_expression()
                self.expect("PUNCT", ":")
                val = self.parse_expression()
                pairs.append((key, val))
                if self.peek().kind == "PUNCT" and self.peek().value == ",":
                    self.consume()
                    if self.peek().kind == "PUNCT" and self.peek().value == "}":
                        break
                else:
                    break
        self.expect("PUNCT", "}")
        return DictLit(pairs)

def parse(source_or_tokens: Union[str, List[Token]]) -> Program:
    if isinstance(source_or_tokens, str):
        tokens = tokenize(source_or_tokens)
    else:
        tokens = source_or_tokens
    parser = Parser(tokens)
    return parser.parse_program()
