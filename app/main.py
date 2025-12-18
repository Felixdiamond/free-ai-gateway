from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.models import PromptRequest, APIResponse, Choice, Message, Usage
from app.core.browser import BrowserManager
from app.providers.chatgpt import ChatGPTProvider
from app.providers.gemini import GeminiProvider
from app.providers.grok import GrokProvider
import uuid
import time
import logging
import asyncio

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

import math

# ... imports ...

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "chatgpt-free", "object": "model", "created": int(time.time()), "owned_by": "openai"},
            {"id": "gemini-free", "object": "model", "created": int(time.time()), "owned_by": "google"},
            {"id": "grok-free", "object": "model", "created": int(time.time()), "owned_by": "xai"},
        ]
    }

@app.post("/v1/providers/{provider_name}/reset")
async def reset_provider(provider_name: str):
    if provider_name not in providers:
        raise HTTPException(status_code=400, detail=f"Provider {provider_name} not supported")
    
    await providers[provider_name].reset()
    return {"status": "success", "message": f"Provider {provider_name} reset successfully"}

@app.post("/v1/chat/completions", response_model=APIResponse)
async def chat_completions(request: PromptRequest):
    provider_name = request.provider
    if provider_name not in providers:
        raise HTTPException(status_code=400, detail=f"Provider {provider_name} not supported")
    
    provider = providers[provider_name]
    
    try:
        # Simple concurrency lock to prevent race conditions on the single browser tab
        # In a future update, we could manage a pool of tabs for concurrent sessions
        async with provider.lock:
            response_text = await provider.send_prompt(request)
        
        # Approximate token count (1 token ~= 4 chars)
        prompt_tokens = math.ceil(len(request.prompt) / 4)
        completion_tokens = math.ceil(len(response_text) / 4)
        
        return APIResponse(
            id=f"chatcmpl-{uuid.uuid4()}",
            created=int(time.time()),
            model=f"{provider_name}-free",
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
