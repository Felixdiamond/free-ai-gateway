import asyncio
import logging
import time
from app.providers.base import BaseProvider
from app.models import PromptRequest
from app.core.browser import BrowserManager
from app.errors import ProviderError

logger = logging.getLogger(__name__)

class GrokProvider(BaseProvider):
    def __init__(self):
        super().__init__()
        self.tab = None
        self.url = "https://grok.com"

    async def ensure_active(self):
        if not self.tab:
            self.tab = await BrowserManager.get_new_tab(self.url)
            await asyncio.sleep(2)
            try:
                await self.tab.select("textarea", timeout=15)
            except Exception:
                pass

    async def detect_response_completion(self, min_message_count: int = 0):
        try:
            if min_message_count > 0:
                start_time = time.time()
                while time.time() - start_time < 10:
                    elements = await self.tab.select_all(".response-content-markdown")
                    if len(elements) >= min_message_count:
                        break
                    await asyncio.sleep(0.5)

            await self.tab.wait_for(selector='button[aria-label="Copy"]', timeout=120)
            return await self.wait_for_stable_content(".response-content-markdown")
        except Exception as e:
            logger.error(f"Error detecting Grok response: {e}")
            return ""

    async def send_prompt(self, request: PromptRequest) -> str:
        for attempt in range(2):
            try:
                await self.ensure_active()
                
                if request.new_chat:
                    await self.tab.reload()
                    await asyncio.sleep(2)

                try:
                    existing_messages = await self.tab.select_all(".response-content-markdown", timeout=1)
                    target_message_count = len(existing_messages) + 1
                except Exception:
                    target_message_count = 1

                # Try to find the input box with various selectors, prioritizing the rich text editor
                input_box = await self.tab.select("textarea", timeout=3)
                
                if not input_box:
                    input_box = await self.tab.select("div.ProseMirror", timeout=3)
                
                if not input_box:
                    input_box = await self.tab.select("div[contenteditable='true']", timeout=3)
                
                if not input_box:
                    input_box = await self.tab.find("What do you want to know?", best_match=True)
                
                if not input_box:
                    input_box = await self.tab.find("How can Grok help?", best_match=True)

                if not input_box:
                    raise ProviderError("Could not find Grok input box")

                await input_box.click()
                await asyncio.sleep(0.2)
                await input_box.send_keys(self.format_prompt(request.prompt, request.system_prompt))
                
                try:
                    submit_button = await self.tab.select('button[aria-label="Submit"]', timeout=5)
                    async with self.tab.expect_response(".*completion.*"):
                        await submit_button.click()
                except Exception:
                    await input_box.send_keys("\n")
                
                return await self.detect_response_completion(target_message_count)
            except Exception as e:
                if self._is_transient_ws_error(e) and attempt == 0:
                    await self.reset()
                    await asyncio.sleep(0.2)
                    continue
                raise
        raise ProviderError("Transient browser error. Please retry.")
