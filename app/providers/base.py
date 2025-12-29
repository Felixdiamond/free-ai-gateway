from abc import ABC, abstractmethod
from app.models import PromptRequest
from app.core.config import settings
from typing import Optional, TYPE_CHECKING
import asyncio
import time
import logging

if TYPE_CHECKING:
    from app.core.tab_manager import ManagedTab

logger = logging.getLogger(__name__)

class BaseProvider(ABC):
    """Base class for AI providers using managed tabs."""
    
    def __init__(self):
        self.url: str = ""
        self.response_selector: str = ""
        self.copy_button_selector: str = ""

    @abstractmethod
    async def send_prompt(self, managed_tab: "ManagedTab", request: PromptRequest) -> str:
        """Send a prompt using the managed tab and return the response text."""
        pass

    @abstractmethod
    async def prepare_tab(self, managed_tab: "ManagedTab"):
        """Prepare a tab for use (e.g., wait for page load, handle popups)."""
        pass

    async def wait_for_stable_content(self, tab, selector: str, timeout: int = None) -> str:
        """Wait for content to stabilize and return the stable text."""
        if timeout is None:
            timeout = settings.TIMEOUT_STABLE_CONTENT
            
        stable_count = 0
        last_text = ""
        check_start_time = time.time()
        
        while stable_count < 3:
            if time.time() - check_start_time > timeout:
                break

            try:
                elements = await tab.select_all(selector)
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
            except Exception:
                pass
            
            await asyncio.sleep(0.1)

        return last_text

    async def wait_for_new_message(self, tab, selector: str, target_count: int, timeout: int = 10):
        """Wait for a new message to appear."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                elements = await tab.select_all(selector)
                if len(elements) >= target_count:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return False

    async def count_messages(self, tab, selector: str) -> int:
        """Count existing messages on the page."""
        try:
            elements = await tab.select_all(selector, timeout=settings.TIMEOUT_ELEMENT_CHECK)
            return len(elements)
        except Exception:
            return 0

    def format_prompt(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Format prompt with optional system instructions."""
        if not system_prompt:
            return prompt
        return f"Context: {system_prompt}. Task: {prompt}"

    def _is_transient_ws_error(self, e: Exception) -> bool:
        """Detect transient websocket/devtools disconnect errors."""
        msg = str(e).lower()
        return (
            "no close frame received or sent" in msg
            or "websocket" in msg
            or "connection closed" in msg
            or "target closed" in msg
            or "session closed" in msg
        )
