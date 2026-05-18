from dataclasses import dataclass
from typing import List, Tuple

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
    
    def peek(self) -> str:
        if self.pos >= len(self.source):
            return ''
        return self.source[self.pos]
    
    def advance(self) -> str:
        if self.pos >= len(self.source):
            return ''
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
            if char == ' ' or char == '\t' or char == '\r':
                self.advance()
            elif char == '/':
                # Check if it's a comment
                self.advance()
                if self.peek() == '/':
                    # Line comment, skip to end of line
                    while self.peek() != '\n' and self.peek() != '':
                        self.advance()
                    self.advance()  # Skip the newline
                else:
                    # Not a comment, put the character back
                    self.pos -= 1
                    self.col -= 1
                    break
            else:
                break
    
    def read_number(self) -> Token:
        start_pos = self.pos
        start_line = self.line
        start_col = self.col
        
        # Read integer part
        while self.peek().isdigit():
            self.advance()
        
        # Read fractional part if present
        if self.peek() == '.':
            self.advance()
            while self.peek().isdigit():
                self.advance()
        
        # Get the value
        value = float(self.source[start_pos:self.pos])
        return Token('NUMBER', value, start_line, start_col)
    
    def read_string(self) -> Token:
        start_pos = self.pos
        start_line = self.line
        start_col = self.col
        
        # Skip the opening quote
        self.advance()
        
        # Read until closing quote
        while True:
            char = self.peek()
            if char == '':
                # Unterminated string at EOF
                raise Exception(f"Unterminated string at line {start_line}, column {start_col}")
            elif char == '\n':
                # String cannot span multiple lines
                raise Exception(f"String cannot span multiple lines at line {start_line}, column {start_col}")
            elif char == '"':
                # End of string
                self.advance()  # Skip closing quote
                value = self.source[start_pos+1:self.pos-1]  # Exclude quotes
                # Handle escape sequences
                value = value.encode().decode('unicode_escape')
                return Token('STRING', value, start_line, start_col)
            else:
                self.advance()
    
    def read_identifier_or_keyword(self) -> Token:
        start_pos = self.pos
        start_line = self.line
        start_col = self.col
        
        # Read identifier
        while self.peek().isalnum() or self.peek() == '_':
            self.advance()
        
        # Get the value
        value = self.source[start_pos:self.pos]
        if value in self.keywords:
            return Token('KEYWORD', value, start_line, start_col)
        else:
            return Token('IDENT', value, start_line, start_col)
    
    def read_punctuation(self) -> Token:
        start_line = self.line
        start_col = self.col
        
        char = self.peek()
        value = char
        self.advance()
        
        # Check for multi-character operators
        if char in ['=', '!', '<', '>', '&', '|']:
            next_char = self.peek()
            if ((char == '=' and next_char == '=') or
                (char == '!' and next_char == '=') or
                (char == '<' and next_char == '=') or
                (char == '>' and next_char == '=') or
                (char == '&' and next_char == '&') or
                (char == '|' and next_char == '|')):
                self.advance()  # consume the next character
                value = char + next_char
        
        return Token('PUNCT', value, start_line, start_col)
    
    def tokenize(self) -> List[Token]:
        tokens = []
        
        while True:
            self.skip_whitespace_and_comments()
            
            if self.pos >= len(self.source):
                tokens.append(Token('EOF', None, self.line, self.col))
                break
            
            char = self.peek()
            
            if char.isdigit() or (char == '.' and self.peek(1).isdigit()):
                tokens.append(self.read_number())
            elif char == '"':
                tokens.append(self.read_string())
            elif char.isalpha() or char == '_':
                tokens.append(self.read_identifier_or_keyword())
            else:
                # Punctuation
                tokens.append(self.read_punctuation())
        
        return tokens

def tokenize(source: str) -> List[Token]:
    lexer = Lexer(source)
    return lexer.tokenize()