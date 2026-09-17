import sys
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.lspec.ast import Spec
from FormalLLM.refinement.engine import RefinementEngine
from FormalLLM.agent.refiner import AutomatedRefiner
from FormalLLM.llm.provider import OllamaProvider
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.lpl.to_python import to_python, expr_to_python
from FormalLLM.execution.runner import run
from FormalLLM.execution.testcase import TestCase
from benchmarks.cases import CASES_BY_ID

def main():
    if len(sys.argv) < 3:
        print("Usage: python benchmark.py <model_name> <case_id>")
        print("Example: python benchmark.py llama3.1 A2-assign")
        sys.exit(1)
        
    model_name = sys.argv[1]
    case_id = sys.argv[2]
    
    if case_id not in CASES_BY_ID:
        print(f"Unknown case ID: {case_id}")
        sys.exit(1)
        
    case_def = CASES_BY_ID[case_id]
    spec_str = case_def["spec"]
    
    print(f"Case: {case_id}")
    spec = parse_spec(spec_str)
    
    # We figure out output variables by looking at the postcondition.
    # The postcondition definition usually looks like `(N:int) := x = N + 1` where N is a param, x is a free variable.
    # However, in L_spec, the parameters are listed. The outputs are the free variables not in params.
    # We can do a simpler heuristic: the output variable in our cases is typically `x`, `s`, `d`, `m`, `y`.
    # Let's extract them manually or pass them in test_cases.
    # To keep it robust without writing a full free-variable collector here, we can extract it from the expected outputs of test_cases
    # or just collect all variables in the postcondition that are not parameters.
    
    from FormalLLM.lspec.substitution import get_free_vars
    post_params = {p.name for p in spec.postcondition.params}
    all_post_vars = get_free_vars(spec.postcondition.expr)
    output_vars = list(all_post_vars - post_params)
    
    print(f"Extracted output variables: {output_vars}")

    # No "oracle" provider: replaying a hand-written playbook of correct moves
    # measures the playbook's author, not the system, and reporting it beside
    # model runs made results look better than they were. The scripted
    # refinements are regression tests now --
    # FormalLLM/tests/test_engine_reachability.py.
    provider = OllamaProvider(model_name=model_name)
        
    engine = RefinementEngine()
    refiner = AutomatedRefiner(engine, provider, max_retries=3)
    graph = RefinementGraph(spec)
    
    try:
        success = refiner.refine_node(graph, graph.root_id)
        if success and graph.is_complete(graph.root_id):
            print("Refinement: SUCCESS")
            program_ast = graph.reconstruct_program()
            
            try:
                python_code = to_python(program_ast)
                print("Generated Python: SUCCESS")
                # print(python_code)
                
                # Execution
                if "test_cases" in case_def:
                    test_cases = [TestCase(inputs=tc["inputs"], expected=tc.get("expected")) for tc in case_def["test_cases"]]
                    
                    # If expected is None in test cases, we need the postcondition
                    needs_postcondition = any(tc.expected is None for tc in test_cases)
                    postcondition_expr = expr_to_python(spec.postcondition.expr) if needs_postcondition else None
                    
                    result = run(python_code, test_cases, output_vars, postcondition_expr)
                    
                    total = len(test_cases)
                    print(f"Tests: {result.passed}/{total}")
                    if result.passed == total:
                        print("Result: PASS")
                    else:
                        print("Result: FAIL")
                        for err in result.errors:
                            print(f"  - {err}")
                else:
                    print("Tests: N/A (no test cases defined)")
                    print("Result: N/A")
            except Exception as e:
                print(f"Generated Python: FAILED ({e})")
                print("Result: FAIL")
        else:
            print("Refinement: FAILED")
            print("Generated Python: N/A")
            print("Result: FAIL")
    except Exception as e:
        print(f"Refinement: ERROR ({e})")
        print("Generated Python: N/A")
        print("Result: FAIL")

if __name__ == "__main__":
    main()
