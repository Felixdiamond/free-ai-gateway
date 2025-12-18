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
        self.url = "https://chatgpt.com" # Updated URL

    async def ensure_active(self):
        if not self.tab:
            self.tab = await BrowserManager.get_new_tab(self.url)
        else:
            # Check if tab is still alive/valid?
            pass
        
        # Initial check for challenges
        try:
            await self.tab.cf_verify()
        except Exception:
            pass # Maybe not present or failed, continue

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
            if await self.tab.find(pattern, timeout=1):
                return error_class(message, details)
        return None

    async def handle_continue_prompt(self) -> bool:
        try:
            stay_logged_out = await self.tab.find("Stay logged out", timeout=2)
            if stay_logged_out:
                await stay_logged_out.click()
                return True
        except Exception:
            pass
        return False

    async def simulate_human_input(self, element, text: str):
        for chunk in [text[i:i+random.randint(5, 15)] for i in range(0, len(text), 10)]:
            await element.send_keys(chunk)
            await asyncio.sleep(random.uniform(0.01, 0.05))

    async def detect_response_completion(self):
        try:

            # Check if there's a "continue generating" button and click it
            if continue_btn := await self.tab.find("Continue generating", timeout=2):
                await continue_btn.click()

            # Wait for the copy button which indicates completion
            await self.tab.wait_for(selector='[aria-label="Copy"]', timeout=120)
            
            # Extra checks since ChatGPT might update dynamically
            stable_count = 0
            last_text = ""
            check_start_time = time.time()
            
            while stable_count < 3:
                # Safety timeout for the stability check loop
                if time.time() - check_start_time > 30:
                    break

                response_divs = await self.tab.select_all("div.markdown.prose")
                if not response_divs:
                    await asyncio.sleep(1)
                    continue

                # Use text_all to get full content including children
                current_text = response_divs[-1].text_all

                if not current_text:
                    await asyncio.sleep(1)
                    continue
                
                stripped_text = current_text.strip()
                
                # Check if text is stable and non-empty
                if current_text == last_text and stripped_text:
                    stable_count += 1
                else:
                    stable_count = 0
                    last_text = current_text
                
                await asyncio.sleep(0.5)

            return last_text
        except Exception as e:
            logger.error(f"Error detecting response: {e}")
            return ""

    async def send_prompt(self, request: PromptRequest) -> str:
        await self.ensure_active()
        
        if request.new_chat:
            await self.tab.reload()
            await asyncio.sleep(2)

        # Check errors
        if error := await self.check_for_errors():
            raise error

        await self.handle_continue_prompt()

        # Input
        textarea = await self.tab.select("#prompt-textarea", timeout=10)
        await textarea.clear_input()
        
        full_prompt = request.prompt
        if request.system_prompt:
            full_prompt = f"{request.system_prompt}\n\n{request.prompt}"

        await self.simulate_human_input(textarea, full_prompt)
        
        # Send
        submit_button = await self.tab.select('[aria-label="Send prompt"]', timeout=5)
        await submit_button.click()

        # Wait for response
        response = await self.detect_response_completion()
        return response
