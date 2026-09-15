from enum import Enum

class AttemptStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    ACCEPTED = "accepted"         # Law verified successfully
    REJECTED = "rejected"         # Z3 proved it invalid (FAILED)
    INCONCLUSIVE = "inconclusive" # Z3 returned UNKNOWN (timeout/nonlinear)
    ERROR = "error"               # Parser crash, LLM format error, etc.
    ABORTED = "aborted"           # Fallback abandoned this path later on

class NodeStatus(Enum):
    OPEN = "open"
    REFINING = "refining"
    DELEGATED = "delegated"       # Split into sub-specs (e.g. via Sequential). Not terminal!
    REFINED = "refined"           # Terminally resolved into code (e.g. Assignment/Skip)
    FAILED = "failed"             # Exhausted all attempts
