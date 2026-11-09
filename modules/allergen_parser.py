"""
Ingredient-text -> allergen engine (REAL component).

Pipeline for one label:
  1. normalise text (lower-case, strip accents, collapse whitespace)
  2. split into "contains" text and "may contain" clauses
  3. for every allergen: mask its false friends, then regex-match plain names,
     hidden derivatives and E-number patterns on word boundaries
  4. apply the "When in doubt, warn" guardrail: ambiguous ingredients,
     unrecognised E-numbers and unparsed chemical names become warnings

Returns {"contains": set, "may_contain": set, "warnings": list, "detected_terms": dict}
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import config


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
def normalize(text: str) -> str:
    """Lower-case, strip accents, unify ligatures and whitespace."""
    if not text:
        return ""
    text = text.replace("œ", "oe").replace("Œ", "oe")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = text.replace("_", " ")  # Open Food Facts marks allergens as _milk_
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _term_regex(term: str) -> str:
    """Word-bounded regex for a term, tolerant to simple plurals and hyphens."""
    parts = [re.escape(p) for p in normalize(term).split(" ")]
    body = r"[\s\-]+".join(parts)
    return rf"(?<![a-z]){body}(?:s|es)?(?![a-z])"


@lru_cache(maxsize=1)
def _compiled_terms() -> dict:
    """allergen -> list of (compiled_regex, original_term, is_hidden)."""
    compiled = {}
    for key, info in config.ALLERGENS.items():
        entries = []
        for term in info["plain"]:
            if term in config.WHOLE_ITEM_ONLY_TERMS:
                continue
            entries.append((re.compile(_term_regex(term)), term, False))
        for term in info["hidden"]:
            entries.append((re.compile(_term_regex(term)), term, True))
        for pattern in config.ALLERGEN_REGEX.get(key, []):
            entries.append((re.compile(pattern), pattern, True))
        # Longest terms first so "durum wheat semolina" is reported before "wheat"
        entries.sort(key=lambda e: -len(e[1]))
        compiled[key] = entries
    return compiled


@lru_cache(maxsize=1)
def _compiled_false_friends() -> list:
    """List of (compiled_regex, phrase, [allergens]) sorted longest first."""
    items = []
    for phrase, allergens in config.FALSE_FRIENDS.items():
        items.append((re.compile(_term_regex(phrase)), phrase, allergens))
    items.sort(key=lambda e: -len(e[1]))
    return items


_TRIGGER_RE = re.compile(
    r"(?<![a-z])(?:" + "|".join(config.MAY_CONTAIN_TRIGGERS) + r")(?![a-z])"
)
# Sentence break: ".", ";", "!" or newline - but not a decimal point like 4.5
_SENTENCE_BREAK_RE = re.compile(r"(?<!\d)[.;!\n]|[.;!\n](?!\d)")


def split_may_contain(text: str) -> tuple[str, list[str]]:
    """
    Split normalised text into (main_text, [may_contain_clauses]).
    A clause starts at a trigger phrase and runs to the next sentence break.
    """
    main_parts, clauses = [], []
    pos = 0
    while True:
        match = _TRIGGER_RE.search(text, pos)
        if not match:
            main_parts.append(text[pos:])
            break
        main_parts.append(text[pos:match.start()])
        end_match = _SENTENCE_BREAK_RE.search(text, match.end())
        end = end_match.start() if end_match else len(text)
        clauses.append(text[match.end():end].strip(" :,"))
        pos = end
    return " ".join(main_parts), [c for c in clauses if c]


def _mask_false_friends(text: str, allergen: str) -> tuple[str, list[str]]:
    """Replace false-friend phrases relevant to `allergen` with spaces."""
    hits = []
    for regex, phrase, targets in _compiled_false_friends():
        if "*" in targets or allergen in targets:
            if regex.search(text):
                hits.append(phrase)
                text = regex.sub(lambda m: " " * len(m.group(0)), text)
    return text, hits


def _items(text: str) -> list[str]:
    """Comma / bracket separated ingredient items."""
    return [i.strip(" .:-*") for i in re.split(r"[,;()\[\]]", text) if i.strip(" .:-*")]


def _find_allergens(text: str) -> tuple[dict, set]:
    """allergen -> list of {term, hidden}; plus false friends that were ignored."""
    found: dict[str, list[dict]] = {}
    false_friends_seen: set[str] = set()
    items = set(_items(text))
    for key, entries in _compiled_terms().items():
        masked, ff = _mask_false_friends(text, key)
        false_friends_seen.update(ff)
        hits = []
        for regex, term, hidden in entries:
            if regex.search(masked):
                hits.append({"term": term, "hidden": hidden})
                # Consume the match so "wheat" isn't double-reported after "durum wheat semolina"
                masked = regex.sub(lambda m: " " * len(m.group(0)), masked)
        for term in config.ALLERGENS[key]["plain"]:
            if term in config.WHOLE_ITEM_ONLY_TERMS and term in items:
                hits.append({"term": term, "hidden": False})
        if hits:
            found[key] = hits
    return found, false_friends_seen


# ---------------------------------------------------------------------------
# Guardrail: "When in doubt, warn"
# ---------------------------------------------------------------------------
_E_NUMBER_RE = re.compile(r"(?<![a-z0-9])e[\s\-]?(\d{3,4}[a-d]?)(?![0-9])")


def _guardrail_warnings(norm: str, detected: dict) -> list[dict]:
    warnings: list[dict] = []

    if len(norm) < 8:
        warnings.append({
            "type": "no_text",
            "term": "",
            "message": "Ingredient list is missing or too short to analyse. Treat this product as UNKNOWN.",
            "possible_allergens": list(config.ALLERGENS.keys()),
        })
        return warnings

    for pattern, (message, possible) in config.AMBIGUOUS_TERMS.items():
        m = re.search(pattern, norm)
        if m:
            warnings.append({
                "type": "ambiguous",
                "term": m.group(0).strip(),
                "message": message,
                "possible_allergens": possible,
            })

    for m in _E_NUMBER_RE.finditer(norm):
        code = "E" + m.group(1).upper()
        if code not in config.ADDITIVES:
            warnings.append({
                "type": "unknown_additive",
                "term": code,
                "message": f"{code} is not in our additive dictionary - check what it is before giving it to your child.",
                "possible_allergens": [],
            })

    matched_terms = {normalize(h["term"]) for hits in detected.values() for h in hits}
    for item in _items(norm):
        # An item that already produced an allergen hit is parsed, not "unknown"
        if any(re.search(rf"(?<![a-z]){re.escape(t)}", item) for t in matched_terms):
            continue
        for m in re.finditer(config.CHEMICAL_SUFFIX_REGEX, item):
            word = m.group(0)
            if word in config.KNOWN_SAFE_CHEMICALS:
                continue
            warnings.append({
                "type": "unparsed_chemical",
                "term": item,
                "message": f"Could not interpret '{item}'. Unrecognised technical ingredient - verify on the package.",
                "possible_allergens": [],
            })
            break

    # Deduplicate by (type, term)
    seen, unique = set(), []
    for w in warnings:
        k = (w["type"], w["term"])
        if k not in seen:
            seen.add(k)
            unique.append(w)
    return unique


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def parse_allergens(ingredient_text: str) -> dict:
    """
    Detect EU-14 allergens in an ingredient list (Spanish, English, partial FR/CA).

    Returns:
        {
          "contains":       set of allergen keys present as ingredients,
          "may_contain":    set of allergen keys only in precautionary clauses,
          "warnings":       list of {"type", "term", "message", "possible_allergens"},
          "detected_terms": {allergen: [{"term", "hidden", "section"}]},
          "false_friends_ignored": sorted list of phrases deliberately not flagged,
          "normalized_text": str,
        }
    """
    norm = normalize(ingredient_text or "")
    main_text, clauses = split_may_contain(norm)

    contains_hits, ff_main = _find_allergens(main_text)
    may_hits, ff_may = {}, set()
    for clause in clauses:
        hits, ff = _find_allergens(clause)
        ff_may.update(ff)
        for k, v in hits.items():
            may_hits.setdefault(k, []).extend(v)

    detected_terms: dict[str, list[dict]] = {}
    for k, hits in contains_hits.items():
        detected_terms.setdefault(k, []).extend({**h, "section": "contains"} for h in hits)
    for k, hits in may_hits.items():
        detected_terms.setdefault(k, []).extend({**h, "section": "may_contain"} for h in hits)

    contains = set(contains_hits)
    may_contain = set(may_hits) - contains  # "contains" always wins

    return {
        "contains": contains,
        "may_contain": may_contain,
        "warnings": _guardrail_warnings(norm, contains_hits),
        "detected_terms": detected_terms,
        "false_friends_ignored": sorted(ff_main | ff_may),
        "normalized_text": norm,
    }


def merge_off_tags(result: dict, allergens_tags: list | None, traces_tags: list | None) -> dict:
    """
    Merge Open Food Facts' own allergen/trace tags into a parser result
    (belt and braces: if either source flags an allergen, we flag it).
    """
    for tag in allergens_tags or []:
        key = config.OFF_TAG_TO_ALLERGEN.get(tag)
        if key:
            if key not in result["contains"]:
                result["detected_terms"].setdefault(key, []).append(
                    {"term": f"OFF tag {tag}", "hidden": False, "section": "contains"})
            result["contains"].add(key)
            result["may_contain"].discard(key)
    for tag in traces_tags or []:
        key = config.OFF_TAG_TO_ALLERGEN.get(tag)
        if key and key not in result["contains"]:
            if key not in result["may_contain"]:
                result["detected_terms"].setdefault(key, []).append(
                    {"term": f"OFF tag {tag}", "hidden": False, "section": "may_contain"})
            result["may_contain"].add(key)
    return result
