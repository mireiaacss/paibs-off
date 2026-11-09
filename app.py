"""
PAIBS Group 10 - AI allergen label scanner (Level 2: Walking Skeleton).

Run:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from benchmark.benchmark_runner import run_benchmark
from modules import ocr_reader
from modules.off_client import MOCK_PRODUCTS
from modules.pipeline import analyze
from modules.profile_matcher import ALERT, SAFE, TRACES, UNCERTAIN, load_profiles

st.set_page_config(page_title="SafeBite Scanner - PAIBS G10", page_icon="🛡️", layout="wide")

SAMPLE_TEXTS = {
    "Surimi salad (ES)": "Surimi (pescado blanco, almidón de trigo, clara de huevo), gambas, mejillones, salsa (mostaza)",
    "Chocolate with traces (ES)": "Chocolate negro, almendras. Puede contener trazas de cacahuete, leche y sésamo",
    "Biscuits with hidden dairy (ES)": "Harina de trigo, azúcar, aceite de palma, suero lácteo en polvo, caseinato sódico, "
                                      "lecitina de soja, gasificante (E500), sal, aromas.",
    "False friends (EN)": "Buckwheat flour, coconut milk, cocoa butter, lactic acid, nutmeg",
    "Dried apricots (EN)": "Dried apricots, preservative (E220)",
    "Clean rice (ES)": "Arroz, agua, aceite de oliva virgen extra, sal",
}

VERDICT_STYLE = {
    ALERT: ("#b91c1c", "#fee2e2", "⛔"),
    TRACES: ("#c2410c", "#ffedd5", "⚠️"),
    UNCERTAIN: ("#a16207", "#fef9c3", "❓"),
    SAFE: ("#15803d", "#dcfce7", "✅"),
}


def allergen_label(key: str) -> str:
    info = config.ALLERGENS[key]
    return f"{info['icon']} {info['label']} / {info['label_es']}"


@st.cache_data
def cached_profiles():
    return load_profiles()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🛡️ SafeBite - Allergen Label Scanner")
st.caption("ESADE PAIBS · Group 10 · **Level 2 - Walking Skeleton running**")
st.error("⚠️ **Important: Always inspect the physical packaging label.** "
         "This prototype is a decision aid, not a medical device.")

tab_demo, tab_bench, tab_arch = st.tabs(
    ["🔎 Live Demo", "📊 Benchmark & Level 2 Validation", "🏗️ Architecture & Real vs Faked"])

# ---------------------------------------------------------------------------
# Tab 1: Live demo
# ---------------------------------------------------------------------------
with tab_demo:
    profiles = cached_profiles()
    left, right = st.columns([1, 2], gap="large")

    with left:
        st.subheader("1 · Family profile")
        names = [p["family_name"] for p in profiles] + ["Custom profile"]
        choice = st.selectbox("Select a family", names)
        if choice == "Custom profile":
            custom = st.multiselect("Allergens to avoid", list(config.ALLERGENS),
                                    default=["Milk", "Nuts"], format_func=allergen_label)
            profile = {"family_name": "Custom profile",
                       "members": [{"name": "My child", "allergens": custom}]}
        else:
            profile = next(p for p in profiles if p["family_name"] == choice)
        for m in profile["members"]:
            allergies = ", ".join(allergen_label(a) for a in m["allergens"]) or "no known allergies"
            st.markdown(f"- **{m['name']}**: {allergies}")

        st.subheader("2 · Product input")
        mode = st.radio("Input mode", ["A · Barcode", "B · Paste ingredient text", "C · Label photo"])

        barcode = text = image_bytes = None
        use_live = True
        if mode.startswith("A"):
            demo_codes = {f"{v['product_name']} ({k})": k for k, v in MOCK_PRODUCTS.items()}
            pick = st.selectbox("Demo barcodes (cached offline)", ["- type your own -"] + list(demo_codes))
            barcode = st.text_input("EAN / UPC barcode",
                                    value=demo_codes.get(pick, "3017620422003"))
            use_live = st.toggle("Use live Open Food Facts API", value=True,
                                 help="Off = use the offline cache only (for flaky Wi-Fi during demos).")
        elif mode.startswith("B"):
            sample = st.selectbox("Load a sample label", ["- write your own -"] + list(SAMPLE_TEXTS))
            text = st.text_area("Ingredient list (Spanish or English)",
                                value=SAMPLE_TEXTS.get(sample, ""), height=150,
                                placeholder="Ingredientes: harina de trigo, leche...")
        else:
            engines = ocr_reader.available_engines()
            st.caption(f"OCR engine: **{engines[0] if engines else 'stub (no OCR installed)'}**")
            upload = st.file_uploader("Upload a label photo", type=["png", "jpg", "jpeg", "webp"])
            camera = st.camera_input("…or take a photo") if st.toggle("Use camera") else None
            src = camera or upload
            if src is not None:
                image_bytes = src.getvalue()
                st.image(image_bytes, caption="Label photo", width="stretch")
                key = f"ocr_{hash(image_bytes)}"
                if key not in st.session_state:
                    with st.spinner("Reading label…"):
                        st.session_state[key] = ocr_reader.read_label(image_bytes)
                ocr = st.session_state[key]
                if ocr["is_stub"]:
                    st.warning(ocr["error"])
                text = st.text_area("Extracted text - check and correct before analysing",
                                    value=ocr["text"], height=150)

        live_alts = st.toggle("Search live OFF for alternatives (slower)", value=False)
        run = st.button("🔍 Analyze Product", type="primary", width="stretch")

    with right:
        if run and mode.startswith("C") and image_bytes is None:
            st.info("Upload or take a photo first.")
        elif run:
            with st.spinner("Analysing…"):
                st.session_state["result"] = analyze(
                    profile, barcode=barcode, text=text, use_live_off=use_live,
                    use_live_alternatives=live_alts)
                st.session_state["result_profile"] = profile["family_name"]

        res = st.session_state.get("result")
        if not res:
            st.info("Choose a profile and an input on the left, then press **Analyze Product**.")
        else:
            prod = res["product"]
            if prod is not None:
                if prod.get("found"):
                    c1, c2 = st.columns([1, 3])
                    if prod.get("image_url"):
                        c1.image(prod["image_url"], width=120)
                    c2.markdown(f"### {prod['product_name']}\n{prod.get('brands', '')} · {prod.get('quantity', '')}")
                    src_txt = "live Open Food Facts" if prod["source"] == "live" else "offline cache of OFF data"
                    c2.caption(f"Barcode {prod['barcode']} · source: {src_txt} · "
                               f"Nutri-Score: {prod.get('nutriscore_grade', 'unknown').upper()}")
                    if prod.get("error"):
                        c2.caption(f"ℹ️ {prod['error']}")
                else:
                    st.warning(f"Product not found: {prod.get('error')}. "
                               "Try pasting the ingredient text (mode B) or a photo (mode C).")

            v = res["verdict"]
            fg, bg, icon = VERDICT_STYLE[v["overall_verdict"]]
            st.markdown(
                f"<div style='background:{bg};border-left:8px solid {fg};padding:16px 20px;border-radius:8px;'>"
                f"<div style='color:{fg};font-size:1.6rem;font-weight:700'>{icon} {v['overall_verdict']}</div>"
                f"<div style='color:#111;font-size:1.05rem'>{v['headline']}</div></div>",
                unsafe_allow_html=True)
            st.caption(v["disclaimer"])

            st.markdown("#### 👪 Per family member")
            cols = st.columns(len(v["members"]))
            for col, m in zip(cols, v["members"]):
                mfg, mbg, micon = VERDICT_STYLE[m["verdict"]]
                reasons = "<br>".join(m["reasons"]) or "Nothing from this member's list detected."
                col.markdown(
                    f"<div style='background:{mbg};padding:10px;border-radius:6px;min-height:110px;color:#111'>"
                    f"<b>{micon} {m['name']}</b><br><span style='color:{mfg};font-weight:600'>{m['verdict']}</span>"
                    f"<br><small>{reasons}</small></div>", unsafe_allow_html=True)

            d = res["detected"]
            st.markdown("#### 🧪 Detected allergens")
            a1, a2 = st.columns(2)
            with a1:
                st.markdown("**Contains**")
                if not d["contains"]:
                    st.write("None detected")
                for a in sorted(d["contains"]):
                    terms = [t for t in d["detected_terms"].get(a, []) if t["section"] == "contains"]
                    hidden = " · 🕵️ hidden name" if any(t["hidden"] for t in terms) else ""
                    st.markdown(f"- {allergen_label(a)} ← _{', '.join(t['term'] for t in terms)}_{hidden}")
            with a2:
                st.markdown("**May contain (traces)**")
                if not d["may_contain"]:
                    st.write("None detected")
                for a in sorted(d["may_contain"]):
                    terms = [t for t in d["detected_terms"].get(a, []) if t["section"] == "may_contain"]
                    st.markdown(f"- {allergen_label(a)} ← _{', '.join(t['term'] for t in terms)}_")

            if d["warnings"]:
                with st.expander(f"❓ When in doubt, warn - {len(d['warnings'])} uncertain item(s)", expanded=True):
                    for w in d["warnings"]:
                        could = f" (could hide: {', '.join(w['possible_allergens'])})" if w["possible_allergens"] and w["type"] != "no_text" else ""
                        st.markdown(f"- **{w['term'] or 'No ingredients'}** - {w['message']}{could}")
            if d["false_friends_ignored"]:
                st.caption("✔️ Recognised as NOT allergens (false friends): " + ", ".join(d["false_friends_ignored"]))

            st.markdown("#### ⚗️ Additives")
            if not res["additives"]:
                st.write("No E-number additives detected.")
            else:
                risk_icon = {"high": "🔴", "medium": "🟠", "low": "🟢", "unknown": "⚪"}
                st.dataframe(pd.DataFrame([{
                    "Risk": f"{risk_icon[a['risk']]} {a['risk']}", "Code": a["code"], "Name": a["name"],
                    "Type": a["category"], "What it means": a["en"], "Explicación": a["es"]}
                    for a in res["additives"]]), hide_index=True, width="stretch")

            alts = res["alternatives"]
            st.markdown(f"#### 🥗 Safer alternatives  ·  category: _{alts['category']}_")
            if not alts["alternatives"]:
                st.write("No alternative in the demo catalogue fits every allergy in this profile.")
            for alt in alts["alternatives"]:
                st.markdown(f"- **{alt['name']}** (Nutri-Score {str(alt.get('nutri', '?')).upper()}) - "
                            f"{alt['why']}  \n  <small>source: {alt['source']}</small>", unsafe_allow_html=True)
            st.caption(alts["note"])

            with st.expander("Ingredient text analysed"):
                st.code(res["ingredient_text"] or "(empty)", language=None)

# ---------------------------------------------------------------------------
# Tab 2: Benchmark
# ---------------------------------------------------------------------------
with tab_bench:
    st.subheader("Benchmark Run 1 · ingredient text → allergen parser")
    st.markdown("10 canonical cases from Session 2, groups **A** plain names · **B** hidden derivatives · "
                "**C** may-contain · **D** clean control · **E** false friends · **F** complex dishes.")
    if st.button("▶️ Run benchmark", type="primary") or "bench" not in st.session_state:
        st.session_state["bench"] = run_benchmark()
    report = st.session_state["bench"]
    s = report["summary"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Catch rate (recall)", f"{s['catch_rate']:.0%}",
              f"{s['lift_vs_baseline_pp']:+.0f} pp vs {s['baseline_reference']:.0%} baseline")
    m2.metric("False alarms", s["false_alarms"], f"naive: {s['naive_false_alarms']}", delta_color="off")
    m3.metric("Cases passed", f"{s['cases_passed']}/{s['n_cases']}")
    m4.metric("Contains vs traces accuracy", f"{s['section_accuracy']:.0%}")

    if s["beats_baseline"]:
        st.success(f"✅ Beats the {s['baseline_reference']:.0%} keyword baseline "
                   f"(our reproduction of the naive scanner scores {s['naive_catch_rate']:.0%}).")
    else:
        st.error("❌ Does not beat the baseline.")

    st.dataframe(pd.DataFrame([{
        "#": r["id"], "Group": f"{r['group']} · {r['group_name']}", "Result": "✅ PASS" if r["passed"] else "❌ FAIL",
        "Label text": r["text"],
        "Expected": ", ".join(r["expected_contains"] + [f"(traces) {x}" for x in r["expected_may_contain"]]) or "none",
        "Detected": ", ".join(r["detected_contains"] + [f"(traces) {x}" for x in r["detected_may_contain"]]) or "none",
        "Missed": ", ".join(r["missed"]), "False alarms": ", ".join(r["false_alarms"]),
        "Naive baseline found": ", ".join(r["naive_detected"]) or "none",
        "Guardrail warnings": ", ".join(r["warnings"]),
    } for r in report["cases"]]), hide_index=True, width="stretch")

    chart = pd.DataFrame({"Catch rate": [s["naive_catch_rate"], s["baseline_reference"], s["catch_rate"]]},
                         index=["Naive keyword (reproduced)", "Spec baseline", "Our parser"])
    st.bar_chart(chart, horizontal=True)
    st.caption("Caveat: these 10 cases were used while building the synonym dictionary, so 100% is an "
               "in-sample score. Level 3 needs a held-out set of real Spanish supermarket labels.")

# ---------------------------------------------------------------------------
# Tab 3: Architecture
# ---------------------------------------------------------------------------
with tab_arch:
    st.subheader("Level 2 walking skeleton")
    st.graphviz_chart("""
