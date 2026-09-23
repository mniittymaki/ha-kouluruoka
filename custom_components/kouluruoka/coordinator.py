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
    MENU_JSON_BASE,
    MENU_PAGE_BASE,
    STORAGE_VERSION,
    USER_AGENT,
)
from .parser import build_snapshot, extract_inlined_page_data, load_catalog

_LOGGER = logging.getLogger(__name__)


async def async_fetch_menu(session: aiohttp.ClientSession, slug: str) -> dict:
    """Load menu JSON, falling back to inlined HTML after the 2026 site change."""
    timeout = aiohttp.ClientTimeout(total=30)
    json_url = f"{MENU_JSON_BASE}/{slug}/page-data.json"
    async with session.get(json_url, timeout=timeout) as resp:
        if resp.status == 200:
            data = await resp.json()
            if isinstance(data, dict) and data.get("result"):
                return data
    page_url = f"{MENU_PAGE_BASE}/{slug}/"
    async with session.get(page_url, timeout=timeout) as resp:
        if resp.status == 404:
            raise UpdateFailed(f"Koulua ei löytynyt: {slug}")
        if resp.status != 200:
            raise UpdateFailed(f"kouluruoka.fi HTTP {resp.status}")
        html = await resp.text()
    try:
        return extract_inlined_page_data(html)
    except ValueError as err:
        raise UpdateFailed(str(err)) from err


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
        try:
            menu = await async_fetch_menu(self._session, self.slug)
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
