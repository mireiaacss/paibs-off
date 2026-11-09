"""
Open Food Facts barcode lookup (REAL component, with offline fallback).

get_product_by_barcode() calls the public OFF API v2. If the network is down or
OFF is slow during a live demo, we fall back to a small cache of real OFF
records (captured from the API on 2026-11-09) so the pipeline never breaks.
The result always says where the data came from ("source").
"""

from __future__ import annotations

import re

import requests

import config

OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
OFF_FIELDS = ",".join([
    "code", "product_name", "product_name_es", "product_name_en", "brands",
    "ingredients_text", "ingredients_text_es", "ingredients_text_en",
    "allergens_tags", "traces_tags", "image_url", "image_front_url",
    "nutriscore_grade", "categories_tags", "additives_tags", "quantity",
])

# Real OFF records, trimmed to the fields we use (offline demo fallback).
MOCK_PRODUCTS = {
    "3017620422003": {
        "barcode": "3017620422003",
        "product_name": "Nutella",
        "brands": "Nutella, Ferrero",
        "ingredients_text": "AZÚCAR, ACEITE VEGETAL, AVELLANAS (13%), LECHE DESCREMADA EN POLVO (8,7%), "
                            "CACAO MAGRO EN POLVO 7,4%), EMULSIONANTE: LECITINA, "
                            "SABORIZANTE IDENTICO AL NATURAL: VAINILLINA",
        "allergens_tags": ["en:milk", "en:nuts", "en:soybeans"],
        "traces_tags": [],
        "image_url": "https://images.openfoodfacts.org/images/products/301/762/042/2003/front_en.879.400.jpg",
        "nutriscore_grade": "unknown",
        "categories_tags": ["en:spreads", "en:sweet-spreads", "en:confectionary-based-spreads"],
        "quantity": "400 g",
    },
    "5000159407236": {
        "barcode": "5000159407236",
        "product_name": "Mars",
        "brands": "Mars, Mars Wrigley",
        "ingredients_text": "sugar, glucose syrup, cocoa butter, milk powder, cocoa paste, sunflower oil, "
                            "skimmed milk powder, lactose, milk powder, lean cocoa, concentrated butter (milk), "
                            "extract of malt barley, emulsifier (soy lecithin), salt, butter, palm, "
                            "white egg powder, protein milk hydrolysate, natural vanilla extract",
        "allergens_tags": ["en:eggs", "en:gluten", "en:milk", "en:soybeans"],
        "traces_tags": ["en:nuts", "en:peanuts"],
        "image_url": "https://images.openfoodfacts.org/images/products/500/015/940/7236/front_en.125.400.jpg",
        "nutriscore_grade": "e",
        "categories_tags": ["en:snacks", "en:confectioneries", "en:chocolate-candies", "en:bars"],
        "quantity": "51 g",
    },
    "3168930010265": {
        "barcode": "3168930010265",
        "product_name": "Cruesli mélange de noix",
        "brands": "Cruesli, Quaker",
        "ingredients_text": "whole oats 32%, whole wheat 18%, glucose syrup, sunflower oil, sugar, toasted almonds 4.2%, "
                            "hazelnuts 4%, oligofructose, pecans 1.5%, wheat flour, rice flour, brazil nuts 1%, "
                            "honey, natural flavours, antioxidant tocopherol, "
                            "may contain traces of milk, soy and sesame.",
        "allergens_tags": ["en:gluten", "en:nuts"],
        "traces_tags": ["en:milk", "en:sesame-seeds", "en:soybeans"],
        "image_url": "https://images.openfoodfacts.org/images/products/316/893/001/0265/front_en.297.400.jpg",
        "nutriscore_grade": "b",
        "categories_tags": ["en:breakfasts", "en:breakfast-cereals", "en:mueslis"],
        "quantity": "450 g",
    },
    "5449000000996": {
        "barcode": "5449000000996",
        "product_name": "Coca-Cola Original",
        "brands": "Coca-Cola",
        "ingredients_text": "Agua carbonatada, azúcar, colorante (E-150d), acidulante (ácido fosfórico), "
                            "aromas naturales (contiene cafeína).",
        "allergens_tags": [],
        "traces_tags": [],
        "image_url": "https://images.openfoodfacts.org/images/products/544/900/000/0996/front_en.1129.400.jpg",
        "nutriscore_grade": "e",
        "categories_tags": ["en:beverages", "en:sodas", "en:colas"],
        "quantity": "330 ml",
    },
    "7622210449283": {
        "barcode": "7622210449283",
        "product_name": "Prince",
        "brands": "LU, Prince",
        "ingredients_text": "Céréale 50 % (Farine de blé 34,8 %, farine de blé complet 15,2 %), sucre, "
                            "huiles végétales (palme, colza), cacao maigre en poudre 4,5 %, sirop de glucose, "
                            "amidon de blé, poudres à lever (carbonates d'ammonium, carbonates de sodium), "
                            "émulsifiant (lécithines de soja), sel, lait écrémé en poudre, "
                            "perméat de lactosérum (de lait), arômes. Peut contenir œuf.",
        "allergens_tags": ["en:eggs", "en:gluten", "en:milk", "en:soybeans"],
        "traces_tags": ["en:eggs"],
        "image_url": "https://images.openfoodfacts.org/images/products/762/221/044/9283/front_en.605.400.jpg",
        "nutriscore_grade": "e",
        "categories_tags": ["en:snacks", "en:biscuits", "en:chocolate-biscuits"],
        "quantity": "300 g",
    },
}


