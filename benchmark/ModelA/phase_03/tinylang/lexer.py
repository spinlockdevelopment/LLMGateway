from dataclasses import dataclass
from typing import List


@dataclass
class Token:
    kind: str
    value: object
    line: int
    col: int


def tokenize(source: str) -> List[Token]:
    """Tokenize tinylang source code into a list of tokens."""
    tokens = []
    line = 1
    col = 1
    i = 0
    
    keywords = {
        'let', 'if', 'else', 'while', 'for', 'in', 'fn', 'return', 
        'break', 'continue', 'true', 'false', 'nil'
    }
    
    # Multi-character punctuation must be checked first
    multi_punct = {
        '==', '!=', '<=', '>=', '&&', '||'
    }
    
    single_punct = {
        '+', '-', '*', '/', '%', '!', '=', '(', ')', '{', '}', 
        '[', ']', ',', ';', ':', '.', '<', '>'
    }
    
    def advance():
        nonlocal i, line, col
        if i < len(source) and source[i] == '\n':
            line += 1
            col = 1
        else:
            col += 1
        i += 1
    
    def peek(offset=0):
        pos = i + offset
        return source[pos] if pos < len(source) else '\0'
    
    def current_char():
        return peek(0)
    
    def next_char():
        return peek(1)
    
    while i < len(source):
        start_line = line
        start_col = col
        ch = current_char()
        
        # Skip whitespace
        if ch.isspace():
            advance()
            continue
        
        # Skip comments
        if ch == '/' and next_char() == '/':
            # Skip to end of line
            while i < len(source) and current_char() != '\n':
                advance()
            continue
        
        # Numbers
        if ch.isdigit() or (ch == '.' and next_char().isdigit()):
            num_str = ''
            has_dot = False
            
            while i < len(source):
                ch = current_char()
                if ch.isdigit():
                    num_str += ch
                    advance()
                elif ch == '.' and not has_dot:
                    has_dot = True
                    num_str += ch
                    advance()
                else:
                    break
            
            tokens.append(Token('NUMBER', float(num_str), start_line, start_col))
            continue
        
        # Strings
        if ch == '"':
            advance()  # Skip opening quote
            string_val = ''
            
            while i < len(source):
                ch = current_char()
                
                if ch == '"':
                    advance()  # Skip closing quote
                    break
                elif ch == '\n':
                    raise Exception(f"Unterminated string at line {start_line}, col {start_col}")
                elif ch == '\\':
                    advance()
                    if i >= len(source):
                        raise Exception(f"Unterminated string at line {start_line}, col {start_col}")
                    
                    escape_ch = current_char()
                    if escape_ch == 'n':
                        string_val += '\n'
                    elif escape_ch == 't':
                        string_val += '\t'
                    elif escape_ch == '"':
                        string_val += '"'
                    elif escape_ch == '\\':
                        string_val += '\\'
                    else:
                        # For other escapes, just include the character as-is
                        string_val += escape_ch
                    advance()
                else:
                    string_val += ch
                    advance()
            else:
                # Reached EOF without closing quote
                raise Exception(f"Unterminated string at line {start_line}, col {start_col}")
            
            tokens.append(Token('STRING', string_val, start_line, start_col))
            continue
        
        # Multi-character punctuation
        two_char = ch + next_char()
        if two_char in multi_punct:
            tokens.append(Token('PUNCT', two_char, start_line, start_col))
            advance()
            advance()
            continue
        
        # Single-character punctuation
        if ch in single_punct:
            tokens.append(Token('PUNCT', ch, start_line, start_col))
            advance()
            continue
        
        # Identifiers and keywords
        if ch.isalpha() or ch == '_':
            ident = ''
            while i < len(source):
                ch = current_char()
                if ch.isalnum() or ch == '_':
                    ident += ch
                    advance()
                else:
                    break
            
            if ident in keywords:
                tokens.append(Token('KEYWORD', ident, start_line, start_col))
            else:
                tokens.append(Token('IDENT', ident, start_line, start_col))
            continue
        
        # Unrecognized character
        raise Exception(f"Unrecognized character '{ch}' at line {line}, col {col}")
    
    # Add EOF token
    tokens.append(Token('EOF', None, line, col))
    return tokens