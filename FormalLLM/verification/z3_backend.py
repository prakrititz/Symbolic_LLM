import z3
from typing import List
from .proof_obligations import ProofObligation
from FormalLLM.lspec.z3_translator import Z3Translator

class VerificationResult:
    PROVED = "PROVED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"

def describe_failure(obligation: ProofObligation, model) -> str:
    """Explain a rejected obligation in terms the model can act on.

    A bare list of variable assignments says nothing about which choice was
    wrong. Measured on the paper's square-root example: the loop body was
    rejected with `x = -2`, which is precisely the evidence that the proposed
    invariant failed to exclude negative x -- but nothing in the message said
    so, and the model responded by abandoning the (correct) law rather than
    strengthening its invariant.
    """
    from FormalLLM.llm.prompts import to_string

    lines = []
    if obligation.description:
        lines.append(f"The obligation that failed: {obligation.description}")
    if obligation.assumptions:
        assumed = " /\ ".join(to_string(a) for a in obligation.assumptions)
        lines.append(f"  assuming:  {assumed}")
    lines.append(f"  must show: {to_string(obligation.goal)}")

    assignments = {d.name(): model[d] for d in model.decls()}
    if assignments:
        rendered = ", ".join(f"{k} = {v}" for k, v in sorted(assignments.items()))
        lines.append(f"Counterexample (these values satisfy the assumptions but "
                     f"falsify the goal): {rendered}")
        lines.append("Your parameters must be changed so that this case cannot "
                     "arise -- typically by strengthening the invariant or the "
                     "intermediate assertion until it excludes these values.")
    return "\n".join(lines)


def verify_obligation(obligation: ProofObligation) -> tuple[str, str]:
    """
    Verifies a proof obligation using Z3.
    Returns (status, message_or_counterexample)
    """
    translator = Z3Translator()
    translator.declare_params(getattr(obligation, "params", []))
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
            return VerificationResult.FAILED, describe_failure(obligation, solver.model())
        else:
            return VerificationResult.UNKNOWN, f"Solver returned unknown: {solver.reason_unknown()}"
            
    except Exception as e:
        return VerificationResult.UNKNOWN, f"Translation or solver error: {str(e)}"
