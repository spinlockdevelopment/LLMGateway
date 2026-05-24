from dataclasses import dataclass
from typing import Any

@dataclass
class Token:
    kind: str        # see kinds below
    value: Any       # str for IDENT/STRING/punct, float for NUMBER, None for KEYWORD/EOF
    line: int        # 1-based
    col: int         # 1-based, column where the token starts

def tokenize(source: str) -> list[Token]:
    tokens = []
    i = 0
    line = 1
    col = 1

    keywords = {
        "let", "if", "else", "while", "for", "in", "fn", 
        "return", "break", "continue", "true", "false", "nil"
    }

    multi_punct = ["==", "!=", "<=", ">=", "&&", "||"]
    single_punct = set("+-*/%!=<>() {}[] , ; : .".replace(" ", ""))

    while i < len(source):
        char = source[i]

        # Skip whitespace
        if char.isspace():
            if char == '\n':
                line += 1
                col = 1
            else:
                col += 1
            i += 1
            continue

        # Skip comments
        if char == '/' and i + 1 < len(source) and source[i+1] == '/':
            while i < len(source) and source[i] != '\n':
                i += 1
            continue

        start_line = line
        start_col = col

        # 1. Multi-character punctuation
        found_multi = False
        for p in multi_punct:
            if source.startswith(p, i):
                tokens.append(Token("PUNCT", p, start_line, start_col))
                i += len(p)
                col += len(p)
                found_multi = True
                break
        if found_multi:
            continue

        # 2. Numbers
        if char.isdigit() or (char == '.' and i + 1 < len(source) and source[i+1].isdigit()):
            num_start = i
            has_dot = False
            if char == '.':
                has_dot = True
                i += 1
                col += 1
            
            while i < len(source) and (source[i].isdigit() or source[i] == '.'):
                if source[i] == '.':
                    if has_dot:
                        break
                    has_dot = True
                i += 1
                col += 1
            
            num_str = source[num_start:i]
            try:
                num_val = float(num_str)
                tokens.append(Token("NUMBER", num_val, start_line, start_col))
            except ValueError:
                raise Exception(f"Invalid number '{num_str}' at line {start_line}, col {start_col}")
            continue

        # 3. Strings
        if char == '"':
            i += 1
            col += 1
            string_val = ""
            while i < len(source) and source[i] != '"':
                if source[i] == '\n':
                    raise Exception(f"Unterminated string at line {start_line}, col {start_col}")
                
                if source[i] == '\\':
                    if i + 1 < len(source):
                        esc = source[i+1]
                        if esc == 'n':
                            string_val += '\n'
                            i += 2
                            col += 2
                        elif esc == 't':
                            string_val += '\t'
                            i += 2
                            col += 2
                        elif esc == '"':
                            string_val += '"'
                            i += 2
                            col += 2
                        elif esc == '\\':
                            string_val += '\\'
                            i += 2
                            col += 2
                        else:
                            # For other escapes, just treat as literal backslash and the char
                            string_val += '\\'
                            i += 1
                            col += 1
                        continue
                    else:
                        raise Exception(f"Unterminated string at line {start_line}, col {start_col}")
                
                string_val += source[i]
                i += 1
                col += 1
            
            if i >= len(source):
                raise Exception(f"Unterminated string at line {start_line}, col {start_col}")
            
            # Now at the closing quote
            i += 1
            col += 1
            tokens.append(Token("STRING", string_val, start_line, start_col))
            continue

        # 4. Single-character punctuation
        if char in single_punct:
            tokens.append(Token("PUNCT", char, start_line, start_col))
            i += 1
            col += 1
            continue

        # 5. Identifiers and Keywords
        if char.isalpha() or char == '_':
            ident_start = i
            while i < len(source) and (source[i].isalnum() or source[i] == '_'):
                i += 1
            ident_text = source[ident_start:i]
            
            if ident_text in keywords:
                tokens.append(Token("KEYWORD", ident_text, start_line, start_col))
            else:
                tokens.append(Token("IDENT", ident_text, start_line, start_col))
            
            col += (i - ident_start)
            continue

        # If we reach here, it is an unrecognized character
        raise Exception(f"Unrecognized character '{char}' at line {line}, col {col}")

    tokens.append(Token("EOF", None, line, col))
    return tokens

