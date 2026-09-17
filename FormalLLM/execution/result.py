from dataclasses import dataclass, field
from typing import List

@dataclass
class ExecutionResult:
    passed: int
    failed: int
    errors: List[str] = field(default_factory=list)
    timeout: bool = False
