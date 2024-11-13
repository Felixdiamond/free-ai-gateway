import asyncio
import logging
import time
import random
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ChatGPTError(Exception):
    """Base class for ChatGPT-related exceptions"""

    message: str
    details: Optional[Dict[str, Any]] = None

    def __str__(self):
        return (
            f"{self.message} - Details: {self.details}"
            if self.details
            else self.message
        )


class KeyErrorFilter(logging.Filter):
    def filter(self, record):
        return "DOM.scrollableFlagUpdated" not in record.getMessage()


class ResponseTimeoutError(ChatGPTError):
    """Raised when response timeout occurs"""

    pass


class ContentFilterError(ChatGPTError):
    """Raised when content filter is triggered"""

    print("Inappropriate content! (according to openai)")
    pass


class BrowserError(ChatGPTError):
    """Raised when browser-related errors occur"""

    pass


class MessageTooLongError(ChatGPTError):
    """Raised when message exceeds length limits"""

    pass


class LoginPromptError(ChatGPTError):
    """Raised when login prompt is detected"""

    pass


logging.getLogger("uc.connection").addFilter(KeyErrorFilter())
logger = logging.getLogger(__name__)


# Enhanced error detection
async def check_for_errors(tab) -> Optional[ChatGPTError]:
    """Check for common error conditions"""
    error_patterns = {
        "This content may violate our usage policies": (
            ContentFilterError,
            "Content filter triggered",
            {"type": "content_filter", "severity": "high"},
        ),
        "Get smarter responses": (
            BrowserError,
            "Rate limit reached",
            {"type": "rate_limit", "retry_after": 60},
        ),
        "Something went wrong": (
            BrowserError,
            "Network or system error detected",
            {"type": "system_error", "recoverable": True},
        ),
        "Too many requests": (
            BrowserError,
            "Rate limit exceeded",
            {"type": "rate_limit", "retry_after": 300},
        ),
        "Please wait": (
            BrowserError,
            "Temporary throttling",
            {"type": "throttling", "retry_after": 30},
        ),
        "Message too long": (
            MessageTooLongError,
            "Message exceeds length limit",
            {"type": "length_limit", "max_length": 4096},
        ),
        "Thanks for trying ChatGPT": (
            LoginPromptError,
            "Login prompt detected",
            {"type": "auth_required", "recoverable": True},
        ),
    }

    try:
        for pattern, (error_class, message, details) in error_patterns.items():
            if await tab.find(pattern, timeout=1):
                return error_class(message, details)

        submit_button = await tab.select('[aria-label="Send prompt"]', timeout=1)
        if submit_button and not "disabled" in submit_button.attributes:
            return MessageTooLongError(
                "Message too long - submit button disabled",
                {"type": "length_limit", "button_state": "disabled"},
            )
    except Exception as e:
        logger.debug(f"Error check failed: {e}")
    return None


