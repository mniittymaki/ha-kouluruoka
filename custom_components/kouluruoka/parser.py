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


def extract_inlined_page_data(html: str) -> dict:
    """Parse Gatsby page-data that kouluruoka.fi now embeds in the menu HTML."""
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
NUM_RE = re.compile(
    r"(?P<label>[^:]+):\s*(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*(?P<unit>kcal|kJ|g)?",
    re.IGNORECASE,
)

# VRN / kouluruokailu – koululaisten viitteelliset annoskoot (g)
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
    (["pyöryk", "pihvi", "nakki", "nappi", "nappeja", "kebab",
      "kala", "turska", "seiti", "lohi", "broileri", "kana", "liha"], 100, "paaruoka"),
]
DEFAULT_PORTION = (100, "paaruoka")

# Fineli-tyyppiset varat kun kouluruoka.fi ei anna 100 g -arvoja
FALLBACK_PER_100G = {
    "leipa": {"kcal": 255, "kj": 1070, "rasva": 3.2, "tyydyttynyt": 0.5,
              "hiilihydraatit": 48.0, "sokerit": 2.8, "proteiini": 8.5, "suola": 1.1},
    "salaatti": {"kcal": 18, "kj": 75, "rasva": 0.2, "tyydyttynyt": 0.0,
                 "hiilihydraatit": 2.8, "sokerit": 1.8, "proteiini": 0.9, "suola": 0.1},
    "kasvislisake": {"kcal": 45, "kj": 188, "rasva": 1.2, "tyydyttynyt": 0.2,
                     "hiilihydraatit": 6.5, "sokerit": 3.0, "proteiini": 1.8, "suola": 0.3},
    "juusto": {"kcal": 340, "kj": 1423, "rasva": 26.0, "tyydyttynyt": 16.0,
               "hiilihydraatit": 0.5, "sokerit": 0.5, "proteiini": 26.0, "suola": 1.2},
    "hedelma": {"kcal": 52, "kj": 218, "rasva": 0.2, "tyydyttynyt": 0.0,
                "hiilihydraatit": 12.0, "sokerit": 10.0, "proteiini": 0.3, "suola": 0.0},
}

EMPTY_NUTRI = {
    "kcal": 0.0, "kj": 0.0, "rasva": 0.0, "tyydyttynyt": 0.0,
    "hiilihydraatit": 0.0, "sokerit": 0.0, "proteiini": 0.0, "suola": 0.0,
}

LABEL_MAP = (
    ("energia, kcal", "kcal"),
    ("energia kcal", "kcal"),
    ("energia, kj", "kj"),
    ("energia kj", "kj"),
    ("josta tyydyttynyttä", "tyydyttynyt"),
    ("tyydyttynyttä", "tyydyttynyt"),
    ("josta sokereita", "sokerit"),
    ("sokereita", "sokerit"),
    ("hiilihydraatit", "hiilihydraatit"),
    ("proteiini", "proteiini"),
    ("rasva", "rasva"),
    ("suola", "suola"),
)

