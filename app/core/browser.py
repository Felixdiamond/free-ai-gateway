import asyncio
import logging
import zendriver as zd
from app.core.config import settings

try:
    from zendriver.cdp import util as cdp_util
    if "DOM.affectedByStartingStylesFlagUpdated" not in cdp_util._event_parsers:
        class DummyEvent:
            @classmethod
            def from_json(cls, _):
                return cls()
        cdp_util._event_parsers["DOM.affectedByStartingStylesFlagUpdated"] = DummyEvent
except (ImportError, AttributeError):
    pass

logger = logging.getLogger(__name__)

class BrowserManager:
    _instance = None
    _browser = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_browser(cls):
        async with cls._lock:
            if not cls._browser:
                await cls._init_browser()
            return cls._browser

    @classmethod
    async def _init_browser(cls):
        logger.info("Initializing browser...")
        try:
            start_kwargs = {
                "headless": settings.HEADLESS,
                "browser_args": settings.BROWSER_ARGS,
                "user_data_dir": settings.USER_DATA_DIR,
                "sandbox": False,
            }
            if settings.BROWSER_PATH:
                start_kwargs["browser_executable_path"] = settings.BROWSER_PATH

            cls._browser = await zd.start(**start_kwargs)
            logger.info("Browser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise

    @classmethod
    async def get_new_tab(cls, url: str):
        browser = await cls.get_browser()
        tab = await browser.get(url, new_tab=True)
        return tab

    @classmethod
    async def close(cls):
        if cls._browser:
            try:
                await cls._browser.stop()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            cls._browser = None
