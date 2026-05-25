from dataclasses import dataclass
from tinylang.errors import LexError

@dataclass
class Token:
    kind: str        # see kinds below
    value: object    # str for IDENT/STRING/punct, float for NUMBER, None for KEYWORD/EOF
    line: int        # 1-based
    col: int         # 1-based, column where the token starts

def tokenize(source: str) -> list[Token]:
    tokens = []
    i = 0
    line = 1
    col = 1
    n = len(source)

    keywords = {
        "let", "if", "else", "while", "for", "in", "fn", 
        "return", "break", "continue", "true", "false", "nil"
    }

    double_punct = ["==", "!=", "<=", ">=", "&&", "||"]
    single_punct = "+-*/%!=<>()[]{},;:."

    while i < n:
        char = source[i]

        # Whitespace
        if char.isspace():
            if char == '\n':
                line += 1
                col = 1
            else:
                col += 1
            i += 1
            continue

        # Comments
        if char == '/' and i + 1 < n and source[i+1] == '/':
            while i < n and source[i] != '\n':
                i += 1
            continue

        start_line = line
        start_col = col

        # Numbers
        if char.isdigit() or (char == '.' and i + 1 < n and source[i+1].isdigit()):
            num_str = ""
            has_dot = False
            
            if char == '.' and i + 1 < n and source[i+1].isdigit():
                has_dot = True
                num_str += char
                i += 1
                col += 1
            
            while i < n and (source[i].isdigit() or source[i] == '.'):
                if source[i] == '.':
                    if has_dot:
                        break
                    has_dot = True
                num_str += source[i]
                i += 1
                col += 1
            
            if num_str:
                tokens.append(Token("NUMBER", float(num_str), start_line, start_col))
                continue

        # Strings
        if char == '"':
            string_val = ""
            i += 1
            col += 1
            while i < n and source[i] != '"':
                if source[i] == '\n':
                    raise LexError(f"Unterminated string at line {start_line}, col {start_col}", start_line, start_col)
                if source[i] == '\\':
                    if i + 1 < n:
                        esc = source[i+1]
                        if esc == 'n':
                            string_val += '\n'
                        elif esc == 't':
                            string_val += '\t'
                        elif esc == '"':
                            string_val += '"'
                        elif esc == '\\':
                            string_val += '\\'
                        else:
                            string_val += '\\' + esc
                        i += 2
                        col += 2
                    else:
                        raise LexError(f"Unterminated string at line {start_line}, col {start_col}", start_line, start_col)
                else:
                    string_val += source[i]
                    i += 1
                    col += 1
            
            if i < n and source[i] == '"':
                i += 1
                col += 1
                tokens.append(Token("STRING", string_val, start_line, start_col))
            else:
                raise LexError(f"Unterminated string at line {start_line}, col {start_col}", start_line, start_col)
            continue

        # Identifiers and Keywords
        if char.isalpha() or char == '_':
            ident_str = ""
            while i < n and (source[i].isalnum() or source[i] == '_'):
                ident_str += source[i]
                i += 1
                col += 1
            
            if ident_str in keywords:
                tokens.append(Token("KEYWORD", ident_str, start_line, start_col))
            else:
                tokens.append(Token("IDENT", ident_str, start_line, start_col))
            continue

        # Double Punctuation
        found_double = False
        for dp in double_punct:
            if source.startswith(dp, i):
                tokens.append(Token("PUNCT", dp, start_line, start_col))
                i += len(dp)
                col += len(dp)
                found_double = True
                break
        if found_double:
            continue

        # Single Punctuation
        if char in single_punct:
            tokens.append(Token("PUNCT", char, start_line, start_col))
            i += 1
            col += 1
            continue

        raise LexError(f"Unexpected character {char} at line {start_line}, col {start_col}", start_line, start_col)

    tokens.append(Token("EOF", None, line, col))
    return tokens
