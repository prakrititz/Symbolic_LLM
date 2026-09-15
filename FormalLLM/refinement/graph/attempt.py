from typing import Dict, Optional, Any, List
from FormalLLM.refinement.graph.status import AttemptStatus

class RefinementAttempt:
    def __init__(self, id: str, source_node_id: str, law: str, parameters: Dict[str, Any]):
        self.id = id
        self.source_node_id = source_node_id
        self.law = law
        self.parameters = parameters
        self.status = AttemptStatus.PENDING
        self.status_history: List[AttemptStatus] = [self.status]
        
        # e.g. {"then": "N2", "else": "N3"} or {"part1": "N4", "part2": "N5"}
        self.destination_roles: Dict[str, str] = {} 
        
        self.counterexample: Optional[str] = None
        self.error_message: Optional[str] = None

    def update_status(self, new_status: AttemptStatus):
        self.status = new_status
        self.status_history.append(new_status)
