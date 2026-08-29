"""Common base classes, decorators, and types for RetailPulse.

This module is the foundation for every Lambda handler. It provides:

- BaseLambda: abstract base class for all stage handlers
- JobContext: per-invocation context (job_id, source_bucket, etc.)
- @stage decorator: ties a handler to its input/output models
- DataCuratorModel: stdlib dataclass base (replaces pydantic.BaseModel)
- Structured logging via structlog
- Exception hierarchy
"""

from __future__ import annotations

import functools
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast, get_args, get_origin

if TYPE_CHECKING:
    from collections.abc import Callable

import boto3
import structlog

logger = structlog.get_logger()


# --- Exceptions ---


class RetailPulseError(Exception):
    """Base exception for all RetailPulse errors."""


class AgentError(RetailPulseError):
    """Agent failed to handle the request."""


class ToolError(RetailPulseError):
    """A tool failed to execute."""


class VoiceError(RetailPulseError):
    """Voice (Transcribe/Polly) failed."""


class IntentError(RetailPulseError):
    """Intent classification failed."""


class CatalogError(RetailPulseError):
    """Catalog lookup failed."""


class OrderError(RetailPulseError):
    """Order lookup failed."""


# --- Job context ---


@dataclass
class JobContext:
    """Per-invocation context passed through the pipeline."""

    session_id: str
    customer_id: str | None = None
    environment: str = "dev"
    started_at: float = 0.0
    cumulative_cost_usd: float = 0.0
    custom: dict[str, Any] | None = None


# --- Dataclass base (pydantic-free) ---


