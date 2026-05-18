from typing import List, Optional, Union
from .lexer import tokenize, Token
from .ast import *


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.current = 0
    
    def is_at_end(self) -> bool:
        return self.current >= len(self.tokens)
    
    def peek(self) -> Token:
        if self.is_at_end():
            # Return a dummy EOF token
            return Token('EOF', None, 0, 0)
        return self.tokens[self.current]
    
    def previous(self) -> Token:
        return self.tokens[self.current - 1]
    
    def advance(self) -> Token:
        if not self.is_at_end():
            self.current += 1
        return self.previous()
    
    def check(self, kind: str, value: str = None) -> bool:
        if self.is_at_end():
            return False
        token = self.peek()
        if token.kind != kind:
            return False
        if value is not None and token.value != value:
            return False
        return True
    
    def match(self, *args) -> bool:
        """Check if current token matches any of the given (kind, value) pairs or just kinds."""
        for arg in args:
            if isinstance(arg, tuple):
                kind, value = arg
                if self.check(kind, value):
                    self.advance()
                    return True
            else:
                kind = arg
                if self.check(kind):
                    self.advance()
                    return True
        return False
    
    def consume(self, kind: str, value: str = None, message: str = "Unexpected token") -> Token:
        if self.check(kind, value):
            return self.advance()
        
        current_token = self.peek()
        raise Exception(f"{message} at line {current_token.line}, col {current_token.col}")
    
    def parse(self) -> Program:
        statements = []
        while not self.is_at_end() and not self.check('EOF'):
            stmt = self.statement()
            if stmt:
                statements.append(stmt)
        return Program(statements)
    
    def statement(self) -> Optional[Stmt]:
        try:
            if self.match(('KEYWORD', 'let')):
                return self.let_statement()
            if self.match(('KEYWORD', 'if')):
                return self.if_statement()
            if self.match(('KEYWORD', 'while')):
                return self.while_statement()
            if self.match(('KEYWORD', 'for')):
                return self.for_statement()
            if self.match(('KEYWORD', 'fn')):
                return self.fn_declaration()
            if self.match(('KEYWORD', 'return')):
                return self.return_statement()
            if self.match(('KEYWORD', 'break')):
                self.consume('PUNCT', ';', "Expected ';' after 'break'")
                return BreakStmt()
            if self.match(('KEYWORD', 'continue')):
                self.consume('PUNCT', ';', "Expected ';' after 'continue'")
                return ContinueStmt()
            if self.check('PUNCT', '{'):
                return self.block()
            
            return self.expression_statement()
        except Exception as e:
            # For now, just re-raise. Phase 10 will improve error handling.
            raise e
    
    def let_statement(self) -> LetStmt:
        name_token = self.consume('IDENT', message="Expected variable name")
        name = name_token.value
        
        self.consume('PUNCT', '=', "Expected '=' after variable name")
        value = self.expression()
        self.consume('PUNCT', ';', "Expected ';' after variable declaration")
        
        return LetStmt(name, value)
    
    def if_statement(self) -> IfStmt:
        self.consume('PUNCT', '(', "Expected '(' after 'if'")
        condition = self.expression()
        self.consume('PUNCT', ')', "Expected ')' after if condition")
        
        then_block = self.block()
        else_block = None
        
        if self.match(('KEYWORD', 'else')):
            if self.check('KEYWORD', 'if'):
                # else if - create a block containing the nested if
                nested_if = self.statement()
                else_block = Block([nested_if])
            else:
                else_block = self.block()
        
        return IfStmt(condition, then_block, else_block)
    
    def while_statement(self) -> WhileStmt:
        self.consume('PUNCT', '(', "Expected '(' after 'while'")
        condition = self.expression()
        self.consume('PUNCT', ')', "Expected ')' after while condition")
        
        body = self.block()
        return WhileStmt(condition, body)
    
    def for_statement(self) -> ForStmt:
        self.consume('PUNCT', '(', "Expected '(' after 'for'")
        
        # Parse variable names
        names = []
        name_token = self.consume('IDENT', message="Expected variable name")
        names.append(name_token.value)
        
        if self.match(('PUNCT', ',')):
            name_token = self.consume('IDENT', message="Expected second variable name")
            names.append(name_token.value)
        
        self.consume('PUNCT', ')', "Expected ')' after variable names")
        self.consume('KEYWORD', 'in', "Expected 'in' in for loop")
        iterable = self.expression()
        
        body = self.block()
        return ForStmt(names, iterable, body)
    
    def fn_declaration(self) -> FnDecl:
        name_token = self.consume('IDENT', message="Expected function name")
        name = name_token.value
        
        self.consume('PUNCT', '(', "Expected '(' after function name")
        params = self.parameter_list()
        self.consume('PUNCT', ')', "Expected ')' after parameters")
        
        body = self.block()
        return FnDecl(name, params, body)
    
    def return_statement(self) -> ReturnStmt:
        value = None
        if not self.check('PUNCT', ';'):
            value = self.expression()
        
        self.consume('PUNCT', ';', "Expected ';' after return statement")
        return ReturnStmt(value)
    
    def block(self) -> Block:
        self.consume('PUNCT', '{', "Expected '{'")
        
        statements = []
        while not self.check('PUNCT', '}') and not self.is_at_end():
            stmt = self.statement()
            if stmt:
                statements.append(stmt)
        
        self.consume('PUNCT', '}', "Expected '}'")
        return Block(statements)
    
    def expression_statement(self) -> ExprStmt:
        expr = self.expression()
        self.consume('PUNCT', ';', "Expected ';' after expression")
        return ExprStmt(expr)
    
    def parameter_list(self) -> List[str]:
        params = []
        
        if not self.check('PUNCT', ')'):
            param_token = self.consume('IDENT', message="Expected parameter name")
            params.append(param_token.value)
            
            while self.match(('PUNCT', ',')):
                param_token = self.consume('IDENT', message="Expected parameter name")
                params.append(param_token.value)
        
        return params
    
    # Expression parsing with precedence climbing
    def expression(self) -> Expr:
        return self.assignment()
    
    def assignment(self) -> Expr:
        expr = self.logic_or()
        
        if self.match(('PUNCT', '=')):
            value = self.assignment()  # Right associative
            
            # Check if expr is a valid lvalue
            if isinstance(expr, (Identifier, Index)):
                return Assign(expr, value)
            else:
                raise Exception(f"Invalid assignment target at line {self.previous().line}, col {self.previous().col}")
        
        return expr
    
    def logic_or(self) -> Expr:
        expr = self.logic_and()
        
        while self.match(('PUNCT', '||')):
            op = self.previous().value
            right = self.logic_and()
            expr = BinaryOp(op, expr, right)
        
        return expr
    
    def logic_and(self) -> Expr:
        expr = self.equality()
        
        while self.match(('PUNCT', '&&')):
            op = self.previous().value
            right = self.equality()
            expr = BinaryOp(op, expr, right)
        
        return expr
    
    def equality(self) -> Expr:
        expr = self.comparison()
        
        while self.match(('PUNCT', '=='), ('PUNCT', '!=')):
            op = self.previous().value
            right = self.comparison()
            expr = BinaryOp(op, expr, right)
        
        return expr
    
    def comparison(self) -> Expr:
        expr = self.term()
        
        while self.match(('PUNCT', '<'), ('PUNCT', '>'), ('PUNCT', '<='), ('PUNCT', '>=')):
            op = self.previous().value
            right = self.term()
            expr = BinaryOp(op, expr, right)
        
        return expr
    
    def term(self) -> Expr:
        expr = self.factor()
        
        while self.match(('PUNCT', '+'), ('PUNCT', '-')):
            op = self.previous().value
            right = self.factor()
            expr = BinaryOp(op, expr, right)
        
        return expr
    
    def factor(self) -> Expr:
        expr = self.unary()
        
        while self.match(('PUNCT', '*'), ('PUNCT', '/'), ('PUNCT', '%')):
            op = self.previous().value
            right = self.unary()
            expr = BinaryOp(op, expr, right)
        
        return expr
    
    def unary(self) -> Expr:
        if self.match(('PUNCT', '!'), ('PUNCT', '-')):
            op = self.previous().value
            expr = self.unary()
            return UnaryOp(op, expr)
        
        return self.call()
    
    def call(self) -> Expr:
        expr = self.primary()
        
        while True:
            if self.match(('PUNCT', '(')):
                args = self.argument_list()
                self.consume('PUNCT', ')', "Expected ')' after arguments")
                expr = Call(expr, args)
            elif self.match(('PUNCT', '[')):
                key = self.expression()
                self.consume('PUNCT', ']', "Expected ']' after index")
                expr = Index(expr, key)
            else:
                break
        
        return expr
    
    def primary(self) -> Expr:
        if self.match('NUMBER'):
            return NumberLit(self.previous().value)
        
        if self.match('STRING'):
            return StringLit(self.previous().value)
        
        if self.match(('KEYWORD', 'true')):
            return BoolLit(True)
        
        if self.match(('KEYWORD', 'false')):
            return BoolLit(False)
        
        if self.match(('KEYWORD', 'nil')):
            return NilLit()
        
        if self.match('IDENT'):
            return Identifier(self.previous().value)
        
        if self.match(('PUNCT', '(')):
            expr = self.expression()
            self.consume('PUNCT', ')', "Expected ')' after expression")
            return expr
        
        if self.check('PUNCT', '['):
            return self.list_literal()
        
        if self.check('PUNCT', '{'):
            return self.dict_literal()
        
        if self.match(('KEYWORD', 'fn')):
            return self.function_literal()
        
        current_token = self.peek()
        raise Exception(f"Unexpected token at line {current_token.line}, col {current_token.col}")
    
    def list_literal(self) -> ListLit:
        self.consume('PUNCT', '[', "Expected '['")
        
        items = []
        if not self.check('PUNCT', ']'):
            items.append(self.expression())
            
            while self.match(('PUNCT', ',')):
                if self.check('PUNCT', ']'):  # Trailing comma
                    break
                items.append(self.expression())
        
        self.consume('PUNCT', ']', "Expected ']'")
        return ListLit(items)
    
    def dict_literal(self) -> DictLit:
        self.consume('PUNCT', '{', "Expected '{'")
        
        pairs = []
        if not self.check('PUNCT', '}'):
            key = self.expression()
            self.consume('PUNCT', ':', "Expected ':' after dict key")
            value = self.expression()
            pairs.append((key, value))
            
            while self.match(('PUNCT', ',')):
                if self.check('PUNCT', '}'):  # Trailing comma
                    break
                key = self.expression()
                self.consume('PUNCT', ':', "Expected ':' after dict key")
                value = self.expression()
                pairs.append((key, value))
        
        self.consume('PUNCT', '}', "Expected '}'")
        return DictLit(pairs)
    
    def function_literal(self) -> FnLit:
        self.consume('PUNCT', '(', "Expected '(' after 'fn'")
        params = self.parameter_list()
        self.consume('PUNCT', ')', "Expected ')' after parameters")
        
        body = self.block()
        return FnLit(params, body)
    
    def argument_list(self) -> List[Expr]:
        args = []
        
        if not self.check('PUNCT', ')'):
            args.append(self.expression())
            
            while self.match(('PUNCT', ',')):
                args.append(self.expression())
        
        return args


def parse(source_or_tokens: Union[str, List[Token]]) -> Program:
    """Parse tinylang source code or tokens into an AST."""
    if isinstance(source_or_tokens, str):
        tokens = tokenize(source_or_tokens)
    else:
        tokens = source_or_tokens
    
    parser = Parser(tokens)
    return parser.parse()