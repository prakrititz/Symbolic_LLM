from typing import Callable, Dict, List, Any, Optional, Union

from FormalLLM.lspec.ast import Spec, ASTNode
from FormalLLM.lpl.ast import MixNode
from FormalLLM.refinement.graph.status import NodeStatus, AttemptStatus
from FormalLLM.refinement.graph.node import RefinementNode
from FormalLLM.refinement.graph.attempt import RefinementAttempt
from FormalLLM.refinement.laws.registry import law_named


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

    # --- structure queries -------------------------------------------------

    def _inbound_map(self) -> Dict[str, RefinementAttempt]:
        """Child node id -> the attempt that produced it.

        Built on demand rather than maintained incrementally because callers
        (the refiner, the tests, ``benchmarks/manual_sqrt.py``) assign
        ``attempt.destination_roles`` directly; an incrementally maintained
        index would silently go stale behind those writes. Building it once per
        top-level query still replaces the previous full scan of every attempt
        at every level of the recursion.
        """
        inbound: Dict[str, RefinementAttempt] = {}
        for attempt in self.attempts.values():
            for child_id in attempt.destination_roles.values():
                inbound[child_id] = attempt
        return inbound

    def accepted_attempt(self, node_id: str) -> Optional[RefinementAttempt]:
        """The one accepted attempt at ``node_id``, if any."""
        for attempt_id in self.nodes[node_id].attempts:
            attempt = self.attempts[attempt_id]
            if attempt.status == AttemptStatus.ACCEPTED:
                return attempt
        return None

    def is_live(self, node_id: str,
                _inbound: Optional[Dict[str, RefinementAttempt]] = None) -> bool:
        """True if ``node_id`` is reachable from the root through accepted steps.

        A node whose inbound attempt was later rejected or aborted is dead: it
        still exists in the graph as a record of what was tried, but it is no
        longer part of the refinement being built.
        """
        inbound = self._inbound_map() if _inbound is None else _inbound

        while node_id != self.root_id:
            attempt = inbound.get(node_id)
            if attempt is None or attempt.status != AttemptStatus.ACCEPTED:
                return False
            node_id = attempt.source_node_id
        return True

    def get_frontier(self) -> List[RefinementNode]:
        inbound = self._inbound_map()
        return [node for node in self.nodes.values()
                if node.status == NodeStatus.OPEN and self.is_live(node.id, inbound)]

    def is_complete(self, node_id: str,
                    _inbound: Optional[Dict[str, RefinementAttempt]] = None) -> bool:
        inbound = self._inbound_map() if _inbound is None else _inbound

        if not self.is_live(node_id, inbound):
            return False

        node = self.nodes[node_id]
        if node.status == NodeStatus.REFINED:
            return True
        if node.status != NodeStatus.DELEGATED:
            return False

        accepted_attempt = self.accepted_attempt(node_id)
        if not accepted_attempt:
            return False

        return all(self.is_complete(child_id, inbound)
                   for child_id in accepted_attempt.destination_roles.values())

    # --- program reconstruction -------------------------------------------

    def _assemble(self, node_id: str,
                  on_unrefined: Callable[[RefinementNode], MixNode]) -> MixNode:
        """Fold the accepted sub-tree at ``node_id`` into a program.

        Each law assembles its own node via ``build_program``, so adding a law
        needs no change here. Both reconstruction entry points share this fold
        and differ only in what they do at a node that is not refined yet.
        """
        node = self.nodes[node_id]
        if node.status == NodeStatus.REFINED:
            return node.program

        accepted_attempt = self.accepted_attempt(node_id)
        if accepted_attempt is None:
            return on_unrefined(node)

        children = {
            role: self._assemble(child_id, on_unrefined)
            for role, child_id in accepted_attempt.destination_roles.items()
        }
        law = law_named(accepted_attempt.law)
        return law.build_program(accepted_attempt.parameters, children)

    def reconstruct_mixed_program(self, node_id: Optional[str] = None) -> Union[ASTNode, Spec]:
        """The L_mix program so far: code where refined, specifications elsewhere."""
        if node_id is None:
            node_id = self.root_id
        return self._assemble(node_id, lambda node: node.specification)

    def reconstruct_program(self, node_id: Optional[str] = None) -> ASTNode:
        """The finished L_pl program, or raise if any leaf is still a specification."""
        if node_id is None:
            node_id = self.root_id

        if not self.is_complete(node_id):
            raise IncompleteRefinementError(f"Refinement graph at node {node_id} is incomplete.")

        def unrefined(node: RefinementNode) -> MixNode:
            raise IncompleteRefinementError(
                f"node {node.id} has no accepted refinement"
            )

        return self._assemble(node_id, unrefined)
