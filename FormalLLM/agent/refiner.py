from typing import List, Optional, Dict
from FormalLLM.refinement.engine import RefinementEngine, VerificationError
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import AttemptStatus, NodeStatus
from FormalLLM.llm.provider import LLMProvider
from FormalLLM.llm.prompts import generate_state_prompt, to_string
from FormalLLM.llm.parser import parse_llm_response

class RefinementExhausted(Exception):
    pass


def spec_key(spec) -> str:
    """Canonical string form of a specification, used for progress checking."""
    return to_string(spec)

class AutomatedRefiner:
    def __init__(self, engine: RefinementEngine, llm: LLMProvider,
                 max_retries: int = 5, max_depth: int = 6):
        self.engine = engine
        self.llm = llm
        self.max_retries = max_retries
        # Structural laws that emit no proof obligations (alternation, sequential)
        # can always be applied again, each time producing a syntactically new
        # sub-specification. Nothing in the calculus bounds that descent, so the
        # search needs an explicit depth limit; past it, only terminal laws
        # (assignment / skip) may be used.
        self.max_depth = max_depth
        self.blacklisted_laws_per_node: Dict[str, List[str]] = {}
        # Derive dynamically so this can't drift when new laws are registered
        self.TOTAL_LAWS = len(engine.laws)
        # How many times each (node, law) pair has been tried with parameters
        # that failed somewhere below. A law is only abandoned once several
        # *different* parameter choices have failed -- see refine_node.
        self.param_failures_per_node: Dict[tuple, int] = {}
        # Why the most recently abandoned subtree failed, so the parent can be
        # told something more useful than "try a different approach".
        self.last_subtree_failure: Optional[str] = None
        # A law whose parameters failed below is given this many chances to be
        # re-proposed with better parameters before it is blacklisted outright.
        self.max_param_attempts = 2

    def refine_node(self, graph: RefinementGraph, node_id: str,
                    ancestry: tuple = ()) -> bool:
        """
        Recursively attempts to refine a node in the graph.
        Returns True if successful, False if it needs to fallback to parent.
        Raises RefinementExhausted if it's the root node and all attempts are exhausted.

        `ancestry` carries the canonical spec strings of this node's ancestors so
        that a step which reproduces an ancestor specification can be rejected as
        making no progress. Without it, identity-refinable laws such as
        strengthen_post (with R = Q) or weaken_pre (with R = P) discharge their
        obligations trivially and the search descends forever.
        """
        node = graph.nodes[node_id]
        path = ancestry + (spec_key(node.specification),)

        if node_id not in self.blacklisted_laws_per_node:
            self.blacklisted_laws_per_node[node_id] = []

        retry_context = ""
        
        for attempt in range(self.max_retries):
            # Check if all possible laws are blacklisted
            if len(self.blacklisted_laws_per_node[node_id]) >= self.TOTAL_LAWS:
                break
                
            # 1. Prompt LLM
            prompt = generate_state_prompt(
                node, 
                blacklisted_laws=self.blacklisted_laws_per_node[node_id],
                retry_context=retry_context,
                available_laws=list(self.engine.laws)
            )
            response = self.llm.generate(prompt)
            
            try:
                # 2. Parse output
                law, parameters = parse_llm_response(response)
                
                # Check blacklist
                if law in self.blacklisted_laws_per_node[node_id]:
                    retry_context = f"Attempted to use blacklisted law: {law}."
                    continue
                    
                # 3. Create attempt in graph
                attempt_id = graph.record_attempt(node_id, law, parameters)
                attempt_obj = graph.attempts[attempt_id]
                
                # 4. Apply engine
                try:
                    result = self.engine.apply(node.specification, law, parameters)
                    
                    # 5. Handle Terminal vs Recursive success branches
                    if result.program is not None:
                        # Terminal branch (e.g. Assignment, Skip)
                        attempt_obj.update_status(AttemptStatus.ACCEPTED)
                        node.status = NodeStatus.REFINED
                        node.program = result.program
                        return True
                    else:
                        # Progress guard: a refinement step must yield strictly
                        # new sub-specifications. Reproducing this node's own
                        # spec, or any ancestor's, is a no-op that would recurse
                        # forever.
                        if len(path) > self.max_depth:
                            attempt_obj.update_status(AttemptStatus.REJECTED)
                            retry_context = (
                                f"Maximum refinement depth ({self.max_depth}) reached. "
                                f"'{law}' would split the specification further. You must "
                                f"now discharge it directly with 'assignment' or 'skip'."
                            )
                            continue

                        repeats = [spec_key(s) for s in result.sub_specs
                                   if spec_key(s) in path]
                        if repeats:
                            attempt_obj.update_status(AttemptStatus.REJECTED)
                            retry_context = (
                                f"The law '{law}' made no progress: it produced a "
                                f"sub-specification identical to one already being "
                                f"refined ({repeats[0]}). Choose parameters that "
                                f"strictly change the specification, or a different law."
                            )
                            continue

                        # Recursive branch (e.g. Sequential, Iteration). The law
                        # names its own sub-specifications, so no per-law table
                        # is needed here -- a newly registered law works
                        # unchanged.
                        roles = {role: graph.create_node(sub_spec)
                                 for role, sub_spec in result.by_role().items()}

                        attempt_obj.destination_roles = roles
                        attempt_obj.update_status(AttemptStatus.ACCEPTED)
                        node.status = NodeStatus.DELEGATED
                        
                        # Recursively refine all children
                        all_success = True
                        for child_id in roles.values():
                            if not self.refine_node(graph, child_id, path):
                                all_success = False
                                break
                                
                        if all_success:
                            return True
                        else:
                            # A child could not be refined. The cause is often
                            # not the law but the *parameters* it was given --
                            # an invariant too weak to discharge the loop body,
                            # say. Blacklisting the law here (as this code used
                            # to) permanently bans the correct move because one
                            # invariant was wrong, and forces the model to
                            # abandon an approach it should be repairing.
                            # Instead, count the failure, hand back the reason
                            # the subtree failed, and let the law be re-proposed
                            # with better parameters.
                            key = (node_id, law)
                            self.param_failures_per_node[key] =                                 self.param_failures_per_node.get(key, 0) + 1

                            attempt_obj.update_status(AttemptStatus.ABORTED)
                            node.status = NodeStatus.OPEN

                            reason = self.last_subtree_failure
                            if self.param_failures_per_node[key] >= self.max_param_attempts:
                                # Repeatedly bad parameters: give up on the law.
                                self.blacklisted_laws_per_node[node_id].append(law)
                                retry_context = (
                                    f"'{law}' has now failed {self.max_param_attempts} "
                                    f"times with different parameters and is no longer "
                                    f"available here. Choose a different law."
                                )
                            else:
                                retry_context = (
                                    f"Your '{law}' step was applied, but the "
                                    f"sub-specification it produced could not be "
                                    f"refined. You may use '{law}' again, but you "
                                    f"must choose DIFFERENT parameters -- the same "
                                    f"ones will fail the same way."
                                )
                            if reason:
                                retry_context += (
                                    "\n\nThe failure deeper in the tree was:\n"
                                    + reason
                                )
                            
                except VerificationError as e:
                    msg = str(e)
                    if "unknown" in msg.lower():
                        # UNKNOWN handling
                        attempt_obj.update_status(AttemptStatus.INCONCLUSIVE)
                        retry_context = "Z3 Verification was INCONCLUSIVE (timeout or non-linear arithmetic complexity). Try a simpler formulation or different law."
                    else:
                        # FAILED handling
                        attempt_obj.update_status(AttemptStatus.REJECTED)
                        attempt_obj.counterexample = msg
                        retry_context = f"Verification failed. {msg}"
                        
            except Exception as e:
                # Parsing or other errors, create a dummy attempt to record the error
                attempt_id = graph.record_attempt(node_id, "unknown", {})
                attempt_obj = graph.attempts[attempt_id]
                attempt_obj.update_status(AttemptStatus.ERROR)
                attempt_obj.error_message = str(e)
                retry_context = f"System Error processing response: {str(e)}"
                
        # If we exit the loop, max_retries exhausted or all laws blacklisted.
        # Remember why, so the parent can pass it to the model instead of a
        # generic "that did not work".
        self.last_subtree_failure = retry_context or None
        node.status = NodeStatus.FAILED
        if node_id == graph.root_id:
            exhausted = self.blacklisted_laws_per_node.get(node_id, [])
            raise RefinementExhausted(f"Refinement exhausted at root node. Failed to refine specification. Blacklisted laws: {exhausted}")
            
        return False
