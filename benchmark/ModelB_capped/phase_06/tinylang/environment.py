class Environment:
    def __init__(self, parent=None):
        self.parent = parent
        self.locals = {}
    
    def define(self, name, value):
        """Define a variable in the current environment."""
        self.locals[name] = value
    
    def assign(self, name, value):
        """Assign a value to a variable, looking up the scope chain."""
        env = self
        while env is not None:
            if name in env.locals:
                env.locals[name] = value
                return
            env = env.parent
        raise RuntimeError(f"Undefined variable '{name}'")
    
    def get(self, name):
        """Get a variable's value, looking up the scope chain."""
        env = self
        while env is not None:
            if name in env.locals:
                return env.locals[name]
            env = env.parent
        raise RuntimeError(f"Undefined variable '{name}'")
    
    def has(self, name):
        """Check if a variable is defined in this environment or any parent."""
        env = self
        while env is not None:
            if name in env.locals:
                return True
            env = env.parent
        return False