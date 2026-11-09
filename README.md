# 🛡️ SafeBite: AI Allergen Label Scanner

![Level](https://img.shields.io/badge/PAIBS%20Level-2%20%C2%B7%20Walking%20Skeleton%20Running-brightgreen)
![Benchmark](https://img.shields.io/badge/Benchmark%20Run%201-100%25%20catch%20rate%20%C2%B7%200%20false%20alarms-blue)

**ESADE PAIBS · Group 10**

> We are building an AI-powered label scanner for parents with allergy-sensitive children so they can instantly detect hidden allergens and risky additives from a photo and discover safe, healthier supermarket alternatives in real time.

> ⚠️ **Always verify the physical packaging label. Do not rely solely on automated detection.** This is a student prototype, not a medical device.

---

## Current level: Level 2, Walking Skeleton running

A real product goes from **input** (barcode, pasted ingredient text, or label photo) to **output** (Streamlit UI with family verdict, allergen warnings, additives and alternatives) end to end. Components that are not production-ready yet are stubbed on purpose and listed in the [Real vs. Faked](#real-vs-faked) table.

Example: barcode `3017620422003` → live Open Food Facts lookup → parser finds *avellanas* (Nuts) and *leche descremada* (Milk), and the OFF tags add Soy → the demo family's profile (Leo: Milk, Nuts) gives **⛔ ALERT: DANGEROUS** → ambiguous items (*aceite vegetal*, *lecitina*) are flagged → alternatives are suggested (sunflower-seed cocoa spread, …).

## Quickstart

```bash
git clone https://github.com/mireiaacss/paibs-off.git
cd paibs-off
python -m venv .venv && source .venv/bin/activate      # optional
pip install -r requirements.txt
streamlit run app.py
```

Validate:

```bash
python benchmark/benchmark_runner.py     # 10 benchmark cases, exits 1 if baseline not beaten
pytest -q                                # 22 tests incl. a headless Streamlit run
```

Optional real OCR for label photos: `pip install easyocr`, or `pip install pytesseract` plus `brew install tesseract tesseract-lang`.

## Architecture

```text
 Parent ──► INPUT ─────────► DATA ─────────────► PROCESSING ─────────► AI / RULES ─────────► OUTPUT ──► Parent
           barcode        off_client.py         allergen_parser.py    profile_matcher.py     app.py
           text           (OFF API + cache)     EU-14 synonyms        family verdict         Streamlit
           photo          ocr_reader.py         false friends         additives_service.py
                          (EasyOCR/Tesseract/   may-contain split     alternatives_service.py
                           stub)                "When in doubt, warn"
                                  └──────────── modules/pipeline.py orchestrates ────────────┘
```

```text
paibs-off/
├── app.py                      # Streamlit UI: Live Demo · Benchmark · Architecture tabs
├── config.py                   # EU-14 allergens, bilingual synonyms, false friends, E-numbers
├── modules/
│   ├── pipeline.py             # analyze(): one call from any input to the full result
│   ├── off_client.py           # Open Food Facts barcode lookup + offline cache (5 real products)
│   ├── ocr_reader.py           # EasyOCR → Tesseract → stub fallback
│   ├── allergen_parser.py      # the core engine (real)
│   ├── profile_matcher.py      # per-member and family verdicts + disclaimer
│   ├── additives_service.py    # E-number risk dictionary
│   └── alternatives_service.py # curated catalogue + optional live OFF search
├── benchmark/
│   ├── benchmark_runner.py     # Run 1 evaluator
│   └── test_cases.json         # 10 canonical cases (groups A–F)
├── data/sample_profile.json    # 4 demo family profiles
└── tests/test_pipeline.py      # pytest suite
```

### How the allergen parser works

1. **Normalise**: lower-case, strip accents (`sésamo` → `sesamo`), drop OFF's `_underscores_`.
2. **Split "may contain"**: trigger phrases (`puede contener`, `trazas de`, `may contain`, `traces of`, `peut contenir`, `pot contenir`…) open a clause that runs to the next sentence break. Allergens in that clause go to **May contain**; if the same allergen is also an ingredient, **Contains** wins.
3. **Mask false friends per allergen**: *coconut milk* is masked for Milk and Nuts, *cocoa butter* for Milk, *buckwheat / trigo sarraceno* for Gluten, *lactic acid* for Milk, *nutmeg / nuez moscada* for Nuts. Masking is per allergen, so *almond milk* still counts as Nuts while it doesn't count as Milk.
4. **Match** around 300 plain and hidden terms with word-bounded regex (plural-tolerant), plus `E220–E228` for sulphites.
5. **Guardrail, "When in doubt, warn"**: unspecified *aromas / flavourings*, *especias*, *aceite vegetal*, *lecitina* with no source, *almidón* with no source, *harina* with no source, *caldo / stock*, unknown E-numbers, unrecognised chemical names, and missing ingredient lists all produce warnings. If a warning could hide one of a member's allergens, that member gets **WARNING: UNCERTAIN**, and a product is never shown as SAFE when it has no ingredient list.

### Verdicts

| Verdict | Colour | Rule |
|---|---|---|
| ⛔ **ALERT: DANGEROUS** | red | a member's allergen is an ingredient |
| ⚠️ **WARNING: TRACES** | orange | a member's allergen is only in a "may contain" clause |
| ❓ **WARNING: UNCERTAIN** | yellow | an ambiguous ingredient could hide a member's allergen, or no ingredient list exists |
| ✅ **SAFE ACCORDING TO DETECTED LIST** | green | nothing from the profile detected |

The family verdict is the worst verdict among its members. Every result shows the mandatory disclaimer.

## Real vs. Faked

| Component | Status | What is real | What is faked / limits |
|---|---|---|---|
| Barcode lookup | ✅ REAL | Live Open Food Facts API v2 (`/api/v2/product/{barcode}.json`) | Offline cache of 5 real OFF records (Nutella, Mars, Cruesli, Coca-Cola, Prince) used when the network fails |
| Ingredient → allergen parser | ✅ REAL | Regex and an EU-14 bilingual (ES/EN, partial FR/CA) synonym dictionary with hidden derivatives | Hand-curated dictionary (~300 terms), not exhaustive |
| May-contain detection | ✅ REAL | Clause splitting on trigger phrases | Free-text "made in a factory that…" variants only partly covered |
| False-friend handling | ✅ REAL | Per-allergen masking list | Curated list |
| "When in doubt, warn" guardrail | ✅ REAL | Ambiguous terms, unknown E-numbers, unparsed chemicals, missing text | Heuristic rules, not a learned model |
| OFF allergen tags merge | ✅ REAL | OFF `allergens_tags` / `traces_tags` are unioned with parser output | — |
| Family profile matcher | ✅ REAL logic | Per-member and worst-case family verdict | Profiles are demo JSON; no accounts or persistence |
| Label photo OCR | 🟨 PARTIAL | EasyOCR or Tesseract when installed; extracted text is editable (human in the loop) | With no OCR engine installed, falls back to a fixed demo label text, clearly flagged in the UI |
| Additive risk lookup | 🟨 STUB | Regex detection of E-numbers (`E220`, `E-150d`, `e 102`) and some additive names | ~35-entry curated dictionary instead of the full EFSA / OFF taxonomy |
| Alternatives | 🟨 STUB | Category detection and allergen filtering; optional live OFF category search sorted by Nutri-Score | Default is a curated catalogue of generic product types, not real shelf stock or prices |
| Mobile camera app | 🟥 FAKED | Browser `st.camera_input` in Streamlit | No native app and no live barcode video decoding (the barcode is typed or picked) |

## Benchmark: Run 1 (ingredient text → allergen parser)

10 canonical cases from Session 2 (`benchmark/test_cases.json`):

| # | Group | Label text | Expected |
|---|---|---|---|
| 1 | A · plain names | Wheat flour, whole milk powder, eggs | Gluten, Milk, Eggs |
| 2 | B · hidden | Azúcar, suero lácteo en polvo, caseinato sódico, lecitina de soja | Milk, Soy |
| 3 | B · hidden | Durum wheat semolina, water, spelt flour | Gluten |
| 4 | E · false friends | Buckwheat flour, coconut milk, cocoa butter, lactic acid, nutmeg | none (0 false alarms) |
| 5 | C · may contain | Chocolate negro, almendras. Puede contener trazas de cacahuete, leche y sésamo | Contains Nuts; May contain Peanuts, Milk, Sesame |
| 6 | B · E-number | Dried apricots, preservative (E220) | Sulphites |
| 7 | D · clean | Arroz, agua, aceite de oliva virgen extra, sal | none |
| 8 | F · complex | Surimi (pescado blanco, almidón de trigo, clara de huevo), gambas, mejillones, salsa (mostaza) | Fish, Gluten, Eggs, Crustaceans, Molluscs, Mustard |
| 9 | F · complex | Vegetable stock (celeriac), lupin flour, ghee | Celery, Lupin, Milk |
| 10 | B · hidden | Tofu, tahini, rice vinegar, salt | Soy, Sesame |

**Metrics**
- **Catch rate (recall)**: expected allergens detected (in either list) ÷ expected allergens.
- **False alarms**: allergens flagged that were not expected.
- **Section accuracy**: expected allergens placed in the correct list (contains vs may contain).
- **Baseline**: a naive keyword scanner that only knows each allergen's everyday name in EN and ES, matches substrings, and does not handle false friends or traces. The spec's reference recall is **57%**. Our reproduction of that scanner scores 59% with 3 false alarms (it reads *buckwheat* as wheat, *coconut milk* as milk, and *coconut / nutmeg* as nuts).

**Results (`python benchmark/benchmark_runner.py`)**

| Metric | Naive keyword baseline | **Our parser** |
|---|---|---|
| Catch rate | 57% (spec) / 59% (reproduced) | **100% (22/22)** |
| False alarms | 3 | **0** |
| Contains vs traces accuracy | n/a | **100%** |
| Cases passed | — | **10/10** |

**Caveat:** we built the synonym dictionary while looking at these 10 cases, so 100% is an in-sample score. For Level 3 we need a held-out set of real Spanish supermarket labels (photographed), plus an OCR → parser run (Run 2).

## Team

ESADE PAIBS, Group 10.