# Huomiot – ei jokaista suola/sokeri-sanaa, vain selkeämmät merkit
INGREDIENT_RULES = [
    (r"voimakassuolainen", "varoitus", "suola", "Merkintä voimakassuolainen"),
    (r"koneellisesti eroteltu", "varoitus", "prosessoitu_liha", "Koneellisesti eroteltu liha (MSM)"),
    (r"\bkamara\b", "varoitus", "prosessoitu_liha", "Kamara"),
    (r"\bsilava\b", "huomio", "prosessoitu_liha", "Silava"),
    (r"palmuöljy|palm oil", "varoitus", "rasva", "Palmuöljy"),
    (r"osittain kovetettu|kovetettu rasva|hydrogenated", "varoitus", "rasva", "Kovetettu rasva"),
    (r"glukoosi-?fruktoosi|fruktoosi-?glukoosi|tärkkelyssiirappi", "huomio", "sokeri", "Siirappi / glukoosi-fruktoosi"),
    (r"\bdekstroosi\b", "huomio", "sokeri", "Dekstroosi"),
    (r"inverttisokeri", "huomio", "sokeri", "Inverttisokeri"),
    (r"aspartaami|asesulfaami|sukraloosi|sakariini", "huomio", "makeutus", "Keinotekoinen makeutusaine"),
    (r"natriumglutamaatti", "huomio", "lisaaine", "Natriumglutamaatti"),
    (r"soijaproteiinivalmiste|proteiinivalmiste", "huomio", "upf", "Proteiinivalmiste"),
    (r"nitriitti|nitraatti", "varoitus", "lisaaine", "Nitriitti/nitraatti"),
    (r"\baromit\b|\baromiaine|\baromi\b", "epailyttava", "teollinen", "Aromit"),
    (r"emulgointiaine", "epailyttava", "teollinen", "Emulgointiaine"),
    (r"stabilointiaine", "epailyttava", "teollinen", "Stabilointiaine"),
    (r"sakeuttamisaine", "epailyttava", "teollinen", "Sakeuttamisaine"),
    (r"muunnettu (maissi)?tärkkelys|muunnettu tärkkelys", "epailyttava", "teollinen", "Muunnettu tärkkelys"),
    (r"kasvirasvasekoite", "epailyttava", "rasva", "Kasvirasvasekoite"),
    (r"peruskastikeaines|valmisaines", "epailyttava", "teollinen", "Teollinen perusaines"),
    (r"maltodekstriini", "epailyttava", "teollinen", "Maltodekstriini"),
    (r"hydrolysoitu", "epailyttava", "teollinen", "Hydrolysoitu aines"),
    (r"säilöntäaine", "epailyttava", "lisaaine", "Säilöntäaine"),
    (r"väriaine", "epailyttava", "vari", "Väriaine"),
]

ECODE_RULES = {
    "E102": ("varoitus", "vari", "Atsoväri (Southampton)"),
    "E104": ("varoitus", "vari", "Atsoväri (Southampton)"),
    "E110": ("varoitus", "vari", "Atsoväri (Southampton)"),
    "E122": ("varoitus", "vari", "Atsoväri (Southampton)"),
    "E124": ("varoitus", "vari", "Atsoväri (Southampton)"),
    "E129": ("varoitus", "vari", "Atsoväri (Southampton)"),
    "E202": ("epailyttava", "lisaaine", "Kaliumsorbaatti"),
    "E211": ("huomio", "lisaaine", "Natriumbentsoaatti"),
    "E249": ("varoitus", "lisaaine", "Nitriitti"),
    "E250": ("varoitus", "lisaaine", "Natriumnitriitti"),
    "E251": ("varoitus", "lisaaine", "Nitraatti"),
    "E252": ("varoitus", "lisaaine", "Kaliumnitraatti"),
    "E320": ("varoitus", "lisaaine", "BHA"),
    "E321": ("varoitus", "lisaaine", "BHT"),
    "E407": ("epailyttava", "lisaaine", "Karrageeni"),
    "E412": ("epailyttava", "lisaaine", "Guarkumi"),
    "E415": ("epailyttava", "lisaaine", "Ksantaanikumi"),
    "E433": ("epailyttava", "lisaaine", "Polysorbaatti"),
    "E450": ("huomio", "lisaaine", "Difosfaatti"),
    "E451": ("huomio", "lisaaine", "Trifosfaatti"),
    "E452": ("huomio", "lisaaine", "Polyfosfaatti"),
    "E466": ("epailyttava", "lisaaine", "Karboksimetyyliselluloosa"),
    "E471": ("epailyttava", "lisaaine", "Rasvahappojen mono- ja diglyseridit"),
    "E472": ("epailyttava", "lisaaine", "Rasvahappojen esterit"),
    "E476": ("epailyttava", "lisaaine", "Polyglyserolipolyrisinoleaatti"),
    "E621": ("huomio", "lisaaine", "Natriumglutamaatti"),
    "E950": ("huomio", "makeutus", "Asesulfaami K"),
    "E951": ("huomio", "makeutus", "Aspartaami"),
    "E952": ("huomio", "makeutus", "Syklamaatti"),
    "E954": ("huomio", "makeutus", "Sakariini"),
    "E955": ("huomio", "makeutus", "Sukraloosi"),
}