digraph G {
  rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
  user [label="👪 Parent\\n(barcode / text / photo)", fillcolor="#e0e7ff"];
  off  [label="DATA\\noff_client.py\\nOpen Food Facts API\\n+ offline cache", fillcolor="#dcfce7"];
  ocr  [label="DATA\\nocr_reader.py\\nEasyOCR / Tesseract\\n(stub fallback)", fillcolor="#fef9c3"];
  parse[label="PROCESSING\\nallergen_parser.py\\nEU-14 synonyms, false friends,\\nmay-contain split", fillcolor="#dcfce7"];
  guard[label="GUARDRAIL\\nWhen in doubt, warn", fillcolor="#dcfce7"];
  prof [label="AI / RULES\\nprofile_matcher.py\\nfamily verdict", fillcolor="#dcfce7"];
  add  [label="additives_service.py\\nE-number dictionary", fillcolor="#fef9c3"];
  alt  [label="alternatives_service.py\\ncurated catalogue\\n(+ optional OFF search)", fillcolor="#fef9c3"];
  ui   [label="OUTPUT\\napp.py (Streamlit)\\nverdict · allergens ·\\nadditives · alternatives", fillcolor="#e0e7ff"];
  user -> off; user -> ocr; user -> parse [label="text"];
  off -> parse; ocr -> parse; parse -> guard -> prof -> ui; parse -> add -> ui; prof -> alt -> ui; ui -> user [label="decision"];
}
""")
    st.caption("🟩 real  ·  🟨 stub / partial  ·  orchestrated by modules/pipeline.py")

    st.subheader("Real vs. Faked")
    st.dataframe(pd.DataFrame([
        ["Barcode lookup", "REAL", "Live Open Food Facts API v2", "Offline cache of 5 real OFF records if network fails"],
        ["Ingredient → allergen parser", "REAL", "Regex + EU-14 bilingual synonym dictionary, hidden derivatives, E220-E228", "Dictionary is hand-curated (~300 terms), not exhaustive"],
        ["May-contain detection", "REAL", "Clause splitting on ES/EN/FR/CA trigger phrases", "-"],
        ["False-friend handling", "REAL", "Per-allergen masking (coconut, buckwheat, cocoa butter, lactic acid, nutmeg…)", "-"],
        ["'When in doubt, warn' guardrail", "REAL", "Ambiguous terms, unknown E-numbers, unparsed chemicals, missing text", "-"],
        ["Family profile matcher", "REAL logic", "Per-member verdict + worst-case family verdict", "Profiles are demo JSON, no login / persistence"],
        ["Label photo OCR", "PARTIAL", "EasyOCR or Tesseract when installed; user can correct text", "Falls back to a fixed demo label when no OCR engine is installed"],
        ["Additive risk lookup", "STUB", "Regex E-number detection", "~35-entry curated dictionary instead of full EFSA taxonomy"],
        ["Alternatives", "STUB", "Category detection + allergen filter; optional live OFF search", "Curated generic product types, not real shelf inventory"],
        ["Mobile camera app", "FAKED", "Streamlit camera_input in the browser", "No native app, no live barcode video scanning"],
    ], columns=["Component", "Status", "What is real", "What is faked / limits"]),
        hide_index=True, width="stretch")