async def handle_continue_prompt(tab) -> bool:
    """Handle the 'Stay logged out' prompt"""
    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            logger.debug("Searching for 'Stay logged out' link...")
            stay_logged_out = await tab.find("Stay logged out", timeout=2)
            if stay_logged_out:
                logger.info("Found 'Stay logged out' link, clicking...")
                await stay_logged_out.click()
                await asyncio.sleep(1)
                return True
        except Exception as e:
            logger.debug(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
    return False


async def clear_conversation(tab, force: bool = False) -> bool:
    """Clear conversation history"""
    try:
        await tab.reload()
        return True
    except Exception as e:
        logger.warning(f"Failed to clear conversation: {e}")
        return False


async def simulate_human_input(textarea, text: str):
    """Simulate natural typing"""
    text_length = len(text)
    base_chunk_size = min(max(text_length // 15, 5), 30)

    pause_probability = 0.1
    max_pause_duration = 0.5

    while text:
        chunk_size = random.randint(max(1, base_chunk_size - 5), base_chunk_size + 5)
        chunk = text[:chunk_size]
        text = text[chunk_size:]

        typing_speed = random.uniform(0.03, 0.12)
        await textarea.send_keys(chunk)
        await asyncio.sleep(typing_speed)

        if random.random() < pause_probability:
            await asyncio.sleep(random.uniform(0.1, max_pause_duration))


def html_to_markdown(tag_name: str, text: str) -> str:
    """
    Convert HTML elements to their markdown equivalents
    """
    markdown_mappings = {
        "h1": f"# {text}",
        "h2": f"## {text}",
        "h3": f"### {text}",
        "h4": f"#### {text}",
        "h5": f"##### {text}",
        "h6": f"###### {text}",
        "p": text,
        "strong": f"**{text}**",
        "b": f"**{text}**",
        "em": f"*{text}*",
        "i": f"*{text}*",
        "code": f"`{text}`",
        "pre": f"```\n{text}\n```",
        "blockquote": f"> {text}",
        "li": f"- {text}",
        "a": lambda text, href: f"[{text}]({href})",
        "hr": "---",
        "del": f"~~{text}~~",
        "sup": f"^{text}^",
        "sub": f"~{text}~",
    }

    return markdown_mappings.get(tag_name.lower(), text)


async def detect_response_completion(tab):
    """
    Detect response completion by waiting for the copy button and getting all content
    from the last markdown prose div
    """
    try:
        logger.info("Waiting for response completion")
        await tab.wait_for(selector='[aria-label="Copy"]')

        response_divs = await tab.query_selector_all("div.markdown.prose")
        if not response_divs:
            return ""

        last_response_div = response_divs[-1]

        formatted_response = []
        current_list = []
        list_type = None

        async def process_element(element):
            """Process HTML element and convert to markdown format"""
            tag_name = element.tag_name.lower()
            text = element.text.strip() if element.text else ""

            if tag_name in ["strong", "em", "b", "i"]:
                markdown_text = html_to_markdown(tag_name, text)
                return markdown_text

            if tag_name in ["ul", "ol"]:
                nested_elements = await element.query_selector_all("li")
                nested_text = []
                for i, li in enumerate(nested_elements, 1):
                    li_text = li.text.strip()
                    if tag_name == "ol":
                        nested_text.append(f"{i}. {li_text}")
                    else:
                        nested_text.append(f"- {li_text}")
                return "\n".join(nested_text) + "\n"

            if tag_name == "a":
                href = element.attrs.get("href", "")
                return f"[{text}]({href})"

            if tag_name == "pre":
                code_element = await element.query_selector("code")
                if code_element:
                    language_class = code_element.attrs.get("class", "")
                    language = (
                        language_class.replace("language-", "")
                        if language_class
                        else ""
                    )
                    code_text = code_element.text.strip()
                    return f"```{language}\n{code_text}\n```"

            return html_to_markdown(tag_name, text) + "\n\n"

        elements = await last_response_div.query_selector_all(
            "h1, h2, h3, h4, h5, h6, p, strong, em, code, pre, blockquote, ul, ol, li, a, hr"
        )

        for element in elements:
            formatted_text = await process_element(element)
            if formatted_text:
                formatted_response.append(formatted_text)

        result = ""
        for i, text in enumerate(formatted_response):
            if text.startswith(("-", "1.", "2.", "3.")) or text.startswith(("**", "*")):
                result += text
            else:
                if i > 0:
                    result += "\n\n"
                result += text

        return result.strip()

    except Exception as e:
        logger.error(f"Error in detect_response_completion: {e}")
        return ""


async def fetch_response(
    prompt: str,
    system_prompt: str,
    browser,
    tab,
    timeout: int = 300,
    new_chat: bool = False,
) -> str:
    start_time = time.time()
    retries = 3
    retry_delay = 2
    last_error = None

    while retries > 0:
        try:
            if error := await check_for_errors(tab):
                if isinstance(error, MessageTooLongError):
                    logger.info("Message too long, refreshing page...")
                    await tab.reload()
                    await asyncio.sleep(2)
                    new_chat = True
                elif isinstance(error, LoginPromptError):
                    logger.info("Handling login prompt...")
                    if not await handle_continue_prompt(tab):
                        raise error
                else:
                    raise error

            if new_chat:
                logger.info("Clearing conversation...")
                if not await clear_conversation(tab):
                    logger.warning("Failed to clear conversation, continuing anyway")

            logger.info("Preparing input field...")
            textarea = await tab.select("#prompt-textarea", timeout=10)
            await textarea.clear_input()

            constructed_system_prompt = f"We're gonna do a bit of roleplay here, imagine you're {system_prompt}. Immerse yourself completely in the role mentioned."

            final_prompt = prompt
            if system_prompt is not None:
                final_prompt = (
                    constructed_system_prompt + " And now my question, " + final_prompt
                )

            logger.info("Sending prompt...")
            await simulate_human_input(textarea, final_prompt)

            submit_button = await tab.select('[aria-label="Send prompt"]', timeout=10)
            if "disabled" in submit_button.attributes:
                raise MessageTooLongError("Message too long - submit button disabled")

            await submit_button.click()
            logger.info("Prompt sent successfully")

            response_timeout = min(timeout, 300)
            last_response = ""
            unchanged_count = 0

            while time.time() - start_time < response_timeout:
                if error := await check_for_errors(tab):
                    raise error

                await handle_continue_prompt(tab)

                current_response = await detect_response_completion(tab)
                if current_response:
                    if current_response == last_response:
                        unchanged_count += 1
                        if unchanged_count >= 3:
                            return current_response.strip()
                    else:
                        unchanged_count = 0
                        last_response = current_response

            retries -= 1
            if retries > 0:
                logger.warning(f"Response timeout, retrying. {retries} retries left")
                await tab.reload()
                await asyncio.sleep(retry_delay)
            else:
                raise ResponseTimeoutError(
                    "Failed to get stable response",
                    {"timeout": timeout, "last_response": last_response[:100] + "..."},
                )

        except Exception as e:
            last_error = e
            logger.error(f"Error in fetch_response: {e}")
            if retries <= 1:
                raise ChatGPTError(
                    "Failed to fetch response",
                    {"original_error": str(last_error), "retries_remaining": 0},
                )
            retries -= 1
            await tab.reload()
            await asyncio.sleep(retry_delay)

    raise ChatGPTError(
        "All retries exhausted", {"original_error": str(last_error), "total_retries": 3}
    )
