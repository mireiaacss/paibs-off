"""
Safer / healthier alternatives (STUB catalogue + optional live OFF query).

Level 2 behaviour:
  * detect a demo category from OFF categories or ingredient keywords
  * return 2-3 curated, generic product *types* that are free of the family's
    allergens (we deliberately do not claim that a specific branded product is
    allergen-free - brand recipes change)
  * optional: query the Open Food Facts search service (search.openfoodfacts.org)
    for same-category products whose allergen AND trace tags avoid the profile's
    allergens, with a completed ingredient list and Nutri-Score A-C. Each hit is
    re-checked locally (OFF data is crowdsourced: a "pan de leche" can be missing
    its milk tag). Any failure falls back to the curated list.
"""

from __future__ import annotations

import requests

import config
from modules.allergen_parser import normalize

CATEGORY_KEYWORDS = {
    "spread": ["spread", "untable", "crema de cacao", "nutella", "pate a tartiner", "tartiner"],
    "pastry": ["croissant", "cruasan", "napolitana", "bolleria", "magdalena", "donut", "pastry"],
    "biscuits": ["biscuit", "galleta", "cookie", "biscuits", "galletas"],
    "cereal": ["cereal", "muesli", "granola", "cruesli", "copos", "avena"],
    "chocolate": ["chocolate", "cocoa", "cacao", "candy", "bar"],
    "pasta_bread": ["pasta", "bread", "pan ", "semolina", "harina", "flour", "durum"],
    "dairy": ["milk", "leche", "yogur", "yogurt", "cheese", "queso"],
    "snack": ["crisps", "patatas fritas", "chips", "snack", "nachos"],
    "drink": ["soda", "refresco", "cola", "beverage", "bebida", "juice", "zumo"],
    "seafood": ["surimi", "pescado", "fish", "gambas", "mejillones"],
}

OFF_CATEGORY_HINTS = {
    "en:spreads": "spread", "en:sweet-spreads": "spread", "en:biscuits": "biscuits",
    "en:breakfast-cereals": "cereal", "en:mueslis": "cereal", "en:chocolates": "chocolate",
    "en:chocolate-candies": "chocolate", "en:confectioneries": "chocolate",
    "en:breads": "pasta_bread", "en:pastas": "pasta_bread", "en:dairies": "dairy",
    "en:milks": "dairy", "en:crisps": "snack", "en:salty-snacks": "snack",
    "en:sodas": "drink", "en:beverages": "drink", "en:seafood": "seafood",
    "en:sweet-pastries-and-pies": "pastry", "en:viennoiseries": "pastry", "en:croissants": "pastry",
    "en:puffed-cereal-cakes": "snack", "en:puffed-rice-cakes": "snack",
}