def _strip_whitespace(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return {k: _strip_whitespace(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_whitespace(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_strip_whitespace(v) for v in value)
    return value


def _check_types(obj: Any) -> None:
    if not is_dataclass(obj):
        return
    for f in fields(obj):
        if f.name.startswith("_"):
            continue
        value = getattr(obj, f.name)
        annotation = f.type
        if get_origin(annotation) is Literal:
            allowed = get_args(annotation)
            if value not in allowed:
                raise TypeError(f"Field {f.name}: {value!r} not in {allowed}")
        if is_dataclass(value):
            _check_types(value)
        elif isinstance(value, list) and value and is_dataclass(value[0]):
            for item in value:
                _check_types(item)


@dataclass
class DataCuratorModel:
    """Base dataclass model — pydantic-free."""

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            stripped = _strip_whitespace(value)
            if stripped is not value:
                object.__setattr__(self, f.name, stripped)
        _check_types(self)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DataCuratorModel:
        if not isinstance(data, dict):
            raise TypeError(f"from_dict requires a dict, got {type(data).__name__}")
        known = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key not in known:
                continue
            f = next((fld for fld in fields(cls) if fld.name == key), None)
            if f is not None:
                annotation = f.type
                if isinstance(annotation, str) and "." in annotation:
                    annotation = annotation.split(".")[-1]
                if isinstance(annotation, str):
                    ann_name = annotation
                else:
                    ann_name = getattr(annotation, "__name__", str(annotation))
                # is_dataclass() narrows to DataclassInstance, which has no
                # from_dict. Every dataclass reachable here is a
                # DataCuratorModel subclass, which does -- the checks below
                # establish that, but the type system cannot see it.
                nested = globals().get(ann_name) or _resolve_typing(annotation)
                if nested is not None and is_dataclass(nested):
                    # is_dataclass() narrows to DataclassInstance, which has
                    # no from_dict. Every dataclass reachable here is a
                    # DataCuratorModel subclass, which does; the cast names
                    # what the branch above has already established.
                    model = cast("type[DataCuratorModel]", nested)
                    if isinstance(value, dict):
                        value = model.from_dict(value)
                    elif isinstance(value, list) and value and isinstance(value[0], dict):
                        value = [model.from_dict(v) for v in value]
            kwargs[key] = value
        return cls(**kwargs)


def _resolve_typing(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        for a in args:
            resolved = _resolve_typing(a)
            if resolved is not None and is_dataclass(resolved):
                return resolved
    if isinstance(annotation, str):
        return globals().get(annotation)
    if isinstance(annotation, type):
        return annotation
    return None


# --- Inter-stage data models ---


@dataclass
class ConversationRequest(DataCuratorModel):
    """Input to the orchestrator."""

    session_id: str
    channel: str  # "voice" | "web" | "api"
    transcript: str
    customer_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestratorDecision(DataCuratorModel):
    """Orchestrator's decision: which agent + what to pass."""

    intent: str  # "sales" | "support" | "returns"
    confidence: float = 0.0
    reasoning: str = ""
    context_for_agent: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall(DataCuratorModel):
    """A single tool invocation by an agent."""

    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    ok: bool = True
    error: str | None = None
    duration_ms: int = 0


@dataclass
class AgentResponse(DataCuratorModel):
    """Final response from an agent."""

    session_id: str
    intent: str
    agent: str
    response: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    audio_url: str | None = None
    duration_ms: int = 0


# --- CrewAI agent definitions ---


# --- Base Lambda ---


class BaseLambda(ABC):
    """Abstract base class for all stage Lambda handlers."""

    NAME: ClassVar[str] = ""
    INPUT_MODEL: ClassVar[type[DataCuratorModel] | None] = None
    OUTPUT_MODEL: ClassVar[type[DataCuratorModel] | None] = None

    def __init__(self) -> None:
        if not self.NAME:
            raise ValueError(f"{type(self).__name__} must set NAME")
        self.log = logger.bind(handler=self.NAME)
        self.s3: Any = None
        self.dynamodb: Any = None
        self.bedrock: Any = None
        self.s3vectors: Any = None
        self.transcribe: Any = None
        self.polly: Any = None
        self._setup_done = False

    def setup(self) -> None:  # noqa: B027
        """Optional per-handler initialisation.

        Deliberately concrete and empty rather than abstract: most handlers
        need nothing beyond the shared clients, and forcing every subclass to
        write an empty override would be noise.
        """

    def ensure_setup(self) -> None:
        """Build the clients this handler needs, once per warm container.

        Only S3, DynamoDB and Bedrock are created here. The base class used to
        open six clients including Transcribe and Polly, which nothing in this
        repo calls -- every cold start paid to construct them. A handler that
        needs another service builds it in its own setup().

        The region comes from the runtime rather than a literal, so the same
        code deploys to a second region without an edit.
        """
        if not self._setup_done:
            self.s3 = boto3.client("s3")
            self.dynamodb = boto3.client("dynamodb")
            self.bedrock = boto3.client("bedrock-runtime")
            self.setup()
            self._setup_done = True

    @abstractmethod
    def handle(
        self, ctx: JobContext, inp: DataCuratorModel
    ) -> DataCuratorModel | list[DataCuratorModel]:
        pass


# --- Stage decorator ---


def stage(
    *,
    name: str,
    input_model: type[DataCuratorModel] | None = None,
    output_model: type[DataCuratorModel] | None = None,
) -> Callable[[type[BaseLambda]], type[BaseLambda]]:
    def decorator(cls: type[BaseLambda]) -> type[BaseLambda]:
        cls.NAME = name
        cls.INPUT_MODEL = input_model
        cls.OUTPUT_MODEL = output_model

        original_handle = cls.handle

        @functools.wraps(original_handle)
        def wrapper(self: BaseLambda, ctx: JobContext, inp: DataCuratorModel) -> Any:
            self.ensure_setup()
            start = time.perf_counter()
            self.log.info("stage.start", job_id=ctx.session_id, input_type=type(inp).__name__)
            try:
                if input_model is not None and not isinstance(inp, input_model):
                    if isinstance(inp, dict):
                        inp = input_model.from_dict(inp)
                    else:
                        inp = input_model.from_dict(
                            inp.to_dict() if hasattr(inp, "to_dict") else inp.__dict__
                        )

                result = original_handle(self, ctx, inp)

                if isinstance(result, list):
                    if output_model is not None:
                        result = [
                            r
                            if isinstance(r, output_model)
                            else output_model.from_dict(
                                r.to_dict() if isinstance(r, DataCuratorModel) else r
                            )
                            for r in result
                        ]
                elif output_model is not None and not isinstance(result, output_model):
                    result = output_model.from_dict(
                        result.to_dict() if hasattr(result, "to_dict") else result.__dict__
                    )

                duration_ms = int((time.perf_counter() - start) * 1000)
                self.log.info(
                    "stage.success",
                    job_id=ctx.session_id,
                    duration_ms=duration_ms,
                    output_count=len(result) if isinstance(result, list) else 1,
                )
                return result
            except Exception as exc:
                duration_ms = int((time.perf_counter() - start) * 1000)
                self.log.exception(
                    "stage.error",
                    job_id=ctx.session_id,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    duration_ms=duration_ms,
                )
                raise

        cls.handle = wrapper  # type: ignore[method-assign]
        return cls

    return decorator


__all__ = [
    "AgentError",
    "AgentResponse",
    "BaseLambda",
    "CatalogError",
    "ConversationRequest",
    "DataCuratorModel",
    "IntentError",
    "JobContext",
    "OrchestratorDecision",
    "OrderError",
    "RetailPulseError",
    "ToolCall",
    "ToolError",
    "VoiceError",
    "stage",
]
