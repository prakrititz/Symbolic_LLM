from dataclasses import dataclass
from typing import List, Union
from FormalLLM.lspec.ast import Expr

@dataclass
class ProgramNode:
    pass

@dataclass
class Assignment(ProgramNode):
    variable: str
    expr: Expr

@dataclass
class Skip(ProgramNode):
    pass

@dataclass
class SequentialComposition(ProgramNode):
    first: ProgramNode
    second: ProgramNode

@dataclass
class IfElse(ProgramNode):
    guard: Expr
    then_branch: ProgramNode
    else_branch: ProgramNode

@dataclass
class While(ProgramNode):
    guard: Expr
    body: ProgramNode
