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
                 max_retries: int = 5, max_depth: int = 6, use_multi_turn: bool = False):
        self.engine = engine
        self.llm = llm
        self.max_retries = max_retries
        self.use_multi_turn = use_multi_turn
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
        # A law whose parameters failed below is given this many chances to be
        # re-proposed with better parameters before it is blacklisted outright.
        self.max_param_attempts = 2

    def _build_history_context(self, graph: RefinementGraph, node_id: str, law: Optional[str] = None) -> str:
        failures = []
        node = graph.nodes[node_id]
        for attempt_id in node.attempts:
            attempt = graph.attempts[attempt_id]
            if law is not None and attempt.law != law:
                continue
            
            if attempt.status == AttemptStatus.REJECTED:
                reason = attempt.counterexample or "Verification failed."
                failures.append(f"- Law '{attempt.law}', Parameters: {attempt.parameters}\n  Failed: {reason}")
            elif attempt.status == AttemptStatus.INCONCLUSIVE:
                failures.append(f"- Law '{attempt.law}', Parameters: {attempt.parameters}\n  Failed: Z3 Verification was INCONCLUSIVE (timeout or non-linear arithmetic complexity).")
            elif attempt.status == AttemptStatus.ERROR:
                reason = attempt.error_message or "System Error."
                failures.append(f"- Law '{attempt.law}', Parameters: {attempt.parameters}\n  Failed: {reason}")
            elif attempt.status == AttemptStatus.ABORTED:
                reason = attempt.error_message or "Sub-specification could not be refined further."
                failures.append(f"- Law '{attempt.law}', Parameters: {attempt.parameters}\n  Failed: The step was applied, but the resulting tree failed. {reason}")
                
        if not failures:
            return ""
            
        header = "Previous failed attempts with '" + law + "':\n" if law else "Previous failed attempts:\n"
        return header + "\n\n".join(failures)

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

        for attempt in range(self.max_retries):
            print(f"\n---> [Refining Node '{node_id}' | Depth: {len(path)-1} | Attempt: {attempt+1}/{self.max_retries}]")
            # Check if all possible laws are blacklisted
            if len(self.blacklisted_laws_per_node[node_id]) >= self.TOTAL_LAWS:
                break
                
            try:
                if not self.use_multi_turn:
                    # 1. Prompt LLM (Single-Turn)
                    history_context = self._build_history_context(graph, node_id, None)
                    prompt = generate_state_prompt(
                        node, 
                        blacklisted_laws=self.blacklisted_laws_per_node[node_id],
                        history_context=history_context,
                        available_laws=list(self.engine.laws)
                    )
                    response = self.llm.generate(prompt)
                    law, parameters = parse_llm_response(response)
                    
                    if law in self.blacklisted_laws_per_node[node_id]:
                        continue
                else:
                    from FormalLLM.llm.prompts import generate_law_selection_prompt, generate_parameter_synthesis_prompt
                    from FormalLLM.llm.parser import parse_law_response, parse_parameters_response
                    
                    # Turn 1: Law Selection
                    prompt = generate_law_selection_prompt(
                        node, 
                        blacklisted_laws=self.blacklisted_laws_per_node[node_id],
                        available_laws=list(self.engine.laws)
                    )
                    response = self.llm.generate(prompt)
                    law = parse_law_response(response)
                    
                    if law in self.blacklisted_laws_per_node[node_id]:
                        continue
                        
                # Evaluation loop (Turn 2 sub-loop if multi-turn, else 1 iteration)
                max_evals = self.max_param_attempts if self.use_multi_turn else 1
                turn2_completed = False
                
                for eval_idx in range(max_evals):
                    if self.use_multi_turn:
                        # Turn 2: Synthesize parameters
                        history_context = self._build_history_context(graph, node_id, law)
                        p_prompt = generate_parameter_synthesis_prompt(node, law, history_context=history_context)
                        # Give Turn 2 extra headroom since reasoning for parameter synthesis is often much longer
                        p_response = self.llm.generate(p_prompt, max_tokens=8192)
                        parameters = parse_parameters_response(p_response, law)
                        
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
                            # Progress guard
                            if len(path) > self.max_depth:
                                attempt_obj.update_status(AttemptStatus.REJECTED)
                                attempt_obj.counterexample = (
                                    f"Maximum refinement depth ({self.max_depth}) reached. "
                                    f"'{law}' would split the specification further. You must "
                                    f"now discharge it directly with 'assignment' or 'skip'."
                                )
                                continue

                            repeats = [spec_key(s) for s in result.sub_specs if spec_key(s) in path]
                            if repeats:
                                attempt_obj.update_status(AttemptStatus.REJECTED)
                                attempt_obj.counterexample = (
                                    f"The law '{law}' made no progress: it produced a "
                                    f"sub-specification identical to one already being "
                                    f"refined ({repeats[0]}). Choose parameters that "
                                    f"strictly change the specification, or a different law."
                                )
                                continue

                            # Recursive branch
                            roles = {role: graph.create_node(sub_spec) for role, sub_spec in result.by_role().items()}

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
                                key = (node_id, law)
                                self.param_failures_per_node[key] = self.param_failures_per_node.get(key, 0) + 1

                                attempt_obj.update_status(AttemptStatus.ABORTED)
                                node.status = NodeStatus.OPEN

                                # We look up the child node that failed to extract its reason
                                child_errors = []
                                for child_id in roles.values():
                                    child_node = graph.nodes[child_id]
                                    if child_node.status == NodeStatus.FAILED:
                                        exhausted = self.blacklisted_laws_per_node.get(child_id, [])
                                        child_errors.append(f"Child node '{child_id}' exhausted all options. Blacklisted: {exhausted}")
                                attempt_obj.error_message = " | ".join(child_errors) if child_errors else "Subtree refinement failed."

                                if self.param_failures_per_node[key] >= self.max_param_attempts:
                                    self.blacklisted_laws_per_node[node_id].append(law)
                                    turn2_completed = True
                                    break
                                else:
                                    continue
                                
                    except VerificationError as e:
                        msg = str(e)
                        if "unknown" in msg.lower():
                            attempt_obj.update_status(AttemptStatus.INCONCLUSIVE)
                        else:
                            attempt_obj.update_status(AttemptStatus.REJECTED)
                            attempt_obj.counterexample = msg
                            
                        continue
                        
                # End of Turn 2 loop
                if self.use_multi_turn and not turn2_completed:
                    # If we exhausted Turn 2 iterations via VerificationErrors/progress guards
                    key = (node_id, locals().get('law'))
                    if key[1] is not None:
                        self.param_failures_per_node[key] = self.param_failures_per_node.get(key, 0) + max_evals
                        if law not in self.blacklisted_laws_per_node[node_id]:
                            self.blacklisted_laws_per_node[node_id].append(law)

            except Exception as e:
                # Parsing or other errors, create a dummy attempt to record the error
                err_law = locals().get('law', 'unknown')
                attempt_id = graph.record_attempt(node_id, err_law, {})
                attempt_obj = graph.attempts[attempt_id]
                attempt_obj.update_status(AttemptStatus.ERROR)
                attempt_obj.error_message = str(e)
                
        # If we exit the loop, max_retries exhausted or all laws blacklisted.
        node.status = NodeStatus.FAILED
        if node_id == graph.root_id:
            exhausted = self.blacklisted_laws_per_node.get(node_id, [])
            raise RefinementExhausted(f"Refinement exhausted at root node. Failed to refine specification. Blacklisted laws: {exhausted}")
            
        return False
