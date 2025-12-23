from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.models import PromptRequest, ChatCompletionRequest, APIResponse, Choice, Message, Usage
from app.core.browser import BrowserManager
from app.providers.chatgpt import ChatGPTProvider
from app.providers.gemini import GeminiProvider
from app.providers.grok import GrokProvider
import uuid
import time
import logging
import asyncio
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Free AI Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Provider instances
providers = {
    "chatgpt": ChatGPTProvider(),
    "gemini": GeminiProvider(),
    "grok": GrokProvider(),
}

@app.on_event("startup")
async def startup_event():
    # Initialize browser on startup
    await BrowserManager.get_browser()

@app.on_event("shutdown")
async def shutdown_event():
    await BrowserManager.close()

# ... imports ...

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "gpt-5-mini", "object": "model", "created": int(time.time()), "owned_by": "openai"},
            {"id": "gemini-3-flash", "object": "model", "created": int(time.time()), "owned_by": "google"},
            {"id": "grok-3-mini", "object": "model", "created": int(time.time()), "owned_by": "xai"},
        ]
    }

@app.post("/v1/providers/{provider_name}/reset")
async def reset_provider(provider_name: str):
    if provider_name not in providers:
        raise HTTPException(status_code=400, detail=f"Provider {provider_name} not supported")
    
    await providers[provider_name].reset()
    return {"status": "success", "message": f"Provider {provider_name} reset successfully"}

@app.post("/v1/chat/completions", response_model=APIResponse)
async def chat_completions(request: ChatCompletionRequest):
    # Flexible provider mapping based on model name keywords
    model_name = request.model.lower()
    provider_name = None
    
    if "gpt" in model_name or "openai" in model_name:
        provider_name = "chatgpt"
    elif "gemini" in model_name:
        provider_name = "gemini"
    elif "grok" in model_name:
        provider_name = "grok"
    
    if not provider_name or provider_name not in providers:
        raise HTTPException(status_code=400, detail=f"Model {request.model} not supported. Use a model name containing 'gpt', 'gemini', or 'grok'.")
    
    provider = providers[provider_name]
    
    # Extract the last user message to use as the prompt
    # This assumes the browser session maintains the conversation history
    last_user_message = next((m for m in reversed(request.messages) if m.role == "user"), None)
    
    if not last_user_message:
        raise HTTPException(status_code=400, detail="No user message found in the request")
    
    prompt_text = last_user_message.content
    
    # Extract system prompt if present (mostly for new chats, but we pass it anyway)
    system_prompt = next((m.content for m in request.messages if m.role == "system"), None)
    
    # Create internal request object
    internal_request = PromptRequest(
        prompt=prompt_text,
        system_prompt=system_prompt,
        new_chat=request.new_chat or False, # Default to False if None
        provider=provider_name
    )
    
    try:
        # Simple concurrency lock to prevent race conditions on the single browser tab
        # In a future update, we could manage a pool of tabs for concurrent sessions
        async with provider.lock:
            response_text = await provider.send_prompt(internal_request)
        
        # Approximate token count (1 token ~= 4 chars)
        prompt_tokens = math.ceil(len(prompt_text) / 4)
        completion_tokens = math.ceil(len(response_text) / 4)
        
        return APIResponse(
            id=f"chatcmpl-{uuid.uuid4()}",
            created=int(time.time()),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content=response_text),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
