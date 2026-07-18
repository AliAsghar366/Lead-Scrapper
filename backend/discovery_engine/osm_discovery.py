"""
OSM/Overpass discovery engine — maximum-coverage multi-strategy approach.

Runs up to 3 Overpass queries IN PARALLEL and merges results:
  1. Named-area query  — area["name"="Lahore"]  (no ID needed, broadest)
  2. ID-area query     — area(id:XXXXXXXX)       (exact admin boundary)
  3. Bounding-box query— (S,W,N,E) from Nominatim (catches suburbs/outskirts)

Each query uses ALL relevant OSM tags for the entity type in one union.
node + way + relation elements are all included.
Results are deduplicated by OSM element ID then by name.
"""
import asyncio
from typing import Optional

import httpx
from loguru import logger

from core.config import settings

HEADERS = {"User-Agent": settings.nominatim_user_agent}

# All relevant OSM tags per entity type — more tags = more results.
_TAG_MAP: dict[str, list[tuple[str, str]]] = {
    # ── Food & Drink ──────────────────────────────────────────────────────────
    "restaurant": [
        ("amenity", "restaurant"), ("amenity", "fast_food"),
        ("amenity", "food_court"), ("amenity", "biergarten"),
    ],
    "cafe": [
        ("amenity", "cafe"), ("shop", "coffee"),
    ],
    "bar": [
        ("amenity", "bar"), ("amenity", "pub"),
        ("amenity", "nightclub"), ("amenity", "biergarten"),
    ],
    "fast food": [
        ("amenity", "fast_food"), ("amenity", "food_court"),
    ],
    "bakery": [
        ("shop", "bakery"), ("shop", "pastry"),
        ("craft", "bakery"),
    ],
    "ice cream shop": [
        ("amenity", "ice_cream"), ("shop", "ice_cream"),
    ],
    "juice bar": [
        ("amenity", "juice_bar"), ("shop", "juice_bar"),
        ("amenity", "cafe"),
    ],
    "food court": [
        ("amenity", "food_court"),
    ],
    "seafood restaurant": [
        ("amenity", "restaurant"),
    ],
    "winery": [
        ("craft", "winery"), ("amenity", "winery"),
        ("tourism", "winery"),
    ],
    "brewery": [
        ("craft", "brewery"), ("industrial", "brewery"),
        ("amenity", "brewery"),
    ],
    "distillery": [
        ("craft", "distillery"),
    ],

    # ── Health & Medical ──────────────────────────────────────────────────────
    "hospital": [
        ("amenity",    "hospital"),  ("healthcare", "hospital"),
        ("amenity",    "clinic"),    ("healthcare", "clinic"),
        ("amenity",    "doctors"),
    ],
    "clinic": [
        ("amenity",    "clinic"),    ("amenity",    "doctors"),
        ("amenity",    "health_post"),
        ("healthcare", "clinic"),    ("healthcare", "doctor"),
        ("healthcare", "centre"),
    ],
    "dentist": [
        ("amenity",    "dentist"),   ("healthcare", "dentist"),
    ],
    "pharmacy": [
        ("amenity",    "pharmacy"),  ("shop",       "chemist"),
        ("healthcare", "pharmacy"),
    ],
    "veterinary clinic": [
        ("amenity", "veterinary"), ("healthcare", "veterinary"),
    ],
    "optician": [
        ("shop", "optician"), ("healthcare", "optometrist"),
    ],
    "physiotherapy": [
        ("healthcare", "physiotherapist"),
        ("healthcare", "rehabilitation"),
    ],
    "mental health": [
        ("healthcare", "psychotherapist"), ("healthcare", "psychologist"),
        ("amenity", "mental_health"),
    ],
    "medical laboratory": [
        ("healthcare", "laboratory"), ("amenity", "laboratory"),
    ],
    "gym": [
        ("leisure", "fitness_centre"), ("leisure", "sports_centre"),
        ("leisure", "sports_hall"),    ("sport",   "fitness"),
        ("amenity", "gym"),
    ],
    "yoga studio": [
        ("sport", "yoga"), ("leisure", "yoga"),
        ("leisure", "fitness_centre"),
    ],
    "spa": [
        ("leisure", "spa"), ("amenity", "spa"),
        ("shop", "beauty"),
    ],
    "massage center": [
        ("amenity", "massage"), ("shop", "massage"),
    ],
    "nursing home": [
        ("amenity", "nursing_home"), ("social_facility", "nursing_home"),
        ("amenity", "social_facility"),
    ],
    "dialysis center": [
        ("healthcare", "dialysis"),
    ],

    # ── Education ─────────────────────────────────────────────────────────────
    "school": [
        ("amenity", "school"), ("amenity", "kindergarten"),
    ],
    "university": [
        ("amenity", "university"), ("amenity", "college"),
    ],
    "kindergarten": [
        ("amenity", "kindergarten"), ("amenity", "childcare"),
    ],
    "language school": [
        ("amenity", "language_school"), ("amenity", "school"),
    ],
    "driving school": [
        ("amenity", "driving_school"),
    ],
    "music school": [
        ("amenity", "music_school"), ("amenity", "school"),
    ],
    "art school": [
        ("amenity", "art_school"), ("amenity", "school"),
    ],
    "dance school": [
        ("leisure", "dance"), ("amenity", "school"),
    ],
    "martial arts": [
        ("sport", "martial_arts"), ("sport", "boxing"),
        ("sport", "judo"),        ("sport", "karate"),
        ("sport", "taekwondo"),   ("leisure", "sports_centre"),
    ],
    "vocational school": [
        ("amenity", "college"), ("amenity", "vocational"),
    ],
    "tutoring center": [
        ("amenity", "tutoring_centre"), ("amenity", "school"),
    ],
    "sports academy": [
        ("leisure", "sports_centre"), ("leisure", "pitch"),
    ],
    "library": [
        ("amenity", "library"),
    ],

    # ── Accommodation ─────────────────────────────────────────────────────────
    "hotel": [
        ("tourism",  "hotel"),     ("tourism",   "motel"),
        ("tourism",  "resort"),    ("tourism",   "apartment"),
        ("building", "hotel"),
    ],
    "hostel": [
        ("tourism", "hostel"), ("tourism", "guest_house"),
    ],
    "resort": [
        ("tourism", "resort"), ("tourism", "hotel"),
    ],
    "camping": [
        ("tourism", "camp_site"), ("tourism", "caravan_site"),
    ],
    "serviced apartment": [
        ("tourism", "apartment"),
    ],

    # ── Tech & Business ───────────────────────────────────────────────────────
    "startup": [
        ("office", "company"), ("office", "it"), ("office", "technology"),
        ("office", "startup"),
    ],
    "software company": [
        ("office", "it"), ("office", "company"), ("office", "technology"),
    ],
    "software house": [
        ("office", "it"), ("office", "company"), ("office", "technology"),
    ],
    "data center": [
        ("office", "it"), ("building", "data_center"),
    ],
    "law firm": [
        ("office", "lawyer"), ("office", "law_firm"),
    ],
    "accounting firm": [
        ("office", "accountant"), ("office", "financial"),
    ],
    "coworking space": [
        ("office", "coworking"), ("amenity", "coworking_space"),
    ],
    "digital marketing agency": [
        ("office", "company"), ("office", "advertising"),
    ],
    "call center": [
        ("office", "company"),
    ],
    "consulting firm": [
        ("office", "consulting"), ("office", "company"),
    ],
    "insurance company": [
        ("office", "insurance"),
    ],
    "investment firm": [
        ("office", "financial"), ("office", "company"),
    ],
    "architecture firm": [
        ("office", "architect"),
    ],
    "engineering firm": [
        ("office", "engineer"), ("office", "engineering"),
    ],
    "media company": [
        ("office", "media"), ("amenity", "studio"),
    ],

    # ── Retail ────────────────────────────────────────────────────────────────
    "supermarket": [
        ("shop", "supermarket"), ("shop", "grocery"),
        ("shop", "convenience"), ("shop", "department_store"),
    ],
    "clothing store": [
        ("shop", "clothes"), ("shop", "fashion"),
    ],
    "electronics store": [
        ("shop", "electronics"), ("shop", "computer"),
        ("shop", "mobile_phone"),
    ],
    "furniture store": [
        ("shop", "furniture"), ("shop", "interior_decoration"),
    ],
    "toy store": [
        ("shop", "toys"),
    ],
    "jewelry store": [
        ("shop", "jewelry"), ("shop", "jewellery"),
        ("shop", "gold"),
    ],
    "shoe store": [
        ("shop", "shoes"), ("shop", "sports"),
    ],
    "sports store": [
        ("shop", "sports"), ("shop", "outdoor"),
    ],
    "music store": [
        ("shop", "musical_instrument"),
    ],
    "bookstore": [
        ("shop", "books"), ("amenity", "library"),
    ],
    "gift shop": [
        ("shop", "gift"), ("shop", "souvenir"),
    ],
    "pet shop": [
        ("shop", "pet"), ("shop", "pet_grooming"),
        ("amenity", "veterinary"),
    ],
    "florist": [
        ("shop", "florist"),
    ],
    "garden center": [
        ("shop", "garden_centre"), ("shop", "agrarian"),
    ],
    "hardware store": [
        ("shop", "hardware"), ("shop", "doityourself"),
        ("shop", "building_materials"),
    ],
    "stationery store": [
        ("shop", "stationery"), ("shop", "art"),
    ],
    "optical store": [
        ("shop", "optician"),
    ],
    "bicycle shop": [
        ("shop", "bicycle"),
    ],
    "antique shop": [
        ("shop", "antiques"), ("shop", "second_hand"),
        ("shop", "vintage"),
    ],
    "pawn shop": [
        ("shop", "pawnbroker"),
    ],
    "shopping mall": [
        ("shop", "mall"), ("building", "mall"),
        ("landuse", "retail"),
    ],
    "market": [
        ("amenity", "marketplace"), ("landuse", "retail"),
        ("shop", "market"),
    ],

    # ── Financial Services ────────────────────────────────────────────────────
    "bank": [
        ("amenity", "bank"), ("office", "financial"),
    ],
    "atm": [
        ("amenity", "atm"),
    ],
    "money exchange": [
        ("amenity", "bureau_de_change"),
    ],

    # ── Professional Services ─────────────────────────────────────────────────
    "real estate": [
        ("office", "estate_agent"), ("office", "real_estate"),
    ],
    "travel agency": [
        ("shop", "travel_agency"), ("office", "travel_agent"),
    ],
    "photography studio": [
        ("craft", "photographer"), ("shop", "photo"),
        ("amenity", "studio"),
    ],
    "printing shop": [
        ("shop", "printing"), ("craft", "print"),
    ],
    "event venue": [
        ("amenity", "events_venue"), ("amenity", "conference_centre"),
        ("amenity", "banquet"), ("leisure", "event_venue"),
    ],
    "shipping company": [
        ("office", "logistics"), ("amenity", "courier"),
    ],
    "storage facility": [
        ("amenity", "storage_rental"), ("building", "warehouse"),
    ],
    "moving company": [
        ("office", "moving_company"),
    ],
    "cleaning service": [
        ("office", "cleaning"),
    ],
    "security company": [
        ("office", "security"),
    ],
    "funeral home": [
        ("amenity", "funeral_home"), ("shop", "funeral_directors"),
    ],
    "internet cafe": [
        ("amenity", "internet_cafe"),
    ],
    "post office": [
        ("amenity", "post_office"),
    ],
    "lottery": [
        ("amenity", "gambling"), ("shop", "lottery"),
    ],
    "recycling center": [
        ("amenity", "recycling"),
    ],

    # ── Personal Services ─────────────────────────────────────────────────────
    "salon": [
        ("shop", "hairdresser"), ("shop", "beauty"),
        ("leisure", "spa"),
    ],
    "nail salon": [
        ("shop", "nail_salon"), ("shop", "beauty"),
    ],
    "tattoo parlor": [
        ("shop", "tattoo"),
    ],
    "laundry": [
        ("shop", "laundry"), ("shop", "dry_cleaning"),
    ],
    "tailor": [
        ("shop", "tailor"), ("craft", "tailor"),
    ],

    # ── Automotive ────────────────────────────────────────────────────────────
    "gas station": [
        ("amenity", "fuel"), ("amenity", "gas_station"),
    ],
    "car dealership": [
        ("shop", "car"), ("shop", "car_dealer"),
    ],
    "car repair": [
        ("amenity", "car_repair"), ("shop", "car_repair"),
    ],
    "car wash": [
        ("amenity", "car_wash"),
    ],
    "car rental": [
        ("amenity", "car_rental"),
    ],
    "auto parts": [
        ("shop", "car_parts"), ("shop", "tyres"),
    ],
    "parking": [
        ("amenity", "parking"),
    ],

    # ── Entertainment ─────────────────────────────────────────────────────────
    "cinema": [
        ("amenity", "cinema"),
    ],
    "theatre": [
        ("amenity", "theatre"),
    ],
    "nightclub": [
        ("amenity", "nightclub"),
    ],
    "casino": [
        ("amenity", "casino"),
    ],
    "bowling alley": [
        ("leisure", "bowling_alley"),
    ],
    "ice rink": [
        ("leisure", "ice_rink"),
    ],
    "escape room": [
        ("leisure", "escape_game"),
    ],
    "museum": [
        ("tourism", "museum"),
    ],
    "art gallery": [
        ("tourism", "gallery"),
    ],
    "zoo": [
        ("tourism", "zoo"),
    ],
    "aquarium": [
        ("tourism", "aquarium"),
    ],
    "stadium": [
        ("leisure", "stadium"), ("leisure", "sports_centre"),
    ],
    "golf course": [
        ("leisure", "golf_course"), ("leisure", "miniature_golf"),
    ],
    "snooker club": [
        ("leisure", "billiard_room"),
    ],
    "arcade": [
        ("leisure", "amusement_arcade"), ("amenity", "amusement_arcade"),
    ],
    "playland": [
        ("tourism", "theme_park"), ("leisure", "amusement_arcade"),
        ("leisure", "playground"), ("amenity", "amusement_arcade"),
        ("leisure", "water_park"),
    ],
    "play land": [
        ("tourism", "theme_park"), ("leisure", "amusement_arcade"),
        ("leisure", "playground"), ("amenity", "amusement_arcade"),
        ("leisure", "water_park"),
    ],
    "play lands": [
        ("tourism", "theme_park"), ("leisure", "amusement_arcade"),
        ("leisure", "playground"), ("amenity", "amusement_arcade"),
        ("leisure", "water_park"),
    ],
    "play area": [
        ("leisure", "playground"), ("leisure", "amusement_arcade"),
        ("tourism", "theme_park"),
    ],
    "play areas": [
        ("leisure", "playground"), ("leisure", "amusement_arcade"),
        ("tourism", "theme_park"),
    ],
    "amusement park": [
        ("tourism", "theme_park"), ("leisure", "amusement_arcade"),
        ("leisure", "playground"), ("leisure", "water_park"),
    ],
    "theme park": [
        ("tourism", "theme_park"), ("leisure", "amusement_arcade"),
    ],
    "playground": [
        ("leisure", "playground"), ("leisure", "amusement_arcade"),
    ],
    "entertainment": [
        ("tourism", "theme_park"), ("amenity", "cinema"),
        ("amenity", "theatre"), ("leisure", "amusement_arcade"),
        ("amenity", "casino"),
    ],
    "swimming pool": [
        ("leisure", "swimming_pool"), ("sport", "swimming"),
    ],
    "tennis club": [
        ("sport", "tennis"), ("leisure", "sports_centre"),
        ("leisure", "tennis"),
    ],
    "cricket club": [
        ("sport", "cricket"), ("leisure", "pitch"),
    ],
    "football club": [
        ("sport", "football"), ("sport", "soccer"),
        ("leisure", "pitch"),
    ],
    "sports club": [
        ("leisure", "sports_centre"), ("leisure", "pitch"),
    ],
    "paintball": [
        ("leisure", "sports_centre"),
    ],

    # ── Hospitality & Tourism ─────────────────────────────────────────────────
    "park": [
        ("leisure", "park"), ("leisure", "nature_reserve"),
        ("leisure", "garden"), ("tourism", "park"),
    ],

    # ── Religious ─────────────────────────────────────────────────────────────
    "mosque": [
        ("amenity", "place_of_worship"),
    ],
    "church": [
        ("amenity", "place_of_worship"),
    ],
    "temple": [
        ("amenity", "place_of_worship"),
    ],
    "synagogue": [
        ("amenity", "place_of_worship"),
    ],
    "gurdwara": [
        ("amenity", "place_of_worship"),
    ],

    # ── Manufacturing & Industrial ────────────────────────────────────────────
    "factory": [
        ("man_made", "works"), ("landuse", "industrial"),
        ("building", "industrial"),
    ],
    "logistics": [
        ("office", "logistics"), ("building", "warehouse"),
    ],

    # ── Agriculture ───────────────────────────────────────────────────────────
    "farm": [
        ("landuse", "farmland"), ("building", "farm"),
        ("landuse", "orchard"),
    ],
    "agricultural supply": [
        ("shop", "agrarian"),
    ],

    # ── Trades / Crafts ───────────────────────────────────────────────────────
    "plumber": [
        ("craft", "plumber"),
    ],
    "electrician": [
        ("craft", "electrician"),
    ],
    "carpenter": [
        ("craft", "carpenter"),
    ],
    "painter": [
        ("craft", "painter"),
    ],
    "construction": [
        ("office", "construction"), ("craft", "construction"),
    ],
}


