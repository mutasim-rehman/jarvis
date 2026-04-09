from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class IntentType(str, Enum):
    OPEN_APP = "OPEN_APP"
    OPEN_PATH = "OPEN_PATH"
    SEARCH_WEB = "SEARCH_WEB"
    UNKNOWN = "UNKNOWN"

class ActionCommand(BaseModel):
    intent: IntentType = Field(description="The underlying intent interpreted from text.")
    target: Optional[str] = Field(default=None, description="The main subject of the intent (e.g. app name, file path).")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Any additional modifiers related to the command.")

class ParseRequest(BaseModel):
    text: str = Field(..., description="The natural language string to parse.")
    
class ParseResponse(BaseModel):
    command: ActionCommand
    original_text: str
