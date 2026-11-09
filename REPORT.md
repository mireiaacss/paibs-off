# Allergen & Additive Verification Tool: Technical Report

**Project:** ESADE PAIBS, Group 10
**Repository:** https://github.com/mireiaacss/paibs-off
**Status:** Level 2, walking skeleton running end to end
**Report date:** 9 November 2026

---

## Contents

1. [System overview and problem statement](#1-system-overview-and-problem-statement)
2. [End-to-end workflow and architecture](#2-end-to-end-workflow-and-architecture)
3. [Model and parsing methodology](#3-model-and-parsing-methodology)
4. [Real vs. faked component audit](#4-real-vs-faked-component-audit)
5. [Benchmark evaluation and results](#5-benchmark-evaluation-and-results)
6. [Known limitations and next steps](#6-known-limitations-and-next-steps)
7. [Reproducing the results](#7-reproducing-the-results)

---

## 1. System overview and problem statement

### 1.1 User context

The primary user is a parent managing a child's food allergy or other dietary restriction. They make the decision at a supermarket shelf or in the kitchen, often under time pressure, often with a product labelled in a language other than their own. Getting it wrong can be serious: for a child with an IgE-mediated allergy, a single missed ingredient can cause anaphylaxis.

The tool answers one question per product: **does this product conflict with my child's restrictions, and how sure can I be?** It also explains the additives on the label and suggests compatible alternatives from the same category.

### 1.2 Why simple keyword matching fails

A scanner that looks for the 14 allergen names ("milk", "wheat", "egg"…) misses most of the cases where a parent actually needs help:

| Failure mode | Example | What a keyword scanner does |
|---|---|---|
| Hidden derivatives | *caseinato sódico*, *suero lácteo*, *ghee* are all milk; *espelta* and *sémola* are gluten; *tahini* is sesame | Misses them: the word "milk" never appears |
| E-numbers | *E220* (sulphur dioxide) is a regulated allergen | Misses it |
| False friends | *coconut milk*, *cocoa butter*, *buckwheat*, *lactic acid*, *nutmeg* | Raises false alarms, so parents learn to ignore warnings |
| Precautionary labelling | "*Puede contener trazas de cacahuete*" | Can't tell "contains" from "may contain"; both look the same |
| Language | Spanish shelves, English imports, French or Catalan text in crowdsourced data | Covers only the language it was written in |
| Crowdsourced data variance | In Open Food Facts the English Nutella entry reads only "sugar, palm oil"; a brioche listing has no milk tag; one Gullón record holds raw OCR noise | Takes the record at face value |

The last row matters for any system built on community data. Open Food Facts (OFF) is the best open source of barcode-linked ingredient lists, but each record is entered by volunteers and may be partial, mistranslated, or out of date. The system therefore (a) combines OFF's own allergen tags with an independent parse of the text, (b) prefers the Spanish text, then English, and skips placeholder text, and (c) treats a missing or unreadable ingredient list as unassessable, never as safe.

### 1.3 Primary metric

**Pooled allergen catch rate (recall):** across all benchmark cases, the share of expected allergens the system detects, whether as a direct ingredient or as a trace.

- **Target: ≥ 95%.**
- Recall is the primary metric because in this domain a miss is far more costly than a false alarm.
- **Secondary metrics:** false-alarm count (a system that cries wolf gets abandoned), and section accuracy, meaning whether each allergen is correctly placed under *contains* or *may contain*.

---

## 2. End-to-end workflow and architecture

### 2.1 Data flow

```text
 ┌─────────────┐   ┌──────────────────────┐   ┌──────────────────┐   ┌────────────────────┐   ┌────────────────────┐   ┌──────────────┐
 │ 1. INPUT    │──►│ 2. EXTRACTION /      │──►│ 3. PARSER ENGINE │──►│ 4. PROFILE         │──►│ 5. ALTERNATIVE     │──►│ 6. USER      │
 │ Barcode     │   │    NORMALISATION     │   │ allergen_parser  │   │    COMPARATOR      │   │    RECOMMENDER     │   │ PRESENTATION │
 │ Label photo │   │ off_client / OCR     │   │ + additives      │   │ profile_matcher    │   │ alternatives_      │   │ app.py       │
 │ Text        │   │ text normalise       │   │   _service       │   │                    │   │ service            │   │ (Streamlit)  │
 └─────────────┘   └──────────────────────┘   └──────────────────┘   └────────────────────┘   └────────────────────┘   └──────────────┘
                              orchestrated by modules/pipeline.py :: analyze()
```

| Step | Module | What happens |
|---|---|---|
| 1. Input | `app.py` | The user picks **Barcode Lookup**, **Label Photo** or **Ingredient Text**, an active profile, and a detection threshold. |
| 2a. Barcode | `modules/off_client.py` | `GET https://world.openfoodfacts.org/api/v2/product/{barcode}.json` with an 8 s timeout. Returns name, brand, ingredient text (ES, then EN, then generic), `allergens_tags`, `traces_tags`, image, Nutri-Score and categories. On network failure, a cache of 7 real OFF records keeps a live demo working. |
| 2b. Photo | `modules/ocr_reader.py` | EasyOCR, then Tesseract (`spa+eng`). The image is EXIF-rotated and upscaled to ≥ 1200 px, and the text after "Ingredientes:/Ingredients:" is kept. The recognised text appears in an editable box so the user can correct it before analysis. |
| 2c. Normalise | `allergen_parser.normalize` | Lower-case, strip accents, replace the œ ligature, turn OFF's `_milk_` markup into plain text, collapse whitespace. |
| 3. Parse | `modules/allergen_parser.py` | Split off precautionary clauses, mask false friends per allergen, match plain and hidden terms, run the guardrail (§2.3). For barcodes, OFF's declared tags are merged in (a union, so neither source can remove an allergen). |
| 3b. Additives | `modules/additives_service.py` | Detect E-numbers (`E220`, `E-150d`, `e 102`) and named additives (*tartrazina*, *aspartame*), and attach descriptions from the reference dictionary. |
| 4. Compare | `modules/profile_matcher.py` | Per-member verdict, then the worst member's verdict becomes the household verdict (§2.4). |
| 5. Recommend | `modules/alternatives_service.py` | Identify the category, then query the OFF search service for same-category products with no allergen or trace tag from the profile, a completed ingredient list, and Nutri-Score A–C, ranked by Nutri-Score. Falls back to a curated catalogue. |
| 6. Present | `app.py` | Status card, then two columns (detected allergens; additives and unverified components), then compatible alternatives. Every page carries the packaging notice. |

### 2.2 Uniform handling of Spanish and English

Spanish and English go through the same code path; there is no language detection step that could fail.

1. **One dictionary, many surface forms.** Each of the 14 EU allergens has a single canonical key (`Milk`, `Gluten`, …) with plain names and hidden derivatives in Spanish and English, plus the French and Catalan forms that appear in OFF data. In total 275 terms (`config.ALLERGENS`).
2. **Accent-insensitive matching.** Both the label and the dictionary are normalised the same way, so *sésamo*, *SESAMO* and *sesamo* are identical, and an OCR result that drops an accent still matches.
3. **Shared tolerances.** Every term is matched with word boundaries, flexible spacing or hyphens between words, and an optional plural (`-s` / `-es`). This covers *almendra/almendras*, *egg/eggs* and *mejillón/mejillones* without listing each form.
4. **Multilingual triggers.** The precautionary-clause triggers cover *puede contener (trazas de)*, *trazas de*, *may contain (traces of)*, *traces of*, *produced in a factory that handles*, *elaborado en una fábrica que…*, *peut contenir* and *pot contenir*.

A label that mixes languages, such as "*Harina de trigo, whey powder. May contain traces of frutos de cáscara*", is handled without special-casing.

### 2.3 Fail-safe logic: "When in doubt, warn"

The system never treats an ingredient it doesn't understand as safe. The guardrail produces **unverified components** in five situations:

| Trigger | Example | Possible hidden allergens |
|---|---|---|
| Unspecified flavourings | *aromas*, *saborizante*, *natural flavourings* | Milk, Celery, Mustard |
| Unspecified spices | *especias*, *spices* | Celery, Mustard, Sesame |
| Vegetable or hydrolysed protein | *proteína vegetal*, *hydrolysed protein* | Soy, Gluten |
| Lecithin with no stated source | *lecitina*, *E322* (but not *lecitina de girasol* or *soy lecithin*) | Soy |
| Starch with no stated source | *almidón*, *modified starch* (but not *corn starch*) | Gluten |
| Vegetable oil with no stated source | *aceite vegetal* (but not *aceites vegetales (girasol, colza)*) | Peanuts |
| Flour with no stated source | *harina* on its own | Gluten |
| Stock / broth | *caldo*, *vegetable stock* | Celery |
| E-number not in the reference dictionary | *E123* | Unknown |
| Unrecognised technical ingredient | e.g. *sodium aluminosilicate* (chemical suffix, not on the known-safe list, no allergen match) | Unknown |
| Missing or very short ingredient text | empty OFF record, failed OCR | All 14 |

How unverified components affect the status depends on the **Detection Threshold** in the sidebar:

- **Maximum Caution (default):** if an unverified component could hide one of the profile's allergens, the status becomes **UNVERIFIED COMPONENTS REQUIRE REVIEW** (amber).
- **Standard Sensitivity:** the status is decided only by explicit declarations. Unverified components are still listed and counted in the status line, and those relevant to the profile are tagged.
- **In both modes**, a product with no usable ingredient list shows **INSUFFICIENT INGREDIENT DATA** and is never reported as compatible.

### 2.4 Status logic

| Status (UI) | Internal verdict | Rule |
|---|---|---|
| **RESTRICTION CONFLICT DETECTED** (muted crimson) | `ALERT: DANGEROUS` | A restricted allergen is a direct ingredient (parser or OFF `allergens_tags`). |
| **POTENTIAL TRACE EXPOSURE** (muted amber) | `WARNING: TRACES` | A restricted allergen appears only in a precautionary statement (parser or OFF `traces_tags`). |
| **UNVERIFIED COMPONENTS REQUIRE REVIEW** (muted amber) | `WARNING: UNCERTAIN` | Maximum Caution only: an ambiguous ingredient could hide a restricted allergen. |
| **INSUFFICIENT INGREDIENT DATA** (muted amber) | `WARNING: UNCERTAIN` | No usable ingredient list, in both modes. |
| **NO CONFLICTS IDENTIFIED WITH ACTIVE PROFILE** (muted sage) | `SAFE ACCORDING TO DETECTED LIST` | None of the above. The wording deliberately avoids "safe". |

If one allergen is found both as an ingredient and in a trace statement, the ingredient finding wins. For a household profile with several members, each member gets a verdict and the household status is the worst one.

### 2.5 Code layout

```text
paibs-off/
├── app.py                      # Streamlit front end (single-view, two-step flow)
├── config.py                   # Allergen dictionary, false friends, triggers, guardrail rules, additives
├── modules/
│   ├── pipeline.py             # analyze(): input → full assessment
│   ├── off_client.py           # Open Food Facts product API + offline cache
│   ├── ocr_reader.py           # EasyOCR / Tesseract / stub
│   ├── allergen_parser.py      # Parser engine and guardrail
│   ├── profile_matcher.py      # Verdicts, sensitivity modes, disclaimer
│   ├── additives_service.py    # E-number detection and lookup
│   └── alternatives_service.py # OFF search + curated catalogue
├── benchmark/
│   ├── benchmark_runner.py     # Run 1 evaluator (CLI report + unittest suite)
│   └── test_cases.json         # The 10 canonical cases
├── data/sample_profile.json    # Reference dietary profiles
├── tests/test_pipeline.py      # pytest: parser, matcher, services, UI flows
└── .streamlit/config.toml      # Light theme, minimal toolbar
```

---

## 3. Model and parsing methodology

The parser is a deterministic, rule-based model: a curated lexicon plus regular expressions. We chose this over a learned model for Level 2 for three reasons. First, every decision can be traced to a dictionary entry, which matters for a safety tool. Second, there is no labelled Spanish training set yet. Third, a dictionary failure is fixed by adding a term, not by retraining.

### 3.1 `modules/allergen_parser.py`, step by step

**Step 1: Normalisation and tokenisation**

`normalize()` lower-cases the text, applies Unicode NFKD decomposition and removes combining marks (accents), and replaces `œ` with `oe` and `_` with a space (OFF marks allergens as `_trigo_`). It then collapses whitespace.

For item-level checks, `_items()` splits on commas, semicolons, parentheses and brackets, and strips leftover punctuation (`. : - *`) from each item. Nested ingredients such as *Surimi (pescado blanco, almidón de trigo, clara de huevo)* are therefore checked both as part of the whole text and as separate items.

**Step 2: Clause splitting, "contains" vs "may contain"**

`split_may_contain()` searches for any of 15 trigger patterns (`config.MAY_CONTAIN_TRIGGERS`), longest first, so *puede contener trazas de* matches before *trazas*. A precautionary clause runs from the trigger to the next sentence break (`.`, `;`, `!`, newline). A decimal point such as *4.5%* is not treated as a sentence break. All other text is the direct-ingredient text.

```text
"chocolate negro, almendras. puede contener trazas de cacahuete, leche y sesamo"
 └──────── contains ────────┘ └trigger──────────────┘└──── may_contain ─────┘
```

Each part is parsed on its own. Any allergen found in the direct text is removed from the trace list, so that "contains milk … may contain milk" reports milk once, as an ingredient.

**Step 3: Synonym mapping for the 14 EU allergens**

Each allergen in `config.ALLERGENS` has `plain` names and `hidden` derivatives. Each term compiles to a word-bounded, plural-tolerant regex, and terms are tried longest first. When a term matches, its span is blanked out, so *durum wheat semolina* is reported once and not again as *wheat*. Examples of hidden derivatives:

| EU allergen | Hidden derivatives (excerpt) |
|---|---|
| Milk | casein, caseína, caseinato (sódico), whey, suero lácteo (en polvo), suero de leche, lactosa, lactoglobulina, ghee, mantequilla, nata, queso, yogur, kefir, cuajada |
| Gluten | durum, semolina, sémola, spelt, espelta, kamut, seitan, cuscús, bulgur, malta, almidón de trigo, cebada, centeno |
| Eggs | albúmina, ovoalbúmina, clara de huevo, yema, lisozima, mayonesa, merengue |
| Soy | tofu, edamame, tempeh, miso, tamari, shoyu, lecitina de soja |
| Sesame | tahini, tahina, ajonjolí, gomasio |
| Celery | celeriac, apionabo, sal de apio |
| Lupin | altramuz, altramuces, lupin flour |
| Tree nuts | almendra, avellana, nuez/nueces, anacardo, pistacho, pecana, macadamia, praliné, mazapán, gianduja |
| Crustaceans | gamba, langostino, cangrejo, bogavante, cigala, camarón, krill |
| Molluscs | mejillón, almeja, ostra, calamar, pulpo, sepia, vieira, berberecho |
| Fish | surimi, anchoa, atún, bacalao, merluza, salmón, sardina, fish sauce |
| Sulphites | metabisulfito, bisulfito, dióxido de azufre, diòxid de sofre, **E220–E228** (regex `\be[\s\-]?22[0-8]\b`) |

Very short Catalan words (*ou* = egg, *api* = celery) match only when they are a whole comma-separated item, so they don't fire inside other words.

**Step 4: False-friend suppression**

`config.FALSE_FRIENDS` has 42 phrases, each linked to the allergens it must **not** trigger. Before an allergen is searched for, its false friends are masked out of the text:

| Phrase | Suppressed for | Reason |
|---|---|---|
| coconut, coconut milk, leche de coco | Tree nuts, Milk | Coconut isn't an EU tree nut; coconut milk isn't dairy |
| buckwheat, trigo sarraceno, alforfón | Gluten | Buckwheat is a gluten-free pseudo-cereal |
| cocoa butter, manteca de cacao, shea butter | Milk | Plant fats |
| lactic acid, ácido láctico, lactato | Milk | Fermentation products, not dairy |
| nutmeg, nuez moscada | Tree nuts | A seed spice |
| almond milk, leche de soja, oat milk… | Milk only | The plant itself is still detected (almond milk still counts as tree nuts) |
| sin gluten, gluten-free, sin lactosa | Gluten, Milk | Absence claims shouldn't trigger the allergen they deny |

Masking per allergen, not across the whole text, is what keeps *almond milk* from becoming a total blind spot. The phrases that were masked are returned (`false_friends_ignored`) and shown to the user as "Excluded look-alike terms", so the suppression is visible.

**Step 5: Guardrail.** See §2.3.

**Output contract**

```python
{
  "contains":       {"Milk", "Soy"},
  "may_contain":    {"Nuts"},
  "warnings":       [{"type": "ambiguous", "term": "aromas", "message": "...", "possible_allergens": ["Milk", ...]}],
  "detected_terms": {"Milk": [{"term": "caseinato", "hidden": True, "section": "contains"}], ...},
  "false_friends_ignored": ["cocoa butter"],
  "normalized_text": "...",
}
```

`merge_off_tags()` then adds OFF `allergens_tags` / `traces_tags` (e.g. `en:soybeans` → Soy) with the same "ingredient wins over trace" rule.

### 3.2 Vision and OCR fallback

`ocr_reader.read_label()` never raises an error and always reports which engine produced the text:

1. **EasyOCR** (`es`, `en`), used if installed. It needs PyTorch (about 1 GB), so it is optional.
2. **Tesseract 5** with `spa+eng`, the engine used on the reference installation (Homebrew `tesseract` plus the `spa.traineddata` fast model). The image is EXIF-rotated, converted to grayscale and upscaled before recognition.
3. **Stub:** if no engine is installed or none returns readable text, a fixed sample ingredient text is inserted and the UI shows a notice telling the user to replace it.

Whatever the engine, the recognised text goes into an **editable text box** before analysis. This human-in-the-loop step is the main defence against OCR errors. If the user can't confirm the text, the "Ingredient Text" path is always available as a structured fallback. On a synthetic Spanish label, Tesseract reproduced the ingredient text exactly and the pipeline returned the expected allergens (Gluten, Milk, Eggs, Soy as ingredients; tree nuts and sesame as traces).

---

## 4. Real vs. faked component audit

| Component | Status | Implementation | Engineering rationale |
|---|---|---|---|
| OFF barcode integration | **Real** | Live OFF product API v2, field-limited request, 8 s timeout, ES→EN→generic text selection, union with OFF allergen/trace tags | Barcode lookup is the fastest input for parents and gives manufacturer-declared tags as a second source. |
| Offline product cache | **Real data, fallback only** | 7 real OFF records captured 9 Nov 2026 (Nutella, Mars, Cruesli, Coca-Cola, Prince, Diet Rádisson corn cakes, Simpl croissants) | OFF rate-limits and occasionally returns errors (observed in development); a live demo must not depend on venue Wi-Fi. The UI labels cached records as such. |
| Dual-language allergen interpreter | **Real** | Rule-based parser, 275-term ES/EN (+FR/CA) lexicon, regex matching | The riskiest part of the product, so it was built for real first. |
| Precautionary-clause splitting | **Real** | 15 multilingual trigger patterns | Telling traces apart from ingredients is core to the decision. |
| False-friend filtering | **Real** | 42-phrase per-allergen mask list | Removes the false alarms that make parents ignore warnings. |
| "When in doubt, warn" guardrail | **Real** | Ambiguous-term rules, unknown E-numbers, unparsed chemicals, missing text | Safety requirement: unknown ≠ safe. |
| Profile matching logic | **Real** | Per-member and household verdicts, two sensitivity modes | Deterministic and testable. |
| Benchmark suite | **Real** | `benchmark_runner.py` (CLI + `unittest`), 10 cases, reproduced naive baseline; 27 pytest tests including headless UI flows | Each change is checked against the acceptance metric. |
| Label OCR | **Real when installed, stub otherwise** | Tesseract `spa+eng` or EasyOCR; stub text if neither is installed | OCR quality is not the Level 2 risk; the editable text box contains its errors. |
| Image quality check (OpenCV blur filter) | **Not implemented** | — | Planned for Level 3 (variance-of-Laplacian blur score to reject unreadable photos). Today a blurry photo yields poor OCR text, which the user sees and can correct; very short text triggers *Insufficient ingredient data*. |
| Native mobile camera capture | **Faked** | Browser `st.camera_input` / file upload; no native app; no live barcode decoding from video (barcode is typed or picked) | A native app adds no evidence for the core hypothesis at this level. Note: phone browsers allow camera access only over HTTPS. |
| Additive explanations | **Stub (static dictionary)** | 34 curated E-numbers with function class and description, plus name aliases; unknown codes are surfaced, not hidden | The full EFSA / OFF additive taxonomy is a data-ingestion task, not a design risk. |
| Alternative recommendations | **Stub with live enrichment** | Live: OFF search service (`search.openfoodfacts.org`) filtered by category, profile allergen/trace tags, completed ingredients, Nutri-Score A–C, plus a local name re-check. Fallback: predefined category catalogue of generic product types | The catalogue keeps the step working offline; live results depend on crowdsourced tags (see §6). |

---

## 5. Benchmark evaluation and results

### 5.1 Methodology: Run 1

**Run 1** sends each case's ingredient text straight to the parser (no OCR, no OFF), which isolates the interpretation step. The 10 canonical cases from Session 2 (`benchmark/test_cases.json`) span six groups:

| Group | Focus | Cases |
|---|---|---|
| A | Plain allergen names | 1 |
| B | Hidden names (derivatives, E-numbers) | 2, 3, 6, 10 |
| C | Traces / may contain | 5 |
| D | Allergen-free control | 7 |
| E | False friends | 4 |
| F | Rare allergens (celery, lupin, molluscs, crustaceans, mustard) in complex dishes | 8, 9 |

For each case, the expected allergen set is compared with the detected set (direct ingredients ∪ traces):

- **Catch rate (recall)** = Σ caught ÷ Σ expected, pooled over all cases (22 expected allergens in total).
- **False alarms** = Σ detected allergens not expected.
- **Section accuracy** = expected allergens placed in the correct list.
- A case **passes** only if it has no misses, no false alarms and correct sections.

### 5.2 Baseline definition

The baseline is a **naive 30-keyword scanner** (`NAIVE_KEYWORDS` in `benchmark_runner.py`): each allergen's everyday name in English and Spanish (*milk/leche*, *wheat/trigo*, *nut*, *soy/soja*…), matched as accent-insensitive substrings, with no derivatives, no false-friend handling and no clause splitting. The project specification sets its expected recall at **57%**; our reproduction scores **59% (13/22)**, which is consistent with that.

### 5.3 Results

| Metric | Naive baseline | **System** | Target |
|---|---|---|---|
| Pooled catch rate (recall) | 57% (spec) / 59% (reproduced, 13/22) | **100% (22/22)** | ≥ 95% |
| False alarms | 3 (all in the false-friend case) | **0** | 0 |
| Section accuracy (contains vs traces) | n/a (no trace concept) | **100%** | — |
| Cases fully passed | 3/10 | **10/10** | — |

The baseline fails exactly where §1.2 predicts: hidden derivatives (cases 2, 6, 9, 10), rare allergens under unfamiliar names (case 8: *gambas*, *mejillones*), tree nuts named only as *almendras* (case 5), and false friends (case 4: three false alarms from *buckwheat*, *coconut milk* and *coconut/nutmeg*).

### 5.4 Case-by-case results

| # | Group | Ingredient text | Expected | Baseline behaviour | System result |
|---|---|---|---|---|---|
| 1 | A | Wheat flour, whole milk powder, eggs | Gluten, Milk, Eggs | Found all 3 | Pass: Gluten, Milk, Eggs |
| 2 | B | Azúcar, suero lácteo en polvo, caseinato sódico, lecitina de soja | Milk, Soy | Found Soy; **missed Milk** | Pass: Milk (*suero lácteo en polvo*, *caseinato sódico*), Soy (*lecitina de soja*) |
| 3 | B | Durum wheat semolina, water, spelt flour | Gluten | Found Gluten (via "wheat"; never saw *spelt*) | Pass: Gluten (*durum wheat semolina*, *spelt*) |
| 4 | E | Buckwheat flour, coconut milk, cocoa butter, lactic acid, nutmeg | None | **3 false alarms**: Gluten, Milk, Tree nuts | Pass: none; all 5 look-alikes listed as excluded |
| 5 | C | Chocolate negro, almendras. Puede contener trazas de cacahuete, leche y sésamo | Contains: Tree nuts. May contain: Peanuts, Milk, Sesame | Found Peanut, Milk, Sesame but **as ingredients**; **missed Tree nuts** (*almendras*) | Pass: Contains Tree nuts; May contain Peanuts, Milk, Sesame |
| 6 | B | Dried apricots, preservative (E220) | Sulphites | **Missed Sulphites** | Pass: Sulphites (E220) |
| 7 | D | Arroz, agua, aceite de oliva virgen extra, sal | None | None | Pass: none, no warnings |
| 8 | F | Surimi (pescado blanco, almidón de trigo, clara de huevo), gambas, mejillones, salsa (mostaza) | Fish, Gluten, Eggs, Crustaceans, Molluscs, Mustard | Found 4; **missed Crustaceans, Molluscs** | Pass: all 6 |
| 9 | F | Vegetable stock (celeriac), lupin flour, ghee | Celery, Lupin, Milk | Found Lupin; **missed Celery, Milk** | Pass: all 3, plus an unverified-component note for *stock* (celery source) |
| 10 | B | Tofu, tahini, rice vinegar, salt | Soy, Sesame | **Missed both** | Pass: Soy (*tofu*), Sesame (*tahini*) |

### 5.5 Interpretation and caveat

The system meets the ≥ 95% recall target with zero false alarms on the standard false friends, a 43-point lift over the specified baseline. **This is an in-sample result:** the lexicon was built while looking at these 10 cases, so it shows the design works but doesn't establish how well it generalises. Results on unseen, real-world labels will be lower. The next evaluation must use a held-out set (see §6).

---

## 6. Known limitations and next steps

| Limitation | Effect | Planned mitigation (Level 3+) |
|---|---|---|
| In-sample benchmark | Recall on unseen labels not yet measured | Held-out set of ≥ 50 photographed Spanish supermarket labels, double-annotated; report recall with a confidence interval |
| No Run 2 (photo → OCR → parser) | OCR errors on real packaging not quantified | Run the benchmark end to end from photos; measure character error rate and its effect on recall |
| Lexicon coverage | Rare derivatives or regional names may be missed | Mine OFF `ingredients_tags` across all Spanish products and review unmatched frequent tokens |
| Crowdsourced OFF data | Partial or wrong ingredient lists and missing tags (e.g. a brioche with no milk tag appearing as an alternative) | Show record completeness, prefer manufacturer-verified records, keep the parser as an independent check, keep the packaging notice |
| Alternatives quality | Live results are filtered only on OFF tags and the product name | Add the parser's verdict on each candidate's full ingredient list before showing it |
| No image quality gate | Blurry photos give poor OCR | OpenCV blur score with a re-take prompt |
| No native camera | Camera needs HTTPS in the browser | Deploy behind HTTPS; later a native barcode scanner |
| Additive dictionary (34 codes) | Many E-numbers show as "not in reference dictionary" | Import the full EU additive list with function classes |
| No profile persistence | Profiles reset each session | Encrypted per-user profiles |

---

## 7. Reproducing the results

```bash
git clone https://github.com/mireiaacss/paibs-off.git && cd paibs-off
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m unittest benchmark/benchmark_runner.py   # Run 1 acceptance tests (4 tests)
python benchmark/benchmark_runner.py               # Printed benchmark report
python -m pytest -q                                # Full suite (27 tests, incl. headless UI flows)
streamlit run app.py                               # Application

# Optional OCR (macOS)
brew install tesseract && pip install pytesseract
curl -L -o "$(brew --prefix)/share/tessdata/spa.traineddata" \
     https://github.com/tesseract-ocr/tessdata_fast/raw/main/spa.traineddata
```

> **Notice:** This tool is a decision aid. Cross-reference all automated assessments against physical product packaging prior to consumption.
