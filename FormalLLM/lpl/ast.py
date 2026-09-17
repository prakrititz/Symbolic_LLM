from dataclasses import dataclass
from typing import List, Union
from FormalLLM.lspec.ast import Expr, Spec, ASTNode

@dataclass
class ProgramNode(ASTNode):
    pass

MixNode = Union[ProgramNode, Spec]

@dataclass
class Assignment(ProgramNode):
    variable: str
    expr: Expr

@dataclass
class Skip(ProgramNode):
    pass

@dataclass
class SequentialComposition(ProgramNode):
    first: MixNode
    second: MixNode

@dataclass
class IfElse(ProgramNode):
    guard: Expr
    then_branch: MixNode
    else_branch: MixNode

@dataclass
class While(ProgramNode):
    guard: Expr
    body: MixNode


# --- Traversal registration ----------------------------------------------
# L_pl nodes appear inside mixed programs (L_mix) and so are walked by the same
# generic traversals as L_spec. Registering here rather than in lspec/walk.py
# keeps the import direction lpl -> lspec.
#
# `Assignment.variable` is registered ATOM, not NAME: it is a write target, not
# a read of the variable, so free-variable collection must not report it.
from FormalLLM.lspec import walk as _walk

_walk.register(Assignment, (("variable", _walk.ATOM), ("expr", _walk.NODE)))
_walk.register(Skip, ())
_walk.register(SequentialComposition, (("first", _walk.NODE), ("second", _walk.NODE)))
_walk.register(IfElse, (("guard", _walk.NODE),
                        ("then_branch", _walk.NODE),
                        ("else_branch", _walk.NODE)))
_walk.register(While, (("guard", _walk.NODE), ("body", _walk.NODE)))
