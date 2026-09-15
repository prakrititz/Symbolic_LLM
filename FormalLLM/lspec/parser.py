import os
from lark import Lark, Transformer, v_args
from .ast import *

# Load grammar
grammar_path = os.path.join(os.path.dirname(__file__), 'grammar.lark')
with open(grammar_path, 'r') as f:
    grammar = f.read()

lspec_parser = Lark(grammar, start='spec', parser='lalr')

@v_args(inline=True)
class LSpecTransformer(Transformer):
    def t_bool(self): return BoolType()
    def t_nat(self): return NatType()
    def t_int(self): return IntType()
    def t_float(self): return FloatType()
    def t_char(self): return CharType()
    def t_array(self, t): return ArrayType(t)

    def spec(self, pre, post):
        return Spec(pre, post)

    def definition(self, *args):
        # args could be: [expr] or [name, expr] or [param1, param2, expr] or [name, param1, expr]
        # We need to distinguish based on types
        name = None
        params = []
        expr = None
        
        for arg in args:
            if isinstance(arg, str): # Only name is str
                name = arg
            elif isinstance(arg, Param):
                params.append(arg)
            elif isinstance(arg, Expr):
                expr = arg
        
        return Definition(name, params, expr)

    def params(self, name, type_):
        # name is Token
        return Param(str(name), type_)

    def and_expr(self, left, right): return BinaryOp(left, '/\\', right)
    def or_expr(self, left, right): return BinaryOp(left, '\\/', right)
    def not_expr(self, expr): return UnaryOp('~', expr)

    def forall_expr(self, *args):
        params = [a for a in args[:-1] if isinstance(a, Param)]
        expr = args[-1]
        return QuantifiedExpr("forall", params, expr)

    def exists_expr(self, *args):
        params = [a for a in args[:-1] if isinstance(a, Param)]
        expr = args[-1]
        return QuantifiedExpr("exists", params, expr)

    def lt_expr(self, left, right): return BinaryOp(left, '<', right)
    def le_expr(self, left, right): return BinaryOp(left, '<=', right)
    def eq_expr(self, left, right): return BinaryOp(left, '=', right)
    def gt_expr(self, left, right): return BinaryOp(left, '>', right)
    def ge_expr(self, left, right): return BinaryOp(left, '>=', right)
    def neq_expr(self, left, right): return BinaryOp(left, '<>', right)

    def add_expr(self, left, right): return BinaryOp(left, '+', right)
    def sub_expr(self, left, right): return BinaryOp(left, '-', right)
    def mul_expr(self, left, right): return BinaryOp(left, '*', right)
    def div_expr(self, left, right): return BinaryOp(left, '/', right)

    def number(self, n): return Number(str(n))
    def name(self, n): return Variable(str(n)) # Will resolve to Const later if needed
    def true_const(self): return BooleanConst(True)
    def false_const(self): return BooleanConst(False)
    def neg_expr(self, expr): return UnaryOp('-', expr)
    
    def prev_state(self, n): 
        # n is "name0", we want "name"
        return VariablePreviousState(str(n)[:-1])

    def array_select(self, name, index):
        return ArraySelect(str(name), index)

    def array_slice(self, name, start, end):
        return ArraySlice(str(name), start, end)

def resolve_names(node: ASTNode, bound_vars: set):
    """
    Second pass to classify generic Variables into Variables or Consts based on bound variables.
    """
    if isinstance(node, Spec):
        resolve_names(node.precondition, bound_vars.copy())
        resolve_names(node.postcondition, bound_vars.copy())
    elif isinstance(node, Definition):
        new_bound = bound_vars.copy()
        for p in node.params:
            new_bound.add(p.name)
        resolve_names(node.expr, new_bound)
    elif isinstance(node, QuantifiedExpr):
        new_bound = bound_vars.copy()
        for p in node.params:
            new_bound.add(p.name)
        resolve_names(node.expr, new_bound)
    elif isinstance(node, BinaryOp):
        resolve_names(node.left, bound_vars)
        resolve_names(node.right, bound_vars)
    elif isinstance(node, UnaryOp):
        resolve_names(node.expr, bound_vars)
    elif isinstance(node, ArraySelect):
        resolve_names(node.index, bound_vars)
    elif isinstance(node, ArraySlice):
        resolve_names(node.start, bound_vars)
        resolve_names(node.end, bound_vars)
    elif isinstance(node, Variable):
        # This is the core logic: if not bound, it is a Const.
        if node.name not in bound_vars:
            node.__class__ = Const # Dynamically change class (dataclass doesn't mind)

def parse_spec(spec_str: str) -> Spec:
    tree = lspec_parser.parse(spec_str)
    ast = LSpecTransformer().transform(tree)
    resolve_names(ast, set())
    return ast
