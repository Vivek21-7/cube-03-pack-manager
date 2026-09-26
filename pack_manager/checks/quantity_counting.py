"""Check 2: Quantity Counting.

Validates that the exact number of physical items in the package matches the expected total
and per-SKU line quantities, checking for shortages, over-counts, and stacking occlusions.
"""

from collections import Counter
from typing import Any, Dict, List
from pack_manager.checks.base import BaseCheck
from pack_manager.models.evidence import CheckVerdict
from pack_manager.models.inputs import Order, CatalogItem, PackPhoto
from pack_manager.models.detection import DetectedItem, Discrepancy


class QuantityCountingCheck(BaseCheck):
    check_key = "quantity_counting"
    model_version = "count-engine-v1.0"

    def evaluate(
        self,
        order: Order,
        catalog: Dict[str, CatalogItem],
        photos: List[PackPhoto],
        detected_items: List[DetectedItem],
        discrepancies: List[Discrepancy],
        context: Dict[str, Any],
    ) -> tuple[CheckVerdict, float, str]:
        expected_total = sum(item.expected_quantity for item in order.line_items)
        observed_total = len(detected_items)

        # Check for photo lighting degradation
        for p in photos:
            if p.lighting_condition in ["blur", "severe_glare", "dark", "occluded"]:
                return (
                    CheckVerdict.UNCERTAIN,
                    0.40,
                    f"Photo quality ({p.lighting_condition}) prevents reliable item counting."
                )

        # Check for ambiguity in counting due to overlaps or occlusions
        for item in detected_items:
            if item.is_ambiguous:
                return (
                    CheckVerdict.UNCERTAIN,
                    0.45,
                    f"Ambiguous item '{item.detected_label}' ({item.ambiguity_reason or 'low clarity'}) prevents reliable quantity count."
                )

        # Count per-SKU detected
        sku_counts: Counter = Counter()
        for item in detected_items:
            if item.matched_sku:
                sku_counts[item.matched_sku] += 1
            else:
                sku_counts["UNKNOWN"] += 1

        expected_sku_counts = {item.sku: item.expected_quantity for item in order.line_items}

        mismatches = []
        for sku, exp_qty in expected_sku_counts.items():
            obs_qty = sku_counts.get(sku, 0)
            if obs_qty != exp_qty:
                mismatches.append(f"{sku} (Expected: {exp_qty}, Observed: {obs_qty})")

        if sku_counts.get("UNKNOWN", 0) > 0:
            mismatches.append(f"UNKNOWN_SKU (Expected: 0, Observed: {sku_counts['UNKNOWN']})")

        # Also check for unexpected SKUs with non-zero count
        for sku, obs_qty in sku_counts.items():
            if sku != "UNKNOWN" and sku not in expected_sku_counts:
                mismatches.append(f"{sku} (Expected: 0, Observed: {obs_qty})")

        if mismatches:
            return (
                CheckVerdict.FAIL,
                0.95,
                f"Quantity count mismatch. Total expected: {expected_total}, Observed: {observed_total}. Discrepancies: {'; '.join(mismatches)}."
            )

        return (
            CheckVerdict.PASS,
            0.98,
            f"Quantity count perfectly verified. All {observed_total} item(s) match expected order counts across all line items."
        )
