# Allergen & Additive Verification Tool

![Level](https://img.shields.io/badge/PAIBS%20Level-2%20%C2%B7%20Walking%20Skeleton%20Running-brightgreen)
![Benchmark](https://img.shields.io/badge/Run%201-100%25%20recall%20%C2%B7%200%20false%20alarms-blue)

**ESADE PAIBS · Group 10**

> We are building an AI-powered label scanner for parents with allergy-sensitive children so they can instantly detect hidden allergens and risky additives from a photo and discover safe, healthier supermarket alternatives in real time.

The tool works from a barcode, a label photo or pasted ingredient text. It checks what it finds against the child's profile and suggests compatible supermarket alternatives.

> **Notice:** Cross-reference all automated assessments against physical product packaging prior to consumption. This is a student prototype, not a medical device.

**Full technical documentation:** [REPORT.md](REPORT.md) covers the workflow, parsing methodology, Real vs. Faked audit and benchmark results.

## Quickstart

```bash
git clone https://github.com/mireiaacss/paibs-off.git && cd paibs-off
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Optional label-photo OCR on macOS: `brew install tesseract && pip install pytesseract`, plus the Spanish model (see [REPORT.md §7](REPORT.md#7-reproducing-the-results)).

## Using the tool

1. **Sidebar:** choose the *Active Profile*, the *Detection Threshold* (Maximum Caution or Standard Sensitivity) and the data sources.
2. **Product Input:** use *Barcode Lookup* (live Open Food Facts, with quick-load samples), *Label Photo* (OCR, then editable text) or *Ingredient Text*.
3. **Analyze Ingredients:** the assessment shows:
   - a status card: *Restriction conflict detected*, *Potential trace exposure*, *Unverified components require review*, *Insufficient ingredient data* or *No conflicts identified with active profile*
   - detected allergens, split into direct ingredients and precautionary warnings, each term mapped to its EU category
   - identified additives and unverified components
   - compatible product alternatives with Nutri-Score

## Verification

```bash
python -m unittest benchmark/benchmark_runner.py   # Run 1 acceptance tests
python benchmark/benchmark_runner.py               # printed benchmark report
python -m pytest -q                                # 27 tests incl. headless UI flows
```

| Run 1 (10 canonical cases) | Naive 30-keyword baseline | System |
|---|---|---|
| Pooled catch rate | 57% (spec) / 59% (reproduced) | **100% (22/22)** |
| False alarms | 3 | **0** |

This is an in-sample score; see [REPORT.md §5.5](REPORT.md#55-interpretation-and-caveat).

## Real vs. Faked (summary)

| Real | Stub / Faked / Not implemented |
|---|---|
| Open Food Facts barcode lookup (offline cache fallback) · bilingual allergen parser · may-contain splitting · false-friend filtering · "when in doubt, warn" guardrail · profile matching · benchmark suite · Tesseract OCR (when installed) | Additive descriptions (static 34-code dictionary) · alternatives (live OFF search with a curated catalogue fallback) · native mobile camera (browser camera / upload only) · image blur filter (not implemented) |

The full audit with rationale is in [REPORT.md §4](REPORT.md#4-real-vs-faked-component-audit).

## Project structure

```text
app.py                  Streamlit front end
config.py               Allergen lexicon, false friends, guardrail rules, additives
modules/                pipeline, off_client, ocr_reader, allergen_parser,
                        profile_matcher, additives_service, alternatives_service
benchmark/              benchmark_runner.py, test_cases.json
data/sample_profile.json
tests/test_pipeline.py
```
