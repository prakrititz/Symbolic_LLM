from abc import ABC, abstractmethod
import json

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Takes a prompt string and returns the generated text from the LLM.
        """
        pass

class MockProvider(LLMProvider):
    """
    A mock provider for testing. 
    It can be configured to return specific responses or a sequence of responses.
    """
    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0
        self.prompts_received = []

    def generate(self, prompt: str) -> str:
        self.prompts_received.append(prompt)
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        
        # Default fallback if run out of responses
        return json.dumps({"law": "skip", "parameters": {}})
