from abc import ABC, abstractmethod
from app.models import PromptRequest
import asyncio

class BaseProvider(ABC):
    def __init__(self):
        self.lock = asyncio.Lock()

    @abstractmethod
    async def send_prompt(self, request: PromptRequest) -> str:
        """Send a prompt to the provider and return the response text."""
        pass

    @abstractmethod
    async def ensure_active(self):
        """Ensure the provider's session/tab is active and ready."""
        pass

    async def reset(self):
        """Reset the provider session."""
        if hasattr(self, 'tab') and self.tab:
            try:
                await self.tab.close()
            except Exception:
                pass
        self.tab = None
