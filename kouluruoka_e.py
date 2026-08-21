#!/usr/bin/env python3
"""Kouluruoka: Lounas + Kasvislounas, raaka-aineet, E-koodit + katalogi."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

MENU_URL = (
    "https://kouluruoka.fi/page-data/menu/"
    "helsinki_haaganylakouluvanhaviertotie/page-data.json"
)
CATALOG_CANDIDATES = [
    Path("/config/www/e_koodit.json"),
    Path(__file__).resolve().parent.parent / "e_koodit.json",
]
CODE_RE = re.compile(r"\bE[0-9]{3,4}[a-zA-Z]?\b", re.IGNORECASE)


def load_catalog() -> dict:
    for path in CATALOG_CANDIDATES:
        if path.is_file():
            with path.open(encoding="utf-8") as f:
                return json.load(f)
    return {}


def fetch_menu() -> dict:
    req = urllib.request.Request(
        MENU_URL,
        headers={"User-Agent": "HomeAssistant-Kouluruoka/1.2"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def normalize(code: str) -> str:
    code = code.strip().upper()
    if not code.startswith("E"):
        code = "E" + code
    return code


def meal_block(meal: dict) -> dict:
    name = (meal.get("Name") or "").strip()
    short = name.split(",")[0].strip() if name else ""
    ingredients = []
    labels = []
    for n in meal.get("Nutritions") or []:
        item_name = (n.get("Name") or "").strip()
        label = (n.get("Label") or "").strip()
        if item_name or label:
            ingredients.append({"name": item_name, "label": label})
        if label:
            labels.append(f"{item_name}: {label}" if item_name else label)
    text = "\n".join(labels)
    codes = sorted({normalize(c) for c in CODE_RE.findall(text)})
    return {
        "name": short or name,
        "full": name,
        "ingredients": ingredients,
        "ainesosat": text,
        "codes": codes,
    }


def lookup(catalog: dict, code: str) -> dict:
    for key in (code, code.upper(), code.lower()):
        if key in catalog:
            return catalog[key]
    for ckey, val in catalog.items():
        if ckey.upper() == code.upper():
            return val
    return {"name": "Tuntematon / ei katalogissa", "type": "", "info": ""}


def details_for(codes: list, catalog: dict) -> list:
    out = []
    for code in codes:
        info = lookup(catalog, code)
        out.append({
            "code": code,
            "name": info.get("name") or "",
            "type": info.get("type") or "",
            "info": (info.get("info") or "")[:240],
        })
    return out


def today_meals(menu: dict) -> dict:
    days = (
        menu.get("result", {})
        .get("pageContext", {})
        .get("menu", {})
        .get("Days")
        or []
    )
    today = f"{date.today().day}.{date.today().month}."
    lounas = None
    kasvis = None
    for day in days:
        if today not in (day.get("Date") or ""):
            continue
        for meal in day.get("Meals") or []:
            mtype = meal.get("MealType")
            if mtype == "Lounas" and lounas is None:
                lounas = meal_block(meal)
            elif mtype == "Kasvislounas" and kasvis is None:
                kasvis = meal_block(meal)
    return {"lounas": lounas, "kasvis": kasvis}


def main() -> None:
    try:
        menu = fetch_menu()
        meals = today_meals(menu)
        catalog = load_catalog()

        lounas = meals.get("lounas") or {}
        kasvis = meals.get("kasvis") or {}
        codes_l = list(lounas.get("codes") or [])
        codes_k = list(kasvis.get("codes") or [])
        all_codes = sorted(set(codes_l) | set(codes_k))

        # enrich meal blocks with details
        if lounas:
            lounas = dict(lounas)
            lounas["details"] = details_for(codes_l, catalog)
        if kasvis:
            kasvis = dict(kasvis)
            kasvis["details"] = details_for(codes_k, catalog)

        out = {
            "count": len(all_codes),
            "codes": all_codes,
            "details": details_for(all_codes, catalog),
            "count_lounas": len(codes_l),
            "codes_lounas": codes_l,
            "details_lounas": details_for(codes_l, catalog),
            "count_kasvis": len(codes_k),
            "codes_kasvis": codes_k,
            "details_kasvis": details_for(codes_k, catalog),
            "lounas": lounas or None,
            "kasvis": kasvis or None,
            "ainesosat_lounas": lounas.get("ainesosat") or "",
            "ainesosat_kasvis": kasvis.get("ainesosat") or "",
        }
        print(json.dumps(out, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({
            "count": 0,
            "codes": [],
            "details": [],
            "count_lounas": 0,
            "codes_lounas": [],
            "details_lounas": [],
            "count_kasvis": 0,
            "codes_kasvis": [],
            "details_kasvis": [],
            "lounas": None,
            "kasvis": None,
            "error": str(exc),
        }, ensure_ascii=False))
        sys.exit(0)


if __name__ == "__main__":
    main()