# free_of = allergens the product type is typically formulated without.
# nutri = indicative Nutri-Score for the product type.
CATALOGUE = {
    "pastry": [
        {"name": "Plain rice cakes", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy", "Sesame"], "nutri": "a",
         "why": "Single-ingredient alternative with no added fat or sugar."},
        {"name": "Wholegrain toast with fruit (egg- and dairy-free bread)", "free_of": ["Milk", "Eggs", "Nuts", "Peanuts", "Soy"], "nutri": "a",
         "why": "Lower in saturated fat and sugar than laminated pastry."},
        {"name": "Certified gluten-free sponge cake (dairy-free)", "free_of": ["Gluten", "Milk", "Nuts", "Peanuts"], "nutri": "c",
         "why": "For coeliac profiles; check the egg declaration."},
    ],
    "spread": [
        {"name": "Sunflower-seed cocoa spread", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy"], "nutri": "d",
         "why": "Gets its creaminess from sunflower seeds instead of hazelnuts and milk."},
        {"name": "Pure tahini (100% sesame)", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy"], "nutri": "b",
         "why": "No added sugar; only safe if no one in the family is sesame-allergic."},
        {"name": "Fruit compote with no added sugar", "free_of": list(config.ALLERGENS), "nutri": "a",
         "why": "Naturally free of all 14 EU allergens and much less sugar."},
    ],
    "biscuits": [
        {"name": "Plain rice cakes", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy", "Sesame"], "nutri": "a",
         "why": "Single-ingredient snack, low in fat and sugar."},
        {"name": "Certified gluten-free oat biscuits (dairy- and egg-free)", "free_of": ["Milk", "Gluten", "Eggs", "Peanuts"], "nutri": "c",
         "why": "Wholegrain fibre without the most common biscuit allergens."},
        {"name": "Dried fruit & seed bars (no nuts)", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy"], "nutri": "b",
         "why": "Sweetened with fruit; look for 'nut-free factory' on the pack."},
    ],
    "cereal": [
        {"name": "Plain puffed rice", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy", "Sesame"], "nutri": "a",
         "why": "Simple single-grain cereal with no added sugar."},
        {"name": "Certified gluten-free porridge oats", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy"], "nutri": "a",
         "why": "High fibre; certified to avoid wheat cross-contamination."},
        {"name": "Corn flakes without malt extract", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy"], "nutri": "c",
         "why": "Many corn flakes contain barley malt - choose one that does not."},
    ],
    "chocolate": [
        {"name": "Dairy-free dark chocolate (70%+) from a nut-free factory", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs"], "nutri": "d",
         "why": "Less sugar than milk chocolate; check the 'may contain' line."},
        {"name": "Carob bar (allergen-free brand)", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy"], "nutri": "c",
         "why": "Naturally sweet, caffeine-free cocoa substitute."},
        {"name": "Freeze-dried fruit pieces", "free_of": list(config.ALLERGENS), "nutri": "a",
         "why": "Sweet treat with zero additives and no allergens."},
    ],
    "pasta_bread": [
        {"name": "Rice or corn pasta (certified gluten-free)", "free_of": ["Gluten", "Milk", "Eggs", "Nuts", "Peanuts", "Soy"], "nutri": "a",
         "why": "Same texture for kids, no wheat."},
        {"name": "Buckwheat noodles (100% buckwheat)", "free_of": ["Gluten", "Milk", "Eggs", "Nuts", "Peanuts"], "nutri": "a",
         "why": "Buckwheat is gluten-free despite its name - check it is not blended with wheat."},
        {"name": "Chickpea or lentil pasta", "free_of": ["Gluten", "Milk", "Eggs", "Nuts", "Peanuts", "Soy"], "nutri": "a",
         "why": "Higher protein and fibre."},
    ],
    "dairy": [
        {"name": "Fortified oat drink (calcium + vitamin D)", "free_of": ["Milk", "Nuts", "Peanuts", "Eggs", "Soy"], "nutri": "b",
         "why": "Dairy-free; contains gluten unless certified gluten-free."},
        {"name": "Fortified rice drink", "free_of": ["Milk", "Nuts", "Peanuts", "Eggs", "Soy", "Gluten"], "nutri": "c",
         "why": "Gentlest option for multiple allergies (not for under-5s as main drink)."},
        {"name": "Coconut-based yoghurt alternative", "free_of": ["Milk", "Nuts", "Peanuts", "Eggs", "Soy", "Gluten"], "nutri": "c",
         "why": "Coconut is not a tree nut under EU rules."},
    ],
    "snack": [
        {"name": "Plain salted popcorn", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy", "Sesame"], "nutri": "b",
         "why": "Wholegrain and less fat than crisps."},
        {"name": "Roasted chickpeas", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy", "Sesame"], "nutri": "a",
         "why": "High protein crunchy snack."},
        {"name": "Vegetable sticks with hummus (sesame-free)", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy"], "nutri": "a",
         "why": "Fresh option; classic hummus contains tahini (sesame)."},
    ],
    "drink": [
        {"name": "Sparkling water with fresh fruit", "free_of": list(config.ALLERGENS), "nutri": "a",
         "why": "No sugar, no additives."},
        {"name": "Unsweetened iced herbal tea", "free_of": list(config.ALLERGENS), "nutri": "a",
         "why": "Flavour without sugar or colourings."},
    ],
    "seafood": [
        {"name": "Fresh white fish fillet (hake / cod)", "free_of": ["Gluten", "Eggs", "Crustaceans", "Molluscs", "Mustard", "Milk"], "nutri": "a",
         "why": "Avoids the wheat, egg and shellfish typically added to surimi."},
        {"name": "Canned tuna in olive oil", "free_of": ["Gluten", "Eggs", "Crustaceans", "Molluscs", "Mustard", "Milk"], "nutri": "b",
         "why": "Single-ingredient protein; check for 'may contain crustaceans'."},
    ],
    "generic": [
        {"name": "Fresh fruit", "free_of": list(config.ALLERGENS), "nutri": "a",
         "why": "Naturally free of all 14 EU allergens."},
        {"name": "Plain rice cakes", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy", "Sesame"], "nutri": "a",
         "why": "Simple snack with a single ingredient."},
        {"name": "Plain natural popcorn", "free_of": ["Milk", "Nuts", "Peanuts", "Gluten", "Eggs", "Soy", "Sesame"], "nutri": "b",
         "why": "Wholegrain snack with no additives."},
    ],
}