LEVEL_RANK = {"ok": 0, "epailyttava": 1, "huomio": 2, "varoitus": 3}


def load_catalog(path: Path | None = None) -> dict:
    candidates = [
        path,
        Path(__file__).resolve().parent / "e_koodit.json",
    ]
    for item in candidates:
        if item and Path(item).is_file():
            with Path(item).open(encoding="utf-8") as handle:
                return json.load(handle)
    return {}


def normalize(code: str) -> str:
    code = code.strip().upper()
    if not code.startswith("E"):
        code = "E" + code
    return code


def parse_number(raw: str) -> float:
    return float(raw.replace(",", "."))


def parse_items(items: list) -> dict:
    out = dict(EMPTY_NUTRI)
    for item in items or []:
        text = (item.get("Text") if isinstance(item, dict) else str(item)) or ""
        match = NUM_RE.search(text)
        if not match:
            continue
        label = re.sub(r"\s+", " ", match.group("label")).strip().lower()
        value = parse_number(match.group("value"))
        for needle, key in LABEL_MAP:
            if needle in label:
                out[key] = value
                break
    return out


def classify_portion(name: str) -> tuple[int, str]:
    low = (name or "").lower()
    for keys, grams, kind in PORTION_RULES:
        if any(k in low for k in keys):
            return grams, kind
    return DEFAULT_PORTION


def scale_nutri(per_100g: dict, grams: float) -> dict:
    factor = grams / 100.0
    return {k: round(float(per_100g.get(k) or 0) * factor, 2) for k in EMPTY_NUTRI}


def round_nutri(data: dict, kcal_int: bool = True) -> dict:
    out = {}
    for key in EMPTY_NUTRI:
        val = float(data.get(key) or 0)
        if key in ("kcal", "kj") and kcal_int:
            out[key] = int(round(val))
        else:
            out[key] = round(val, 1)
    return out


def component_nutrition(comp: dict) -> dict:
    name = (comp.get("Name") or "").strip()
    grams, kind = classify_portion(name)
    official = parse_items(comp.get("Items") or [])
    has_official = official.get("kcal", 0) > 0 or official.get("proteiini", 0) > 0
    if has_official:
        per_100g = official
        source = "kouluruoka.fi 100 g"
    else:
        per_100g = dict(FALLBACK_PER_100G.get(kind) or EMPTY_NUTRI)
        source = "arvio (Fineli-tyyppinen)" if kind in FALLBACK_PER_100G else "ei dataa"
    annos = scale_nutri(per_100g, grams)
    return {
        "name": name,
        "osuus_g": grams,
        "tyyppi": kind,
        "lahde": source,
        "per_100g": round_nutri(per_100g, kcal_int=False),
        "annos": round_nutri(annos, kcal_int=False),
    }


def sum_annos(components: list) -> dict:
    total = dict(EMPTY_NUTRI)
    grams = 0
    official = 0
    estimated = 0
    missing = 0
    for comp in components:
        grams += int(comp.get("osuus_g") or 0)
        src = comp.get("lahde") or ""
        if src.startswith("kouluruoka"):
            official += 1
        elif src.startswith("arvio"):
            estimated += 1
        else:
            missing += 1
        for key in EMPTY_NUTRI:
            total[key] += float((comp.get("annos") or {}).get(key) or 0)
    rounded = round_nutri(total)
    rounded["osuus_g"] = grams
    rounded["komponentteja"] = len(components)
    rounded["virallinen_kpl"] = official
    rounded["arvio_kpl"] = estimated
    rounded["puuttuu_kpl"] = missing
    return rounded


def yhteenveto(tot: dict) -> str:
    if not tot or not tot.get("kcal"):
        return "Ei ravintotietoa"
    return (
        f"{tot['kcal']} kcal · P {tot['proteiini']} g · "
        f"H {tot['hiilihydraatit']} g · R {tot['rasva']} g · "
        f"Suola {tot['suola']} g"
    )


