from dataclasses import dataclass, field
from typing import List, Optional, Any, Union
from FormalLLM.lspec.ast import Spec
from FormalLLM.lpl.ast import ProgramNode

@dataclass
class RefinementNode:
    specification: Spec
    parent: Optional['RefinementNode'] = None
    children: List['RefinementNode'] = field(default_factory=list)
    refinement_operation: Optional[str] = None
    program: Optional[ProgramNode] = None # The resulting program if it's a leaf node that refined to code

    def add_child(self, spec: Spec, operation: str) -> 'RefinementNode':
        child = RefinementNode(specification=spec, parent=self, refinement_operation=operation)
        self.children.append(child)
        return child
