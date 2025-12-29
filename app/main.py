from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models import PromptRequest, ChatCompletionRequest, APIResponse, Choice, Message, Usage
from app.core.browser import BrowserManager
from app.core.tab_manager import TabManager
from app.providers.chatgpt import ChatGPTProvider
from app.providers.gemini import GeminiProvider
from app.providers.grok import GrokProvider
import uuid
import time
import logging
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

providers = {
    "chatgpt": ChatGPTProvider(),
    "gemini": GeminiProvider(),
    "grok": GrokProvider(),
}

tab_manager = TabManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    await BrowserManager.get_browser()
    
    for name, provider in providers.items():
        tab_manager.register_provider(name, provider.url)
    
    tab_manager.start_cleanup_task()
    
    logger.info("Application started with tab management enabled")
    
    yield
    
    await tab_manager.shutdown()
    await BrowserManager.close()
    logger.info("Application shutdown complete")

app = FastAPI(title="Free AI Gateway", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    """Reset a provider's tabs (close all tabs for this provider)."""
    if provider_name not in providers:
        raise HTTPException(status_code=400, detail=f"Provider {provider_name} not supported")
    
    await tab_manager.close_provider_tabs(provider_name)
    return {"status": "success", "message": f"Provider {provider_name} tabs reset successfully"}

@app.get("/v1/sessions/{session_id}/status")
async def session_status(session_id: str):
    """Get status of a session's tabs across all providers."""
    status = tab_manager.get_session_status(session_id)
    return {"session_id": session_id, "tabs": status}

@app.delete("/v1/sessions/{session_id}")
async def close_session(session_id: str):
    """Close all tabs for a specific session."""
    await tab_manager.close_session_tabs(session_id)
    return {"status": "success", "message": f"Session {session_id} closed"}

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
        new_chat=request.new_chat if hasattr(request, 'new_chat') else False
    )
    
    managed_tab = None
    try:
        managed_tab = await tab_manager.acquire_tab(provider_name, request.session_id)
        
        if prompt_request.new_chat:
            await tab_manager.reload_tab(managed_tab)
        
        if managed_tab.message_count == 0:
            await provider.prepare_tab(managed_tab)
        
        async with managed_tab.lock:
            response = await provider.send_prompt(managed_tab, prompt_request)
        
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
    finally:
        if managed_tab:
            await tab_manager.release_tab(managed_tab)

@app.get("/health")
async def health_check():
    """Health check endpoint with tab stats."""
    stats = tab_manager.get_stats()
    return {
        "status": "healthy",
        "tab_stats": stats
    }
