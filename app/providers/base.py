from abc import ABC, abstractmethod
from app.models import PromptRequest
from typing import Optional
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

class BaseProvider(ABC):
    def __init__(self):
        self.lock = asyncio.Lock()
        self.tab = None
        self.url = None

    @abstractmethod
    async def send_prompt(self, request: PromptRequest) -> str:
        """Send a prompt to the provider and return the response text."""
        pass

    @abstractmethod
    async def ensure_active(self):
        """Ensure the provider's tab pool is active and ready."""
        pass

    async def wait_for_stable_content(self, selector: str, timeout: int = 30) -> str:
        """Wait for content to stabilize and return the stable text."""
        stable_count = 0
        last_text = ""
        check_start_time = time.time()
        
        while stable_count < 3:
            if time.time() - check_start_time > timeout:
                break

            elements = await self.tab.select_all(selector)
            if not elements:
                await asyncio.sleep(0.1)
                continue

            current_text = elements[-1].text_all
            if not current_text:
                await asyncio.sleep(0.1)
                continue
            
            if current_text == last_text and current_text.strip():
                stable_count += 1
            else:
                stable_count = 0
                last_text = current_text
            
            await asyncio.sleep(0.1)

        return last_text

    def format_prompt(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Format prompt with optional system instructions using light prompt engineering."""
        if not system_prompt:
            return prompt
        
        return f"Context: {system_prompt}. Task: {prompt}"

    async def reset(self):
        """Reset the provider session."""
        if hasattr(self, 'tab') and self.tab:
            try:
                await self.tab.close()
            except Exception:
                pass
        self.tab = None

    def _is_transient_ws_error(self, e: Exception) -> bool:
        """Detect transient websocket/devtools disconnect errors to allow a one-time retry."""
        msg = str(e).lower()
        return (
            "no close frame received or sent" in msg
            or "websocket" in msg
            or "connection closed" in msg
            or "target closed" in msg
            or "session closed" in msg
        )
