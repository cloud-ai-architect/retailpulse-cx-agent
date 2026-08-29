"""Agent core: a Bedrock Converse tool-use loop.

This replaces the CrewAI layer the project started with. CrewAI never ran
here: it was imported at module scope in every agent and tool, and it is far
too large to package into a Lambda deployment zip, so the handlers failed at
import before any request reached them.

What the agents actually need is narrower than a framework. Each one is a
system prompt plus a small set of tools, and the model decides which tools to
call. The Converse API expresses exactly that through ``toolConfig``, in the
same normalised request shape the rest of this portfolio already uses -- so
the agents run inside a plain Lambda with boto3 and nothing else.

The loop below is the whole of it: ask the model, run whatever tools it asked
for, hand back the results, repeat until it answers in prose.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, ClassVar

import structlog

logger = structlog.get_logger()

REGION = os.environ.get("AWS_REGION", "ap-south-1")

# Two tiers. Routing and short factual replies go to the cheap model; the
# customer-facing agents use the standard one. Both are read from the
# environment so Terraform stays the single source of truth for model choice.
MODEL_STANDARD = os.environ.get(
    "BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
)
MODEL_FAST = os.environ.get("HAIKU_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")

# A tool-calling conversation that has not resolved after this many rounds is
# not going to. The cap stops a model that keeps re-calling the same tool from
# burning the Lambda timeout and the token budget with it.
MAX_TOOL_TURNS = 6


class ModelError(Exception):
    """A model call failed, or returned a shape we cannot use."""


class ToolExecutionError(Exception):
    """A tool raised. Reported back to the model rather than to the caller."""


class BaseAgent:
    """An agent: a system prompt, a model, and a set of tools.

    Subclasses set NAME, SYSTEM_PROMPT and TOOLS. TOOLS maps a tool name to a
    ``(spec, fn)`` pair, where spec is the JSON schema the model sees and fn
    is the Python callable that runs when the model asks for it.
    """

    NAME: ClassVar[str] = ""
    MODEL: ClassVar[str] = MODEL_STANDARD
    SYSTEM_PROMPT: ClassVar[str] = ""
    TOOLS: ClassVar[dict[str, tuple[dict[str, Any], Any]]] = {}

    def __init__(self) -> None:
        if not self.NAME:
            raise ValueError(f"{type(self).__name__} must set NAME")
        self.log = logger.bind(agent=self.NAME)
        self.bedrock: Any = None
        self._setup_done = False
        self.tool_calls: list[dict[str, Any]] = []

    def setup(self) -> None:
        """Override for agent-specific initialisation."""

    def ensure_setup(self) -> None:
        if self._setup_done:
            return
        # Imported here rather than at module scope: a cold start should not
        # pay for boto3 on a request that never reaches the model.
        import boto3

        self.bedrock = boto3.client("bedrock-runtime", region_name=REGION)
        self.setup()
        self._setup_done = True

    # --- tool plumbing -----------------------------------------------------

    def _tool_config(self) -> dict[str, Any] | None:
        if not self.TOOLS:
            return None
        return {"tools": [{"toolSpec": spec} for spec, _ in self.TOOLS.values()]}

    def _run_tool(self, name: str, args: dict[str, Any]) -> str:
        """Execute one tool and return its result as text for the model.

        A tool that raises is reported back to the model as an error string
        rather than propagating. The model can then apologise, try a
        different tool, or ask the customer for something it is missing --
        all of which are better outcomes than a 500.
        """
        entry = self.TOOLS.get(name)
        if entry is None:
            return json.dumps({"error": f"unknown tool: {name}"})

        _, fn = entry
        start = time.perf_counter()
        try:
            result = fn(**args)
        except Exception as exc:
            self.log.warning("tool.failed", tool=name, error=str(exc))
            self.tool_calls.append({"tool": name, "args": args, "ok": False, "error": str(exc)})
            return json.dumps({"error": str(exc)})

        duration_ms = int((time.perf_counter() - start) * 1000)
        self.log.info("tool.ok", tool=name, duration_ms=duration_ms)
        self.tool_calls.append({"tool": name, "args": args, "ok": True, "error": None})
        return result if isinstance(result, str) else json.dumps(result)

    # --- model calls -------------------------------------------------------

    def converse(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> str:
        """Run the conversation to completion and return the final text.

        Tools are executed as the model asks for them. The loop ends when the
        model replies without requesting a tool, or when MAX_TOOL_TURNS is
        reached -- in which case the model is asked once more, without tools,
        to answer from what it already has.
        """
        self.ensure_setup()
        self.tool_calls = []

        model_id = model or self.MODEL
        system_prompt = system if system is not None else self.SYSTEM_PROMPT
        messages: list[dict[str, Any]] = [{"role": "user", "content": [{"text": prompt}]}]
        tool_config = self._tool_config()

        for turn in range(MAX_TOOL_TURNS):
            # On the final turn, withhold the tools. Left available, a model
            # that is looping will simply call one again and we would return
            # a tool request to the customer instead of an answer.
            last_turn = turn == MAX_TOOL_TURNS - 1
            response = self._call(
                model_id=model_id,
                messages=messages,
                system_prompt=system_prompt,
                tool_config=None if last_turn else tool_config,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            message = response["output"]["message"]
            messages.append(message)

            if response.get("stopReason") != "tool_use":
                return self._text_of(message)

            tool_results = []
            for block in message.get("content", []):
                use = block.get("toolUse")
                if not use:
                    continue
                output = self._run_tool(use["name"], use.get("input") or {})
                tool_results.append(
                    {
                        "toolResult": {
                            "toolUseId": use["toolUseId"],
                            "content": [{"text": output}],
                        }
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        raise ModelError(f"{self.NAME}: tool loop did not converge in {MAX_TOOL_TURNS} turns")

    def _call(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tool_config: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]
        if tool_config:
            kwargs["toolConfig"] = tool_config

        start = time.perf_counter()
        try:
            response: dict[str, Any] = self.bedrock.converse(**kwargs)
        except Exception as exc:
            raise ModelError(f"{self.NAME}: model call failed ({model_id}): {exc}") from exc

        usage = response.get("usage", {})
        self.log.info(
            "model.invoke",
            model=model_id,
            input_tokens=usage.get("inputTokens"),
            output_tokens=usage.get("outputTokens"),
            stop_reason=response.get("stopReason"),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return response

    @staticmethod
    def _text_of(message: dict[str, Any]) -> str:
        """Join the text blocks of a reply, ignoring any non-text blocks."""
        parts = [b["text"] for b in message.get("content", []) if "text" in b]
        if not parts:
            raise ModelError("model reply contained no text")
        return "\n".join(parts).strip()

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Entry point: build clients if needed, then hand off to handle()."""
        self.ensure_setup()
        return self.handle(*args, **kwargs)

    def handle(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def invoke_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Call the model and parse its reply as JSON.

        Models often wrap JSON in prose or a fenced block, so the outermost
        braces are extracted rather than trusting the reply to be bare JSON.
        """
        raw = self.converse(prompt, **kwargs)
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ModelError(f"{self.NAME}: no JSON object in model reply: {raw[:200]}")
        try:
            parsed: dict[str, Any] = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ModelError(f"{self.NAME}: malformed JSON from model: {exc}") from exc
        return parsed


__all__ = [
    "MAX_TOOL_TURNS",
    "MODEL_FAST",
    "MODEL_STANDARD",
    "REGION",
    "BaseAgent",
    "ModelError",
    "ToolExecutionError",
]
