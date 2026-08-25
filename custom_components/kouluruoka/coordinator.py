"""Kouluruoka coordinator."""
from __future__ import annotations

from datetime import date, timedelta
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SLUG,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MENU_BASE,
    STORAGE_VERSION,
    USER_AGENT,
)
from .parser import build_snapshot, load_catalog

_LOGGER = logging.getLogger(__name__)


class KouluruokaCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.entry = entry
        self.slug = entry.data[CONF_SLUG]
        self._session: aiohttp.ClientSession | None = None
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_historia")
        self._catalog: dict = {}
        self._history: dict = {"updated": "", "days": {}, "codes": {}}

    async def async_setup(self) -> None:
        self._session = aiohttp.ClientSession(headers={"User-Agent": USER_AGENT})
        self._catalog = await self.hass.async_add_executor_job(load_catalog)
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._history = stored

    async def async_shutdown(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def _async_update_data(self) -> dict:
        if self._session is None:
            raise UpdateFailed("HTTP-istunto ei ole valmis")
        url = f"{MENU_BASE}/{self.slug}/page-data.json"
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"kouluruoka.fi HTTP {resp.status}")
                menu = await resp.json()
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(str(err)) from err

        snapshot, history = await self.hass.async_add_executor_job(
            build_snapshot, menu, self._catalog, date.today(), self._history
        )
        self._history = history
        await self._store.async_save(history)
        snapshot["slug"] = self.slug
        return snapshot
