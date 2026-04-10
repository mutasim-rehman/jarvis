from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from .workflows import IntentType

class CommandType(str, Enum):
    SINGLE = "single_step"
    MULTI = "multi_step"

class Task(BaseModel):
    model_config = ConfigDict(extra='allow')
    action: str = Field(description="The specific action to perform (e.g., OPEN_APP, CREATE_FOLDER).")
    target: Optional[str] = Field(default=None, description="The target of the action if applicable.")

class ActionCommand(BaseModel):
    intent: IntentType = Field(description="The matched intent for the request.")
    type: CommandType = Field(default=CommandType.SINGLE, description="Whether this request maps to a single action or a predefined multi-step pipeline.")
    
    target: Optional[str] = Field(default=None, description="The main subject of the intent (e.g. app name, query, file path).")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Any additional modifiers related to the command.")
    
    tasks: Optional[List[Task]] = Field(default=None, exclude=True)

class AssistantResponse(BaseModel):
    message: str = Field(description="The natural language conversational response to the user.")
    command: Optional[ActionCommand] = Field(default=None, description="The structural command to execute, if the user requested an action. If pure conversation, omit this.")


