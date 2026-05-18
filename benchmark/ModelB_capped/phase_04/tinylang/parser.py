from typing import List, Union
from tinylang.ast import *
from tinylang.lexer import tokenize, Token

class ParseError(Exception):
    def __init__(self, message: str, line: int, col: int):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(f"{message} at line {line}, column {col}")

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
    
    def peek(self) -> Token:
        if self.pos >= len(self.tokens):
            return Token('EOF', '', 0, 0)
        return self.tokens[self.pos]
    
    def advance(self) -> Token:
        token = self.peek()
        self.pos += 1
        return token
    
    def consume(self, expected_kind: str, error_msg: str = None) -> Token:
        token = self.peek()
        if token.kind != expected_kind:
            if error_msg is None:
                error_msg = f"Expected {expected_kind}, got {token.kind}"
            raise ParseError(error_msg, token.line, token.col)
        return self.advance()
    
    def parse_program(self) -> Program:
        stmts = []
        while self.peek().kind != 'EOF':
            stmts.append(self.parse_statement())
        return Program(stmts)
    
    def parse_statement(self) -> object:
        token = self.peek()
        if token.kind == 'KEYWORD':
            keyword = token.value
            if keyword == 'let':
                self.advance()  # consume 'let'
                return self.parse_let_stmt()
            elif keyword == 'if':
                self.advance()  # consume 'if'
                return self.parse_if_stmt()
            elif keyword == 'while':
                self.advance()  # consume 'while'
                return self.parse_while_stmt()
            elif keyword == 'for':
                self.advance()  # consume 'for'
                return self.parse_for_stmt()
            elif keyword == 'fn':
                self.advance()  # consume 'fn'
                return self.parse_fn_decl()
            elif keyword == 'return':
                self.advance()  # consume 'return'
                return self.parse_return_stmt()
            elif keyword == 'break':
                self.advance()  # consume 'break'
                return self.parse_break_stmt()
            elif keyword == 'continue':
                self.advance()  # consume 'continue'
                return self.parse_continue_stmt()
            else:
                raise ParseError(f"Unexpected keyword: {keyword}", token.line, token.col)
        elif token.kind == '{':
            return self.parse_block()
        elif token.kind == 'IDENT':
            # Check if this is an assignment (identifier followed by =)
            # This is a bit tricky in the parser, so we'll handle it in parse_expr_stmt
            # but for now, let's just try to parse it as an expression statement
            return self.parse_expr_stmt()
        else:
            return self.parse_expr_stmt()
    
    def parse_let_stmt(self) -> LetStmt:
        # The 'let' keyword was already consumed by parse_statement
        # So we should be at the identifier
        identifier = self.consume('IDENT', "Expected identifier after 'let'")
        # Consume the '=' token (which is a PUNCT)
        self.consume('PUNCT', "Expected '=' after identifier")
        value = self.parse_expression()
        self.consume('PUNCT', "Expected ';' after let statement")
        return LetStmt(identifier.value, value)
    
    def parse_if_stmt(self) -> IfStmt:
        self.advance()  # consume 'if'
        self.consume('(', "Expected '(' after 'if'")
        cond = self.parse_expression()
        self.consume(')', "Expected ')' after if condition")
        then_block = self.parse_block()
        else_block = None
        if self.peek().value == 'else':
            self.advance()  # consume 'else'
            if self.peek().value == 'if':
                # Handle else if
                else_block = self.parse_if_stmt()
            else:
                else_block = self.parse_block()
        return IfStmt(cond, then_block, else_block)
    
    def parse_while_stmt(self) -> WhileStmt:
        self.advance()  # consume 'while'
        self.consume('(', "Expected '(' after 'while'")
        cond = self.parse_expression()
        self.consume(')', "Expected ')' after while condition")
        body = self.parse_block()
        return WhileStmt(cond, body)
    
    def parse_for_stmt(self) -> ForStmt:
        self.advance()  # consume 'for'
        self.consume('(', "Expected '(' after 'for'")
        
        # Parse loop variables
        names = []
        first = self.peek()
        if first.kind == 'IDENT':
            names.append(first.value)
            self.advance()
            if self.peek().kind == ',':
                self.advance()  # consume ','
                second = self.peek()
                if second.kind == 'IDENT':
                    names.append(second.value)
                    self.advance()
        self.consume('IN', "Expected 'in' after for loop variables")
        iterable = self.parse_expression()
        self.consume(')', "Expected ')' after for loop")
        body = self.parse_block()
        return ForStmt(names, iterable, body)
    
    def parse_fn_decl(self) -> FnDecl:
        self.advance()  # consume 'fn'
        identifier = self.consume('IDENT', "Expected identifier after 'fn'")
        self.consume('(', "Expected '(' after function name")
        params = self.parse_params()
        self.consume(')', "Expected ')' after function parameters")
        body = self.parse_block()
        return FnDecl(identifier.value, params, body)
    
    def parse_return_stmt(self) -> ReturnStmt:
        self.advance()  # consume 'return'
        value = None
        if self.peek().kind != ';':
            value = self.parse_expression()
        self.consume(';', "Expected ';' after return statement")
        return ReturnStmt(value)
    
    def parse_break_stmt(self) -> BreakStmt:
        self.advance()  # consume 'break'
        self.consume(';', "Expected ';' after break statement")
        return BreakStmt()
    
    def parse_continue_stmt(self) -> ContinueStmt:
        self.advance()  # consume 'continue'
        self.consume(';', "Expected ';' after continue statement")
        return ContinueStmt()
    
    def parse_block(self) -> Block:
        self.consume('{', "Expected '{' at start of block")
        stmts = []
        while self.peek().kind != '}' and self.peek().kind != 'EOF':
            stmts.append(self.parse_statement())
        self.consume('}', "Expected '}' at end of block")
        return Block(stmts)
    
    def parse_expr_stmt(self) -> ExprStmt:
        expr = self.parse_expression()
        self.consume(';', "Expected ';' after expression")
        return ExprStmt(expr)
    
    def parse_params(self) -> List[str]:
        params = []
        if self.peek().kind == ')':
            return params
        while True:
            param = self.consume('IDENT', "Expected parameter name")
            params.append(param.value)
            if self.peek().kind == ')':
                break
            self.consume(',', "Expected ',' or ')' after parameter")
        return params
    
    def parse_expression(self) -> object:
        return self.parse_assignment()
    
    def parse_assignment(self) -> object:
        left = self.parse_logic_or()
        if self.peek().kind == '=':
            self.advance()  # consume '='
            right = self.parse_assignment()
            # Check if left is a valid assignment target
            if not isinstance(left, (Identifier, Index)):
                raise ParseError("Invalid assignment target", self.peek().line, self.peek().col)
            return Assign(left, right)
        return left
    
    def parse_logic_or(self) -> object:
        left = self.parse_logic_and()
        if self.peek().value == '||':
            self.advance()
            right = self.parse_logic_or()  # Right associative
            return BinaryOp('||', left, right)
        return left
    
    def parse_logic_and(self) -> object:
        left = self.parse_equality()
        if self.peek().value == '&&':
            self.advance()
            right = self.parse_logic_and()  # Right associative
            return BinaryOp('&&', left, right)
        return left
    
    def parse_equality(self) -> object:
        left = self.parse_comparison()
        if self.peek().value in ('==', '!='):
            op = self.advance().value
            right = self.parse_equality()
            return BinaryOp(op, left, right)
        return left
    
    def parse_comparison(self) -> object:
        left = self.parse_term()
        if self.peek().value in ('<', '>', '<=', '>='):
            op = self.advance().value
            right = self.parse_comparison()
            return BinaryOp(op, left, right)
        return left
    
    def parse_term(self) -> object:
        left = self.parse_factor()
        if self.peek().value in ('+', '-'):
            op = self.advance().value
            right = self.parse_term()
            return BinaryOp(op, left, right)
        return left
    
    def parse_factor(self) -> object:
        left = self.parse_unary()
        if self.peek().value in ('*', '/', '%'):
            op = self.advance().value
            right = self.parse_factor()
            return BinaryOp(op, left, right)
        return left
    
    def parse_unary(self) -> object:
        if self.peek().value in ('!', '-'):
            op = self.advance().value
            operand = self.parse_unary()
            return UnaryOp(op, operand)
        return self.parse_call()
    
    def parse_call(self) -> object:
        left = self.parse_primary()
        while self.peek().kind == '(':
            self.advance()  # consume '('
            args = self.parse_args()
            self.consume(')', "Expected ')' after function call")
            left = Call(left, args)
        return left
    
    def parse_primary(self) -> object:
        token = self.peek()
        if token.kind == 'NUMBER':
            self.advance()
            return NumberLit(float(token.value))
        elif token.kind == 'STRING':
            self.advance()
            return StringLit(token.value)
        elif token.kind == 'IDENT':
            self.advance()
            return Identifier(token.value)
        elif token.kind == 'TRUE':
            self.advance()
            return BoolLit(True)
        elif token.kind == 'FALSE':
            self.advance()
            return BoolLit(False)
        elif token.kind == 'NIL':
            self.advance()
            return NilLit()
        elif token.kind == 'LEFT_PAREN':
            self.advance()
            expr = self.parse_expression()
            self.consume(')', "Expected ')' after expression")
            return expr
        elif token.kind == 'LEFT_BRACKET':
            return self.parse_list_lit()
        elif token.kind == 'LEFT_BRACE':
            return self.parse_dict_lit()
        else:
            raise ParseError(f"Unexpected token: {token.kind}", token.line, token.col)
    
    def parse_list_lit(self) -> ListLit:
        self.consume('LEFT_BRACKET', "Expected '['")
        items = []
        if self.peek().kind != 'RIGHT_BRACKET':
            while True:
                items.append(self.parse_expression())
                if self.peek().kind == 'RIGHT_BRACKET':
                    break
                self.consume(',', "Expected ',' or ']' after list item")
        self.consume('RIGHT_BRACKET', "Expected ']' after list")
        return ListLit(items)
    
    def parse_dict_lit(self) -> DictLit:
        self.consume('LEFT_BRACE', "Expected '{'")
        pairs = []
        if self.peek().kind != 'RIGHT_BRACE':
            while True:
                key = self.parse_expression()
                self.consume(':', "Expected ':' after dict key")
                value = self.parse_expression()
                pairs.append((key, value))
                if self.peek().kind == 'RIGHT_BRACE':
                    break
                self.consume(',', "Expected ',' or '}' after dict pair")
        self.consume('RIGHT_BRACE', "Expected '}' after dict")
        return DictLit(pairs)
    
    def parse_fn_lit(self) -> FnLit:
        self.consume('FN', "Expected 'fn'")
        self.consume('(', "Expected '('")
        params = self.parse_params()
        self.consume(')', "Expected ')' after function parameters")
        body = self.parse_block()
        return FnLit(params, body)
    
    def parse_args(self) -> List[object]:
        args = []
        if self.peek().kind == ')':
            return args
        while True:
            args.append(self.parse_expression())
            if self.peek().kind == ')':
                break
            self.consume(',', "Expected ',' or ')' after argument")
        return args

def parse(source_or_tokens: Union[str, List[Token]]) -> Program:
    if isinstance(source_or_tokens, str):
        tokens = tokenize(source_or_tokens)
    else:
        tokens = source_or_tokens
    parser = Parser(tokens)
    return parser.parse_program()