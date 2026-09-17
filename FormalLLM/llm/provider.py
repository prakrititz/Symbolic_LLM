from abc import ABC, abstractmethod
import base64
import json
import os
import socket
import time
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


class OpenAIChatProvider(LLMProvider):
    """Connects to any OpenAI-compatible ``/v1/chat/completions`` endpoint.

    Used for the hosted high-end models (gpt-oss:120b, qwen3-coder-next), which
    are served behind an authenticating proxy rather than a local Ollama
    socket. The refinement loop only ever needs one turn, so each call sends a
    single user message and reads one choice back.

    Like :class:`OllamaProvider`, this falls back to the reasoning channel:
    gpt-oss returns its chain of thought in ``message.reasoning`` and, when the
    visible content comes back empty, the structured answer is in there. A
    model scored as "produced no output" when it in fact answered would quietly
    corrupt every rate in the benchmark.

    Credentials are read from the environment (``FORMALLLM_REMOTE_AUTH``, in
    ``user:password`` form) rather than baked in, so the endpoint's password
    does not end up in the repository or in a results file.
    """

    #: Fields that have carried the reasoning text on the endpoints we use.
    REASONING_FIELDS = ("reasoning", "reasoning_content", "thinking")

    def __init__(self,
                 model_name: str,
                 base_url: str,
                 auth: str = None,
                 auth_env: str = "FORMALLLM_REMOTE_AUTH",
                 temperature: float = 0.2,
                 max_tokens: int = 512,
                 response_format: str = "json_object",
                 timeout: int = 900,
                 stream: bool = True,
                 max_transport_retries: int = 4,
                 extra_body: dict = None):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.auth = auth if auth is not None else os.environ.get(auth_env)
        self.auth_env = auth_env
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.response_format = response_format
        self.timeout = timeout
        # Streaming is the default because the tunnel in front of these models
        # resets a connection that produces no bytes for ~90s, and a cold load
        # of a 120B model takes longer than that. Streaming starts the response
        # immediately and keeps data flowing, so nothing idles out. A
        # non-streaming request is otherwise identical and is kept for
        # endpoints that do not support SSE.
        self.stream = stream
        self.max_transport_retries = max_transport_retries
        self.extra_body = extra_body or {}
        self.last_meta = {}

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if not self.auth:
            raise Exception(
                f"No credentials for {self.base_url}. Set {self.auth_env} to "
                f"'user:password' (or pass auth=...) before running."
            )
        if ":" in self.auth and not self.auth.lower().startswith("bearer "):
            token = base64.b64encode(self.auth.encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        else:
            token = self.auth.split(" ", 1)[-1]
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def generate(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"

        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": self.stream,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.response_format:
            data["response_format"] = {"type": self.response_format}
        if self.stream:
            # Without this, a streaming response carries no usage block and the
            # per-trial token counts in the benchmark silently become null.
            data.setdefault("stream_options", {"include_usage": True})
        data.update(self.extra_body)

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )

        # A long refinement makes one HTTPS connection per call, and Windows
        # intermittently refuses an outbound socket under that churn
        # (WinError 10013) or the tunnel drops a connection mid-flight. Both are
        # transient and unrelated to the model, but they abort a whole trial and
        # get recorded as a refinement failure -- three runs were lost this way
        # before this retry existed.
        last_error = None
        for attempt in range(self.max_transport_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    if self.stream:
                        return self._read_stream(response)
                    body = response.read().decode("utf-8")
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:500]
                raise Exception(f"{self.base_url} returned HTTP {e.code}: {detail}")
            except (urllib.error.URLError, socket.error, OSError) as e:
                last_error = e
                if attempt == self.max_transport_retries - 1:
                    raise Exception(
                        f"Failed to reach {self.base_url} after "
                        f"{self.max_transport_retries} attempts. Error: {e}"
                    )
                # Back off long enough for a refused ephemeral port to be
                # released before trying again.
                time.sleep(2 * (attempt + 1))

        if not body.strip():
            raise Exception(
                f"{self.base_url} returned an empty body for model "
                f"{self.model_name!r} (timeout was {self.timeout}s)"
            )

        result = json.loads(body)
        choices = result.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}

        usage = result.get("usage") or {}
        self.last_meta = {
            "prompt_eval_count": usage.get("prompt_tokens"),
            "eval_count": usage.get("completion_tokens"),
            "total_duration": None,
            "used_thinking_channel": False,
            "finish_reason": choices[0].get("finish_reason") if choices else None,
        }

        text = message.get("content") or ""
        if not text.strip():
            for field in self.REASONING_FIELDS:
                reasoning = message.get(field) or ""
                if reasoning.strip():
                    self.last_meta["used_thinking_channel"] = True
                    text = reasoning
                    break
        return text

    def _read_stream(self, response) -> str:
        """Consume a server-sent-event stream into one response string.

        Content and reasoning are accumulated separately so the same
        "answer landed in the reasoning channel" fallback applies as in the
        non-streaming path.
        """
        content_parts, reasoning_parts = [], []
        usage, finish_reason = {}, None

        for raw_line in response:
            line = raw_line.decode("utf-8", "replace").strip()
            if not line or not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue

            usage = chunk.get("usage") or usage
            for choice in chunk.get("choices") or []:
                finish_reason = choice.get("finish_reason") or finish_reason
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    content_parts.append(delta["content"])
                for field in self.REASONING_FIELDS:
                    if delta.get(field):
                        reasoning_parts.append(delta[field])

        self.last_meta = {
            "prompt_eval_count": usage.get("prompt_tokens"),
            "eval_count": usage.get("completion_tokens"),
            "total_duration": None,
            "used_thinking_channel": False,
            "finish_reason": finish_reason,
        }

        text = "".join(content_parts)
        if not text.strip() and reasoning_parts:
            self.last_meta["used_thinking_channel"] = True
            text = "".join(reasoning_parts)
        return text
