"""Kouluruoka calendar."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KouluruokaCoordinator

_TZ = ZoneInfo("Europe/Helsinki")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: KouluruokaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KouluruokaCalendar(coordinator, entry)])


class KouluruokaCalendar(CoordinatorEntity[KouluruokaCoordinator], CalendarEntity):
    _attr_has_entity_name = True
    _attr_name = "Kalenteri"
    _attr_icon = "mdi:calendar-month"

    def __init__(self, coordinator: KouluruokaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "kouluruoka.fi",
            "model": coordinator.slug,
        }

    @property
    def event(self) -> CalendarEvent | None:
        today = date.today()
        events = self._events(today, today + timedelta(days=7))
        return events[0] if events else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return self._events(start_date.date(), end_date.date())

    def _events(self, start: date, end: date) -> list[CalendarEvent]:
        data = self.coordinator.data or {}
        events: list[CalendarEvent] = []
        for day in data.get("calendar") or []:
            day_date = day.get("date")
            if not isinstance(day_date, date) or day_date < start or day_date > end:
                continue
            start_dt = datetime.combine(day_date, datetime.min.time(), tzinfo=_TZ)
            end_dt = start_dt + timedelta(days=1)
            lounas = day.get("lounas") or {}
            kasvis = day.get("kasvis") or {}
            if lounas.get("name"):
                events.append(
                    CalendarEvent(
                        start=start_dt,
                        end=end_dt,
                        summary=f"🍽️ {lounas.get('name')}",
                        description=lounas.get("full") or "",
                    )
                )
            if kasvis.get("name"):
                events.append(
                    CalendarEvent(
                        start=start_dt,
                        end=end_dt,
                        summary=f"🥗 {kasvis.get('name')}",
                        description=kasvis.get("full") or "",
                    )
                )
        return events
