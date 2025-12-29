import asyncio
import logging
import random
import time
from app.providers.base import BaseProvider
from app.models import PromptRequest
from app.core.browser import BrowserManager
from app.errors import (
    ProviderError, ResponseTimeoutError, ContentFilterError, 
    BrowserError, MessageTooLongError, LoginPromptError
)
from app.utils import html_to_markdown
from typing import Optional

logger = logging.getLogger(__name__)

class ChatGPTProvider(BaseProvider):
    def __init__(self):
        super().__init__()
        self.tab = None
        self.url = "https://chatgpt.com"

    async def ensure_active(self):
        if not self.tab:
            self.tab = await BrowserManager.get_new_tab(self.url)
            await asyncio.sleep(0.5)
            try:
                await self.tab.verify_cf()
            except Exception:
                pass

    async def check_for_errors(self) -> Optional[ProviderError]:
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
                if await self.tab.find(pattern, timeout=0.2, best_match=True):
                    logger.warning(f"Error pattern detected: {pattern}")
                    return error_class(message, details)
            except Exception:
                continue
        return None

    async def handle_continue_prompt(self) -> bool:
        try:
            stay_logged_out = await self.tab.find("Stay logged out", timeout=2, best_match=True)
            if stay_logged_out:
                await stay_logged_out.click()
                logger.info("Clicked 'Stay logged out' button")
                return True
        except Exception as e:
            logger.debug(f"No 'Stay logged out' prompt found: {e}")
        return False

    async def detect_response_completion(self, min_message_count: int = 0):
        try:
            if min_message_count > 0:
                start_time = time.time()
                while time.time() - start_time < 10:
                    elements = await self.tab.select_all("div.markdown.prose")
                    if len(elements) >= min_message_count:
                        break
                    await asyncio.sleep(0.5)

            try:
                if continue_btn := await self.tab.find("Continue generating", timeout=0.5, best_match=True):
                    await continue_btn.click()
            except Exception:
                pass

            await self.tab.wait_for(selector='[aria-label="Copy"]', timeout=120)
            return await self.wait_for_stable_content("div.markdown.prose")
        except Exception as e:
            logger.error(f"Error detecting response: {e}")
            return ""

    async def send_prompt(self, request: PromptRequest) -> str:
        for attempt in range(2):
            try:
                await self.ensure_active()
                
                if request.new_chat:
                    await self.tab.reload()
                    await asyncio.sleep(2)

                error = await self.check_for_errors()
                if error:
                    raise error

                await self.handle_continue_prompt()

                try:
                    existing_messages = await self.tab.select_all("div.markdown.prose", timeout=1)
                    target_message_count = len(existing_messages) + 1
                except Exception:
                    target_message_count = 1

                textarea = await self.tab.select("#prompt-textarea", timeout=10)
                await textarea.clear_input()
                
                full_prompt = self.format_prompt(request.prompt, request.system_prompt)
                await textarea.send_keys(full_prompt)
                
                submit_button = await self.tab.select('[aria-label="Send prompt"]', timeout=5)
                
                async with self.tab.expect_response(".*conversation.*"):
                    await submit_button.click()

                response = await self.detect_response_completion(target_message_count)
                return response
            except Exception as e:
                if self._is_transient_ws_error(e) and attempt == 0:
                    await self.reset()
                    await asyncio.sleep(0.2)
                    continue
                raise
        raise ProviderError("Transient browser error. Please retry.")
