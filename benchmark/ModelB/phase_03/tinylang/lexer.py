from dataclasses import dataclass
from typing import List

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
        self.punct = {'+', '-', '*', '/', '%', '==', '!=', '<', '>', '<=', '>=', 
                     '&&', '||', '!', '=', '(', ')', '{', '}', '[', ']', ',', ';', ':', '.'}
    
    def peek(self, offset: int = 0) -> str:
        """Peek at the character at current position + offset"""
        if self.pos + offset >= len(self.source):
            return ''
        return self.source[self.pos + offset]
    
    def advance(self) -> str:
        """Advance and return the current character"""
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
    
    def is_digit(self, char: str) -> bool:
        """Check if character is a digit"""
        return char.isdigit()
    
    def is_alpha(self, char: str) -> bool:
        """Check if character is alphabetic"""
        return char.isalpha() or char == '_'
    
    def read_number(self) -> Token:
        """Read a number token"""
        start_line = self.line
        start_col = self.col
        num_str = ""
        
        # Read integer part
        while self.peek() and self.is_digit(self.peek()):
            num_str += self.advance()
        
        # Check for decimal part
        if self.peek() == '.':
            num_str += self.advance()  # consume '.'
            # Read fractional part
            while self.peek() and self.is_digit(self.peek()):
                num_str += self.advance()
        
        value = float(num_str)
        return Token('NUMBER', value, start_line, start_col)
    
    def read_string(self) -> Token:
        """Read a string token"""
        start_line = self.line
        start_col = self.col
        # consume opening quote
        self.advance()
        str_value = ""
        
        while self.peek() and self.peek() != '"':
            char = self.peek()
            if char == '\\':
                # consume backslash
                self.advance()
                escaped_char = self.peek()
                if escaped_char == 'n':
                    str_value += '\n'
                elif escaped_char == 't':
                    str_value += '\t'
                elif escaped_char == '"':
                    str_value += '"'
                elif escaped_char == '\\':
                    str_value += '\\'
                else:
                    str_value += escaped_char
                # consume the escaped character
                self.advance()
            else:
                str_value += self.advance()
        
        # Check for closing quote
        if self.peek() == '"':
            self.advance()  # consume closing quote
        else:
            # Unterminated string
            raise Exception(f"Unterminated string at line {start_line}, column {start_col}")
        
        return Token('STRING', str_value, start_line, start_col)
    
    def read_identifier(self) -> Token:
        """Read an identifier or keyword"""
        start_line = self.line
        start_col = self.col
        ident = ""
        
        while self.peek() and (self.is_alpha(self.peek()) or self.is_digit(self.peek())):
            ident += self.advance()
        
        if ident in self.keywords:
            return Token('KEYWORD', ident, start_line, start_col)
        else:
            return Token('IDENT', ident, start_line, start_col)
    
    def read_punct(self) -> Token:
        """Read a punctuation token"""
        start_line = self.line
        start_col = self.col
        
        # Check for multi-character operators first
        current_char = self.peek()
        if current_char in ['=', '!', '<', '>', '&', '|']:
            # Try to match multi-character operators
            if self.peek(1) is not None:
                two_char = current_char + self.peek(1)
                if two_char in ['==', '!=', '<=', '>=', '&&', '||']:
                    self.advance()  # consume first char
                    self.advance()  # consume second char
                    return Token('PUNCT', two_char, start_line, start_col)
        
        # Single character punctuation
        punct = self.advance()
        return Token('PUNCT', punct, start_line, start_col)
    
    def tokenize(self) -> List[Token]:
        """Tokenize the source code"""
        tokens = []
        while self.pos < len(self.source):
            # Skip whitespace and comments
            while self.peek() and self.peek() in ' \t':
                self.advance()
            
            # Check for EOF
            if self.pos >= len(self.source):
                break
            
            # Check for comments
            if self.peek() == '/' and self.peek(1) == '/':
                # Skip line comment
                while self.peek() and self.peek() != '\n':
                    self.advance()
                # Continue to next token
                continue
            
            # Check for numbers
            if self.is_digit(self.peek()):
                tokens.append(self.read_number())
            
            # Check for strings
            elif self.peek() == '"':
                tokens.append(self.read_string())
            
            # Check for identifiers and keywords
            elif self.is_alpha(self.peek()):
                tokens.append(self.read_identifier())
            
            # Check for punctuation
            elif self.peek() in self.punct:
                tokens.append(self.read_punct())
            
            # If we get here, we have an unrecognized character
            else:
                raise Exception(f"Unrecognized character '{self.peek()}' at line {self.line}, column {self.col}")
        
        # Add EOF token
        tokens.append(Token('EOF', None, self.line, self.col))
        return tokens

def tokenize(source: str) -> List[Token]:
    """Tokenize source code into tokens"""
    lexer = Lexer(source)
    return lexer.tokenize()