class Environment:
    def __init__(self, parent=None):
        self.parent = parent
        self.locals = {}

    def define(self, name, value):
        if name in self.locals:
            raise RuntimeError(f"Variable '{name}' is already defined in this scope")
        self.locals[name] = value

    def assign(self, name, value):
        if name in self.locals:
            self.locals[name] = value
        elif self.parent:
            self.parent.assign(name, value)
        else:
            raise RuntimeError(f"Variable '{name}' is not defined")

    def lookup(self, name):
        if name in self.locals:
            return self.locals[name]
        elif self.parent:
            return self.parent.lookup(name)
        else:
            raise RuntimeError(f"Variable '{name}' is not defined")