# ── Overpass query builders ────────────────────────────────────────────────────

def _tag_union(tags: list[tuple[str, str]], scope: str) -> str:
    lines = []
    for key, val in tags:
        lines += [
            f'  node["{key}"="{val}"]{scope};',
            f'  way["{key}"="{val}"]{scope};',
            f'  relation["{key}"="{val}"]{scope};',
        ]
    return "\n".join(lines)


def _stem(keyword: str) -> str:
    """Strip common plural/possessive suffixes so 'playlands' → 'playland'."""
    w = keyword.lower()
    if len(w) > 5 and w.endswith("ies"):
        return w[:-3] + "y"          # bakeries → bakery
    if len(w) > 5 and w.endswith("es") and not w.endswith("ses"):
        return w[:-2]                 # churches → church
    if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]                 # playlands → playland
    return w


def _generic_union(keyword: str, scope: str) -> str:
    stem = _stem(keyword)
    # Include both the original keyword and its stem so either form matches
    pat = f"{stem}|{keyword}" if stem != keyword.lower() else stem
    return "\n".join([
        f'  node["name"~"{pat}",i]{scope};',
        f'  way["name"~"{pat}",i]{scope};',
        f'  relation["name"~"{pat}",i]{scope};',
    ])


def _resolve_tags(entity_type: str) -> list[tuple[str, str]] | None:
    """Look up tag list by entity type, also trying the stemmed singular form."""
    et = entity_type.lower()
    return _TAG_MAP.get(et) or _TAG_MAP.get(_stem(et))