def meal_nutrition(meal: dict | None) -> dict | None:
    if not meal:
        return None
    components = [component_nutrition(n) for n in (meal.get("Nutritions") or [])]
    total = sum_annos(components)
    name = (meal.get("Name") or "").strip()
    short = (components[0].get("name") if components else "") or (
        name.split(",")[0].strip() if name else ""
    )
    return {
        "name": short,
        "full": name,
        "kcal": total.get("kcal", 0),
        "kj": total.get("kj", 0),
        "rasva": total.get("rasva", 0),
        "tyydyttynyt": total.get("tyydyttynyt", 0),
        "hiilihydraatit": total.get("hiilihydraatit", 0),
        "sokerit": total.get("sokerit", 0),
        "proteiini": total.get("proteiini", 0),
        "suola": total.get("suola", 0),
        "osuus_g": total.get("osuus_g", 0),
        "yhteenveto": yhteenveto(total),
        "komponentit": components,
        "virallinen_kpl": total.get("virallinen_kpl", 0),
        "arvio_kpl": total.get("arvio_kpl", 0),
        "huomio": (
            "Summa on arvio: kouluruoka.fi ilmoittaa arvot per 100 g, "
            "annoskoot VRN-koululaistaulukon mukaan. "
            "Salaatti/leipä/hedelmä usein ilman virallista riviä → Fineli-varat."
        ),
    }


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
        "ravinto": meal_nutrition(meal),
    }


def _add_flag(flags: list, seen: set, level: str, kind: str, title: str, where: str) -> None:
    key = (level, kind, title, where)
    if key in seen:
        return
    seen.add(key)
    flags.append({
        "taso": level,
        "tyyppi": kind,
        "otsikko": title,
        "kohde": where,
    })


def scan_watch(block: dict | None) -> dict:
    empty = {
        "taso": "ok",
        "varoitus_kpl": 0,
        "huomio_kpl": 0,
        "epailyttava_kpl": 0,
        "yhteenveto": "Ei erityisiä huomioita",
        "liput": [],
        "tyypit": [],
    }
    if not block:
        return empty
    flags: list = []
    seen: set = set()
    ingredients = block.get("ingredients") or []
    for item in ingredients:
        name = item.get("name") or ""
        label = item.get("label") or ""
        text = f"{name} {label}".lower()
        where = name or "ainesosa"
        for pattern, level, kind, title in INGREDIENT_RULES:
            if re.search(pattern, text, re.IGNORECASE):
                _add_flag(flags, seen, level, kind, title, where)
    for code in block.get("codes") or []:
        rule = ECODE_RULES.get(normalize(code))
        if not rule:
            continue
        level, kind, title = rule
        _add_flag(flags, seen, level, kind, f"{normalize(code)} {title}", "E-koodi")

    rav = block.get("ravinto") or {}
    for comp in rav.get("komponentit") or []:
        per = comp.get("per_100g") or {}
        cname = comp.get("name") or "komponentti"
        kind = comp.get("tyyppi") or ""
        salt = float(per.get("suola") or 0)
        sugars = float(per.get("sokerit") or 0)
        sat = float(per.get("tyydyttynyt") or 0)
        if salt >= 1.5:
            _add_flag(flags, seen, "varoitus", "suola", f"Suola {salt} g/100 g (korkea)", cname)
        elif salt >= 1.2:
            _add_flag(flags, seen, "huomio", "suola", f"Suola {salt} g/100 g", cname)
        if kind != "jalkiruoka" and sugars >= 10:
            _add_flag(flags, seen, "huomio", "sokeri", f"Sokerit {sugars} g/100 g", cname)
        elif kind == "jalkiruoka" and sugars >= 15:
            _add_flag(flags, seen, "huomio", "sokeri", f"Sokerit {sugars} g/100 g", cname)
        if sat >= 5 and kind not in ("juusto",):
            _add_flag(flags, seen, "huomio", "rasva", f"Tyydyttynyt rasva {sat} g/100 g", cname)

    meal_salt = float(rav.get("suola") or 0)
    meal_sugar = float(rav.get("sokerit") or 0)
    meal_sat = float(rav.get("tyydyttynyt") or 0)
    if meal_salt >= 2.5:
        _add_flag(flags, seen, "varoitus", "suola", f"Annosarvio suola {meal_salt} g", "koko annos")
    elif meal_salt >= 1.8:
        _add_flag(flags, seen, "huomio", "suola", f"Annosarvio suola {meal_salt} g", "koko annos")
    if meal_sugar >= 20:
        _add_flag(flags, seen, "huomio", "sokeri", f"Annosarvio sokerit {meal_sugar} g", "koko annos")
    if meal_sat >= 10:
        _add_flag(flags, seen, "huomio", "rasva", f"Annosarvio tyydyttynyt {meal_sat} g", "koko annos")

    warn_n = sum(1 for f in flags if f["taso"] == "varoitus")
    note_n = sum(1 for f in flags if f["taso"] == "huomio")
    sus_n = sum(1 for f in flags if f["taso"] == "epailyttava")
    if warn_n:
        level = "varoitus"
    elif note_n:
        level = "huomio"
    elif sus_n:
        level = "epailyttava"
    else:
        level = "ok"
    types = sorted({f["tyyppi"] for f in flags})
    if not flags:
        summary = "Ei erityisiä huomioita"
    else:
        bits = [f"{f['otsikko']} ({f['kohde']})" for f in flags[:6]]
        summary = " · ".join(bits)
    return {
        "taso": level,
        "varoitus_kpl": warn_n,
        "huomio_kpl": note_n,
        "epailyttava_kpl": sus_n,
        "yhteenveto": summary,
        "liput": flags,
        "tyypit": types,
    }


