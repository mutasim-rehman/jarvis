from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from .workflows import IntentType  # re-export for clients/tests

# Bump when breaking API or command shape changes (executor / controllers depend on this).
SCHEMA_VERSION = "1.2.0"


class RouteKind(str, Enum):
    """Phase 1 routing stub: whether a future executor should run."""

    INFORMATIONAL = "informational"
    DESKTOP_EXECUTION = "desktop_execution"


class Task(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str = Field(description="The specific action to perform (e.g., OPEN_APP, CREATE_FOLDER).")
    target: Optional[str] = Field(default=None, description="The target of the action if applicable.")


class ActionCommand(BaseModel):
    intent: str = Field(description="The matched intent for the request.")
    target: Optional[str] = Field(
        default=None,
        description="The main subject of the intent (e.g. app name, query, file path).",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Any additional modifiers related to the command.",
    )

    tasks: Optional[List[Task]] = Field(default=None)


class AssistantResponse(BaseModel):
    message: str = Field(description="The natural language conversational response to the user.")
    command: Optional[ActionCommand] = Field(
        default=None,
        description="The structural command to execute, if the user requested an action.",
    )
    route: RouteKind = Field(
        default=RouteKind.INFORMATIONAL,
        description="Whether this turn should trigger desktop execution downstream.",
    )
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional provider/runtime metadata for clients (e.g., fallback options).",
    )


class ParseRequest(BaseModel):
    text: str
    chat_provider: Optional[str] = Field(
        default=None,
        description="Optional per-request chatbot provider override (e.g., huggingface, ollama).",
    )


class ParseResponse(BaseModel):
    schema_version: str = Field(
        default=SCHEMA_VERSION,
        description="Shared command schema version for clients and executor.",
    )
    command: AssistantResponse
    original_text: str


class TaskResult(BaseModel):
    """Per-task outcome from the desktop executor."""

    action: str
    success: bool
    error_code: Optional[str] = Field(default=None, description="Stable machine-readable error, e.g. NOT_IMPLEMENTED.")
    message: str = ""
    artifacts: Dict[str, Any] = Field(default_factory=dict)


class RunCommandRequest(BaseModel):
    command: ActionCommand


class RunCommandResponse(BaseModel):
    schema_version: str = Field(default=SCHEMA_VERSION)
    overall_success: bool = Field(description="True when every task succeeded.")
    results: List[TaskResult] = Field(default_factory=list)


class InteractResponse(BaseModel):
    """Phase 3: Unified response containing both intent and execution results."""

    schema_version: str = Field(default=SCHEMA_VERSION)
    assistant_response: AssistantResponse
    execution_result: Optional[RunCommandResponse] = None
    original_text: str
