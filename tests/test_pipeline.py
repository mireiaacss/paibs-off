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

DEMO_FAMILY = load_profiles()[0]  # Milk, Nuts / Eggs


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
    assert "Always verify the physical packaging label" in v["disclaimer"]


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


def test_streamlit_app_runs():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception
    at.radio[0].set_value("B · Paste ingredient text").run()
    at.text_area[0].set_value("Harina de trigo, leche, huevo. Puede contener trazas de avellanas.").run()
    next(b for b in at.button if "Analyze" in b.label).click().run()
    assert not at.exception
    assert any("ALERT: DANGEROUS" in m.value for m in at.markdown)
