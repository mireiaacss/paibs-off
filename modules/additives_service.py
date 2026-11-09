"""
E-number additive lookup (STUB: curated dictionary in config.ADDITIVES, ~35 codes).

Detects E-numbers written as E220, E-220, E 220, e150d and a few additives
written by name (e.g. "tartrazina", "aspartame"), then explains them in plain
English / Spanish. A future level would replace the dictionary with the full
EFSA / Open Food Facts additives taxonomy.
"""

from __future__ import annotations

import re

import config
from modules.allergen_parser import normalize

_E_RE = re.compile(r"(?<![a-z0-9])e[\s\-]?(\d{3,4}[a-d]?)(?![0-9])")
RISK_ORDER = {"high": 0, "medium": 1, "low": 2, "unknown": 3}


def find_additives(ingredient_text: str, off_additives_tags: list | None = None) -> list[dict]:
    """
    Return a list of {code, name, category, risk, en, es, known}, sorted by risk.
    Unknown E-numbers are returned with risk "unknown" (never silently dropped).
    """
    norm = normalize(ingredient_text or "")
    codes: list[str] = []

    for m in _E_RE.finditer(norm):
        codes.append("E" + m.group(1).upper())
    for alias, code in config.ADDITIVE_NAME_ALIASES.items():
        if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", norm):
            codes.append(code)
    for tag in off_additives_tags or []:          # e.g. "en:e322i"
        m = re.match(r"en:e(\d{3,4}[a-d]?)", tag)
        if m:
            codes.append("E" + m.group(1).upper())

    results, seen = [], set()
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        info = config.ADDITIVES.get(code)
        if info:
            results.append({"code": code, "known": True, **info})
        else:
            results.append({
                "code": code, "known": False, "name": "Not in our dictionary",
                "category": "Unknown", "risk": "unknown",
                "en": "We do not have information on this additive yet. When in doubt, check it before use.",
                "es": "Todavía no tenemos información sobre este aditivo. Ante la duda, consúltelo.",
            })
    results.sort(key=lambda r: (RISK_ORDER.get(r["risk"], 9), r["code"]))
    return results