def _clean_barcode(barcode: str) -> str:
    return re.sub(r"\D", "", str(barcode or ""))


def _pick_ingredients(p: dict) -> str:
    """Prefer Spanish, then English, then generic text; skip placeholder junk."""
    for field in ("ingredients_text_es", "ingredients_text_en", "ingredients_text"):
        text = (p.get(field) or "").strip()
        if len(text) > 10 and ("," in text or " " in text) and "Ingredients-EN" not in text:
            return text
    return ""


def _normalise_product(barcode: str, p: dict) -> dict:
    return {
        "barcode": barcode,
        "product_name": p.get("product_name_es") or p.get("product_name") or p.get("product_name_en") or "Unknown product",
        "brands": p.get("brands", ""),
        "ingredients_text": _pick_ingredients(p),
        "allergens_tags": p.get("allergens_tags", []) or [],
        "traces_tags": p.get("traces_tags", []) or [],
        "image_url": p.get("image_front_url") or p.get("image_url") or "",
        "nutriscore_grade": (p.get("nutriscore_grade") or "unknown").lower(),
        "categories_tags": p.get("categories_tags", []) or [],
        "quantity": p.get("quantity", ""),
    }


def get_product_by_barcode(barcode: str, use_live: bool = True, timeout: float | None = None) -> dict:
    """
    Look up a product by EAN/UPC barcode.

    Returns a dict with: found, source ("live" | "offline_cache" | "none"), error,
    barcode, product_name, brands, ingredients_text, allergens_tags, traces_tags,
    image_url, nutriscore_grade, categories_tags, quantity.
    """
    code = _clean_barcode(barcode)
    if not code:
        return {"found": False, "source": "none", "error": "Empty or invalid barcode.", "barcode": ""}

    error = None
    if use_live:
        try:
            resp = requests.get(
                OFF_PRODUCT_URL.format(barcode=code),
                params={"fields": OFF_FIELDS},
                headers={"User-Agent": config.OFF_USER_AGENT},
                timeout=timeout or config.OFF_TIMEOUT_SECONDS,
            )
            if resp.status_code == 404:
                data = {"status": 0}
            else:
                resp.raise_for_status()
                data = resp.json()
            if data.get("status") == 1 and data.get("product"):
                return {"found": True, "source": "live", "error": None,
                        **_normalise_product(code, data["product"])}
            error = "Product not found in Open Food Facts."
        except (requests.RequestException, ValueError) as exc:
            error = f"Open Food Facts unreachable ({exc.__class__.__name__}); using offline cache."

    if code in MOCK_PRODUCTS:
        return {"found": True, "source": "offline_cache", "error": error, **MOCK_PRODUCTS[code]}

    return {"found": False, "source": "none", "error": error or "Product not in offline cache.", "barcode": code}
