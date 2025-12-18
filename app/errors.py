from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class ProviderError(Exception):
    """Base class for Provider-related exceptions"""
    message: str
    details: Optional[Dict[str, Any]] = None

    def __str__(self):
        return f"{self.message} - Details: {self.details}" if self.details else self.message

class ResponseTimeoutError(ProviderError):
    pass

class ContentFilterError(ProviderError):
    pass

class BrowserError(ProviderError):
    pass

class MessageTooLongError(ProviderError):
    pass

class LoginPromptError(ProviderError):
    pass

class AuthError(ProviderError):
    pass
