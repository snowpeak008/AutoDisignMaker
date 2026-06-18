from dataclasses import dataclass


@dataclass
class BackendCapabilities:
    name: str
    supports_prompt_cache: bool = False
    supports_streaming: bool = False
    max_prompt_tokens: int | None = None
    cost_estimate: str = "unknown"


class LLMBackend:
    def capabilities(self):
        return BackendCapabilities(name=self.__class__.__name__)

    def run_json_task(self, prompt, schema=None, schema_name="codex_task_response.schema.json", session_id=""):
        raise NotImplementedError

    def run_turn(self, prompt, session_id="", schema_mode="turn"):
        raise NotImplementedError
