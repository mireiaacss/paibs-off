"""Level 2 tests: benchmark, guardrails, end-to-end pipeline and UI smoke test."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmark.benchmark_runner import load_cases, run_benchmark  # noqa: E402
from modules.additives_service import find_additives  # noqa: E402
from modules.allergen_parser import parse_allergens  # noqa: E402
from modules.ocr_reader import read_label  # noqa: E402
from modules.off_client import get_product_by_barcode  # noqa: E402
from modules.pipeline import analyze  # noqa: E402
from modules.profile_matcher import ALERT, SAFE, TRACES, UNCERTAIN, load_profiles, match_profile  # noqa: E402
from modules.alternatives_service import get_alternatives  # noqa: E402

DEMO_FAMILY = next(p for p in load_profiles() if p["family_name"] == "Household - Dairy, Tree Nut & Egg")


@pytest.mark.parametrize("case", load_cases()["cases"], ids=lambda c: f"case{c['id']}-{c['group']}")
def test_benchmark_case(case):
    r = parse_allergens(case["text"])
    assert r["contains"] == set(case["expected_contains"])
    assert r["may_contain"] == set(case["expected_may_contain"])


def test_benchmark_beats_baseline():
    s = run_benchmark()["summary"]
    assert s["catch_rate"] > s["baseline_reference"]
    assert s["false_alarms"] == 0


def test_contains_wins_over_may_contain():
    r = parse_allergens("Leche entera, azúcar. Puede contener trazas de leche y avellanas.")
    assert r["contains"] == {"Milk"}
    assert r["may_contain"] == {"Nuts"}


def test_plant_milk_still_flags_plant():
    r = parse_allergens("Bebida de almendra: agua, leche de almendra 7%, sal")
    assert "Nuts" in r["contains"] and "Milk" not in r["contains"]


def test_guardrail_warns_on_ambiguous_terms():
    r = parse_allergens("Azúcar, aceite vegetal, aromas, E999, lecitina")
    types = {w["type"] for w in r["warnings"]}
    assert {"ambiguous", "unknown_additive"} <= types


def test_empty_text_is_never_safe():
    verdict = match_profile(parse_allergens(""), DEMO_FAMILY)
    assert verdict["overall_verdict"] == UNCERTAIN


def test_profile_verdicts():
    assert match_profile(parse_allergens("Leche, azúcar"), DEMO_FAMILY)["overall_verdict"] == ALERT
    assert match_profile(parse_allergens("Azúcar. Puede contener huevo."), DEMO_FAMILY)["overall_verdict"] == TRACES
    assert match_profile(parse_allergens("Arroz, agua, sal"), DEMO_FAMILY)["overall_verdict"] == SAFE


def test_disclaimer_always_present():
    v = match_profile(parse_allergens("Arroz, agua, sal"), DEMO_FAMILY)
    assert "Cross-reference all automated assessments" in v["disclaimer"]


def test_additives_lookup():
    codes = {a["code"]: a for a in find_additives("colorante (E-102), conservante E220, E999")}
    assert codes["E102"]["risk"] == "high"
    assert codes["E220"]["known"]
    assert not codes["E999"]["known"]


def test_offline_barcode_fallback():
    p = get_product_by_barcode("3017620422003", use_live=False)
    assert p["found"] and p["source"] == "offline_cache"


def test_end_to_end_barcode_offline():
    res = analyze(DEMO_FAMILY, barcode="3017620422003", use_live_off=False)
    assert res["verdict"]["overall_verdict"] == ALERT          # Nutella: milk + hazelnuts
    assert {"Milk", "Nuts"} <= res["detected"]["contains"]
    assert res["alternatives"]["alternatives"]


def test_end_to_end_photo_stub():
    assert read_label(None)["is_stub"]
    res = analyze(DEMO_FAMILY, image_bytes=b"")
    assert res["input_mode"] == "photo"
    assert res["verdict"]["overall_verdict"] == ALERT


def test_standard_sensitivity_does_not_escalate_ambiguity():
    detected = parse_allergens("Arroz, aromas")         # aromas could hide Milk
    assert match_profile(detected, DEMO_FAMILY, "maximum")["overall_verdict"] == UNCERTAIN
    standard = match_profile(detected, DEMO_FAMILY, "standard")
    assert standard["overall_verdict"] == SAFE
    assert any(m["uncertain_hits"] for m in standard["members"])   # still reported


def test_missing_ingredients_never_safe_even_at_standard():
    assert match_profile(parse_allergens(""), DEMO_FAMILY, "standard")["overall_verdict"] == UNCERTAIN


def test_curated_alternatives_respect_profile():
    alts = get_alternatives({"Milk", "Peanuts"}, ingredient_text="croissant", use_live=False)["alternatives"]
    assert alts and all({"Milk", "Peanuts"} <= set(a["free_of"]) for a in alts)


def _app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)


def test_app_has_no_tabs_and_no_emoji():
    import re
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert not re.search("[\U0001F300-\U0001FAFF\u2600-\u27BF]", source)
    at = _app().run()
    assert not at.exception
    assert len(at.tabs) == 0


def test_app_text_flow_conflict():
    at = _app().run()
    at.segmented_control[0].set_value("Ingredient Text").run()
    at.text_area[0].set_value("Harina de trigo, leche, huevo. Puede contener trazas de avellanas.").run()
    next(b for b in at.button if b.label == "Analyze Ingredients").click().run()
    assert not at.exception
    assert any("RESTRICTION CONFLICT DETECTED" in m.value for m in at.markdown)


def test_app_barcode_flow_offline_clear():
    at = _app().run()
    at.sidebar.checkbox[0].uncheck()     # live OFF lookup off -> cached record
    at.sidebar.checkbox[1].uncheck()     # live alternatives off
    at.run()
    next(b for b in at.button if b.label == "Allergen-free grain cake").click().run()
    next(b for b in at.button if b.label == "Analyze Ingredients").click().run()
    assert not at.exception
    assert any("NO CONFLICTS IDENTIFIED WITH ACTIVE PROFILE" in m.value for m in at.markdown)
