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

    async def detect_response_completion(self):
        try:
            # Wait for the copy button which indicates completion
            await self.tab.wait_for(selector='button[aria-label="Copy"]', timeout=120)
            
            stable_count = 0
            last_text = ""
            check_start_time = time.time()
            
            while stable_count < 3:
                if time.time() - check_start_time > 30:
                    break

                # Selector based on the user provided HTML
                response_divs = await self.tab.select_all(".response-content-markdown")
                if not response_divs:
                    await asyncio.sleep(1)
                    continue
                
                # Use text_all to get full content including children
                current_text = response_divs[-1].text_all

                if not current_text:
                    await asyncio.sleep(1)
                    continue
                
                stripped_text = current_text.strip()
                
                if current_text == last_text and stripped_text:
                    stable_count += 1
                else:
                    stable_count = 0
                    last_text = current_text
                
                await asyncio.sleep(0.5)

            return last_text
        except Exception as e:
            logger.error(f"Error detecting Grok response: {e}")
            return ""

    async def send_prompt(self, request: PromptRequest) -> str:
        await self.ensure_active()
        
        if request.new_chat:
            await self.tab.reload()
            await asyncio.sleep(2)

        # Grok selectors
        input_box = await self.tab.select("textarea", timeout=10)
        if not input_box:
            input_box = await self.tab.find("Ask Grok", best_match=True)

        if not input_box:
            raise ProviderError("Could not find Grok input box")

        await input_box.click()
        await input_box.send_keys(request.prompt)
        
        # Send using the specific submit button selector
        try:
            submit_button = await self.tab.select('button[aria-label="Submit"]', timeout=5)
            await submit_button.click()
        except Exception:
            # Fallback to Enter key if button not found
            await input_box.send_keys("\n")
        
        return await self.detect_response_completion()
