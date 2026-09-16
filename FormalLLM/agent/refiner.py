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

                        # Recursive branch (e.g. Sequential, Iteration)
                        roles = {}
                        if law == "sequential" or law == "flexible_sequential":
                            roles["part1"] = graph.create_node(result.sub_specs[0])
                            roles["part2"] = graph.create_node(result.sub_specs[1])
                        elif law == "alternation":
                            roles["then"] = graph.create_node(result.sub_specs[0])
                            roles["else"] = graph.create_node(result.sub_specs[1])
                        elif law == "iteration":
                            if len(result.sub_specs) == 2:
                                roles["init"] = graph.create_node(result.sub_specs[0])
                                roles["body"] = graph.create_node(result.sub_specs[1])
                            else:
                                roles["body"] = graph.create_node(result.sub_specs[0])
                        elif law in ["strengthen_post", "weaken_pre"]:
                            roles["sub"] = graph.create_node(result.sub_specs[0])
                            
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
                            # FallBack triggered! A child completely failed to be refined.
                            # We must abandon this law choice and retry at this node.
                            self.blacklisted_laws_per_node[node_id].append(law)
                            attempt_obj.update_status(AttemptStatus.ABORTED)
                            node.status = NodeStatus.OPEN
                            retry_context = f"The law choice '{law}' led to an unrefinable sub-specification deeper in the tree. Try a different approach."
                            
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
        node.status = NodeStatus.FAILED
        if node_id == graph.root_id:
            exhausted = self.blacklisted_laws_per_node.get(node_id, [])
            raise RefinementExhausted(f"Refinement exhausted at root node. Failed to refine specification. Blacklisted laws: {exhausted}")
            
        return False