def _named_area_query(entity_type: str, location_name: str) -> str:
    """Match area by name OR name:en — handles cities whose OSM name is non-Latin."""
    tags = _resolve_tags(entity_type)
    safe = location_name.replace('"', '\\"')
    scope = "(area.searchArea)"
    union = _tag_union(tags, scope) if tags else _generic_union(entity_type, scope)
    return f"""[out:json][timeout:120][maxsize:67108864];
(area["name"="{safe}"];area["name:en"="{safe}"];)->.searchArea;
(
{union}
);
out center tags;"""


def _id_area_query(entity_type: str, osm_id: int) -> str:
    """area(id:XXXXXXXX) — exact OSM relation boundary."""
    tags = _resolve_tags(entity_type)
    scope = "(area.searchArea)"
    union = _tag_union(tags, scope) if tags else _generic_union(entity_type, scope)
    area_id = osm_id + 3_600_000_000
    return f"""[out:json][timeout:120][maxsize:67108864];
area(id:{area_id})->.searchArea;
(
{union}
);
out center tags;"""


def _bbox_query(entity_type: str, bbox: list[float]) -> str:
    """Bounding box (S,W,N,E) from Nominatim — catches outskirts and suburbs."""
    south, north, west, east = bbox[0], bbox[1], bbox[2], bbox[3]
    scope = f"({south},{west},{north},{east})"
    tags = _resolve_tags(entity_type)
    union = _tag_union(tags, scope) if tags else _generic_union(entity_type, scope)
    return f"""[out:json][timeout:120][maxsize:67108864];
(
{union}
);
out center tags;"""


