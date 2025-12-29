import asyncio
import logging
import time
from app.providers.base import BaseProvider
from app.models import PromptRequest
from app.core.config import settings
from app.errors import (
    ProviderError, ContentFilterError, 
    BrowserError, MessageTooLongError, LoginPromptError
)
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.tab_manager import ManagedTab

logger = logging.getLogger(__name__)

class ChatGPTProvider(BaseProvider):
    def __init__(self):
        super().__init__()
        self.url = settings.CHATGPT_URL
        self.response_selector = "div.markdown.prose"
        self.copy_button_selector = '[aria-label="Copy"]'

    async def prepare_tab(self, managed_tab: "ManagedTab"):
        """Prepare a ChatGPT tab for use."""
        tab = managed_tab.tab
        await asyncio.sleep(0.5)
        try:
            await tab.verify_cf()
        except Exception:
            pass

    async def check_for_errors(self, tab) -> Optional[ProviderError]:
        """Check for error messages on the page."""
        error_patterns = {
            "This content may violate our usage policies": (ContentFilterError, "Content filter triggered", {"type": "content_filter"}),
            "Get smarter responses": (BrowserError, "Rate limit reached", {"type": "rate_limit"}),
            "Something went wrong": (BrowserError, "System error", {"type": "system_error"}),
            "Too many requests": (BrowserError, "Rate limit exceeded", {"type": "rate_limit"}),
            "Message too long": (MessageTooLongError, "Message too long", {"type": "length_limit"}),
            "Thanks for trying ChatGPT": (LoginPromptError, "Login prompt detected", {"type": "auth_required"}),
        }

        for pattern, (error_class, message, details) in error_patterns.items():
            try:
                if await tab.find(pattern, timeout=0.2, best_match=True):
                    logger.warning(f"Error pattern detected: {pattern}")
                    return error_class(message, details)
            except Exception:
                continue
        return None

    async def handle_continue_prompt(self, tab) -> bool:
        """Handle the 'Stay logged out' prompt."""
        try:
            stay_logged_out = await tab.find("Stay logged out", timeout=2, best_match=True)
            if stay_logged_out:
                await stay_logged_out.click()
                logger.info("Clicked 'Stay logged out' button")
                return True
        except Exception as e:
            logger.debug(f"No 'Stay logged out' prompt found: {e}")
        return False

    async def detect_response_completion(self, tab, target_count: int = 0):
        """Wait for ChatGPT response to complete."""
        try:
            if target_count > 0:
                await self.wait_for_new_message(tab, self.response_selector, target_count)

            try:
                if continue_btn := await tab.find("Continue generating", timeout=0.5, best_match=True):
                    await continue_btn.click()
            except Exception:
                pass

            await tab.wait_for(selector=self.copy_button_selector, timeout=settings.TIMEOUT_RESPONSE)
            return await self.wait_for_stable_content(tab, self.response_selector)
        except Exception as e:
            logger.error(f"Error detecting response: {e}")
            return ""

    async def send_prompt(self, managed_tab: "ManagedTab", request: PromptRequest) -> str:
        """Send a prompt to ChatGPT and return the response."""
        tab = managed_tab.tab
        
        for attempt in range(2):
            try:
                error = await self.check_for_errors(tab)
                if error:
                    raise error

                await self.handle_continue_prompt(tab)

                target_count = await self.count_messages(tab, self.response_selector) + 1

                textarea = await tab.select("#prompt-textarea", timeout=settings.TIMEOUT_INPUT)
                await textarea.clear_input()
                
                full_prompt = self.format_prompt(request.prompt, request.system_prompt)
                await textarea.send_keys(full_prompt)
                
                submit_button = await tab.select('[aria-label="Send prompt"]', timeout=settings.TIMEOUT_BUTTON)
                
                async with tab.expect_response(".*conversation.*"):
                    await submit_button.click()

                response = await self.detect_response_completion(tab, target_count)
                managed_tab.message_count += 1
                return response
                
            except Exception as e:
                if self._is_transient_ws_error(e) and attempt == 0:
                    logger.warning(f"Transient error, retrying: {e}")
                    await asyncio.sleep(0.5)
                    continue
                raise
        
        raise ProviderError("Transient browser error. Please retry.")
