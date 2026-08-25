"""Kouluruoka sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KouluruokaCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: KouluruokaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MealSensor(coordinator, entry, "lounas_tanaan", "Lounas tänään", "mdi:food", "lounas_full", "ainesosat_lounas"),
            MealSensor(coordinator, entry, "kasvis_tanaan", "Kasvis tänään", "mdi:leaf", "kasvis_full", "ainesosat_kasvis"),
            MealSensor(coordinator, entry, "lounas_huomenna", "Lounas huomenna", "mdi:food-outline", None, None),
            MealSensor(coordinator, entry, "kasvis_huomenna", "Kasvis huomenna", "mdi:leaf", None, None),
            CodesSensor(coordinator, entry, "e_koodit", "E-koodit", "mdi:flask", "count", "codes", "details"),
            CodesSensor(coordinator, entry, "e_koodit_lounas", "E-koodit lounas", "mdi:flask-outline", "count_lounas", "codes_lounas", "details_lounas"),
            CodesSensor(coordinator, entry, "e_koodit_kasvis", "E-koodit kasvis", "mdi:flask-empty", "count_kasvis", "codes_kasvis", "details_kasvis"),
            HistorySensor(coordinator, entry),
            TopCodeSensor(coordinator, entry),
            NutritionSensor(coordinator, entry, "ravinto_lounas", "Ravinto lounas"),
            NutritionSensor(coordinator, entry, "ravinto_kasvis", "Ravinto kasvis"),
            WatchSensor(coordinator, entry, "huomio_lounas", "Huomio lounas"),
            WatchSensor(coordinator, entry, "huomio_kasvis", "Huomio kasvis"),
            SchoolSensor(coordinator, entry),
        ]
    )


class Base(CoordinatorEntity[KouluruokaCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: KouluruokaCoordinator, entry: ConfigEntry, uid: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{uid}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "kouluruoka.fi",
            "model": coordinator.slug,
        }

    @property
    def data(self) -> dict:
        return self.coordinator.data or {}


class SchoolSensor(Base):
    _attr_name = "Koulu"
    _attr_icon = "mdi:school"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "koulu")

    @property
    def native_value(self) -> str:
        return self.data.get("school") or self.coordinator.slug

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "slug": self.data.get("slug"),
            "city": self.data.get("city"),
        }


class MealSensor(Base):
    def __init__(self, coordinator, entry, uid, name, icon, full_key, ingredients_key):
        super().__init__(coordinator, entry, uid)
        self._attr_name = name
        self._attr_icon = icon
        self._uid = uid
        self._full_key = full_key
        self._ingredients_key = ingredients_key

    @property
    def native_value(self) -> str:
        return self.data.get(self._uid) or "Ei tietoa"

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {}
        if self._full_key:
            attrs["full"] = self.data.get(self._full_key)
        if self._ingredients_key:
            attrs["ainesosat"] = self.data.get(self._ingredients_key)
        return attrs


class CodesSensor(Base):
    _attr_native_unit_of_measurement = "kpl"

    def __init__(self, coordinator, entry, uid, name, icon, count_key, codes_key, details_key):
        super().__init__(coordinator, entry, uid)
        self._attr_name = name
        self._attr_icon = icon
        self._count_key = count_key
        self._codes_key = codes_key
        self._details_key = details_key

    @property
    def native_value(self) -> int:
        return int(self.data.get(self._count_key) or 0)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "codes": self.data.get(self._codes_key) or [],
            "details": self.data.get(self._details_key) or [],
        }


class HistorySensor(Base):
    _attr_name = "E-koodit historia"
    _attr_icon = "mdi:chart-bar"
    _attr_native_unit_of_measurement = "kpl"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "e_historia")

    @property
    def native_value(self) -> int:
        return int(self.data.get("koodeja") or 0)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "paivia": self.data.get("paivia"),
            "top": self.data.get("top") or [],
            "top_teksti": self.data.get("top_teksti") or "",
            "top1": self.data.get("top1") or "",
            "top1_paivia": self.data.get("top1_paivia") or 0,
        }


class TopCodeSensor(Base):
    _attr_name = "E-koodit yleisin"
    _attr_icon = "mdi:trophy"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "e_yleisin")

    @property
    def native_value(self) -> str:
        return self.data.get("top1") or "ei vielä"

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "paivia": self.data.get("top1_paivia") or 0,
            "top": self.data.get("top") or [],
        }


class NutritionSensor(Base):
    _attr_native_unit_of_measurement = "kcal"
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator, entry, key, name):
        super().__init__(coordinator, entry, key)
        self._attr_name = name
        self._key = key

    @property
    def native_value(self) -> int:
        block = self.data.get(self._key) or {}
        return int(block.get("kcal") or 0)

    @property
    def extra_state_attributes(self) -> dict:
        return self.data.get(self._key) or {}


class WatchSensor(Base):
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator, entry, key, name):
        super().__init__(coordinator, entry, key)
        self._attr_name = name
        self._key = key

    @property
    def native_value(self) -> str:
        block = self.data.get(self._key) or {}
        return block.get("taso") or "ok"

    @property
    def extra_state_attributes(self) -> dict:
        return self.data.get(self._key) or {}
