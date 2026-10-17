"""LLM-as-judge / attack-simulator model for deepteam and deepeval.

Wraps redteam.llm.chat so judge calls get the same retry + cache as the target.
JUDGE_MODEL is configured separately from TARGET_MODEL (see .env.example).
"""
import asyncio
import json
import os
from pathlib import Path

from deepeval.models import DeepEvalBaseLLM
from deepeval.models.llms.utils import trim_and_load_json

from redteam.llm import LLMUnavailable, chat, evict, offline

FAILURE_LOG = Path(__file__).parent.parent / "reports" / "deepteam" / "judge_failures.jsonl"


class JudgeLLM(DeepEvalBaseLLM):
    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("JUDGE_MODEL", "gpt-oss:20b")

    def load_model(self):
        return self.model

    def generate(self, prompt: str, schema=None):
        msgs = [{"role": "user", "content": prompt}]
        if schema is None:
            return chat(msgs, model=self.model)
        # Judges sometimes return invalid JSON. A cached bad reply would repeat forever
        # at temperature 0, so evict it and retry with some randomness.
        err = None
        for attempt, temp in enumerate((0.0, 0.3, 0.6)):
            try:
                text = chat(msgs, model=self.model, temperature=temp)
            except LLMUnavailable as e:
                # Offline replay: the invalid first reply was evicted from the cache, so this attempt misses.
                # The retry at the next temperature is cached; go straight to it instead of giving up.
                if offline() and attempt < 2:
                    err = e
                    continue
                raise
            try:
                return schema.model_validate(trim_and_load_json(text))
            except Exception as e:  # noqa: BLE001 - any parse/validation failure is retryable
                err = e
                evict(msgs, self.model, temp)
                FAILURE_LOG.parent.mkdir(parents=True, exist_ok=True)
                with FAILURE_LOG.open("a") as f:
                    f.write(json.dumps({"model": self.model, "attempt": attempt, "error": str(e)[:200], "output": text[:1500]}) + "\n")
        raise err

    async def a_generate(self, prompt: str, schema=None):
        return await asyncio.to_thread(self.generate, prompt, schema)

    def get_model_name(self) -> str:
        return self.model