def compact_watch(block: dict | None) -> dict:
    watch = scan_watch(block)
    return {
        "taso": watch.get("taso") or "ok",
        "varoitus_kpl": watch.get("varoitus_kpl", 0),
        "huomio_kpl": watch.get("huomio_kpl", 0),
        "epailyttava_kpl": watch.get("epailyttava_kpl", 0),
        "yhteenveto": watch.get("yhteenveto") or "",
        "tyypit": watch.get("tyypit") or [],
        "liput": watch.get("liput") or [],
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


def parse_menu_date(raw: str, today: date) -> date | None:
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.", raw or "")
    if not match:
        return None
    day_n, month_n = int(match.group(1)), int(match.group(2))
    year = today.year
    try:
        parsed = date(year, month_n, day_n)
    except ValueError:
        return None
    if parsed - today > timedelta(days=180):
        parsed = date(year - 1, month_n, day_n)
    elif today - parsed > timedelta(days=180):
        parsed = date(year + 1, month_n, day_n)
    return parsed


def rebuild_code_stats(days: dict) -> dict:
    codes: dict = {}
    for iso, day in days.items():
        seen = set()
        for side in ("lounas", "kasvis"):
            block = day.get(side) or {}
            meal_name = block.get("name") or ""
            for code in block.get("codes") or []:
                rec = codes.setdefault(code, {
                    "days": 0,
                    "lounas": 0,
                    "kasvis": 0,
                    "last": "",
                    "last_meal": "",
                    "ruoat": [],
                })
                rec[side] = int(rec.get(side) or 0) + 1
                if iso >= (rec.get("last") or ""):
                    rec["last"] = iso
                    rec["last_meal"] = meal_name
                if meal_name and meal_name not in rec["ruoat"]:
                    rec["ruoat"] = (list(rec["ruoat"]) + [meal_name])[-8:]
                seen.add(code)
        for code in seen:
            codes[code]["days"] = int(codes[code].get("days") or 0) + 1
    return codes


def prune_days(days: dict, today: date) -> dict:
    cutoff = (today - timedelta(days=HISTORY_KEEP_DAYS)).isoformat()
    return {iso: row for iso, row in days.items() if iso >= cutoff}


def compact_day_side(block: dict | None) -> dict | None:
    if not block:
        return None
    watch = scan_watch(block)
    return {
        "name": block.get("name") or "",
        "codes": list(block.get("codes") or []),
        "taso": watch.get("taso") or "ok",
        "tyypit": list(watch.get("tyypit") or []),
    }


def merge_history(menu: dict, catalog: dict, today: date, hist: dict | None = None) -> dict:
    hist = hist or {"updated": "", "days": {}, "codes": {}}
    days = dict(hist.get("days") or {})
    menu_days = (
        menu.get("result", {})
        .get("pageContext", {})
        .get("menu", {})
        .get("Days")
        or []
    )
    for raw_day in menu_days:
        parsed = parse_menu_date(raw_day.get("Date") or "", today)
        if not parsed:
            continue
        lounas = None
        kasvis = None
        for meal in raw_day.get("Meals") or []:
            mtype = meal.get("MealType")
            if mtype == "Lounas" and lounas is None:
                lounas = meal_block(meal)
            elif mtype == "Kasvislounas" and kasvis is None:
                kasvis = meal_block(meal)
        days[parsed.isoformat()] = {
            "date_label": raw_day.get("Date") or parsed.isoformat(),
            "lounas": compact_day_side(lounas),
            "kasvis": compact_day_side(kasvis),
        }
    days = prune_days(days, today)
    codes = rebuild_code_stats(days)
    hist = {
        "updated": today.isoformat(),
        "days": days,
        "codes": codes,
    }
    ranked = sorted(
        codes.items(),
        key=lambda kv: (-int(kv[1].get("days") or 0), kv[0]),
    )
    top = []
    for code, rec in ranked[:TOP_LIMIT]:
        info = lookup(catalog, code)
        top.append({
            "code": code,
            "name": info.get("name") or "",
            "type": info.get("type") or "",
            "paivia": int(rec.get("days") or 0),
            "lounas": int(rec.get("lounas") or 0),
            "kasvis": int(rec.get("kasvis") or 0),
            "viimeksi": rec.get("last") or "",
            "ruoka": rec.get("last_meal") or "",
            "ruoat": list(rec.get("ruoat") or []),
        })
    lines = []
    for row in top:
        extra = f" — {row['name']}" if row.get("name") else ""
        lines.append(f"{row['code']}{extra}: {row['paivia']} pv")
    return hist, {
        "paivia": len(days),
        "koodeja": len(codes),
        "top": top,
        "top_teksti": "\n".join(lines),
        "top1": (top[0]["code"] if top else ""),
        "top1_paivia": (top[0]["paivia"] if top else 0),
    }


def meals_for_date(menu: dict, target: date) -> dict:
    days = (
        menu.get("result", {})
        .get("pageContext", {})
        .get("menu", {})
        .get("Days")
        or []
    )
    stamp = f"{target.day}.{target.month}."
    lounas = None
    kasvis = None
    for day in days:
        if stamp not in (day.get("Date") or ""):
            continue
        for meal in day.get("Meals") or []:
            mtype = meal.get("MealType")
            if mtype == "Lounas" and lounas is None:
                lounas = meal_block(meal)
            elif mtype == "Kasvislounas" and kasvis is None:
                kasvis = meal_block(meal)
    return {"lounas": lounas, "kasvis": kasvis}


def compact_ravinto(block: dict | None) -> dict | None:
    if not block:
        return None
    rav = block.get("ravinto") or {}
    return {
        "name": rav.get("name") or block.get("name"),
        "kcal": rav.get("kcal", 0),
        "kj": rav.get("kj", 0),
        "rasva": rav.get("rasva", 0),
        "tyydyttynyt": rav.get("tyydyttynyt", 0),
        "hiilihydraatit": rav.get("hiilihydraatit", 0),
        "sokerit": rav.get("sokerit", 0),
        "proteiini": rav.get("proteiini", 0),
        "suola": rav.get("suola", 0),
        "osuus_g": rav.get("osuus_g", 0),
        "yhteenveto": rav.get("yhteenveto") or "",
        "huomio": rav.get("huomio") or "",
        "virallinen_kpl": rav.get("virallinen_kpl", 0),
        "arvio_kpl": rav.get("arvio_kpl", 0),
        "komponentit": [
            {
                "name": c.get("name"),
                "osuus_g": c.get("osuus_g"),
                "lahde": c.get("lahde"),
                "kcal": (c.get("annos") or {}).get("kcal"),
                "proteiini": (c.get("annos") or {}).get("proteiini"),
                "hiilihydraatit": (c.get("annos") or {}).get("hiilihydraatit"),
                "rasva": (c.get("annos") or {}).get("rasva"),
                "suola": (c.get("annos") or {}).get("suola"),
            }
            for c in (rav.get("komponentit") or [])
        ],
    }


def menu_meta(menu: dict) -> dict:
    raw = (
        menu.get("result", {})
        .get("pageContext", {})
        .get("menu", {})
        or {}
    )
    return {
        "name": raw.get("RestaurantName") or "",
        "city": raw.get("CityName") or "",
        "start": raw.get("Start") or "",
        "days": raw.get("Days") or [],
    }


def calendar_days(menu: dict, today: date) -> list[dict]:
    out = []
    for raw_day in menu_meta(menu).get("days") or []:
        parsed = parse_menu_date(raw_day.get("Date") or "", today)
        if not parsed:
            continue
        lounas = None
        kasvis = None
        for meal in raw_day.get("Meals") or []:
            mtype = meal.get("MealType")
            if mtype == "Lounas" and lounas is None:
                lounas = meal_block(meal)
            elif mtype == "Kasvislounas" and kasvis is None:
                kasvis = meal_block(meal)
        out.append({
            "date": parsed,
            "label": raw_day.get("Date") or parsed.isoformat(),
            "lounas": lounas,
            "kasvis": kasvis,
        })
    return out


def build_snapshot(menu: dict, catalog: dict, today: date, hist: dict | None = None) -> tuple[dict, dict]:
    today_meals = meals_for_date(menu, today)
    tomorrow = meals_for_date(menu, today + timedelta(days=1))
    lounas = today_meals.get("lounas") or {}
    kasvis = today_meals.get("kasvis") or {}
    codes_l = list(lounas.get("codes") or [])
    codes_k = list(kasvis.get("codes") or [])
    all_codes = sorted(set(codes_l) | set(codes_k))
    if lounas:
        lounas = dict(lounas)
        lounas["details"] = details_for(codes_l, catalog)
    if kasvis:
        kasvis = dict(kasvis)
        kasvis["details"] = details_for(codes_k, catalog)
    new_hist, hist_view = merge_history(menu, catalog, today, hist)
    meta = menu_meta(menu)
    snapshot = {
        "school": meta.get("name") or "",
        "city": meta.get("city") or "",
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
        "ravinto_lounas": compact_ravinto(lounas or None),
        "ravinto_kasvis": compact_ravinto(kasvis or None),
        "ravinto_huomenna_lounas": compact_ravinto(tomorrow.get("lounas")),
        "ravinto_huomenna_kasvis": compact_ravinto(tomorrow.get("kasvis")),
        "huomio_lounas": compact_watch(lounas or None),
        "huomio_kasvis": compact_watch(kasvis or None),
        "lounas_tanaan": (lounas or {}).get("name") or "Ei tietoa",
        "kasvis_tanaan": (kasvis or {}).get("name") or "Ei tietoa",
        "lounas_huomenna": (tomorrow.get("lounas") or {}).get("name") if tomorrow.get("lounas") else "Ei tietoa",
        "kasvis_huomenna": (tomorrow.get("kasvis") or {}).get("name") if tomorrow.get("kasvis") else "Ei tietoa",
        "lounas_full": (lounas or {}).get("full") or "",
        "kasvis_full": (kasvis or {}).get("full") or "",
        "calendar": calendar_days(menu, today),
        **hist_view,
    }
    return snapshot, new_hist
