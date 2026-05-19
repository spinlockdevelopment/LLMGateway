from dataclasses import dataclass

@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int

@dataclass
class ListLit:
    elements: list

@dataclass
class Index:
    target: any
    index: any

@dataclass
class Assign:
    target: any
    value: any
