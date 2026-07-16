"""
Wikidata SPARQL discovery engine.

Queries the Wikidata knowledge graph for businesses by type and location.
100% free — no API key, no rate-limit beyond polite usage.
Returns entities with websites and phones that may not be in OSM at all.
"""
import asyncio
import httpx
from loguru import logger
from core.config import settings

_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
_WD_API = "https://www.wikidata.org/w/api.php"
_HEADERS = {
    "User-Agent": settings.nominatim_user_agent,
    "Accept": "application/sparql-results+json",
}

# Wikidata Q-IDs for each entity type (include common subtypes)
_ENTITY_QIDS: dict[str, list[str]] = {
    # ── Food & Drink ──────────────────────────────────────────────────────────
    "restaurant":           ["Q11707", "Q1010720", "Q2095549"],
    "cafe":                 ["Q30022",  "Q5282"],
    "bar":                  ["Q187456", "Q653534", "Q622425"],
    "fast food":            ["Q524757", "Q1941116"],
    "bakery":               ["Q274393"],
    "ice cream shop":       ["Q3573915"],
    "juice bar":            ["Q30022"],
    "food court":           ["Q1193345"],
    "seafood restaurant":   ["Q11707"],
    "winery":               ["Q156551"],
    "brewery":              ["Q131734"],
    "distillery":           ["Q2634597"],

    # ── Health & Medical ──────────────────────────────────────────────────────
    "hospital":             ["Q16917",  "Q1774898"],
    "clinic":               ["Q1026626","Q3745008"],
    "dentist":              ["Q1349308","Q27954952"],
    "pharmacy":             ["Q35428",  "Q1929963"],
    "veterinary clinic":    ["Q2512251", "Q170427"],
    "optician":             ["Q30023"],
    "physiotherapy":        ["Q1774898"],
    "mental health":        ["Q7284", "Q1774898"],
    "medical laboratory":   ["Q1814999"],
    "gym":                  ["Q988108", "Q7075"],
    "yoga studio":          ["Q234497"],
    "spa":                  ["Q219616"],
    "massage center":       ["Q213156"],
    "nursing home":         ["Q837940"],
    "dialysis center":      ["Q1774898"],

    # ── Education ─────────────────────────────────────────────────────────────
    "school":               ["Q3914",   "Q9842",   "Q875538"],
    "university":           ["Q3918",   "Q875538"],
    "kindergarten":         ["Q132580"],
    "language school":      ["Q1664720"],
    "driving school":       ["Q319604"],
    "music school":         ["Q81060"],
    "art school":           ["Q1553741"],
    "dance school":         ["Q1075753"],
    "martial arts":         ["Q169534"],
    "vocational school":    ["Q9826"],
    "tutoring center":      ["Q3914"],
    "sports academy":       ["Q875538"],
    "library":              ["Q7075"],

    # ── Accommodation ─────────────────────────────────────────────────────────
    "hotel":                ["Q27686",  "Q2217812"],
    "hostel":               ["Q654893"],
    "resort":               ["Q875131"],
    "camping":              ["Q832778"],
    "serviced apartment":   ["Q27686"],

    # ── Tech & Business ───────────────────────────────────────────────────────
    "software company":     ["Q1650915","Q4182287"],
    "software house":       ["Q1650915","Q4182287"],
    "data center":          ["Q247153"],
    "law firm":             ["Q613142"],
    "accounting firm":      ["Q815614"],
    "coworking space":      ["Q1628032"],
    "digital marketing agency": ["Q1440390"],
    "call center":          ["Q485096"],
    "consulting firm":      ["Q1198596"],
    "insurance company":    ["Q43183"],
    "investment firm":      ["Q1137756"],
    "architecture firm":    ["Q170065"],
    "engineering firm":     ["Q170065"],
    "media company":        ["Q2088357"],

    # ── Retail ────────────────────────────────────────────────────────────────
    "supermarket":          ["Q180846", "Q1632976"],
    "clothing store":       ["Q811966"],
    "electronics store":    ["Q1139686"],
    "furniture store":      ["Q2071316"],
    "toy store":            ["Q7836"],
    "jewelry store":        ["Q188048"],
    "shoe store":           ["Q577048"],
    "sports store":         ["Q1517632"],
    "music store":          ["Q1203867"],
    "bookstore":            ["Q292079"],
    "gift shop":            ["Q866588"],
    "pet shop":             ["Q1553930"],
    "florist":              ["Q920864"],
    "garden center":        ["Q766578"],
    "hardware store":       ["Q1197685"],
    "stationery store":     ["Q1340387"],
    "optical store":        ["Q30023"],
    "bicycle shop":         ["Q1530702"],
    "antique shop":         ["Q866588"],
    "pawn shop":            ["Q2092279"],
    "shopping mall":        ["Q11315"],
    "market":               ["Q161513"],

    # ── Financial Services ────────────────────────────────────────────────────
    "bank":                 ["Q806",    "Q22687"],
    "atm":                  ["Q101965"],
    "money exchange":       ["Q208750"],

    # ── Professional Services ─────────────────────────────────────────────────
    "real estate":          ["Q1368930"],
    "travel agency":        ["Q217107"],
    "photography studio":   ["Q41298"],
    "printing shop":        ["Q1665651"],
    "event venue":          ["Q797930"],
    "shipping company":     ["Q1432774"],
    "storage facility":     ["Q200263"],
    "moving company":       ["Q2120398"],
    "cleaning service":     ["Q31045"],
    "security company":     ["Q789687"],
    "funeral home":         ["Q846821"],
    "internet cafe":        ["Q259175"],
    "post office":          ["Q35054"],
    "lottery":              ["Q2582016"],
    "recycling center":     ["Q189970"],

    # ── Personal Services ─────────────────────────────────────────────────────
    "salon":                ["Q852160"],
    "nail salon":           ["Q1340904"],
    "tattoo parlor":        ["Q23488"],
    "laundry":              ["Q132811"],
    "tailor":               ["Q35217"],

    # ── Automotive ────────────────────────────────────────────────────────────
    "gas station":          ["Q205495"],
    "car dealership":       ["Q1136912"],
    "car repair":           ["Q1338222"],
    "car wash":             ["Q1047389"],
    "car rental":           ["Q2178765"],
    "auto parts":           ["Q1338222"],
    "parking":              ["Q44539"],

    # ── Entertainment ─────────────────────────────────────────────────────────
    "cinema":               ["Q41253"],
    "theatre":              ["Q24354"],
    "nightclub":            ["Q622425"],
    "casino":               ["Q133215"],
    "bowling alley":        ["Q1371150"],
    "ice rink":             ["Q201684"],
    "escape room":          ["Q20000498"],
    "museum":               ["Q33506"],
    "art gallery":          ["Q207694"],
    "zoo":                  ["Q43501"],
    "aquarium":             ["Q188065"],
    "stadium":              ["Q483110"],
    "golf course":          ["Q1048525"],
    "snooker club":         ["Q23397"],
    "arcade":               ["Q1137105"],
    "playland":             ["Q194166", "Q1137105", "Q5320"],
    "play land":            ["Q194166", "Q1137105", "Q5320"],
    "amusement park":       ["Q194166"],
    "theme park":           ["Q194166"],
    "playground":           ["Q5320"],
    "entertainment":        ["Q194166", "Q41253"],
    "swimming pool":        ["Q1501",   "Q784750"],
    "tennis club":          ["Q27573"],
    "cricket club":         ["Q476028"],
    "football club":        ["Q476028"],
    "sports club":          ["Q476028", "Q2933455"],
    "paintball":            ["Q3063"],

    # ── Hospitality & Tourism ─────────────────────────────────────────────────
    "park":                 ["Q22698",  "Q179049"],

    # ── Religious ─────────────────────────────────────────────────────────────
    "mosque":               ["Q32815"],
    "church":               ["Q16970"],
    "temple":               ["Q44539"],
    "synagogue":            ["Q34627"],
    "gurdwara":             ["Q228385"],

    # ── Manufacturing & Industrial ────────────────────────────────────────────
    "factory":              ["Q83405"],
    "logistics":            ["Q1432774"],

    # ── Agriculture ───────────────────────────────────────────────────────────
    "farm":                 ["Q131596"],
    "agricultural supply":  ["Q131596"],

    # ── Trades / Crafts ───────────────────────────────────────────────────────
    "plumber":              ["Q252924"],
    "electrician":          ["Q165029"],
    "carpenter":            ["Q159705"],
    "painter":              ["Q1028181"],
    "construction":         ["Q13226383"],
}


