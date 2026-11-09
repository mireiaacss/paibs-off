"""
Family allergy profile matcher (REAL rule logic, demo profiles).

Verdict levels, worst first:
  ALERT: DANGEROUS                - a member's allergen is an ingredient
  WARNING: TRACES                 - a member's allergen appears in a "may contain" clause
  WARNING: UNCERTAIN              - an ambiguous ingredient could hide a member's allergen,
                                    or there is no ingredient list at all ("When in doubt, warn")
  SAFE ACCORDING TO DETECTED LIST - nothing detected for this family

Sensitivity:
  "maximum"  (default) - ambiguous ingredients that could hide a restricted
                         allergen escalate the verdict to WARNING: UNCERTAIN.
  "standard"           - ambiguous ingredients are still reported per member
                         (uncertain_hits) but do not change the verdict.
  In both modes a missing ingredient list is never reported as SAFE.

Every result carries the mandatory safety disclaimer.
"""

from __future__ import annotations

import json
from pathlib import Path

import config

PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_profile.json"

ALERT = "ALERT: DANGEROUS"
TRACES = "WARNING: TRACES"
UNCERTAIN = "WARNING: UNCERTAIN"
SAFE = "SAFE ACCORDING TO DETECTED LIST"

LEVELS = {ALERT: 3, TRACES: 2, UNCERTAIN: 1, SAFE: 0}
COLOURS = {ALERT: "red", TRACES: "orange", UNCERTAIN: "orange", SAFE: "green"}


def load_profiles(path: str | Path = PROFILE_PATH) -> list[dict]:
    """Load the list of family profiles from JSON."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    profiles = data.get("profiles", data if isinstance(data, list) else [data])
    for p in profiles:
        for m in p.get("members", []):
            unknown = set(m.get("allergens", [])) - set(config.ALLERGENS)
            if unknown:
                raise ValueError(f"Unknown allergen(s) in profile '{m.get('name')}': {sorted(unknown)}")
    return profiles


SENSITIVITIES = ("maximum", "standard")


def _member_verdict(member: dict, detected: dict, sensitivity: str = "maximum") -> dict:
    allergies = set(member.get("allergens", []))
    contains_hit = sorted(allergies & set(detected.get("contains", set())))
    traces_hit = sorted(allergies & set(detected.get("may_contain", set())))
    uncertain = []
    for w in detected.get("warnings", []):
        overlap = allergies & set(w.get("possible_allergens", []))
        if overlap:
            uncertain.append({"term": w.get("term", ""), "allergens": sorted(overlap),
                              "message": w.get("message", "")})

    if contains_hit:
        verdict = ALERT
    elif traces_hit:
        verdict = TRACES
    elif any(w.get("type") == "no_text" for w in detected.get("warnings", [])):
        verdict = UNCERTAIN
    elif uncertain and sensitivity == "maximum":
        verdict = UNCERTAIN
    else:
        verdict = SAFE

    reasons = []
    for a in contains_hit:
        reasons.append(f"Contains {a}")
    for a in traces_hit:
        reasons.append(f"May contain traces of {a}")
    for u in uncertain:
        if u["term"]:
            reasons.append(f"'{u['term']}' could hide {', '.join(u['allergens'])}")
        else:
            reasons.append(u["message"])

    return {
        "name": member.get("name", "Member"),
        "allergens": sorted(allergies),
        "verdict": verdict,
        "colour": COLOURS[verdict],
        "contains_hits": contains_hit,
        "trace_hits": traces_hit,
        "uncertain_hits": uncertain,
        "reasons": reasons,
    }


def match_profile(detected_allergens: dict, profile: dict, sensitivity: str = "maximum") -> dict:
    """
    Compare parser output against a family profile.

    `profile` is either a family {"family_name", "members": [...]} or a single
    member {"name", "allergens": [...]}. `sensitivity` is "maximum" or "standard".
    """
    if sensitivity not in SENSITIVITIES:
        raise ValueError(f"sensitivity must be one of {SENSITIVITIES}")
    members = profile.get("members") or [profile]
    results = [_member_verdict(m, detected_allergens, sensitivity) for m in members]
    worst = max(results, key=lambda r: LEVELS[r["verdict"]]) if results else None
    overall = worst["verdict"] if worst else SAFE

    if overall == ALERT:
        names = [r["name"] for r in results if r["verdict"] == ALERT]
        headline = f"Do NOT give this product to {', '.join(names)}."
    elif overall == TRACES:
        headline = "Cross-contamination risk for your family - avoid unless your allergist says traces are OK."
    elif overall == UNCERTAIN:
        headline = "We could not rule out a hidden allergen. When in doubt, check the package or ask the manufacturer."
    else:
        headline = "No allergen from your family profile was detected in this label."

    return {
        "family_name": profile.get("family_name", profile.get("name", "Family")),
        "overall_verdict": overall,
        "colour": COLOURS[overall],
        "headline": headline,
        "members": results,
        "sensitivity": sensitivity,
        "disclaimer": config.SAFETY_DISCLAIMER,
    }