def detect_category(ingredient_text: str = "", product_name: str = "", categories_tags: list | None = None) -> str:
    for tag in reversed(categories_tags or []):
        if tag in OFF_CATEGORY_HINTS:
            return OFF_CATEGORY_HINTS[tag]
    haystack = normalize(f"{product_name} {ingredient_text}")
    for category, words in CATEGORY_KEYWORDS.items():
        if any(w in haystack for w in words):
            return category
    return "generic"


SEARCH_URL = "https://search.openfoodfacts.org/search"


def _search_query(category_tag: str, avoid_tags: set, country: str | None) -> str:
    parts = [f'categories_tags:"{category_tag}"', 'states_tags:"en:ingredients-completed"',
             "nutriscore_grade:(a OR b OR c)"]
    for tag in sorted(avoid_tags):
        parts += [f'-allergens_tags:"{tag}"', f'-traces_tags:"{tag}"']
    if country:
        parts.append(f'countries_tags:"{country}"')
    return " ".join(parts)


def _live_off_alternatives(categories_tags: list, avoid: set, limit: int = 3, timeout: float = 8,
                           exclude_barcode: str | None = None) -> list[dict]:
    """Query OFF for same-category products compatible with `avoid`. Raises on network errors."""
    from modules.allergen_parser import parse_allergens  # local import avoids a cycle at module load

    en_tags = [t for t in (categories_tags or []) if t.startswith("en:")]
    avoid_tags = {config.ALLERGEN_TO_OFF_TAG[a] for a in avoid if a in config.ALLERGEN_TO_OFF_TAG}
    # Most specific category first, then its parent; Spain first, then worldwide
    attempts = [(tag, country) for tag in en_tags[::-1][:2] for country in ("en:spain", None)]
    out, seen = [], {exclude_barcode}
    for tag, country in attempts:
        resp = requests.get(
            SEARCH_URL,
            params={"q": _search_query(tag, avoid_tags, country), "page_size": 20,
                    "sort_by": "-unique_scans_n",
                    "fields": "code,product_name,brands,nutriscore_grade,allergens_tags,traces_tags"},
            headers={"User-Agent": config.OFF_USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
        for p in resp.json().get("hits", []):
            name = (p.get("product_name") or "").strip()
            tags = set(p.get("allergens_tags") or []) | set(p.get("traces_tags") or [])
            if not name or p.get("code") in seen or tags & avoid_tags:
                continue
            # Local re-check (OFF tags are crowdsourced): a name that itself reveals an EU
            # allergen ("croissant de crevettes", "pan de leche") is not a lower-risk option
            if parse_allergens(name)["contains"]:
                continue
            brands = p.get("brands") or []
            brands = ", ".join(brands) if isinstance(brands, list) else str(brands)
            seen.add(p.get("code"))
            out.append({
                "name": name,
                "brand": brands,
                "barcode": p.get("code"),
                "nutri": p.get("nutriscore_grade") or "unknown",
                "why": "No allergen or trace declaration from the active profile in Open Food Facts.",
                "source": "Open Food Facts",
            })
        if len(out) >= limit:          # stop at the most specific / local query that suffices
            break
    out.sort(key=lambda a: a["nutri"])          # Nutri-Score A first
    return out[:limit]


def get_alternatives(family_allergens: set | list, ingredient_text: str = "", product_name: str = "",
                     categories_tags: list | None = None, use_live: bool = False, limit: int = 3,
                     exclude_barcode: str | None = None) -> dict:
    """
    Return {"category", "alternatives": [{name, nutri, why, source, free_of?}], "source", "note"}.
    """
    avoid = set(family_allergens or [])
    category = detect_category(ingredient_text, product_name, categories_tags)
    note = "Suggestions are not endorsements. Verify the label of any product before purchase."

    if use_live and categories_tags:
        try:
            live = _live_off_alternatives(categories_tags, avoid, limit=limit, exclude_barcode=exclude_barcode)
            if live:
                return {"category": category, "alternatives": live, "source": "live", "note": note}
        except (requests.RequestException, ValueError):
            pass

    options = CATALOGUE.get(category, []) + CATALOGUE["generic"]
    picked, names = [], set()
    for alt in options:
        if avoid.issubset(set(alt["free_of"])) and alt["name"] not in names:
            picked.append({**alt, "brand": "", "barcode": None, "source": "Curated catalogue"})
            names.add(alt["name"])
        if len(picked) >= limit:
            break
    return {"category": category, "alternatives": picked, "source": "catalogue", "note": note}
