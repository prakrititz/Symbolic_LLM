from abc import ABC, abstractmethod
import json
import urllib.request
import urllib.error

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

class OllamaProvider(LLMProvider):
    """
    Connects to a local Ollama instance (default: localhost:11434).
    Expects the model to output JSON that matches the Refine4LLM format.

    Reasoning ("thinking") models such as qwen3.5 emit their JSON inside the
    separate `thinking` channel when `format: json` is requested, leaving
    `response` empty. We therefore fall back to the thinking channel so that
    such models are not silently scored as producing no output at all.
    """
    def __init__(self,
                 model_name: str = "llama3",
                 base_url: str = "http://localhost:11434",
                 think: bool = None,
                 options: dict = None,
                 response_format: str = "json",
                 timeout: int = 600,
                 keep_alive: str = "30m"):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.think = think
        self.options = options or {}
        # "json" constrains output to a JSON object (used by the refinement
        # loop); None leaves the model free, which is what code generation needs.
        self.response_format = response_format
        self.timeout = timeout
        self.keep_alive = keep_alive
        self.last_meta = {}

    def generate(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"

        # We explicitly request JSON format to help the model adhere to our schema
        data = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        if self.response_format:
            data["format"] = self.response_format
        if self.options:
            data["options"] = self.options
        if self.think is not None:
            data["think"] = self.think

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as e:
            raise Exception(f"Failed to connect to Ollama at {self.base_url}. Is Ollama running? Error: {e}")

        self.last_meta = {
            "prompt_eval_count": result.get("prompt_eval_count"),
            "eval_count": result.get("eval_count"),
            "total_duration": result.get("total_duration"),
            "used_thinking_channel": False,
        }

        text = result.get('response', '') or ''
        if not text.strip():
            # Reasoning model: the structured answer landed in the thinking channel.
            thinking = result.get('thinking', '') or ''
            if thinking.strip():
                self.last_meta["used_thinking_channel"] = True
                text = thinking
        return text
