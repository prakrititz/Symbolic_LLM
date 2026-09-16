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