def _radius_query(entity_type: str, lat: float, lon: float, radius_m: int) -> str:
    """Radius fallback — always works."""
    scope = f"(around:{radius_m},{lat},{lon})"
    tags = _resolve_tags(entity_type)
    union = _tag_union(tags, scope) if tags else _generic_union(entity_type, scope)
    return f"""[out:json][timeout:120][maxsize:67108864];
(
{union}
);
out center tags;"""


# ── Geocoding ─────────────────────────────────────────────────────────────────

async def geocode(location: str) -> Optional[dict]:
    """
    Geocode a location using Nominatim.
    Fetches up to 8 results and prefers an admin boundary relation so that
    the Overpass area queries can use the correct OSM relation ID.
    """
    params = {"q": location, "format": "json", "limit": 8, "addressdetails": 1}
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                f"{settings.NOMINATIM_BASE_URL}/search",
                params=params, headers=HEADERS,
            )
            resp.raise_for_status()
            results = resp.json()
            if not results:
                return None

            # Prefer a result that is an admin boundary relation —
            # that gives us an accurate Overpass area ID.
            best = results[0]
            relation_result = None
            for r in results:
                if r.get("osm_type") == "relation" and r.get("class") in ("boundary", "place"):
                    relation_result = r
                    break

            primary = relation_result or best
            addr = primary.get("address", {})
            bbox_raw = primary.get("boundingbox")   # [S, N, W, E] as strings

            # city name: prefer address fields, fall back to the user's input
            city = (
                addr.get("city") or addr.get("town")
                or addr.get("municipality") or addr.get("county")
                or addr.get("village") or location
            )

            return {
                "lat":         float(primary["lat"]),
                "lon":         float(primary["lon"]),
                "osm_id":      primary.get("osm_id"),
                "osm_type":    primary.get("osm_type"),
                # Nominatim bbox: [south_lat, north_lat, west_lon, east_lon]
                "boundingbox": [float(x) for x in bbox_raw] if bbox_raw else None,
                "city":        city,
                "country":     addr.get("country", ""),
                # Always keep the raw user-supplied name for named-area queries
                "location_input": location,
            }
        except Exception as exc:
            logger.warning(f"Nominatim geocode failed for {location!r}: {exc}")
            return None


