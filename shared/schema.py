from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

class CommandType(str, Enum):
    SINGLE = "single_step"
    MULTI = "multi_step"

class Task(BaseModel):
    model_config = ConfigDict(extra='allow')
    action: str = Field(description="The specific action to perform (e.g., OPEN_APP, CREATE_FOLDER).")
    target: Optional[str] = Field(default=None, description="The target of the action if applicable.")

class ActionCommand(BaseModel):
    intent: str = Field(description="The underlying intent interpreted from text. For single_step, use OPEN_APP, OPEN_PATH, SEARCH_WEB, etc. For multi_step, use a high-level goal name like HANDLE_ASSIGNMENTS.")
    type: CommandType = Field(default=CommandType.SINGLE, description="Whether this request is a single action or a multi-step pipeline.")
    
    target: Optional[str] = Field(default=None, description="The main subject of the intent (e.g. app name, file path). Used mainly when type is single_step.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Any additional modifiers related to the command. Used mainly when type is single_step.")
    
    tasks: Optional[List[Task]] = Field(default=None, description="The sequence of tasks to execute. Required if type is multi_step.")

class AssistantResponse(BaseModel):
    message: str = Field(description="The natural language conversational response to the user.")
    command: Optional[ActionCommand] = Field(default=None, description="The structural command to execute, if the user requested an action. If pure conversation, omit this.")

