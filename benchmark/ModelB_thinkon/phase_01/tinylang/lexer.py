from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Token:
    kind: str
    value: object
    line: int
    col: int

class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.keywords = {
            'let', 'if', 'else', 'while', 'for', 'in', 'fn', 'return',
            'break', 'continue', 'true', 'false', 'nil'
        }
    
    def peek(self, offset=0) -> Optional[str]:
        if self.pos + offset >= len(self.source):
            return None
        return self.source[self.pos + offset]
    
    def advance(self) -> str:
        if self.pos >= len(self.source):
            return None
        char = self.source[self.pos]
        self.pos += 1
        if char == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return char
    
    def skip_whitespace_and_comments(self):
        while True:
            char = self.peek()
            if char is None:
                break
            if char.isspace():
                self.advance()
            elif char == '/' and self.peek(1) == '/':
                # Skip line comment
                while self.peek() and self.peek() != '\n':
                    self.advance()
                self.advance()  # Skip the newline
            else:
                break
    
    def read_number(self) -> Token:
        start_pos = self.pos
        start_col = self.col
        
        # Read integer part
        while self.peek() and (self.peek().isdigit() or self.peek() == '.'):
            self.advance()
        
        # Check if we have a valid number
        number_str = self.source[start_pos:self.pos]
        try:
            value = float(number_str)
        except ValueError:
            raise Exception(f"Invalid number at line {self.line}, col {self.col}")
        
        return Token('NUMBER', value, self.line, start_col)
    
    def read_string(self) -> Token:
        start_pos = self.pos
        start_col = self.col
        
        # Skip opening quote
        self.advance()
        
        # Read string content
        content = ""
        while True:
            char = self.peek()
            if char is None:
                raise Exception(f"Unterminated string at line {self.line}, col {start_col}")
            elif char == '"':
                self.advance()
                break
            elif char == '\\':
                self.advance()
                if self.peek() is None:
                    raise Exception(f"Unterminated string at line {self.line}, col {start_col}")
                escaped_char = self.advance()
                if escaped_char == 'n':
                    content += '\n'
                elif escaped_char == 't':
                    content += '\t'
                elif escaped_char == '"':
                    content += '"'
                elif escaped_char == '\\':
                    content += '\\'
                else:
                    content += escaped_char
            elif char == '\n':
                raise Exception(f"Unterminated string at line {self.line}, col {start_col}")
            else:
                content += self.advance()
        
        return Token('STRING', content, self.line, start_col)
    
    def read_identifier_or_keyword(self) -> Token:
        start_pos = self.pos
        start_col = self.col
        
        # Read identifier/keyword
        while self.peek() and (self.peek().isalnum() or self.peek() == '_'):
            self.advance()
        
        identifier = self.source[start_pos:self.pos]
        kind = 'KEYWORD' if identifier in self.keywords else 'IDENT'
        
        return Token(kind, identifier, self.line, start_col)
    
    def read_punctuation(self) -> Token:
        start_pos = self.pos
        start_col = self.col
        
        # Check for multi-character operators first (longest first)
        multi_ops = ['==', '!=', '<=', '>=', '&&', '||']
        for op in multi_ops:
            if (self.pos + len(op) <= len(self.source) and 
                self.source[self.pos:self.pos + len(op)] == op):
                # Advance by the length of the operator
                for _ in range(len(op)):
                    self.advance()
                return Token('PUNCT', op, self.line, start_col)
        
        # Single character punctuation
        char = self.peek()
        if char is not None:
            self.advance()
            return Token('PUNCT', char, self.line, start_col)
        
        return None
    
    def next_token(self) -> Token:
        self.skip_whitespace_and_comments()
        
        if self.pos >= len(self.source):
            return Token('EOF', None, self.line, self.col)
        
        char = self.peek()
        
        if char.isdigit():
            return self.read_number()
        elif char == '"':
            return self.read_string()
        elif char.isalpha() or char == '_':
            return self.read_identifier_or_keyword()
        else:
            # For all other cases, try to read punctuation
            return self.read_punctuation()
    
    def tokenize(self) -> List[Token]:
        tokens = []
        while True:
            token = self.next_token()
            tokens.append(token)
            if token.kind == 'EOF':
                break
        return tokens

def tokenize(source: str) -> List[Token]:
    lexer = Lexer(source)
    return lexer.tokenize()