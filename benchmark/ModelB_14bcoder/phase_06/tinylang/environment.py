from dataclasses import dataclass

class Environment:
    def __init__(self, parent=None):
        self.parent = parent
        self.locals = {}

    def define(self, name, value):
        if name in self.locals:
            raise RuntimeError(f'Redeclaration of variable \