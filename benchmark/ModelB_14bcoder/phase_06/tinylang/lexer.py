from dataclasses import dataclass

@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int

# Example usage
print(tokenize('let x=1;'))