# ── Overpass executor ─────────────────────────────────────────────────────────

_OVERPASS_MIRRORS = [
    settings.OVERPASS_BASE_URL,
    "https://overpass.kumi.systems/api/interpreter",
]


async def _run_overpass(query: str, label: str = "") -> list:
    for mirror in _OVERPASS_MIRRORS:
        try:
            async with httpx.AsyncClient(timeout=130) as client:
                resp = await client.post(
                    mirror, data={"data": query}, headers=HEADERS,
                )
                resp.raise_for_status()
                elements = resp.json().get("elements", [])
                logger.debug(f"Overpass [{label}] via {mirror}: {len(elements)} elements")
                return elements
        except Exception as exc:
            logger.warning(f"Overpass [{label}] failed on {mirror}: {exc}")
    return []


# ── Element parser ─────────────────────────────────────────────────────────────

def _parse_element(el: dict, entity_type: str, city: str, country: str) -> Optional[dict]:
    tags = el.get("tags", {})
    name = (
        tags.get("name") or tags.get("name:en")
        or tags.get("name:ur") or tags.get("name:ar")
    )
    if not name:
        return None
    address_parts = [
        v for k, v in tags.items()
        if k in ("addr:housenumber", "addr:street", "addr:suburb", "addr:city") and v
    ]
    return {
        "name":     name,
        "category": entity_type,
        "website":  tags.get("website") or tags.get("contact:website") or tags.get("url"),
        "phone":    tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile"),
        "email":    tags.get("email") or tags.get("contact:email"),
        "address":  ", ".join(address_parts) if address_parts else None,
        "city":     tags.get("addr:city") or city,
        "country":  country,
        "source":   "osm",
    }


