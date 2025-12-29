from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
import re

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    
    new_chat: Optional[bool] = False
    session_id: Optional[str] = None
    
    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v):
        if v is None:
            return None
        v = v.strip().lower()
        if not re.match(r'^[a-f0-9]{8,32}$', v):
            raise ValueError("session_id must be a hexadecimal string between 8-32 characters")
        return v

class PromptRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    timeout: int = Field(default=300, ge=30, le=600)
    stream: bool = False
    new_chat: bool = Field(default=False, description="Force start a new chat")
    provider: Literal["chatgpt", "gemini", "grok"] = Field(default="chatgpt", description="AI Provider to use")

    @field_validator("prompt")
    @classmethod
    def validate_prompt_length(cls, v):
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        if len(v) > 32000:
            raise ValueError("Prompt exceeds maximum length")
        return v.strip()

class Message(BaseModel):
    role: str
    content: str

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: str

class APIResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage
