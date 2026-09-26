"""Evaluation Metrics and Statistical Analysis.

Calculates:
- Inter-annotator agreement (Cohen's Kappa) between Human Annotators
- Binary Classification & Error Metrics (TP, TN, FP, FN, Precision, Recall, F1, Specificity)
- Per-Check Performance and Failure Mode taxonomy
- Latency and Uncertainty Rate analytics
"""

import math
from typing import Any, Dict, List


def calculate_cohens_kappa(rater1_labels: List[str], rater2_labels: List[str]) -> float:
    """Computes Cohen's Kappa coefficient for inter-rater reliability."""
    if len(rater1_labels) != len(rater2_labels) or len(rater1_labels) == 0:
        return 0.0

    n = len(rater1_labels)
    categories = sorted(list(set(rater1_labels) | set(rater2_labels)))
    
    # Confusion matrix between raters
    matrix = {c1: {c2: 0 for c2 in categories} for c1 in categories}
    for r1, r2 in zip(rater1_labels, rater2_labels):
        matrix[r1][r2] += 1

    # Observed agreement (Po)
    po = sum(matrix[c][c] for c in categories) / n

    # Expected agreement by chance (Pe)
    pe = 0.0
    for c in categories:
        row_total = sum(matrix[c][c2] for c2 in categories)
        col_total = sum(matrix[c1][c] for c1 in categories)
        pe += (row_total / n) * (col_total / n)

    if pe >= 1.0:
        return 1.0

    kappa = (po - pe) / (1.0 - pe)
    return round(kappa, 4)


def compute_eval_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes full evaluation metrics across all evaluated test units."""
    total_units = len(results)
    if total_units == 0:
        return {}

    # 1. Inter-human agreement
    h1_decisions = [r["human_1"]["decision"] for r in results]
    h2_decisions = [r["human_2"]["decision"] for r in results]
    inter_human_kappa = calculate_cohens_kappa(h1_decisions, h2_decisions)

    # 2. Agent vs Ground Truth Metrics
    # Positive class = STOP_AND_FIX (Defect detection)
    # Negative class = SEAL (Clean pass)
    tp = 0  # Ground truth STOP_AND_FIX, Agent STOP_AND_FIX
    tn = 0  # Ground truth SEAL, Agent SEAL
    fp = 0  # Ground truth SEAL, Agent STOP_AND_FIX (False Alarm)
    fn = 0  # Ground truth STOP_AND_FIX, Agent SEAL (Dangerous Miss)

    uncertain_count = 0
    latencies = []

    per_scenario = {}
    check_pass_fail_counts = {}
    failure_modes = []

    for r in results:
        gt = r["ground_truth_decision"]
        agent_dec = r["agent_decision"]
        latencies.append(r["latency_ms"])

        if r["is_uncertain"]:
            uncertain_count += 1

        # Track per-scenario
        sc_type = r["scenario_type"]
        if sc_type not in per_scenario:
            per_scenario[sc_type] = {"total": 0, "correct": 0, "uncertain": 0}
        per_scenario[sc_type]["total"] += 1
        if agent_dec == gt:
            per_scenario[sc_type]["correct"] += 1
        if r["is_uncertain"]:
            per_scenario[sc_type]["uncertain"] += 1

        # Confusion Matrix
        if gt == "STOP_AND_FIX" and agent_dec == "STOP_AND_FIX":
            tp += 1
        elif gt == "SEAL" and agent_dec == "SEAL":
            tn += 1
        elif gt == "SEAL" and agent_dec == "STOP_AND_FIX":
            fp += 1
            failure_modes.append({
                "unit_id": r["unit_id"],
                "type": "FALSE_ALARM",
                "detail": f"Agent flagged STOP_AND_FIX on clean pack: {r['summary']}",
            })
        elif gt == "STOP_AND_FIX" and agent_dec == "SEAL":
            fn += 1
            failure_modes.append({
                "unit_id": r["unit_id"],
                "type": "CRITICAL_MISS",
                "detail": f"Agent SEALed a defective pack: Expected {r['expected_discrepancy_type']}",
            })

        # Track check breakdown
        for chk in r["checks"]:
            k = chk["check_key"]
            if k not in check_pass_fail_counts:
                check_pass_fail_counts[k] = {"PASS": 0, "FAIL": 0, "UNCERTAIN": 0, "latencies": []}
            check_pass_fail_counts[k][chk["verdict"]] += 1
            check_pass_fail_counts[k]["latencies"].append(chk["latency_ms"])

    accuracy = (tp + tn) / total_units if total_units > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    latencies_sorted = sorted(latencies)
    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0
    p50_latency = latencies_sorted[int(len(latencies_sorted) * 0.50)] if latencies else 0.0
    p95_latency = latencies_sorted[int(len(latencies_sorted) * 0.95)] if latencies else 0.0

    return {
        "total_units_evaluated": total_units,
        "inter_human_kappa": inter_human_kappa,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "specificity": round(specificity, 4),
        "confusion_matrix": {
            "true_positives": tp,
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
        },
        "uncertainty_count": uncertain_count,
        "uncertainty_rate": round(uncertain_count / total_units, 4),
        "latency_stats_ms": {
            "mean": round(mean_latency, 2),
            "p50": round(p50_latency, 2),
            "p95": round(p95_latency, 2),
        },
        "per_scenario_accuracy": per_scenario,
        "per_check_counts": check_pass_fail_counts,
        "failure_modes": failure_modes,
    }
