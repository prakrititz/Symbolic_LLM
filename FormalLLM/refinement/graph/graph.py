from typing import Dict, List, Any, Optional
from FormalLLM.lspec.ast import Spec, ASTNode
from FormalLLM.lpl.ast import SequentialComposition, IfElse, While
from FormalLLM.refinement.graph.status import NodeStatus, AttemptStatus
from FormalLLM.refinement.graph.node import RefinementNode
from FormalLLM.refinement.graph.attempt import RefinementAttempt

class IncompleteRefinementError(Exception):
    pass

class RefinementGraph:
    def __init__(self, root_spec: Spec):
        self.nodes: Dict[str, RefinementNode] = {}
        self.attempts: Dict[str, RefinementAttempt] = {}
        self.node_counter = 0
        self.attempt_counter = 0
        
        self.root_id = self.create_node(root_spec)

    def create_node(self, spec: Spec) -> str:
        node_id = f"N{self.node_counter}"
        self.node_counter += 1
        self.nodes[node_id] = RefinementNode(node_id, spec)
        return node_id

    def record_attempt(self, source_id: str, law: str, parameters: Dict[str, Any]) -> str:
        attempt_id = f"A{self.attempt_counter}"
        self.attempt_counter += 1
        
        attempt = RefinementAttempt(attempt_id, source_id, law, parameters)
        self.attempts[attempt_id] = attempt
        
        source_node = self.nodes[source_id]
        source_node.attempts.append(attempt_id)
        if source_node.status == NodeStatus.OPEN:
            source_node.status = NodeStatus.REFINING
            
        return attempt_id

    def is_live(self, node_id: str) -> bool:
        if node_id == self.root_id:
            return True
            
        # Find the inbound attempt for this node
        for attempt in self.attempts.values():
            if node_id in attempt.destination_roles.values():
                if attempt.status == AttemptStatus.ACCEPTED:
                    return self.is_live(attempt.source_node_id)
                return False
        return False

    def get_frontier(self) -> List[RefinementNode]:
        frontier = []
        for node in self.nodes.values():
            if node.status == NodeStatus.OPEN and self.is_live(node.id):
                frontier.append(node)
        return frontier

    def is_complete(self, node_id: str) -> bool:
        if not self.is_live(node_id):
            return False
            
        node = self.nodes[node_id]
        if node.status == NodeStatus.REFINED:
            return True
        if node.status != NodeStatus.DELEGATED:
            return False
            
        # Find the accepted attempt
        accepted_attempt = None
        for attempt_id in node.attempts:
            attempt = self.attempts[attempt_id]
            if attempt.status == AttemptStatus.ACCEPTED:
                accepted_attempt = attempt
                break
                
        if not accepted_attempt:
            return False
            
        # All live destinations must be complete
        for child_id in accepted_attempt.destination_roles.values():
            if not self.is_complete(child_id):
                return False
        return True

    def reconstruct_program(self, node_id: Optional[str] = None) -> ASTNode:
        if node_id is None:
            node_id = self.root_id
            
        if not self.is_complete(node_id):
            raise IncompleteRefinementError(f"Refinement graph at node {node_id} is incomplete.")
            
        node = self.nodes[node_id]
        if node.status == NodeStatus.REFINED:
            return node.program
            
        # It's DELEGATED, find the accepted attempt
        accepted_attempt = None
        for attempt_id in node.attempts:
            attempt = self.attempts[attempt_id]
            if attempt.status == AttemptStatus.ACCEPTED:
                accepted_attempt = attempt
                break
                
        law = accepted_attempt.law
        roles = accepted_attempt.destination_roles
        
        if law == "sequential":
            prog1 = self.reconstruct_program(roles["part1"])
            prog2 = self.reconstruct_program(roles["part2"])
            return SequentialComposition(prog1, prog2)
            
        elif law == "alternation":
            guard = accepted_attempt.parameters["guard"]
            then_prog = self.reconstruct_program(roles["then"])
            else_prog = self.reconstruct_program(roles["else"])
            return IfElse(guard, then_prog, else_prog)
            
        elif law == "iteration":
            guard = accepted_attempt.parameters["guard"]
            init_prog = self.reconstruct_program(roles["init"])
            body_prog = self.reconstruct_program(roles["body"])
            return SequentialComposition(init_prog, While(guard, body_prog))
            
        raise ValueError(f"Cannot reconstruct unknown recursive law: {law}")
