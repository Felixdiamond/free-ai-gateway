from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal

class PromptRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    timeout: int = Field(default=300, ge=30, le=600)
    stream: bool = False
    new_chat: bool = Field(default=False, description="Force start a new chat")
    provider: Literal["chatgpt", "gemini", "grok"] = Field(default="chatgpt", description="AI Provider to use")

    @validator("prompt")
    def validate_prompt_length(cls, v):
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        if len(v) > 32000: # Increased limit for newer models
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
