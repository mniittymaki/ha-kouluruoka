"""Config flow for Kouluruoka."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLUG,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLUG,
    DOMAIN,
    MENU_BASE,
    USER_AGENT,
)
from .parser import menu_meta


def _normalize_slug(value: str) -> str:
    raw = (value or "").strip().rstrip("/")
    if "/menu/" in raw:
        raw = raw.split("/menu/", 1)[1]
    raw = raw.replace("page-data.json", "").strip("/")
    return raw.lower()


async def _validate(slug: str) -> str:
    url = f"{MENU_BASE}/{slug}/page-data.json"
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        try:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 404:
                    raise InvalidSlug
                if resp.status >= 400:
                    raise CannotConnect
                data = await resp.json()
        except InvalidSlug:
            raise
        except Exception as err:
            raise CannotConnect from err
    meta = menu_meta(data)
    if not meta.get("days"):
        raise InvalidSlug
    return meta.get("name") or slug


class KouluruokaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            slug = _normalize_slug(user_input[CONF_SLUG])
            await self.async_set_unique_id(slug)
            self._abort_if_unique_id_configured()
            try:
                school = await _validate(slug)
            except InvalidSlug:
                errors["base"] = "invalid_slug"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                title = (user_input.get(CONF_NAME) or "").strip() or school
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_SLUG: slug,
                        CONF_NAME: title,
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SLUG, default=DEFAULT_SLUG): str,
                    vol.Optional(CONF_NAME, default=""): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.All(vol.Coerce(int), vol.Range(min=1800, max=86400)),
                }
            ),
            errors=errors,
        )


class InvalidSlug(HomeAssistantError):
    """Unknown school slug."""


class CannotConnect(HomeAssistantError):
    """Cannot reach kouluruoka.fi."""
