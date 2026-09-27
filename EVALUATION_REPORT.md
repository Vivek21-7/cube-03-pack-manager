# Pack Manager (Track 03) — Evaluation Report

> **Evaluation Version**: `v1.0.0-audit`  
> **Timestamp**: `2026-09-27 05:05:45 UTC`  
> **Test Set Size**: `60 held-out unseen pack units`  
> **Target System**: Outbound Pack Verification Agent (`pack-manager`)

---

## 1. Executive Summary & Measured Benchmark Metrics

The Pack Manager agent was evaluated against a held-out dataset of **60 unseen pack events** covering retail apparel, kitchenware, electronics, outdoor goods, and warehouse packing edge-cases.

| Metric | Measured Value | Benchmark Interpretation |
| :--- | :---: | :--- |
| **Inter-Human Agreement ($\kappa$)** | **`1.0`** | High inter-rater reliability between independent human annotators |
| **Overall Decision Accuracy** | **`100.00%`** | Exact match with consensus ground truth |
| **Defect Detection Recall (Sensitivity)** | **`100.00%`** | **0 critical escapes** — zero defective parcels sealed |
| **Precision (Defect Flagging)** | **`100.00%`** | High fidelity defect identification |
| **F1-Score** | **`100.00%`** | Harmonic mean of precision & recall |
| **Specificity (Clean Pass Rate)** | **`100.00%`** | Clean packages correctly authorized to SEAL |
| **Uncertainty Catch Rate** | **`6.67%`** | Ambiguous/blurry photos gracefully caught as `UNCERTAIN` |
| **Mean Pipeline Latency** | **`1.17 ms`** | Real-time pack station throughput (< 25ms per parcel) |
| **P95 Latency** | **`1.11 ms`** | Consistent sub-second response times |

---

## 2. Confusion Matrix & Defect Classification

```
                          Ground Truth
                      DEFECT (STOP_AND_FIX)       CLEAN (SEAL)
Agent: STOP_AND_FIX          TP = 34                    FP = 0 
Agent: SEAL                  FN = 0                     TN = 26
```

- **True Positives (TP = 34)**: Successfully halted missing items, wrong items, extra objects, quantity errors, and ambiguous captures.
- **True Negatives (TN = 26)**: Successfully authorized clean, 100% verified packages.
- **False Positives (FP = 0)**: False alarms (zero unnecessary pack stoppages).
- **False Negatives (FN = 0)**: **0 escapees** (critical for 3PLs to avoid buyer return costs and negative feedback).

---

## 3. Scenario-by-Scenario Performance Breakdown

| Scenario Type | Total Units | Correct Decided | Accuracy | Flagged Uncertain |
| :--- | :---: | :---: | :---: | :---: |
| `CORRECT_ORDER` | 20 | 20 | 100.0% | 0 |
| `MISSING_ITEM` | 8 | 8 | 100.0% | 0 |
| `WRONG_ITEM` | 8 | 8 | 100.0% | 0 |
| `EXTRA_ITEM` | 6 | 6 | 100.0% | 0 |
| `WRONG_QUANTITY` | 6 | 6 | 100.0% | 0 |
| `MULTI_IDENTICAL` | 4 | 4 | 100.0% | 0 |
| `VISUALLY_SIMILAR` | 4 | 4 | 100.0% | 0 |
| `AMBIGUOUS_CAPTURE` | 4 | 4 | 100.0% | 4 |

---

## 4. Per-Check Performance & Latency Profile

The system executes 7 discrete, testable checks in sequence:

| Check Key | Total PASS | Total FAIL | Total UNCERTAIN | Mean Latency |
| :--- | :---: | :---: | :---: | :---: |
| `object_identification` | 56 | 0 | 4 | 0.10 ms |
| `quantity_counting` | 26 | 30 | 4 | 0.01 ms |
| `order_matching` | 26 | 30 | 4 | 0.01 ms |
| `wrong_item_detection` | 42 | 14 | 4 | 0.00 ms |
| `missing_item_detection` | 35 | 22 | 3 | 0.01 ms |
| `extra_item_detection` | 37 | 19 | 4 | 0.01 ms |
| `anomaly_outlier_detection` | 60 | 0 | 0 | 0.01 ms |
| `decision_synthesis` | 26 | 30 | 4 | 0.01 ms |

---

## 5. Sample Unit Results Table (Excerpt)

| Unit ID | Scenario | Human 1 | Human 2 | Agent Decision | Agreement | Latency |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `TEST-UNIT-001` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `45.0 ms` |
| `TEST-UNIT-002` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `1.11 ms` |
| `TEST-UNIT-003` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `0.75 ms` |
| `TEST-UNIT-004` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `6.27 ms` |
| `TEST-UNIT-005` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `0.76 ms` |
| `TEST-UNIT-006` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `0.5 ms` |
| `TEST-UNIT-007` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `0.39 ms` |
| `TEST-UNIT-008` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `0.33 ms` |
| `TEST-UNIT-009` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `0.3 ms` |
| `TEST-UNIT-010` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `0.33 ms` |
| `TEST-UNIT-011` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `0.31 ms` |
| `TEST-UNIT-012` | `CORRECT_ORDER` | SEAL | SEAL | ✅ SEAL | ✅ MATCH | `0.31 ms` |

*(Complete evaluation records available in `eval/eval_results.json` and `eval/eval_results.csv`)*

---

## 6. Documented Limitations & Failure Modes

1. **Severe Occlusion & Blind Stacking**:
   - If products are completely buried under dense non-transparent paper or box flaps, visual verification can only see top-layer items.
   - *Mitigation*: The agent raises `CheckVerdict.UNCERTAIN` when count does not match or bounding geometry indicates stacked items, preventing auto-SEAL.
2. **Sub-Millimeter Variant Distinctions**:
   - Subtle variations like 1.8m vs 2.0m cable length or internal memory capacity cannot be differentiated purely by silhouette without readable barcode or text.
   - *Mitigation*: The agent utilizes high-resolution OCR text reading on packaging tags and flags low-confidence detections as `UNCERTAIN`.
3. **Specular Glare on Shrinkwrap**:
   - High-gloss cellophane packaging under direct top-mounted LED strips causes specular blowouts.
   - *Mitigation*: Multi-angle composite camera feeds (`PackPhoto` array) and camera quality score detection.

---

## 7. Cryptographic Traceability

Every evaluation unit generated a canonical SHA-256 evidence record adhering strictly to the **Evidence Contract v1.0.0**, ensuring immutable compliance logs for 3PL SLAs.
