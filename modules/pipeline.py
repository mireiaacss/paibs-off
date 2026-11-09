"""
Walking-skeleton orchestrator: one function from any input to the full output.

    Input (barcode | text | photo)
      -> Data      off_client / ocr_reader
      -> Processing allergen_parser (+ OFF tag merge)
      -> AI / rules profile_matcher, additives_service, alternatives_service
      -> Output    dict rendered by app.py
"""

from __future__ import annotations

from modules import additives_service, alternatives_service, ocr_reader, off_client
from modules.allergen_parser import merge_off_tags, parse_allergens
from modules.profile_matcher import match_profile


def family_allergens(profile: dict) -> set:
    members = profile.get("members") or [profile]
    return {a for m in members for a in m.get("allergens", [])}


def analyze(profile: dict, *, barcode: str | None = None, text: str | None = None,
            image_bytes: bytes | None = None, use_live_off: bool = True,
            use_live_alternatives: bool = False) -> dict:
    """
    Run the full pipeline. Exactly one of barcode / text / image_bytes is used
    (priority: text if given explicitly, then barcode, then image).
    """
    product = None
    ocr = None
    input_mode = "text"

    if text is not None and text.strip():
        ingredient_text = text
    elif barcode:
        input_mode = "barcode"
        product = off_client.get_product_by_barcode(barcode, use_live=use_live_off)
        ingredient_text = product.get("ingredients_text", "") if product.get("found") else ""
    elif image_bytes is not None:
        input_mode = "photo"
        ocr = ocr_reader.read_label(image_bytes)
        ingredient_text = ocr["text"]
    else:
        ingredient_text = ""

    detected = parse_allergens(ingredient_text)
    if product and product.get("found"):
        merge_off_tags(detected, product.get("allergens_tags"), product.get("traces_tags"))

    verdict = match_profile(detected, profile)
    additives = additives_service.find_additives(ingredient_text)
    alternatives = alternatives_service.get_alternatives(
        family_allergens(profile),
        ingredient_text=ingredient_text,
        product_name=(product or {}).get("product_name", ""),
        categories_tags=(product or {}).get("categories_tags"),
        use_live=use_live_alternatives,
    )

    return {
        "input_mode": input_mode,
        "product": product,
        "ocr": ocr,
        "ingredient_text": ingredient_text,
        "detected": detected,
        "verdict": verdict,
        "additives": additives,
        "alternatives": alternatives,
    }
