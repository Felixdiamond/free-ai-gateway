import asyncio
import logging
import time
from app.providers.base import BaseProvider
from app.models import PromptRequest
from app.core.browser import BrowserManager
from app.errors import ProviderError

logger = logging.getLogger(__name__)

class GeminiProvider(BaseProvider):
    def __init__(self):
        super().__init__()
        self.tab = None
        self.url = "https://gemini.google.com/app"

    async def ensure_active(self):
        if not self.tab:
            self.tab = await BrowserManager.get_new_tab(self.url)
            await asyncio.sleep(2) # Wait for load
            
            # Handle potential "Sign in" or "Welcome" modals if possible
            # For "free taste", it might just work.
            try:
                # Try to find input to verify we are ready
                await self.tab.select("div[contenteditable='true']", timeout=5)
            except Exception:
                logger.warning("Could not find Gemini input immediately.")

    async def detect_response_completion(self):
        try:
            # Wait for the copy button which indicates completion
            # Using data-test-id as it is more reliable based on user provided HTML
            await self.tab.wait_for(selector='button[data-test-id="copy-button"]', timeout=120)
            
            stable_count = 0
            last_text = ""
            check_start_time = time.time()
            
            while stable_count < 3:
                if time.time() - check_start_time > 30:
                    break

                # Selector based on the user provided image
                response_divs = await self.tab.select_all(".markdown.markdown-main-panel")
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
            logger.error(f"Error detecting Gemini response: {e}")
            return ""

    async def send_prompt(self, request: PromptRequest) -> str:
        await self.ensure_active()
        
        if request.new_chat:
            await self.tab.reload()
            await asyncio.sleep(2)

        # Find input
        # Gemini usually uses a contenteditable div
        input_box = await self.tab.select("div[contenteditable='true']", timeout=10)
        if not input_box:
             # Fallback: try finding by placeholder text
            input_box = await self.tab.find("Enter a prompt here", best_match=True)

        if not input_box:
            raise ProviderError("Could not find Gemini input box")

        await input_box.click()
        await input_box.send_keys(request.prompt)
        
        # Find send button
        send_button = await self.tab.select("button[aria-label*='Send']", timeout=5)
        if not send_button:
             # Fallback
            send_button = await self.tab.find("Send", best_match=True)
            
        if send_button:
            await send_button.click()
        else:
            # Maybe enter key works?
            await input_box.send_keys("\n")

        return await self.detect_response_completion()
