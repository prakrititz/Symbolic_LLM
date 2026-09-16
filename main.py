import sys
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.refinement.engine import RefinementEngine
from FormalLLM.agent.refiner import AutomatedRefiner
from FormalLLM.llm.provider import OllamaProvider
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.trace.serializer import export_graph_text

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <model_name>")
        print("Example: python main.py llama3")
        sys.exit(1)
        
    model_name = sys.argv[1]
    
    # A simple specification for computing an integer square root
    spec_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    
    print(f"Parsing Specification:\n{spec_str.strip()}")
    spec = parse_spec(spec_str)
    
    print(f"\nInitializing Automated Refiner with Ollama ({model_name})...")
    provider = OllamaProvider(model_name=model_name)
    engine = RefinementEngine()
    
    # max_retries = 3 to avoid waiting too long if the model loops
    refiner = AutomatedRefiner(engine, provider, max_retries=3)
    
    graph = RefinementGraph(spec)
    
    print("\nStarting refinement search... (This may take a while depending on the model)")
    try:
        success = refiner.refine_node(graph, graph.root_id)
        if success:
            print("\n[SUCCESS] Refinement completed perfectly!")
            program = graph.reconstruct_program()
            print("\nFinal Verified Program AST:")
            print(program)
        else:
            print("\n[FAILED] Refinement could not complete.")
    except Exception as e:
        print(f"\n[ERROR] Refinement halted: {e}")
        
    print("\n" + "="*80)
    print("REFINEMENT TRACE")
    print("="*80)
    print(export_graph_text(graph))

if __name__ == "__main__":
    main()
