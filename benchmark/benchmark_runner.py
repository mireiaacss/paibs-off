"""
Benchmark Run 1: ingredient text -> allergen parser, on the 10 canonical cases.

Metrics
  * Catch rate (recall) = expected allergens detected (in either list) / expected allergens
  * False alarms        = allergens flagged that are not expected (in either list)
  * Section accuracy    = expected allergens placed in the right list ("contains" vs "may contain")
  * Naive baseline      = plain-name keyword substring matching (EN + ES), no hidden
                          derivatives, no false-friend handling, no trace parsing.
                          The project spec reference for this baseline is 57 %.

Usage:  python benchmark/benchmark_runner.py   (exit code 1 if we don't beat the baseline
        or raise any false alarm)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.allergen_parser import normalize, parse_allergens  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "test_cases.json"

# What a naive keyword scanner knows: the allergen's everyday name in EN + ES.
NAIVE_KEYWORDS = {
    "Gluten": ["gluten", "wheat", "trigo"],
    "Crustaceans": ["crustacean", "crustaceo"],
    "Eggs": ["egg", "huevo"],
    "Fish": ["fish", "pescado"],
    "Peanuts": ["peanut", "cacahuete"],
    "Soy": ["soy", "soja"],
    "Milk": ["milk", "leche"],
    "Nuts": ["nut", "frutos de cascara"],
    "Celery": ["celery", "apio"],
    "Mustard": ["mustard", "mostaza"],
    "Sesame": ["sesame", "sesamo"],
    "Sulphites": ["sulphite", "sulfite", "sulfito"],
    "Lupin": ["lupin", "altramuz"],
    "Molluscs": ["mollusc", "molusco"],
}


def naive_parse(text: str) -> set:
    norm = normalize(text)
    return {k for k, words in NAIVE_KEYWORDS.items() if any(w in norm for w in words)}


def load_cases(path: Path = CASES_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def run_benchmark(path: Path = CASES_PATH) -> dict:
    data = load_cases(path)
    rows = []
    tot_expected = tot_caught = tot_fa = tot_section_ok = 0
    naive_caught = naive_fa = 0

    for case in data["cases"]:
        exp_c = set(case["expected_contains"])
        exp_m = set(case["expected_may_contain"])
        expected = exp_c | exp_m

        result = parse_allergens(case["text"])
        got_c, got_m = result["contains"], result["may_contain"]
        got = got_c | got_m

        caught = expected & got
        missed = expected - got
        false_alarms = got - expected
        section_ok = len(exp_c & got_c) + len(exp_m & got_m)

        naive = naive_parse(case["text"])
        n_caught = expected & naive
        n_fa = naive - expected

        tot_expected += len(expected)
        tot_caught += len(caught)
        tot_fa += len(false_alarms)
        tot_section_ok += section_ok
        naive_caught += len(n_caught)
        naive_fa += len(n_fa)

        passed = not missed and not false_alarms and section_ok == len(expected)
        rows.append({
            "id": case["id"],
            "group": case["group"],
            "group_name": case["group_name"],
            "text": case["text"],
            "expected_contains": sorted(exp_c),
            "expected_may_contain": sorted(exp_m),
            "detected_contains": sorted(got_c),
            "detected_may_contain": sorted(got_m),
            "missed": sorted(missed),
            "false_alarms": sorted(false_alarms),
            "warnings": [w["term"] or w["type"] for w in result["warnings"]],
            "naive_detected": sorted(naive),
            "naive_missed": sorted(expected - naive),
            "naive_false_alarms": sorted(n_fa),
            "passed": passed,
        })

    recall = tot_caught / tot_expected if tot_expected else 1.0
    naive_recall = naive_caught / tot_expected if tot_expected else 1.0
    baseline_ref = data.get("baseline_recall_reference", 0.57)
    return {
        "cases": rows,
        "summary": {
            "n_cases": len(rows),
            "cases_passed": sum(r["passed"] for r in rows),
            "expected_allergens": tot_expected,
            "caught": tot_caught,
            "catch_rate": recall,
            "false_alarms": tot_fa,
            "section_accuracy": tot_section_ok / tot_expected if tot_expected else 1.0,
            "naive_catch_rate": naive_recall,
            "naive_false_alarms": naive_fa,
            "baseline_reference": baseline_ref,
            "beats_baseline": recall > baseline_ref,
            "lift_vs_baseline_pp": (recall - baseline_ref) * 100,
        },
    }


def _fmt(items: list) -> str:
    return ", ".join(items) if items else "-"


def main() -> int:
    report = run_benchmark()
    s = report["summary"]
    print("PAIBS Group 10 - Benchmark Run 1 (ingredient text -> allergen parser)\n")
    print(f"{'#':>2}  {'Grp':3}  {'Result':6}  {'Contains':38}  {'May contain':24}  {'Missed':10}  False alarms")
    print("-" * 120)
    for r in report["cases"]:
        print(f"{r['id']:>2}  {r['group']:3}  {'PASS' if r['passed'] else 'FAIL':6}  "
              f"{_fmt(r['detected_contains']):38}  {_fmt(r['detected_may_contain']):24}  "
              f"{_fmt(r['missed']):10}  {_fmt(r['false_alarms'])}")
    print("-" * 120)
    print(f"Cases passed:          {s['cases_passed']}/{s['n_cases']}")
    print(f"Catch rate (recall):   {s['catch_rate']:.0%}  ({s['caught']}/{s['expected_allergens']} allergens)")
    print(f"False alarms:          {s['false_alarms']}")
    print(f"Section accuracy:      {s['section_accuracy']:.0%}  (contains vs may-contain)")
    print(f"Naive keyword scanner: {s['naive_catch_rate']:.0%} recall, {s['naive_false_alarms']} false alarms (reproduced here)")
    print(f"Spec baseline:         {s['baseline_reference']:.0%} recall")
    print(f"Lift vs baseline:      {s['lift_vs_baseline_pp']:+.0f} pp -> "
          f"{'BEATS BASELINE' if s['beats_baseline'] else 'DOES NOT BEAT BASELINE'}")
    return 0 if s["beats_baseline"] and s["false_alarms"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
