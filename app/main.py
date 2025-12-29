from fastapi import FastAPI, HTTPException
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
import json

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

providers = {
    "chatgpt": ChatGPTProvider(),
    "gemini": GeminiProvider(),
    "grok": GrokProvider(),
}

@app.on_event("startup")
async def startup_event():
    await BrowserManager.get_browser()

@app.on_event("shutdown")
async def shutdown_event():
    await BrowserManager.close()



@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "gpt", "object": "model", "created": int(time.time()), "owned_by": "openai"},
            {"id": "gemini", "object": "model", "created": int(time.time()), "owned_by": "google"},
            {"id": "grok", "object": "model", "created": int(time.time()), "owned_by": "xai"},
        ]
    }

@app.post("/v1/providers/{provider_name}/reset")
async def reset_provider(provider_name: str):
    if provider_name not in providers:
        raise HTTPException(status_code=400, detail=f"Provider {provider_name} not supported")
    
    await providers[provider_name].reset()
    return {"status": "success", "message": f"Provider {provider_name} reset successfully"}

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    model_name = request.model.lower()
    
    provider_name = None
    if "gpt" in model_name or "chatgpt" in model_name:
        provider_name = "chatgpt"
    elif "gemini" in model_name:
        provider_name = "gemini"
    elif "grok" in model_name:
        provider_name = "grok"
    else:
        raise HTTPException(status_code=400, detail=f"Model {request.model} not supported")
    
    provider = providers[provider_name]
    
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty")
    
    last_user_message = next((m for m in reversed(request.messages) if m.role == "user"), None)
    
    if not last_user_message:
        raise HTTPException(status_code=400, detail="No user message found in the request")
    
    system_prompt = None
    for msg in request.messages:
        if msg.role == "system":
            system_prompt = msg.content
            break
    
    prompt_request = PromptRequest(
        prompt=last_user_message.content,
        system_prompt=system_prompt,
        new_chat=False
    )
    
    try:
        async with provider.lock:
            response = await provider.send_prompt(prompt_request)
        prompt_tokens = math.ceil(len(prompt_request.prompt) / 4)
        completion_tokens = math.ceil(len(response) / 4)

        return APIResponse(
            id=f"chatcmpl-{uuid.uuid4()}",
            created=int(time.time()),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content=response),
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
