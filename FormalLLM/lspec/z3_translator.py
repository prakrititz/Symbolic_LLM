import z3
from .ast import *

class Z3Translator:
    def __init__(self):
        self.env = {} # mapping from variable/const name to z3 expression

    def sort_of(self, type_):
        if isinstance(type_, BoolType):
            return z3.BoolSort()
        if isinstance(type_, (IntType, NatType)):
            return z3.IntSort()
        if isinstance(type_, FloatType):
            return z3.RealSort()
        return None

    def declare_params(self, params):
        """Seed the environment with declared parameters (and their primed
        previous-state twins) so that names are given their declared sort."""
        for p in params or []:
            if isinstance(p.type_, ArrayType):
                self.env[p.name] = z3.Array(p.name, z3.IntSort(), z3.IntSort())
                continue
            sort = self.sort_of(p.type_)
            if sort is None:
                continue
            self.env[p.name] = z3.Const(p.name, sort)
            self.env[f"{p.name}0"] = z3.Const(f"{p.name}0", sort)

    def translate(self, node: ASTNode):
        if isinstance(node, Spec):
            # A Spec is a pair of precondition and postcondition
            pre = self.translate(node.precondition)
            post = self.translate(node.postcondition)
            return z3.And(pre, post)
            
        elif isinstance(node, Definition):
            # Translate params into z3 variables and add them to env
            old_env = self.env.copy()
            for p in node.params:
                if isinstance(p.type_, BoolType):
                    self.env[p.name] = z3.Bool(p.name)
                elif isinstance(p.type_, IntType) or isinstance(p.type_, NatType):
                    self.env[p.name] = z3.Int(p.name)
                elif isinstance(p.type_, FloatType):
                    self.env[p.name] = z3.Real(p.name) # Z3 uses Real for float
                elif isinstance(p.type_, ArrayType):
                    # Simplified: Array(Int, Int)
                    self.env[p.name] = z3.Array(p.name, z3.IntSort(), z3.IntSort())
            
            expr = self.translate(node.expr)
            self.env = old_env
            return expr

        elif isinstance(node, QuantifiedExpr):
            old_env = self.env.copy()
            z3_vars = []
            for p in node.params:
                if isinstance(p.type_, BoolType):
                    var = z3.Bool(p.name)
                elif isinstance(p.type_, IntType) or isinstance(p.type_, NatType):
                    var = z3.Int(p.name)
                elif isinstance(p.type_, FloatType):
                    var = z3.Real(p.name)
                else:
                    var = z3.Int(p.name) # Default fallback
                self.env[p.name] = var
                z3_vars.append(var)
                
            body = self.translate(node.expr)
            self.env = old_env
            
            if node.quantifier == 'forall':
                return z3.ForAll(z3_vars, body)
            else:
                return z3.Exists(z3_vars, body)

        elif isinstance(node, BinaryOp):
            l = self.translate(node.left)
            r = self.translate(node.right)
            if node.op == '/\\': return z3.And(l, r)
            if node.op == '\\/': return z3.Or(l, r)
            if node.op == '<': return l < r
            if node.op == '<=': return l <= r
            if node.op == '=': return l == r
            if node.op == '>': return l > r
            if node.op == '>=': return l >= r
            if node.op == '<>': return l != r
            if node.op == '+': return l + r
            if node.op == '-': return l - r
            if node.op == '*': return l * r
            if node.op == '/': return l / r

        elif isinstance(node, UnaryOp):
            e = self.translate(node.expr)
            if node.op == '~': return z3.Not(e)
            if node.op == '-': return -e

        elif isinstance(node, Variable) or isinstance(node, Const):
            if node.name in self.env:
                return self.env[node.name]
            # If not in env, create a new uninterpreted constant
            # We assume it's a Real by default if untyped context, but ideally we'd infer types.
            # For this MVP, we create a Real to match float examples.
            var = z3.Real(node.name) 
            self.env[node.name] = var
            return var

        elif isinstance(node, VariablePreviousState):
            var_name = f"{node.name}0"
            if var_name in self.env:
                return self.env[var_name]
            var = z3.Real(var_name)
            self.env[var_name] = var
            return var

        elif isinstance(node, Number):
            if '.' in node.value:
                return z3.RealVal(node.value)
            return z3.IntVal(node.value)

        elif isinstance(node, BooleanConst):
            return z3.BoolVal(node.value)

        elif isinstance(node, ArraySelect):
            arr = self.translate(Variable(node.array)) 
            idx = self.translate(node.index)
            return z3.Select(arr, idx)
            
        elif isinstance(node, ArraySlice):
            raise NotImplementedError("Z3 does not have native Array slice. Requires axioms.")
            
        raise ValueError(f"Unknown AST node type: {type(node)}")
