from dataclasses import dataclass
from typing import List, Optional, Union

# Types
@dataclass
class Type:
    pass

@dataclass
class BoolType(Type):
    pass

@dataclass
class NatType(Type):
    pass

@dataclass
class IntType(Type):
    pass

@dataclass
class FloatType(Type):
    pass

@dataclass
class CharType(Type):
    pass

@dataclass
class ArrayType(Type):
    element_type: Type

# AST Nodes
@dataclass
class ASTNode:
    pass

@dataclass
class Param(ASTNode):
    name: str
    type_: Type

@dataclass
class Definition(ASTNode):
    name: Optional[str]
    params: List[Param]
    expr: 'Expr'

@dataclass
class Spec(ASTNode):
    precondition: Definition
    postcondition: Definition
    #: Morgan's frame: the names the program may modify (paper section 2.1,
    #: `variables : [pre, post]`). Every other name is *rigid* -- it cannot
    #: change, so what the precondition says about it stays true throughout the
    #: refinement and may be carried into sub-specifications.
    #:
    #: `None` means "unknown", which is treated as "everything may change" and
    #: reproduces the behaviour of specs written before frames existed.
    frame: Optional[List[str]] = None

# Expressions
@dataclass
class Expr(ASTNode):
    pass

@dataclass
class QuantifiedExpr(Expr):
    quantifier: str  # 'forall' or 'exists'
    params: List[Param]
    expr: Expr

@dataclass
class BinaryOp(Expr):
    left: Expr
    op: str # /\, \/, <, <=, =, >, >=, <>, +, -, *, /
    right: Expr

@dataclass
class UnaryOp(Expr):
    op: str # ~, -
    expr: Expr

@dataclass
class Variable(Expr):
    name: str

@dataclass
class Const(Expr):
    name: str

@dataclass
class Number(Expr):
    value: str # Store as string

@dataclass
class BooleanConst(Expr):
    value: bool

@dataclass
class VariablePreviousState(Expr):
    name: str

@dataclass
class ArraySelect(Expr):
    array: str
    index: Expr

@dataclass
class ArraySlice(Expr):
    array: str
    start: Expr
    end: Expr
