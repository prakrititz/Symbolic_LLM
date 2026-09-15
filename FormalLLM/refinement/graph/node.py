from typing import List, Optional
from FormalLLM.lspec.ast import Spec, ASTNode
from FormalLLM.refinement.graph.status import NodeStatus

class RefinementNode:
    def __init__(self, id: str, specification: Spec):
        self.id = id
        self.specification = specification
        self.status = NodeStatus.OPEN
        self.program: Optional[ASTNode] = None
        self.attempts: List[str] = [] # IDs of RefinementAttempts
