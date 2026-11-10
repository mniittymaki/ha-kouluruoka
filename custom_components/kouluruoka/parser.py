"""Kouluruoka.fi menu parsing: meals, E-codes, nutrition, watch flags."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

INLINED_PAGE_DATA_RE = re.compile(
    r'<script[^>]*id=["\']gatsby-inlined-page-data["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

HISTORY_KEEP_DAYS = 365
TOP_LIMIT = 15
CODE_RE = re.compile(r"\bE[0-9]{3,4}[a-zA-Z]?\b", re.IGNORECASE)
NUM_RE = re.compile(
    r"(?P<label>[^:]+):\s*(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*(?P<unit>kcal|kJ|g)?",
    re.IGNORECASE,
)

PORTION_RULES = [
    (["keitto"], 300, "keitto"),
    (["kiisseli", "jälkiruoka", "vanukas", "jogurtti"], 150, "jalkiruoka"),
    (["majoneesi", "remoulade", "dippi", "aioli"], 25, "tahna"),
    (["kastike", "kastiketta"], 50, "lisakekastike"),
    (["sose", "muusi"], 150, "perunasose"),
    (["peruna", "perunoita", "riisi", "riisiä", "pasta", "makaroni", "nuudeli"], 100, "lisake"),
    (["salaatti", "tuorepala", "raaste"], 50, "salaatti"),
    (["lämmin kasvis", "kasvislisäke"], 50, "kasvislisake"),
    (["leipä"], 35, "leipa"),
    (["juusto"], 20, "juusto"),
    (["hedelmä", "hedelmää", "banaani", "omena", "päärynä"], 100, "hedelma"),
    (["pata", "vuoka", "laatikko", "risotto", "wok"], 300, "laatikko"),
    (["pyöryk", "pihvi", "nakki", "nappi", "nappeja", "kebab", "kala", "turska", "seiti", "lohi", "broileri", "kana", "liha"], 100, "paaruoka"),
]
DEFAULT_PORTION = (100, "paaruoka")

WATCH_MSM = re.compile(r"\b(MSM|natriumglutamaatti|E621)\b", re.I)
WATCH_NITRITE = re.compile(r"\b(nitriitti|E250|E249)\b", re.I)
WATCH_SYRUP = re.compile(r"\b(glukoosi-fruktoosisiirappi|fruktoosi-glukoosisiirappi)\b", re.I)
WATCH_SALT = re.compile(r"suola[:\s]+([0-9]+(?:[.,][0-9]+)?)\s*g", re.I)


def extract_inlined_page_data(html: str) -> dict:
    match = INLINED_PAGE_DATA_RE.search(html or "")
    if not match:
        raise ValueError("gatsby-inlined-page-data puuttuu")
    raw = match.group(1)
    idx = raw.find("var d=")
    if idx < 0:
        raise ValueError("pageData-objekti puuttuu")
    data, _ = json.JSONDecoder().raw_decode(raw, idx + 6)
    if not isinstance(data, dict) or "result" not in data:
        raise ValueError("pageData-rakenne ei täsmää")
    return data


def _norm_mt(mt: str) -> str:
    if not mt:
        return ""
    return mt.strip().lstrip("*").strip().lower()


def _is_lounas(mt: str) -> bool:
    s = _norm_mt(mt)
    if not s:
        return False
    if s in ("lounas", "lunch", "kotiruokalounas"):
        return True
    if s.startswith("lounas ") and not any(x in s for x in ("salaatti", "patonki", "keitto")):
        return True
    if s.startswith("koululounas "):
        return True
    return False


def _is_kasvis(mt: str) -> bool:
    s = _norm_mt(mt)
    if not s:
        return False
    if s in ("kasvislounas", "kasvis", "vegetarisk lunch", "kasvisvaihtoehto", "lounas kasvisruoka", "kasviskeitto"):
        return True
    if s.startswith("kasvislounas"):
        return True
    return False


def _pick_meals(meals: list) -> tuple[dict | None, dict | None]:
    lounas = kasvis = None
    for m in meals or []:
        mt = m.get("MealType") or ""
        if _is_kasvis(mt) and kasvis is None:
            kasvis = m
        elif _is_lounas(mt):
            # exact "Lounas" wins over variants
            if lounas is None or _norm_mt(mt) == "lounas":
                lounas = m
    # Koululounas 1 as lounas, 2 as kasvis if no separate kasvis
    if lounas is None or kasvis is None:
        k1 = k2 = None
        for m in meals or []:
            mt = _norm_mt(m.get("MealType") or "")
            if mt == "koululounas 1":
                k1 = m
            elif mt == "koululounas 2":
                k2 = m
        if lounas is None and k1:
            lounas = k1
        if kasvis is None and k2:
            kasvis = k2
    return lounas, kasvis


def _meal_name(meal: dict | None) -> str:
    if not meal:
        return ""
    return (meal.get("Name") or "").strip()


def _ingredients(meal: dict | None) -> str:
    if not meal:
        return ""
    parts = []
    for item in meal.get("Ingredients") or []:
        name = (item.get("Name") or item.get("Ingredient") or "").strip()
        if name:
            parts.append(name)
    return ", ".join(parts)


def _nutrition(meal: dict | None) -> dict:
    if not meal:
        return {}
    out = {"kcal": 0, "proteiini": 0, "hiilihydraatti": 0, "rasva": 0, "suola": 0}
    for n in meal.get("Nutritions") or []:
        label = (n.get("Name") or "").lower()
        val = n.get("Value")
        try:
            v = float(str(val).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if "energia" in label and "kcal" in label:
            out["kcal"] = round(v)
        elif "proteiini" in label:
            out["proteiini"] = round(v, 1)
        elif "hiilihydraatti" in label and "sokeri" not in label:
            out["hiilihydraatti"] = round(v, 1)
        elif "rasva" in label and "tyydytty" not in label:
            out["rasva"] = round(v, 1)
        elif "suola" in label:
            out["suola"] = round(v, 2)
    return out


def _watch(ingredients: str, nutrition: dict) -> dict:
    text = ingredients or ""
    flags = []
    level = "ok"
    if WATCH_MSM.search(text):
        flags.append("MSM/E621")
        level = "varoitus"
    if WATCH_NITRITE.search(text):
        flags.append("nitriitti")
        level = "varoitus" if level == "ok" else level
    if WATCH_SYRUP.search(text):
        flags.append("siirappi")
        if level == "ok":
            level = "huomio"
    salt = nutrition.get("suola") or 0
    if salt >= 1.0:
        flags.append(f"suola {salt} g")
        if level == "ok":
            level = "huomio"
    return {"taso": level, "yhteenveto": ", ".join(flags) if flags else "Ei erityisiä huomioita", "flags": flags}


def _codes(text: str, catalog: dict) -> list:
    found = []
    for m in CODE_RE.finditer(text or ""):
        code = m.group(0).upper()
        if code not in [c["code"] for c in found]:
            info = catalog.get(code, {})
            found.append({
                "code": code,
                "name": info.get("name") or "",
                "type": info.get("type") or "",
                "info": info.get("info") or "",
            })
    return found


def load_catalog() -> dict:
    p = Path(__file__).parent / "e_koodit.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {c["code"]: c for c in data if isinstance(c, dict) and c.get("code")}
    except Exception:
        return {}


def menu_meta(menu: dict) -> dict:
    ctx = (menu.get("result") or {}).get("pageContext") or {}
    m = ctx.get("menu") or {}
    days = m.get("Days") or []
    return {
        "name": m.get("RestaurantName") or "",
        "city": m.get("City") or "",
        "days": len(days),
    }


def build_snapshot(menu: dict, catalog: dict, today: date, history: dict) -> tuple[dict, dict]:
    ctx = (menu.get("result") or {}).get("pageContext") or {}
    m = ctx.get("menu") or {}
    school = m.get("RestaurantName") or ""
    city = m.get("City") or ""
    days = m.get("Days") or []

    def day_meals(offset: int):
        target = today + timedelta(days=offset)
        for d in days:
            raw = d.get("Date") or ""
            # "maanantai 21.9." style
            parts = raw.split()
            if len(parts) >= 2 and "." in parts[-1]:
                try:
                    dd, mm = parts[-1].rstrip(".").split(".")
                    if int(dd) == target.day and int(mm) == target.month:
                        return d.get("Meals") or []
                except Exception:
                    continue
        return []

    def pack(meals):
        l, k = _pick_meals(meals)
        ln = _meal_name(l)
        kn = _meal_name(k)
        li = _ingredients(l)
        ki = _ingredients(k)
        ln_nut = _nutrition(l)
        kn_nut = _nutrition(k)
        lc = _codes(li, catalog)
        kc = _codes(ki, catalog)
        return {
            "lounas": ln,
            "kasvis": kn,
            "lounas_full": ln,
            "kasvis_full": kn,
            "ainesosat_lounas": li,
            "ainesosat_kasvis": ki,
            "ravinto_lounas": ln_nut,
            "ravinto_kasvis": kn_nut,
            "huomio_lounas": _watch(li, ln_nut),
            "huomio_kasvis": _watch(ki, kn_nut),
            "codes_lounas": [c["code"] for c in lc],
            "codes_kasvis": [c["code"] for c in kc],
            "details_lounas": lc,
            "details_kasvis": kc,
            "count_lounas": len(lc),
            "count_kasvis": len(kc),
            "codes": [c["code"] for c in lc + kc],
            "details": lc + kc,
            "count": len(lc) + len(kc),
        }

    today_m = day_meals(0)
    tomorrow_m = day_meals(1)
    t = pack(today_m)
    tom = pack(tomorrow_m)

    snap = {
        "school": school,
        "city": city,
        "lounas_tanaan": t["lounas"] or "Ei tietoa",
        "kasvis_tanaan": t["kasvis"] or "Ei tietoa",
        "lounas_huomenna": tom["lounas"] or "Ei tietoa",
        "kasvis_huomenna": tom["kasvis"] or "Ei tietoa",
        "lounas_full": t["lounas_full"],
        "kasvis_full": t["kasvis_full"],
        "ainesosat_lounas": t["ainesosat_lounas"],
        "ainesosat_kasvis": t["ainesosat_kasvis"],
        "ravinto_lounas": t["ravinto_lounas"],
        "ravinto_kasvis": t["ravinto_kasvis"],
        "huomio_lounas": t["huomio_lounas"],
        "huomio_kasvis": t["huomio_kasvis"],
        "codes": t["codes"],
        "details": t["details"],
        "count": t["count"],
        "codes_lounas": t["codes_lounas"],
        "details_lounas": t["details_lounas"],
        "count_lounas": t["count_lounas"],
        "codes_kasvis": t["codes_kasvis"],
        "details_kasvis": t["details_kasvis"],
        "count_kasvis": t["count_kasvis"],
    }

    # history
    hist = history or {"updated": "", "days": {}, "codes": {}}
    day_key = today.isoformat()
    if day_key not in hist.get("days", {}):
        hist.setdefault("days", {})[day_key] = {
            "lounas": t["codes_lounas"],
            "kasvis": t["codes_kasvis"],
        }
        for code in set(t["codes"]):
            hist.setdefault("codes", {}).setdefault(code, {"paivia": 0, "lounas": 0, "kasvis": 0, "viimeksi": day_key})
            hist["codes"][code]["paivia"] += 1
            hist["codes"][code]["viimeksi"] = day_key
        if any(c in t["codes_lounas"] for c in t["codes"]):
            for c in t["codes_lounas"]:
                if c in hist["codes"]:
                    hist["codes"][c]["lounas"] += 1
        if any(c in t["codes_kasvis"] for c in t["codes"]):
            for c in t["codes_kasvis"]:
                if c in hist["codes"]:
                    hist["codes"][c]["kasvis"] += 1
    # trim old
    cutoff = (today - timedelta(days=HISTORY_KEEP_DAYS)).isoformat()
    hist["days"] = {k: v for k, v in hist.get("days", {}).items() if k >= cutoff}
    # top
    top = sorted(
        [{"code": c, **info} for c, info in hist.get("codes", {}).items()],
        key=lambda x: x.get("paivia", 0),
        reverse=True,
    )[:TOP_LIMIT]
    snap["koodeja"] = len(hist.get("codes", {}))
    snap["paivia"] = len(hist.get("days", {}))
    snap["top"] = top
    snap["top1"] = top[0]["code"] if top else ""
    snap["top1_paivia"] = top[0].get("paivia", 0) if top else 0
    snap["top_teksti"] = ", ".join(f"{x['code']} ({x.get('paivia', 0)})" for x in top[:8])
    hist["updated"] = today.isoformat()
    return snap, hist
