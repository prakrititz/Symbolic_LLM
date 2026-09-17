import json
import subprocess
import sys
import textwrap
from typing import List, Optional

from .result import ExecutionResult
from .testcase import TestCase

def run(program_code: str, test_cases: List[TestCase], output_vars: List[str], postcondition_expr: Optional[str] = None) -> ExecutionResult:
    result = ExecutionResult(passed=0, failed=0, errors=[])
    
    # Indent the program code so it can fit inside a try-except block
    indented_code = textwrap.indent(program_code, "    ")
    
    for i, case in enumerate(test_cases):
        script_template = f"""import json
import sys

# Load inputs
inputs = {json.dumps(case.inputs)}
for k, v in inputs.items():
    globals()[k] = v

# Run generated program
try:
{indented_code}
except Exception as e:
    print(json.dumps({{"error": "Runtime error: " + type(e).__name__ + ": " + str(e)}}))
    sys.exit(0)

# Collect output variables
output_vars = {json.dumps(output_vars)}
outputs = {{k: globals().get(k) for k in output_vars}}

# Evaluate postcondition if provided
postcondition_str = {json.dumps(postcondition_expr) if postcondition_expr is not None else "None"}
if postcondition_str:
    try:
        valid = eval(postcondition_str)
        print(json.dumps({{"outputs": outputs, "valid": bool(valid)}}))
    except Exception as e:
        print(json.dumps({{"error": "Postcondition error: " + type(e).__name__ + ": " + str(e)}}))
else:
    print(json.dumps({{"outputs": outputs}}))
"""
        
        try:
            proc = subprocess.run(
                [sys.executable, "-c", script_template],
                capture_output=True,
                text=True,
                timeout=1.0
            )
            
            if proc.returncode != 0:
                result.failed += 1
                result.errors.append(f"Test {i} failed with non-zero exit code: {proc.stderr}")
                continue
                
            try:
                out_data = json.loads(proc.stdout)
            except json.JSONDecodeError:
                result.failed += 1
                result.errors.append(f"Test {i} returned invalid JSON: {proc.stdout}")
                continue
                
            if "error" in out_data:
                result.failed += 1
                result.errors.append(f"Test {i} failed: {out_data['error']}")
                continue
                
            outputs = out_data.get("outputs", {})
            
            # Check expected exact values if provided
            if case.expected is not None:
                matches = True
                for k, expected_v in case.expected.items():
                    if outputs.get(k) != expected_v:
                        result.failed += 1
                        result.errors.append(f"Test {i} failed: output {k} was {outputs.get(k)}, expected {expected_v}")
                        matches = False
                        break
                if matches:
                    result.passed += 1
            # Otherwise check if postcondition evaluation was valid
            elif postcondition_expr is not None:
                if out_data.get("valid") is True:
                    result.passed += 1
                else:
                    result.failed += 1
                    result.errors.append(f"Test {i} failed: postcondition '{postcondition_expr}' evaluated to False for outputs {outputs}")
            else:
                # If neither is provided, we can't verify correctness, so count as error.
                result.failed += 1
                result.errors.append(f"Test {i} failed: no expected outputs or postcondition provided")
                
        except subprocess.TimeoutExpired:
            result.failed += 1
            result.timeout = True
            result.errors.append(f"Test {i} timed out after 1.0s")
            
    return result
