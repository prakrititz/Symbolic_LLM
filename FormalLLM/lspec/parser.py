import os
from lark import Lark, Transformer, v_args
from . import walk
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

    def spec(self, *args):
        # `Frame:` is optional, so the frame list may or may not be present.
        frame = args[0] if isinstance(args[0], list) else None
        pre, post = args[-2], args[-1]
        return Spec(pre, post, frame)

    def frame(self, *entries):
        return list(entries)

    def frame_var(self, name, type_=None):
        # An untyped frame variable is still usable -- it just gives the SMT
        # backend no sort to declare, so the name falls back to Real. Declaring
        # `Frame: q:int` is what keeps an integer program from being reasoned
        # about over the rationals.
        return Param(str(name), type_)

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

def resolve_names(node: ASTNode, bound_vars: set) -> ASTNode:
    """Classify each generic ``Variable`` as bound (``Variable``) or free (``Const``).

    A name is a ``Const`` exactly when no enclosing ``Definition`` params list
    or quantifier binds it. Structure comes from :mod:`lspec.walk`, so a node
    type added later is scoped correctly without touching this function.

    This returns a rebuilt tree. The previous version walked the AST for effect
    and reclassified in place via ``node.__class__ = Const``, which mutates the
    object every alias of it can see -- including nodes shared into an already
    constructed spec -- and depends on ``Variable`` and ``Const`` happening to
    have identical layouts.
    """
    inner = bound_vars | {p.name for p in walk.binders_of(node)}

    if isinstance(node, Variable) and node.name not in bound_vars:
        return Const(node.name)

    overrides = {}
    for attr, kind in walk.schema_of(node):
        value = getattr(node, attr)
        if kind == walk.NODE:
            overrides[attr] = resolve_names(value, inner)
        elif kind == walk.NODES:
            overrides[attr] = [resolve_names(c, inner) for c in value]
    return walk.rebuild(node, **overrides)

def parse_spec(spec_str: str) -> Spec:
    tree = lspec_parser.parse(spec_str)
    ast = LSpecTransformer().transform(tree)
    return resolve_names(ast, set())
