from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class TestCase:
    inputs: Dict[str, Any]
    expected: Optional[Dict[str, Any]] = None