# ── Main engine ───────────────────────────────────────────────────────────────

class OSMDiscoveryEngine:

    async def discover(self, entity_type: str, location: str, radius_km: int = 0) -> list[dict]:
        geo = await geocode(location)
        if not geo:
            logger.warning(f"Could not geocode {location!r}")
            return []

        # Scale radius to the bounding-box diagonal so the fallback covers the
        # whole queried area — a country needs ~500 km, a city needs ~20 km.
        if radius_km == 0:
            bb = geo.get("boundingbox")
            if bb:
                import math
                lat_span = abs(bb[1] - bb[0])   # north - south (degrees)
                lon_span = abs(bb[3] - bb[2])   # east  - west  (degrees)
                # 1 degree ≈ 111 km; use half-diagonal as radius
                radius_km = max(20, int(math.hypot(lat_span, lon_span) * 111 / 2))
                radius_km = min(radius_km, 600)  # cap at 600 km to avoid Overpass timeout
            else:
                radius_km = 40

        # Build parallel tasks — run all applicable strategies simultaneously
        tasks: list[tuple[str, asyncio.coroutine]] = []

        # 1. Named area — use original user input (most reliable name for Overpass)
        area_name = geo.get("location_input") or geo.get("city") or location
        tasks.append(("named_area", _run_overpass(
            _named_area_query(entity_type, area_name), label="named_area"
        )))

        # 2. ID-based area — only if Nominatim returned an OSM relation
        if geo.get("osm_type") == "relation" and geo.get("osm_id"):
            tasks.append(("id_area", _run_overpass(
                _id_area_query(entity_type, geo["osm_id"]), label="id_area"
            )))

        # 3. Bounding box — always try (catches suburbs outside admin boundary)
        if geo.get("boundingbox"):
            tasks.append(("bbox", _run_overpass(
                _bbox_query(entity_type, geo["boundingbox"]), label="bbox"
            )))

        # Run all in parallel
        raw_results = await asyncio.gather(
            *[coro for _, coro in tasks], return_exceptions=True
        )

        # Merge — deduplicate first by OSM element ID, then by name
        city    = geo.get("city") or location
        country = geo.get("country", "")

        seen_osm: set[tuple] = set()
        seen_names: set[str] = set()
        combined: list[dict] = []

        for elements in raw_results:
            if not isinstance(elements, list):
                continue
            for el in elements:
                osm_key = (el.get("type"), el.get("id"))
                if osm_key in seen_osm:
                    continue
                seen_osm.add(osm_key)

                parsed = _parse_element(el, entity_type, city, country)
                if parsed and parsed["name"] not in seen_names:
                    seen_names.add(parsed["name"])
                    combined.append(parsed)

        # Fallback: if all strategies returned nothing, use large radius
        if not combined:
            logger.info(f"All area/bbox queries empty — falling back to {radius_km}km radius")
            elements = await _run_overpass(
                _radius_query(entity_type, geo["lat"], geo["lon"], radius_km * 1000),
                label="radius_fallback",
            )
            for el in elements:
                parsed = _parse_element(el, entity_type, city, country)
                if parsed and parsed["name"] not in seen_names:
                    seen_names.add(parsed["name"])
                    combined.append(parsed)

        logger.info(
            f"OSM found {len(combined)} unique {entity_type!r} in {location!r} "
            f"({len(seen_osm)} raw elements across all strategies)"
        )
        return combined


osm_discovery = OSMDiscoveryEngine()
