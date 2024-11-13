from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from contextlib import asynccontextmanager
import nodriver as driver
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import time


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class PromptRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    timeout: int = Field(default=300, ge=30, le=600)
    stream: bool = False
    new_chat: bool = Field(default=False, description="Force start a new chat")

    @validator("prompt")
    def validate_prompt_length(cls, v):
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        if len(v) > 4096:
            raise ValueError("Prompt exceeds maximum length of 4096 characters")
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
    model: str = "chatgpt-free"
    choices: List[Choice]
    usage: Usage


class BrowserState:
    def __init__(self):
        self.browser = None
        self.tab = None
        self.last_reset = time.time()
        self.request_count = 0
        self.max_requests = 25
        self.lock = asyncio.Lock()
        self.last_error = None
        self.error_count = 0
        self.max_errors = 3
        self.last_request_time = time.time()
        self.min_request_interval = 2.0

    async def get_browser(self):
        async with self.lock:
            current_time = time.time()
            if current_time - self.last_reset > 3600:
                await self.reset()
            elif not self.browser or not self.tab:
                await self.reset()
            return self.browser, self.tab

    async def increment_request(self):
        async with self.lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time

            if time_since_last_request < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last_request)

            self.request_count += 1
            self.last_request_time = time.time()

            if self.request_count >= self.max_requests:
                await self.reset()

    async def handle_error(self, error: Exception):
        async with self.lock:
            self.error_count += 1
            self.last_error = {
                "time": datetime.now().isoformat(),
                "error": str(error),
                "type": error.__class__.__name__,
            }

            if self.error_count >= self.max_errors:
                await self.reset()
                self.error_count = 0
                self.last_error = None

    async def reset(self):
        try:
            if self.browser:
                await self.browser.close()

            config = driver.Config(
                headless=False,
            )
            self.browser = await driver.start(config=config)
            self.tab = await browser_setup(self.browser)
            self.last_reset = time.time()
            self.request_count = 0
            logger.info("Browser state reset successfully")
        except Exception as e:
            logger.error(f"Failed to reset browser state: {e}")
            raise


browser_state = BrowserState()


async def browser_setup(browser):
    try:
        logger.info("Setting up browser...")
        tab = await browser.get("https://chatgpt.com")
        await handle_initial_setup(tab)
        return tab
    except Exception as e:
        logger.error(f"Browser setup failed: {e}")
        raise


async def handle_initial_setup(tab):
    """Handle various initial setup dialogs and popups"""
    try:
        for _ in range(3):
            try:
                trial_btn = await tab.find("Try it first", timeout=2)
                if trial_btn:
                    logger.info("Found 'Try it first' button")
                    await trial_btn.click()
                    await asyncio.sleep(1)
                    break
            except Exception:
                await asyncio.sleep(1)
        return True
    except Exception as e:
        logger.warning(f"Non-critical error in initial setup: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await browser_state.reset()
        logger.info("Application startup complete")
        yield
    finally:
        if browser_state.browser:
            await browser_state.browser.close()
        logger.info("Application shutdown complete")


app = FastAPI(
    title="ChatGPT API",
    description="A FastAPI application for interacting with ChatGPT",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def estimate_tokens(text: str) -> int:
    return len(text.encode("utf-8")) // 4


async def generate_response_object(prompt: str, response: str) -> APIResponse:
    prompt_tokens = estimate_tokens(prompt)
    completion_tokens = estimate_tokens(response)

    return APIResponse(
        id=f"chatcmpl-{int(time.time()*1000)}",
        created=int(time.time()),
        choices=[
            Choice(
                index=0,
                message=Message(role="assistant", content=response),
                finish_reason="stop",
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


@app.post("/v1/chat/completions", response_model=APIResponse)
async def create_completion(prompt_request: PromptRequest):
    try:
        browser, tab = await browser_state.get_browser()
        await browser_state.increment_request()

        from main import fetch_response

        logger.info(f"Processing prompt request: {len(prompt_request.prompt)} chars")
        response = await fetch_response(
            prompt=prompt_request.prompt,
            system_prompt=prompt_request.system_prompt,
            browser=browser,
            tab=tab,
            timeout=prompt_request.timeout,
            new_chat=prompt_request.new_chat,
        )

        return await generate_response_object(prompt_request.prompt, response)

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        await browser_state.handle_error(e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": str(e),
                    "type": type(e).__name__,
                    "code": "processing_error",
                    "timestamp": datetime.now().isoformat(),
                }
            },
        )



@app.get("/health")
async def health_check():
    browser, tab = await browser_state.get_browser()
    return {
        "status": "havent found implementation yet :)",
        "uptime": time.time() - browser_state.last_reset,
        "last_reset": datetime.fromtimestamp(browser_state.last_reset).isoformat(),
        "request_count": browser_state.request_count,
        "last_error": browser_state.last_error,
        "error_count": browser_state.error_count,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app, host="0.0.0.0", port=8000, log_level="info", reload=False, workers=1
    )
