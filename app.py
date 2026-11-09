"""
Allergen & Additive Verification Tool - Streamlit front end.

Run:  streamlit run app.py
"""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

import config
from modules import ocr_reader
from modules.pipeline import analyze
from modules.profile_matcher import ALERT, TRACES, UNCERTAIN, load_profiles

APP_NAME = "Allergen & Additive Verification Tool"

st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")

# ---------------------------------------------------------------------------
# Reference data for the input helpers
# ---------------------------------------------------------------------------
SAMPLE_BARCODES = {
    "Standard snack": "5000159407236",            # Mars bar
    "Allergen-free grain cake": "8412224028852",  # Corn & quinoa cakes
    "Processed pastry": "8431876336764",          # Supermarket croissants
    "Chocolate spread": "3017620422003",          # Nutella
}

SAMPLE_TEXTS = {
    "Hidden dairy derivatives": "Harina de trigo, azúcar, aceite de palma, suero lácteo en polvo, "
                                "caseinato sódico, lecitina de soja, gasificante (E500), sal, aromas.",
    "Precautionary traces": "Chocolate negro, almendras. Puede contener trazas de cacahuete, leche y sésamo.",
    "Seafood preparation": "Surimi (pescado blanco, almidón de trigo, clara de huevo), gambas, "
                           "mejillones, salsa (mostaza)",
    "Look-alike terms": "Buckwheat flour, coconut milk, cocoa butter, lactic acid, nutmeg",
    "Preserved fruit": "Dried apricots, preservative (E220)",
}

EU_NAME = {
    "Gluten": "Gluten", "Crustaceans": "Crustaceans", "Eggs": "Egg", "Fish": "Fish",
    "Peanuts": "Peanut", "Soy": "Soybean", "Milk": "Milk", "Nuts": "Tree nuts",
    "Celery": "Celery", "Mustard": "Mustard", "Sesame": "Sesame", "Sulphites": "Sulphites",
    "Lupin": "Lupin", "Molluscs": "Molluscs",
}

STATUS = {
    "conflict": ("RESTRICTION CONFLICT DETECTED", "status-conflict"),
    "trace": ("POTENTIAL TRACE EXPOSURE", "status-trace"),
    "unverified": ("UNVERIFIED COMPONENTS REQUIRE REVIEW", "status-trace"),
    "no_data": ("INSUFFICIENT INGREDIENT DATA", "status-trace"),
    "clear": ("NO CONFLICTS IDENTIFIED WITH ACTIVE PROFILE", "status-clear"),
}

