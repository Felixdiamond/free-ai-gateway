import asyncio
import logging
import time
from app.providers.base import BaseProvider
from app.models import PromptRequest
from app.core.config import settings
from app.errors import ProviderError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.tab_manager import ManagedTab

logger = logging.getLogger(__name__)

class GeminiProvider(BaseProvider):
    def __init__(self):
        super().__init__()
        self.url = settings.GEMINI_URL
        self.response_selector = ".markdown.markdown-main-panel"
        self.copy_button_selector = 'button[data-test-id="copy-button"]'

    async def prepare_tab(self, managed_tab: "ManagedTab"):
        """Prepare a Gemini tab for use."""
        tab = managed_tab.tab
        await asyncio.sleep(0.5)
        try:
            await tab.select("div[contenteditable='true']", timeout=5)
        except Exception:
            pass

    async def detect_response_completion(self, tab, target_count: int = 0):
        """Wait for Gemini response to complete."""
        try:
            if target_count > 0:
                await self.wait_for_new_message(tab, self.response_selector, target_count)

            await tab.wait_for(selector=self.copy_button_selector, timeout=settings.TIMEOUT_RESPONSE)
            return await self.wait_for_stable_content(tab, self.response_selector)
        except Exception as e:
            logger.error(f"Error detecting Gemini response: {e}")
            return ""

    async def send_prompt(self, managed_tab: "ManagedTab", request: PromptRequest) -> str:
        """Send a prompt to Gemini and return the response."""
        tab = managed_tab.tab
        
        for attempt in range(2):
            try:
                target_count = await self.count_messages(tab, self.response_selector) + 1

                input_box = await tab.select("div[contenteditable='true']", timeout=settings.TIMEOUT_INPUT)
                if not input_box:
                    input_box = await tab.find("Enter a prompt here", best_match=True)

                if not input_box:
                    raise ProviderError("Could not find Gemini input box")

                await input_box.click()
                await input_box.send_keys(self.format_prompt(request.prompt, request.system_prompt))
                
                send_button = await tab.select("button[aria-label*='Send']", timeout=settings.TIMEOUT_BUTTON)
                if not send_button:
                    send_button = await tab.find("Send", best_match=True)
                    
                if send_button:
                    async with tab.expect_response(".*batchexecute.*"):
                        await send_button.click()
                else:
                    await input_box.send_keys("\n")

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
