# Project Decision & Management Log — Group 10

**Project:** Allergen & Additive Verification Tool (ESADE PAIBS)  
**Repository:** https://github.com/mireiaacss/paibs-off  
**Demo Day:** 2 December 2026  

---

## 1. Key Decisions & Architecture Changes

| Date | Area | Previous Plan | Current Decision | Why |
| :--- | :--- | :--- | :--- | :--- |
| 9 Nov | Allergen Parser | Hugging Face LLM from day one | 275-term ES/EN/FR/CA rule-based parser as baseline | Needed a fast, deterministic Level 2 walking skeleton with zero training data; now serves as the baseline to beat at Level 3. |
| 9 Nov | Label OCR | Hugging Face vision model | EasyOCR with Tesseract (`spa+eng`) fallback + editable text box | Faster to integrate into the skeleton and lets the user fix obvious OCR typos before analysis. |
| 9 Nov | Family Profiles | SQLite database | Local JSON file + custom profile builder | Avoids database overhead while supporting multi-child household profiles. |
| 9 Nov | Alternatives | Hardcoded mock list | Live Open Food Facts API search (filtered by Nutri-Score A–C) + curated fallback | Easy to make partially real once the OFF client was working. |
| 9 Nov | Demo Reliability | Live API calls only | Added local offline cache of 7 real OFF records | Guarantees the live demo will not crash if Wi-Fi or the OFF API fails. |

---

## 2. Press Release & FAQs (Work 2)

* **Headline:** Parents with allergy-sensitive children can now scan supermarket food labels in seconds to catch hidden allergens, understand risky additives, and discover safer alternatives.
* **Problem:** Checking tiny, crowded ingredient lists in the supermarket aisle is stressful and risky, especially when allergens hide behind technical names like *casein* or *suero de leche* or appear in another language.
* **Solution:** Our Streamlit web app lets parents enter a barcode, upload a label photo, or paste ingredient text in Spanish or English. It flags the 14 EU allergens—separating direct ingredients from "may contain" traces—translates E-numbers, and suggests allergen-free alternatives.
* **User Quote:** *"I finally don't have to google weird ingredient names in the middle of the supermarket just to make sure a snack is safe for my kid."*

**FAQs:**
* **Where does the data come from?** We query the Open Food Facts API (backed by a local offline cache of 7 real records) and evaluate our pipeline on a fixed set of real supermarket label photos.
* **How accurate is the model?** On our initial 10 typed test cases, our 275-term dictionary parser caught 22/22 expected allergens (100%) with 0 false alarms, compared to 59% (3 false alarms) for a simple keyword search. We are now evaluating an LLM against this baseline on 30–50 unseen real label photos to measure true end-to-end recall.
* **What is still faked or out of scope?** Automated photo quality checks, barcode-vs-photo cross-checking, and supermarket prices are cut/faked for this demo. Profiles are stored in JSON rather than a full database, and the interface runs as a Streamlit web app instead of a native mobile app.

---

## 3. Final Scope & Cut List (Work 3)

**In Scope for 2 December:**
* **Real Label Photo Benchmark (30–50 unseen photos):** *Done when* the labeled ground-truth CSV is complete and evaluated end-to-end through OCR + parser.
* **Level 3 AI Allergen Parser (LLM vs. dictionary baseline):** *Done when* both run on the exact same unseen evaluation set and pooled recall per allergen is logged (target: ≥ 95%).
* **Alternative Safety Verification:** *Done when* every suggested Open Food Facts alternative is double-checked by our own parser before being shown.
* **Public Deployment (Level 4):** *Done when* the app is live on Streamlit Community Cloud and tested by someone outside the team.

**Cut List (Won't / Faked for 2 December):**
* Automated photo quality check (blur/lighting rejection).
* Barcode vs. photo discrepancy check.
* Supermarket availability and prices (Open Prices).
* Native mobile app build.

---

## 4. Pre-mortem: Top 3 Risks & Decision Rules (Work 5)

| Risk | Likelihood | Impact | Fallback | Decision Rule (Continue / Revise / Stop) |
| :--- | :--- | :--- | :--- | :--- |
| **OCR errors on real phone photos cause missed allergens** | High | High | Use barcode lookup + editable OCR text box + "when in doubt, warn" threshold | **By 27 Nov:** If photo-to-allergen recall is below 90%, *revise* demo scope to prioritize barcode/editable-text flow and declare OCR limits in the log. |
| **LLM parser does not beat the 275-term dictionary baseline (or is too slow)** | Medium | High | Keep the rule-based parser for the live demo and document the LLM benchmark comparison | **By 28 Nov:** If the LLM does not improve recall on unseen photos over the baseline, *stop* LLM integration and log the result. |
| **Open Food Facts API is slow or unreachable on Demo Day** | Medium | Medium | Switch to the local offline cache of real OFF products | Keep the offline cache toggle tested and ready before code freeze. |

---

## 5. Milestones & Team Rules (Work 6)

**Milestones to 2 December:**
* **25 Nov:** 30–50 real supermarket label photos collected + ground-truth CSV ready — *Owner: Martina*
* **27 Nov:** Level 3 benchmark complete (OCR + LLM vs. dictionary baseline logged) — *Owner: Mireia*
* **29 Nov:** App deployed to Streamlit Community Cloud + external Smoke Test completed — *Owner: Maria*
* **30 Nov:** **Code Freeze** (no new features; bug fixes only) — *Owner: All*
* **1 Dec:** **Full Rehearsal** + final 1-slide guide ready — *Ana: All*
* **2 Dec:** Demo Day

**Team Rules:**
* **Branches:** One per task, merged in 1–2 days.
* **Review:** Every merge reviewed by another member.
* **Integration:** Merge into `main` twice a week.
* **Testing:** Smoke test of the demo path before every merge.

---

## 6. Smoke Test Log (Work 7)

* **Internal Smoke Test (22 Nov — Martina's laptop):** Running `streamlit run app.py` crashed on startup with `TypeError: ButtonGroupMixin.segmented_control() got an unexpected keyword argument 'required'` at `app.py:223`.
  * **Fix & Owner:** Removed `required=True` and added a default fallback (`or "Barcode Lookup"`). Fixed by Martina on branch `fix-streamlit-segmented-control`. All three input modes verified working.
* **External Smoke Test (Pending — 29 Nov):** Share only the repository link and live URL with another team (no verbal instructions) and log every point where they get stuck.
