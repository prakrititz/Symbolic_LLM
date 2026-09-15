from typing import List, Optional, Dict
from FormalLLM.refinement.engine import RefinementEngine, VerificationError
from FormalLLM.refinement.tree import RefinementNode
from FormalLLM.llm.provider import LLMProvider
from FormalLLM.llm.prompts import generate_state_prompt
from FormalLLM.llm.parser import parse_llm_response

class RefinementFailure(Exception):
    pass

class AutomatedRefiner:
    def __init__(self, engine: RefinementEngine, llm: LLMProvider, max_retries: int = 5):
        self.engine = engine
        self.llm = llm
        self.max_retries = max_retries
        self.blacklisted_laws_per_node: Dict[int, List[str]] = {}
        # The 5 core laws implemented
        self.TOTAL_LAWS = 5

    def refine_node(self, node: RefinementNode) -> bool:
        """
        Recursively attempts to refine a node.
        Returns True if successful, False if it needs to fallback to parent.
        Raises RefinementFailure if it's the root node and all attempts are exhausted.
        """
        if id(node) not in self.blacklisted_laws_per_node:
            self.blacklisted_laws_per_node[id(node)] = []
            
        retry_context = ""
        
        for attempt in range(self.max_retries):
            # Check if all possible laws are blacklisted
            if len(self.blacklisted_laws_per_node[id(node)]) >= self.TOTAL_LAWS:
                break
                
            # 1. Prompt LLM
            prompt = generate_state_prompt(
                node, 
                blacklisted_laws=self.blacklisted_laws_per_node[id(node)],
                retry_context=retry_context
            )
            response = self.llm.generate(prompt)
            
            try:
                # 2. Parse output
                law, parameters = parse_llm_response(response)
                
                # Check blacklist
                if law in self.blacklisted_laws_per_node[id(node)]:
                    retry_context = f"Attempted to use blacklisted law: {law}."
                    continue
                
                # 3. Apply engine
                result = self.engine.apply(node.specification, law, parameters)
                node.refinement_operation = law
                
                # 4. Handle Terminal vs Recursive success branches
                if result.program is not None:
                    # Terminal branch (e.g. Assignment, Skip)
                    node.program = result.program
                    return True
                else:
                    # Recursive branch (e.g. Sequential, Iteration)
                    node.children = [] # Clear any previous failed attempts
                    for sub_spec in result.sub_specs:
                        # add_child creates the child RefinementNode
                        child_node = node.add_child(sub_spec, law)
                        
                    # Recursively refine all children
                    all_success = True
                    for child_node in node.children:
                        if not self.refine_node(child_node):
                            all_success = False
                            break
                            
                    if all_success:
                        return True
                    else:
                        # FallBack triggered! A child completely failed to be refined.
                        # We must abandon this law choice and retry at this node.
                        self.blacklisted_laws_per_node[id(node)].append(law)
                        node.children.clear()
                        node.refinement_operation = None
                        retry_context = f"The law choice '{law}' led to an unrefinable sub-specification deeper in the tree. Try a different approach."
                        
            except VerificationError as e:
                msg = str(e)
                if "unknown" in msg.lower():
                    # UNKNOWN handling
                    retry_context = "Z3 Verification was INCONCLUSIVE (timeout or non-linear arithmetic complexity). Try a simpler formulation or different law."
                else:
                    # FAILED handling
                    retry_context = f"Verification failed. {msg}"
            except Exception as e:
                # Parsing or other errors
                retry_context = f"System Error processing response: {str(e)}"
                
        # If we exit the loop, max_retries exhausted or all laws blacklisted. 
        # Trigger FallBack to parent.
        if node.parent is None:
            exhausted = self.blacklisted_laws_per_node.get(id(node), [])
            raise RefinementFailure(f"Refinement exhausted at root node. Failed to refine specification. Blacklisted laws: {exhausted}")
            
        return False
