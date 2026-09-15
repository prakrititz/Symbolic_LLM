import z3
from typing import List
from .proof_obligations import ProofObligation
from FormalLLM.lspec.z3_translator import Z3Translator

class VerificationResult:
    PROVED = "PROVED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"

def verify_obligation(obligation: ProofObligation) -> tuple[str, str]:
    """
    Verifies a proof obligation using Z3.
    Returns (status, message_or_counterexample)
    """
    translator = Z3Translator()
    solver = z3.Solver()
    
    try:
        # Translate assumptions
        for assumption in obligation.assumptions:
            z3_assumption = translator.translate(assumption)
            solver.add(z3_assumption)
            
        # Translate goal and add Not(goal)
        z3_goal = translator.translate(obligation.goal)
        solver.add(z3.Not(z3_goal))
        
        result = solver.check()
        
        if result == z3.unsat:
            return VerificationResult.PROVED, "Obligation is logically valid."
        elif result == z3.sat:
            model = solver.model()
            counterexample = []
            for d in model.decls():
                counterexample.append(f"{d.name()} = {model[d]}")
            return VerificationResult.FAILED, "Counterexample found:\n" + "\n".join(counterexample)
        else:
            return VerificationResult.UNKNOWN, f"Solver returned unknown: {solver.reason_unknown()}"
            
    except Exception as e:
        return VerificationResult.UNKNOWN, f"Translation or solver error: {str(e)}"
