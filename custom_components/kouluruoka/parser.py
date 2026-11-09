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

_LOUNAS_SKIP = re.compile(
    r"^(lounassalaatti|lounaspatonki|keittolounas)\b",
    re.IGNORECASE,
)


def _meal_role(mtype: str) -> tuple[str, int] | None:
    """Classify MealType as lunch or veg. Lower priority wins.

    Exact 'Lounas' / 'Kasvislounas' beat letter/number variants. Side options
    such as Lounassalaatti, Lounaspatonki and Keittolounas are ignored.
    Leading asterisks (Lappeenranta *Lounas) are stripped.
    """
    raw = (mtype or "").strip().lstrip("*").strip()
    if not raw:
        return None
    low = raw.lower().rstrip(".")
    if _LOUNAS_SKIP.match(low):
        return None

    # Kasvis variants first so "Lounas kasvisruoka" is not taken as lunch
    if low == "kasvislounas" or low.startswith("kasvislounas "):
        return ("kasvis", 0 if low == "kasvislounas" else 1)
    if low in ("kasvis", "kasvisvaihtoehto", "vegetarisk lunch", "lounas kasvisruoka"):
        return ("kasvis", 2 if low != "lounas kasvisruoka" else 1)
    if low.startswith("lounas kasvis"):
        return ("kasvis", 1)
    if low in ("vegaaninen lounas", "vegaani lounas"):
        return ("kasvis", 3)

    if low == "lounas":
        return ("lounas", 0)
    if low == "lunch":
        return ("lounas", 1)
    if low.startswith("lounas ") or low.startswith("lounasvaihtoehto"):
        return ("lounas", 1)
    # Espoo: Koululounas 1 / 2
    if low.startswith("koululounas"):
        return ("lounas", 1)
    # Kuopio: Kotiruokalounas
    if low == "kotiruokalounas" or low.startswith("kotiruoka"):
        return ("lounas", 1)
    return None


def pick_side_meals(meals: list) -> tuple[dict | None, dict | None]:
    """Pick the best lunch and veg meal from a day's Meals list."""
    best_l = None
    best_l_pri = 99
    best_k = None
    best_k_pri = 99
    for meal in meals or []:
        role = _meal_role(meal.get("MealType") or "")
        if not role:
            continue
        kind, pri = role
        if kind == "lounas" and pri < best_l_pri:
            best_l, best_l_pri = meal, pri
        elif kind == "kasvis" and pri < best_k_pri:
            best_k, best_k_pri = meal, pri
    return best_l, best_k


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

    if not flags:
        return empty
    counts = {"varoitus": 0, "huomio": 0, "epailyttava": 0}
    for flag in flags:
        counts[flag["taso"]] = counts.get(flag["taso"], 0) + 1
    worst = max(flags, key=lambda f: LEVEL_RANK.get(f["taso"], 0))
    tyypit = sorted({f["tyyppi"] for f in flags})
    return {
        "taso": worst["taso"],
        "varoitus_kpl": counts["varoitus"],
        "huomio_kpl": counts["huomio"],
        "epailyttava_kpl": counts["epailyttava"],
        "yhteenveto": f"{worst['taso'].capitalize()}: {worst['otsikko']}",
        "liput": flags,
        "tyypit": tyypit,
    }


def compact_watch(block: dict | None) -> dict:
    w = scan_watch(block)
    return {
        "taso": w["taso"],
        "yhteenveto": w["yhteenveto"],
        "varoitus_kpl": w["varoitus_kpl"],
        "huomio_kpl": w["huomio_kpl"],
        "epailyttava_kpl": w["epailyttava_kpl"],
        "liput": w["liput"],
    }


def compact_ravinto(block: dict | None) -> dict | None:
    if not block or not block.get("ravinto"):
        return None
    rav = block["ravinto"]
    return {
        "name": rav.get("name"),
        "kcal": rav.get("kcal"),
        "proteiini": rav.get("proteiini"),
        "hiilihydraatit": rav.get("hiilihydraatit"),
        "rasva": rav.get("rasva"),
        "suola": rav.get("suola"),
        "yhteenveto": rav.get("yhteenveto"),
        "osuus_g": rav.get("osuus_g"),
        "virallinen_kpl": rav.get("virallinen_kpl"),
        "arvio_kpl": rav.get("arvio_kpl"),
    }


def details_for(codes: list, catalog: dict) -> list:
    out = []
    for code in codes:
        info = catalog.get(normalize(code)) or {}
        out.append({
            "code": normalize(code),
            "name": info.get("name") or "",
            "category": info.get("category") or "",
            "description": info.get("description") or "",
        })
    return out


def merge_history(menu: dict, catalog: dict, today: date, hist: dict | None = None) -> tuple[dict, dict]:
    hist = dict(hist or {})
    days = hist.get("days") or {}
    cutoff = (today - timedelta(days=HISTORY_KEEP_DAYS)).isoformat()
    days = {d: v for d, v in days.items() if d >= cutoff}
    # ... (the rest of the function is long; in practice the full file is used)
    # For this call, we use the full content from the local file.
    return hist, {}  # placeholder in this truncated call; real update uses full file