SENSITIVITY_OPTIONS = {
    "Maximum Caution (flag all traces and ambiguous terms)": "maximum",
    "Standard Sensitivity": "standard",
}

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  html, body, [class*="css"] { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                                "Helvetica Neue", Arial, sans-serif; }
  .block-container { padding-top: 2rem; max-width: 1200px; }
  h1 { font-size: 1.6rem !important; font-weight: 650 !important; letter-spacing: -0.01em; margin-bottom: 0.25rem; }
  h3 { font-size: 1.05rem !important; font-weight: 600 !important; }
  .notice { border: 1px solid #d1d5db; background: #f9fafb; color: #374151; padding: 10px 14px;
            border-radius: 4px; font-size: 0.9rem; margin: 0.5rem 0 1.25rem 0; }
  .section-label { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
                   color: #6b7280; margin: 1.1rem 0 0.4rem 0; }
  .status { padding: 14px 18px; border-radius: 4px; border-left: 5px solid; margin-bottom: 0.75rem; }
  .status-title { font-weight: 700; font-size: 1.05rem; letter-spacing: 0.02em; }
  .status-detail { font-size: 0.9rem; margin-top: 4px; }
  .status-conflict { background: #f2dede; border-color: #8b2e2e; color: #3d1212; }
  .status-trace { background: #f5ead0; border-color: #9a6b12; color: #3f2c06; }
  .status-clear { background: #e3eae4; border-color: #4b6352; color: #1f2d23; }
  .term-list { border: 1px solid #e5e7eb; border-radius: 4px; }
  .term-row { display: flex; justify-content: space-between; gap: 12px; padding: 7px 12px;
              border-bottom: 1px solid #f0f1f3; font-size: 0.9rem; color: #111827; }
  .term-row:last-child { border-bottom: none; }
  .term-src { color: #374151; }
  .term-cat { font-weight: 600; white-space: nowrap; }
  .restricted { background: #fbf3f3; }
  .tag { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.05em; padding: 1px 6px; border-radius: 3px;
         border: 1px solid #8b2e2e; color: #8b2e2e; margin-left: 8px; }
  .empty { color: #6b7280; font-size: 0.9rem; padding: 6px 0; }
  .meta { color: #4b5563; font-size: 0.85rem; }
  .product-name { font-size: 1.1rem; font-weight: 600; color: #111827; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@st.cache_data
def cached_profiles() -> list[dict]:
    return load_profiles()


def esc(value) -> str:
    return html.escape(str(value))


def display_term(term: str) -> str:
    if term.startswith("OFF tag"):
        return "Manufacturer declaration (Open Food Facts)"
    if term.startswith("\\b"):
        return "Sulphite additive (E220-E228)"
    return term[:1].upper() + term[1:]


def section_label(text: str) -> None:
    st.markdown(f"<div class='section-label'>{esc(text)}</div>", unsafe_allow_html=True)


def term_rows(detected: dict, section: str, restricted: set) -> str:
    keys = sorted(detected["contains"] if section == "contains" else detected["may_contain"],
                  key=lambda k: (k not in restricted, k))
    if not keys:
        return "<div class='empty'>None identified.</div>"
    rows = []
    for key in keys:
        terms = [t for t in detected["detected_terms"].get(key, []) if t["section"] == section]
        names = ", ".join(dict.fromkeys(display_term(t["term"]) for t in terms)) or "-"
        tag = "<span class='tag'>RESTRICTED</span>" if key in restricted else ""
        css = "term-row restricted" if key in restricted else "term-row"
        rows.append(f"<div class='{css}'><span class='term-src'>{esc(names)}</span>"
                    f"<span class='term-cat'>&rarr; {esc(EU_NAME[key])}{tag}</span></div>")
    return "<div class='term-list'>" + "".join(rows) + "</div>"


def status_for(verdict: dict, detected: dict) -> tuple[str, str]:
    """Map the matcher verdict to a status card key and a detail line."""
    members = verdict["members"]
    multi = len(members) > 1

    def who(m):
        return f"{m['name']}: " if multi else ""

    overall = verdict["overall_verdict"]
    if overall == ALERT:
        parts = [who(m) + ", ".join(EU_NAME[a] for a in m["contains_hits"]) for m in members if m["contains_hits"]]
        detail = "Restricted allergen present as a direct ingredient - " + "; ".join(parts) + "."
        traces = sorted({a for m in members for a in m["trace_hits"]})
        if traces:
            detail += " Precautionary statement also lists " + ", ".join(EU_NAME[a] for a in traces) + "."
        return "conflict", detail
    if overall == TRACES:
        parts = [who(m) + ", ".join(EU_NAME[a] for a in m["trace_hits"]) for m in members if m["trace_hits"]]
        return "trace", ("Restricted allergen listed in a precautionary (may contain) statement - "
                         + "; ".join(parts) + ".")
    if overall == UNCERTAIN:
        if any(w["type"] == "no_text" for w in detected["warnings"]):
            return "no_data", "No ingredient list was available. The product cannot be assessed; inspect the packaging."
        hits = sorted({(u["term"], a) for m in members for u in m["uncertain_hits"] for a in u["allergens"]})
        detail = "; ".join(f"'{t}' may contain {EU_NAME[a]}" for t, a in hits)
        return "unverified", f"Ambiguous ingredients could conceal a restricted allergen: {detail}."
    pending = sum(len(m["uncertain_hits"]) for m in members)
    if pending:
        return "clear", (f"{pending} unverified component(s) that could relate to the profile are listed below "
                         "and were not counted at Standard Sensitivity.")
    return "clear", "No restricted allergen was found in the ingredient list or precautionary statements."


def set_state(key: str, value: str) -> None:
    st.session_state[key] = value


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
profiles = cached_profiles()
with st.sidebar:
    st.markdown("### Active Profile")
    names = [p["family_name"] for p in profiles] + ["Custom Profile"]
    profile_name = st.selectbox("Profile", names, label_visibility="collapsed")
    if profile_name == "Custom Profile":
        custom = st.multiselect("Restricted allergens", list(config.ALLERGENS), default=["Milk"],
                                format_func=lambda k: EU_NAME[k])
        profile = {"family_name": "Custom Profile", "members": [{"name": "Custom", "allergens": custom}]}
    else:
        profile = next(p for p in profiles if p["family_name"] == profile_name)

    for member in profile["members"]:
        restricted_names = ", ".join(EU_NAME[a] for a in member["allergens"]) or "None"
        label = f"{member['name']}: " if len(profile["members"]) > 1 else "Restrictions: "
        st.markdown(f"<div class='meta'>{esc(label)}{esc(restricted_names)}</div>", unsafe_allow_html=True)

    st.markdown("### Detection Threshold")
    sensitivity_label = st.radio("Detection threshold", list(SENSITIVITY_OPTIONS), label_visibility="collapsed",
                                 help="Maximum Caution treats ambiguous ingredients (unspecified flavourings, "
                                      "starch, lecithin, vegetable oil) as potential exposures. Standard Sensitivity "
                                      "lists them for review without changing the status.")
    sensitivity = SENSITIVITY_OPTIONS[sensitivity_label]

    st.markdown("### Data Sources")
    use_live_off = st.checkbox("Live Open Food Facts lookup", value=True,
                               help="When disabled or unreachable, a local cache of reference products is used.")
    use_live_alts = st.checkbox("Live alternative search", value=True,
                                help="Searches Open Food Facts for same-category products without the profile's "
                                     "allergens. Falls back to a curated list.")

restricted = {a for m in profile["members"] for a in m["allergens"]}
signature = (profile_name, tuple(sorted(restricted)), sensitivity)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title(APP_NAME)
st.markdown(f"<div class='notice'>{esc(config.SAFETY_DISCLAIMER)}</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Step 1 - Input
# ---------------------------------------------------------------------------
st.markdown("### 1. Product Input")
mode = st.segmented_control("Input method", ["Barcode Lookup", "Label Photo", "Ingredient Text"],
                            default="Barcode Lookup", required=True, key="mode")

barcode = text = None
photo_ready = True

if mode == "Barcode Lookup":
    st.session_state.setdefault("barcode_input", SAMPLE_BARCODES["Standard snack"])
    st.text_input("EAN / UPC barcode", key="barcode_input", placeholder="e.g. 8431876336764")
    cols = st.columns(len(SAMPLE_BARCODES))
    for col, (label, code) in zip(cols, SAMPLE_BARCODES.items()):
        col.button(label, key=f"bc_{code}", on_click=set_state, args=("barcode_input", code), width="stretch")
    barcode = st.session_state["barcode_input"]

elif mode == "Label Photo":
    upload = st.file_uploader("Label photo", type=["png", "jpg", "jpeg"])
    camera = st.camera_input("Camera") if st.checkbox("Use device camera") else None
    source = camera or upload
    if source is None:
        photo_ready = False
        st.markdown("<div class='meta'>Upload a clear, well-lit photo of the ingredient panel.</div>",
                    unsafe_allow_html=True)
    else:
        image_bytes = source.getvalue()
        ocr_key = f"ocr_{hash(image_bytes)}"
        if ocr_key not in st.session_state:
            with st.spinner("Extracting text"):
                st.session_state[ocr_key] = ocr_reader.read_label(image_bytes)
        ocr = st.session_state[ocr_key]
        img_col, txt_col = st.columns([1, 2])
        img_col.image(image_bytes, width="stretch")
        with txt_col:
            if ocr["is_stub"]:
                st.warning("Text recognition is unavailable on this installation. Sample text has been inserted; "
                           "replace it with the ingredient list from the photo.")
            else:
                st.markdown(f"<div class='meta'>Text recognised with {esc(ocr['engine'].title())}. "
                            "Review and correct before analysis.</div>", unsafe_allow_html=True)
            text = st.text_area("Extracted ingredient text", value=ocr["text"], height=170, key=f"txt_{ocr_key}")

else:
    st.session_state.setdefault("ingredient_text", "")
    st.text_area("Ingredient list (English or Spanish)", key="ingredient_text", height=130,
                 placeholder="Ingredientes: harina de trigo, leche entera en polvo, ...")
    cols = st.columns(len(SAMPLE_TEXTS))
    for col, (label, sample) in zip(cols, SAMPLE_TEXTS.items()):
        col.button(label, key=f"tx_{label}", on_click=set_state, args=("ingredient_text", sample), width="stretch")
    text = st.session_state["ingredient_text"]

run = st.button("Analyze Ingredients", type="primary", disabled=not photo_ready)

if run:
    if mode == "Barcode Lookup" and not (barcode or "").strip():
        st.error("Enter a barcode.")
    elif mode != "Barcode Lookup" and not (text or "").strip():
        st.error("Enter or extract an ingredient list.")
    else:
        with st.spinner("Analysing"):
            result = analyze(
                profile,
                barcode=barcode if mode == "Barcode Lookup" else None,
                text=text if mode != "Barcode Lookup" else None,
                use_live_off=use_live_off,
                use_live_alternatives=use_live_alts,
                sensitivity=sensitivity,
            )
        st.session_state["result"] = result
        st.session_state["result_signature"] = signature

# ---------------------------------------------------------------------------
# Step 2 - Assessment
# ---------------------------------------------------------------------------
res = st.session_state.get("result")
if res:
    st.markdown("### 2. Assessment")
    if st.session_state.get("result_signature") != signature:
        st.info("The active profile or detection threshold has changed. Select Analyze Ingredients to update "
                "the assessment.")
        st.stop()

    product = res["product"]
    if product is not None:
        if product.get("found"):
            info_col, img_col = st.columns([5, 1])
            source = "Open Food Facts" if product["source"] == "live" else "Open Food Facts (cached record)"
            nutri = product.get("nutriscore_grade", "unknown")
            nutri = nutri.upper() if nutri and nutri not in ("unknown", "not-applicable") else "Not available"
            info_col.markdown(
                f"<div class='product-name'>{esc(product['product_name'])}</div>"
                f"<div class='meta'>{esc(product.get('brands', ''))}"
                f"{' &middot; ' + esc(product['quantity']) if product.get('quantity') else ''}"
                f" &middot; Barcode {esc(product['barcode'])} &middot; Nutri-Score: {esc(nutri)}"
                f" &middot; Source: {esc(source)}</div>", unsafe_allow_html=True)
            if product.get("image_url"):
                img_col.image(product["image_url"], width=90)
        else:
            st.markdown(f"<div class='meta'>Barcode {esc(product.get('barcode', ''))} was not found in Open Food "
                        "Facts. Use Label Photo or Ingredient Text instead.</div>", unsafe_allow_html=True)

    detected = res["detected"]
    status_key, detail = status_for(res["verdict"], detected)
    title, css = STATUS[status_key]
    st.markdown(f"<div class='status {css}'><div class='status-title'>{esc(title)}</div>"
                f"<div class='status-detail'>{esc(detail)}</div></div>", unsafe_allow_html=True)

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### Detected Allergens")
        section_label("Direct Ingredients")
        st.markdown(term_rows(detected, "contains", restricted), unsafe_allow_html=True)
        section_label("Precautionary Warnings (Traces / May Contain)")
        st.markdown(term_rows(detected, "may_contain", restricted), unsafe_allow_html=True)
        if detected["false_friends_ignored"]:
            section_label("Excluded Look-alike Terms")
            st.markdown("<div class='meta'>Not EU-regulated allergens: "
                        f"{esc(', '.join(detected['false_friends_ignored']))}.</div>", unsafe_allow_html=True)

    with right:
        st.markdown("#### Additive & Safety Analysis")
        section_label("Identified Additives")
        if res["additives"]:
            st.dataframe(pd.DataFrame([{
                "Code": a["code"],
                "Substance": a["name"] if a["known"] else "Not in reference dictionary",
                "Function": a["category"] if a["known"] else "-",
                "Description": a["en"],
            } for a in res["additives"]]), hide_index=True, width="stretch")
        else:
            st.markdown("<div class='empty'>No E-numbers identified.</div>", unsafe_allow_html=True)

        section_label("Unverified Components")
        warnings = [w for w in detected["warnings"] if w["type"] != "no_text"]
        if warnings:
            rows = []
            for w in warnings:
                related = [EU_NAME[a] for a in w["possible_allergens"]]
                hit = set(w["possible_allergens"]) & restricted
                tag = "<span class='tag'>PROFILE</span>" if hit else ""
                note = f" Possible source of: {', '.join(related)}." if related else ""
                rows.append(f"<div class='term-row{' restricted' if hit else ''}'><span class='term-src'>"
                            f"<b>{esc(display_term(w['term']))}</b>{tag}<br>{esc(w['message'])}{esc(note)}"
                            "</span></div>")
            st.markdown("<div class='term-list'>" + "".join(rows) + "</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='empty'>All components were interpreted.</div>", unsafe_allow_html=True)

    st.markdown("#### Compatible Product Alternatives")
    alts = res["alternatives"]
    if alts["alternatives"]:
        st.dataframe(pd.DataFrame([{
            "Product": a["name"],
            "Brand": a.get("brand") or ("Product type" if a["source"] == "Curated catalogue" else "-"),
            "Nutri-Score": (a.get("nutri") or "").upper() if a.get("nutri") not in (None, "", "unknown") else "-",
            "Barcode": a.get("barcode") or "-",
            "Basis": a["why"],
            "Source": a["source"],
        } for a in alts["alternatives"]]), hide_index=True, width="stretch")
    else:
        st.markdown("<div class='empty'>No alternative in the reference set satisfies every restriction in "
                    "this profile.</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='meta'>{esc(alts['note'])}</div>", unsafe_allow_html=True)

    with st.expander("Analysed ingredient text"):
        st.code(res["ingredient_text"] or "(none)", language=None, wrap_lines=True)
