from dataclasses import dataclass
from typing import List

@dataclass
class Token:
    kind: str
    value: object
    line: int
    col: int

def tokenize(source: str) -> List[Token]:
    """Tokenize tinylang source into a list of tokens."""
    tokens = []
    pos = 0
    line = 1
    col = 1
    
    def peek() -> str:
        if pos >= len(source):
            return ''
        return source[pos]
    
    def advance() -> str:
        nonlocal pos, line, col
        if pos >= len(source):
            return ''
        char = source[pos]
        pos += 1
        if char == '\n':
            line += 1
            col = 1
        else:
            col += 1
        return char
    
    def skip_whitespace_and_comments():
        nonlocal pos, line, col
        while True:
            char = peek()
            if char == ' ' or char == '\t' or char == '\r' or char == '\n':
                advance()
            elif char == '/':
                # Check for comment
                advance()
                if peek() == '/':
                    # Skip comment
                    while peek() != '\n' and peek() != '':
                        advance()
                    # Skip the newline
                    if peek() == '\n':
                        advance()
                else:
                    # Not a comment, put back the /
                    pos -= 1
                    col -= 1
                    break
            else:
                break
    
    def read_number() -> Token:
        nonlocal pos, line, col
        start_pos = pos
        start_col = col
        
        # Read integer part
        while peek().isdigit():
            advance()
        
        # Check for decimal point
        if peek() == '.':
            advance()
            # Read fractional part
            while peek().isdigit():
                advance()
        
        # Get the value
        value_str = source[start_pos:pos]
        value = float(value_str)
        
        return Token('NUMBER', value, line, start_col)
    
    def read_string() -> Token:
        nonlocal pos, line, col
        start_pos = pos
        start_col = col
        advance()  # Skip opening quote
        
        # Read string content
        while True:
            char = peek()
            if char == '':
                # Unterminated string
                raise Exception(f"Unterminated string at line {line}, column {col}")
            elif char == '\n':
                # String cannot span multiple lines
                raise Exception(f"String cannot span multiple lines at line {line}, column {col}")
            elif char == '"':
                advance()  # Skip closing quote
                # Get the value (without quotes)
                value_str = source[start_pos+1:pos-1]
                # Process escape sequences
                value_str = value_str.encode().decode('unicode_escape')
                return Token('STRING', value_str, line, start_col)
            elif char == '\\':
                advance()  # Skip backslash
                # Skip the escaped character
                advance()
            else:
                advance()
    
    def read_identifier_or_keyword() -> Token:
        nonlocal pos, line, col
        start_pos = pos
        start_col = col
        
        # Read identifier
        while peek().isalnum() or peek() == '_':
            advance()
        
        value_str = source[start_pos:pos]
        
        # Check if it's a keyword
        keywords = {
            'let', 'if', 'else', 'while', 'for', 'in', 'fn', 'return',
            'break', 'continue', 'true', 'false', 'nil'
        }
        
        if value_str in keywords:
            return Token('KEYWORD', value_str, line, start_col)
        else:
            return Token('IDENT', value_str, line, start_col)
    
    def read_punctuation() -> Token:
        nonlocal pos, line, col
        start_pos = pos
        start_col = col
        
        char = advance()
        
        # Check for multi-character operators
        if char == '=' and peek() == '=':
            advance()  # consume the second '='
            return Token('PUNCT', '==', line, start_col)
        elif char == '!' and peek() == '=':
            advance()  # consume the second '='
            return Token('PUNCT', '!=', line, start_col)
        elif char == '<' and peek() == '=':
            advance()  # consume the second '='
            return Token('PUNCT', '<=', line, start_col)
        elif char == '>' and peek() == '=':
            advance()  # consume the second '='
            return Token('PUNCT', '>=', line, start_col)
        elif char == '&' and peek() == '&':
            advance()  # consume the second '&'
            return Token('PUNCT', '&&', line, start_col)
        elif char == '|' and peek() == '|':
            advance()  # consume the second '|'
            return Token('PUNCT', '||', line, start_col)
        elif char == '{':
            return Token('LEFT_BRACE', '{', line, start_col)
        elif char == '}':
            return Token('RIGHT_BRACE', '}', line, start_col)
        elif char == '[':
            return Token('LEFT_BRACKET', '[', line, start_col)
        elif char == ']':
            return Token('RIGHT_BRACKET', ']', line, start_col)
        elif char == '(':
            return Token('LEFT_PAREN', '(', line, start_col)
        elif char == ')':
            return Token('RIGHT_PAREN', ')', line, start_col)
        
        return Token('PUNCT', char, line, start_col)
    
    # Main tokenization loop
    while pos < len(source):
        skip_whitespace_and_comments()
        
        if pos >= len(source):
            break
            
        char = peek()
        
        if char.isdigit():
            tokens.append(read_number())
        elif char == '"':
            tokens.append(read_string())
        elif char.isalpha() or char == '_':
            tokens.append(read_identifier_or_keyword())
        elif char in '+-*/%(){}[];,=:<>!&|.,':
            tokens.append(read_punctuation())
        else:
            # Unknown character
            raise Exception(f"Unexpected character '{char}' at line {line}, column {col}")
    
    # Add EOF token
    tokens.append(Token('EOF', None, line, col))
    
    return tokens