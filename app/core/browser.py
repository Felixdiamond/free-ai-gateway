import asyncio
import logging
import nodriver as uc
from app.core.config import settings

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
            }
            if settings.BROWSER_PATH:
                start_kwargs["browser_executable_path"] = settings.BROWSER_PATH

            cls._browser = await uc.start(**start_kwargs)
            logger.info("Browser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise

    @classmethod
    async def close(cls):
        if cls._browser:
            try:
                cls._browser.stop()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            cls._browser = None

    @classmethod
    async def get_new_tab(cls, url: str):
        browser = await cls.get_browser()
        return await browser.get(url, new_tab=True)
