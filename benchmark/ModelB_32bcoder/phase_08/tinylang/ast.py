class Node:
    pass

class Program(Node):
    def __init__(self, statements):
        self.statements = statements

    def __repr__(self):
        return f"Program({self.statements})"

class FnDecl(Node):
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body

    def __repr__(self):
        return f"FnDecl({self.name}, {self.params}, {self.body})"

class FnLit(Node):
    def __init__(self, params, body):
        self.params = params
        self.body = body

    def __repr__(self):
        return f"FnLit({self.params}, {self.body})"

class Call(Node):
    def __init__(self, func, args):
        self.func = func
        self.args = args

    def __repr__(self):
        return f"Call({self.func}, {self.args})"

class ReturnStmt(Node):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"ReturnStmt({self.value})"

class ListLit(Node):
    def __init__(self, elements):
        self.elements = elements

    def __repr__(self):
        return f"ListLit({self.elements})"

class Index(Node):
    def __init__(self, target, index):
        self.target = target
        self.index = index

    def __repr__(self):
        return f"Index({self.target}, {self.index})"

class Assign(Node):
    def __init__(self, target, value):
        self.target = target
        self.value = value

    def __repr__(self):
        return f"Assign({self.target}, {self.value})"