async def _get_location_qid(location: str) -> str | None:
    """Resolve a city/location name to its Wikidata Q-ID."""
    params = {
        "action": "wbsearchentities",
        "search": location,
        "language": "en",
        "type": "item",
        "limit": 8,
        "format": "json",
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                _WD_API, params=params,
                headers={"User-Agent": settings.nominatim_user_agent},
            )
            resp.raise_for_status()
            items = resp.json().get("search", [])

        # Prefer items whose description contains settlement/city keywords
        settlement_kws = {
            "city", "town", "municipality", "capital", "district",
            "metropolitan", "division", "province", "state",
        }
        for item in items:
            desc = item.get("description", "").lower()
            if any(kw in desc for kw in settlement_kws):
                logger.debug(f"Wikidata location QID for {location!r}: {item['id']} ({desc})")
                return item["id"]

        # Fallback: first result
        if items:
            return items[0]["id"]
    except Exception as exc:
        logger.debug(f"Wikidata location lookup failed for {location!r}: {exc}")
    return None


async def _run_sparql(entity_type: str, location_qid: str) -> list[dict]:
    qids = _resolve_qids(entity_type.lower())
    if not qids:
        return []

    type_values = " ".join(f"wd:{q}" for q in qids)

    # Search the location and its administrative sub-divisions (up to 3 levels deep)
    sparql = f"""
SELECT DISTINCT ?item ?name ?website ?phone ?address WHERE {{
  VALUES ?entityType {{ {type_values} }}
  ?item wdt:P31/wdt:P279* ?entityType.
  {{
    {{ ?item wdt:P131 wd:{location_qid}. }}
    UNION
    {{ ?item wdt:P131/wdt:P131 wd:{location_qid}. }}
    UNION
    {{ ?item wdt:P131/wdt:P131/wdt:P131 wd:{location_qid}. }}
    UNION
    {{ ?item wdt:P276 wd:{location_qid}. }}
  }}
  ?item rdfs:label ?name FILTER(LANG(?name) = "en").
  OPTIONAL {{ ?item wdt:P856 ?website. }}
  OPTIONAL {{ ?item wdt:P1329 ?phone. }}
  OPTIONAL {{ ?item wdt:P6375 ?address. }}
}}
LIMIT 1000
"""
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            resp = await client.get(
                _SPARQL_ENDPOINT,
                params={"query": sparql},
                headers=_HEADERS,
            )
            resp.raise_for_status()
            bindings = resp.json().get("results", {}).get("bindings", [])

        results: list[dict] = []
        seen: set[str] = set()
        for b in bindings:
            name = b.get("name", {}).get("value", "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            results.append({
                "name":     name,
                "website":  b.get("website", {}).get("value"),
                "phone":    b.get("phone", {}).get("value"),
                "address":  b.get("address", {}).get("value"),
                "source":   "wikidata",
            })
        logger.info(f"Wikidata found {len(results)} {entity_type!r} in QID {location_qid}")
        return results

    except Exception as exc:
        logger.warning(f"Wikidata SPARQL failed: {exc}")
        return []


def _resolve_qids(entity_type: str) -> list[str] | None:
    """Look up QIDs by entity type, falling back to the stemmed singular form."""
    et = entity_type.lower()
    if et in _ENTITY_QIDS:
        return _ENTITY_QIDS[et]
    # Try simple plural strip: "play lands" → "play land", "arcades" → "arcade"
    if et.endswith("s") and et[:-1] in _ENTITY_QIDS:
        return _ENTITY_QIDS[et[:-1]]
    return None


async def wikidata_discover(entity_type: str, location: str) -> list[dict]:
    """Entry point: find businesses by type and location via Wikidata."""
    if not _resolve_qids(entity_type.lower()):
        return []

    location_qid = await _get_location_qid(location)
    if not location_qid:
        logger.info(f"Wikidata: no Q-ID found for {location!r}, skipping")
        return []

    return await _run_sparql(entity_type, location_qid)
