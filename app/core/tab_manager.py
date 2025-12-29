"""
Tab Management System for concurrent browser tab handling.

Provides session-based tab management with:
- Per-tab locks for true concurrency
- Session ID labeling for conversation persistence
- Anonymous tab pooling for one-off requests
- Automatic cleanup of inactive tabs
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from zendriver import Tab

logger = logging.getLogger(__name__)


@dataclass
class ManagedTab:
    """A managed browser tab with its own lock and metadata."""
    tab: "Tab"
    provider: str
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    session_id: Optional[str] = None
    last_used: datetime = field(default_factory=datetime.now)
    in_use: bool = False
    message_count: int = 0
    
    def update_last_used(self):
        self.last_used = datetime.now()
    
    @property
    def inactive_seconds(self) -> float:
        return (datetime.now() - self.last_used).total_seconds()


class ProviderTabPool:
    """Tab pool for a specific provider (ChatGPT, Gemini, Grok)."""
    
    def __init__(self, provider_name: str, url: str):
        self.provider_name = provider_name
        self.url = url
        self.session_tabs: Dict[str, ManagedTab] = {}
        self.anonymous_tabs: List[ManagedTab] = []
        self._pool_lock = asyncio.Lock()
    
    async def get_tab(self, session_id: Optional[str] = None) -> ManagedTab:
        """Get or create a tab for the given session."""
        async with self._pool_lock:
            if session_id:
                if session_id in self.session_tabs:
                    managed_tab = self.session_tabs[session_id]
                    logger.info(f"[{self.provider_name}] Reusing session tab: {session_id}")
                    return managed_tab
                
                managed_tab = await self._create_tab(session_id)
                self.session_tabs[session_id] = managed_tab
                logger.info(f"[{self.provider_name}] Created new session tab: {session_id}")
                return managed_tab
            else:
                for tab in self.anonymous_tabs:
                    if not tab.in_use:
                        logger.info(f"[{self.provider_name}] Reusing anonymous tab")
                        return tab
                
                if len(self.anonymous_tabs) < settings.TAB_POOL_SIZE:
                    managed_tab = await self._create_tab(None)
                    self.anonymous_tabs.append(managed_tab)
                    logger.info(f"[{self.provider_name}] Created new anonymous tab (pool size: {len(self.anonymous_tabs)})")
                    return managed_tab
                
                logger.warning(f"[{self.provider_name}] All tabs busy, waiting...")
                return await self._wait_for_free_tab()
    
    async def _create_tab(self, session_id: Optional[str]) -> ManagedTab:
        """Create a new browser tab."""
        from app.core.browser import BrowserManager
        
        tab = await BrowserManager.get_new_tab(self.url)
        await asyncio.sleep(settings.TIMEOUT_PAGE_LOAD / 10)
        
        return ManagedTab(
            tab=tab,
            provider=self.provider_name,
            session_id=session_id
        )
    
    async def _wait_for_free_tab(self) -> ManagedTab:
        """Wait until a tab becomes free."""
        max_wait = 60
        start = time.time()
        
        while time.time() - start < max_wait:
            for tab in self.anonymous_tabs:
                if not tab.in_use:
                    return tab
            await asyncio.sleep(0.5)
        
        logger.warning(f"[{self.provider_name}] Wait timeout, force creating new tab")
        managed_tab = await self._create_tab(None)
        self.anonymous_tabs.append(managed_tab)
        return managed_tab
    
    async def release_tab(self, managed_tab: ManagedTab):
        """Mark a tab as no longer in use."""
        managed_tab.in_use = False
        managed_tab.update_last_used()
    
    async def reload_tab(self, managed_tab: ManagedTab):
        """Reload a tab (for new_chat or error recovery)."""
        try:
            await managed_tab.tab.reload()
            await asyncio.sleep(settings.TIMEOUT_PAGE_LOAD / 5)
            managed_tab.message_count = 0
        except Exception as e:
            logger.error(f"[{self.provider_name}] Error reloading tab: {e}")
            await self._recreate_tab(managed_tab)
    
    async def _recreate_tab(self, managed_tab: ManagedTab):
        """Close and recreate a tab."""
        try:
            await managed_tab.tab.close()
        except Exception:
            pass
        
        from app.core.browser import BrowserManager
        new_tab = await BrowserManager.get_new_tab(self.url)
        managed_tab.tab = new_tab
        managed_tab.message_count = 0
        await asyncio.sleep(settings.TIMEOUT_PAGE_LOAD / 10)
    
    async def cleanup_inactive(self):
        """Close tabs that have been inactive too long."""
        inactive_threshold = settings.TAB_INACTIVE_MINUTES * 60
        
        async with self._pool_lock:
            tabs_to_remove = []
            for tab in self.anonymous_tabs:
                if not tab.in_use and tab.inactive_seconds > inactive_threshold:
                    tabs_to_remove.append(tab)
            
            for tab in tabs_to_remove:
                try:
                    await tab.tab.close()
                    self.anonymous_tabs.remove(tab)
                    logger.info(f"[{self.provider_name}] Closed inactive anonymous tab")
                except Exception as e:
                    logger.error(f"[{self.provider_name}] Error closing tab: {e}")
            
            sessions_to_remove = []
            for session_id, tab in self.session_tabs.items():
                if not tab.in_use and tab.inactive_seconds > inactive_threshold:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                try:
                    tab = self.session_tabs[session_id]
                    await tab.tab.close()
                    del self.session_tabs[session_id]
                    logger.info(f"[{self.provider_name}] Closed inactive session tab: {session_id}")
                except Exception as e:
                    logger.error(f"[{self.provider_name}] Error closing session tab: {e}")
    
    async def close_all(self):
        """Close all tabs in the pool."""
        async with self._pool_lock:
            for tab in self.anonymous_tabs:
                try:
                    await tab.tab.close()
                except Exception:
                    pass
            self.anonymous_tabs.clear()
            
            for tab in self.session_tabs.values():
                try:
                    await tab.tab.close()
                except Exception:
                    pass
            self.session_tabs.clear()
    
    def get_stats(self) -> dict:
        """Get pool statistics."""
        return {
            "provider": self.provider_name,
            "session_tabs": len(self.session_tabs),
            "anonymous_tabs": len(self.anonymous_tabs),
            "anonymous_in_use": sum(1 for t in self.anonymous_tabs if t.in_use),
        }


class TabManager:
    """Global tab manager for all providers."""
    
    _instance: Optional["TabManager"] = None
    
    def __init__(self):
        self.pools: Dict[str, ProviderTabPool] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
    
    @classmethod
    def get_instance(cls) -> "TabManager":
        if cls._instance is None:
            cls._instance = TabManager()
        return cls._instance
    
    def register_provider(self, name: str, url: str):
        """Register a provider with its URL."""
        if name not in self.pools:
            self.pools[name] = ProviderTabPool(name, url)
            logger.info(f"Registered provider pool: {name}")
    
    async def acquire_tab(self, provider: str, session_id: Optional[str] = None) -> ManagedTab:
        """Acquire a tab for the given provider and optional session."""
        if provider not in self.pools:
            raise ValueError(f"Unknown provider: {provider}")
        
        pool = self.pools[provider]
        managed_tab = await pool.get_tab(session_id)
        managed_tab.in_use = True
        managed_tab.update_last_used()
        return managed_tab
    
    async def release_tab(self, managed_tab: ManagedTab):
        """Release a tab back to its pool."""
        if managed_tab.provider in self.pools:
            await self.pools[managed_tab.provider].release_tab(managed_tab)
    
    async def reload_tab(self, managed_tab: ManagedTab):
        """Reload a tab."""
        if managed_tab.provider in self.pools:
            await self.pools[managed_tab.provider].reload_tab(managed_tab)
    
    def start_cleanup_task(self):
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started tab cleanup task")
    
    async def _cleanup_loop(self):
        """Background task to clean up inactive tabs."""
        while True:
            try:
                await asyncio.sleep(settings.TAB_CLEANUP_INTERVAL)
                for pool in self.pools.values():
                    await pool.cleanup_inactive()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def shutdown(self):
        """Shutdown the tab manager."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        for pool in self.pools.values():
            await pool.close_all()
        
        logger.info("TabManager shutdown complete")
    
    async def close_provider_tabs(self, provider_name: str):
        """Close all tabs for a specific provider."""
        if provider_name in self.pools:
            await self.pools[provider_name].close_all()
            logger.info(f"Closed all tabs for provider: {provider_name}")
    
    async def close_session_tabs(self, session_id: str):
        """Close tabs for a specific session across all providers."""
        for pool in self.pools.values():
            if session_id in pool.session_tabs:
                try:
                    tab = pool.session_tabs[session_id]
                    await tab.tab.close()
                    del pool.session_tabs[session_id]
                    logger.info(f"[{pool.provider_name}] Closed session tab: {session_id}")
                except Exception as e:
                    logger.error(f"Error closing session tab: {e}")
    
    def get_session_status(self, session_id: str) -> dict:
        """Get status of a session's tabs across all providers."""
        status = {}
        for name, pool in self.pools.items():
            if session_id in pool.session_tabs:
                tab = pool.session_tabs[session_id]
                status[name] = {
                    "active": True,
                    "in_use": tab.in_use,
                    "message_count": tab.message_count,
                    "inactive_seconds": round(tab.inactive_seconds, 1)
                }
            else:
                status[name] = {"active": False}
        return status
    
    def get_stats(self) -> dict:
        """Get statistics for all pools."""
        return {
            "pools": [pool.get_stats() for pool in self.pools.values()]
        }


def validate_session_id(session_id: Optional[str]) -> Optional[str]:
    """Validate and normalize a session ID."""
    if session_id is None:
        return None
    
    session_id = session_id.strip().lower()
    
    if not re.match(r'^[a-f0-9]{8,32}$', session_id):
        raise ValueError("session_id must be a hexadecimal string between 8-32 characters")
    
    return session_id


tab_manager = TabManager.get_instance()
