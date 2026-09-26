"""Check 3: Order-to-Image Matching.

Maps detected physical items to expected order lines to ensure complete bijective alignment.
"""

from collections import Counter
from typing import Any, Dict, List
from pack_manager.checks.base import BaseCheck
from pack_manager.models.evidence import CheckVerdict
from pack_manager.models.inputs import Order, CatalogItem, PackPhoto
from pack_manager.models.detection import DetectedItem, Discrepancy


class OrderMatchingCheck(BaseCheck):
    check_key = "order_matching"
    model_version = "matcher-engine-v1.0"

    def evaluate(
        self,
        order: Order,
        catalog: Dict[str, CatalogItem],
        photos: List[PackPhoto],
        detected_items: List[DetectedItem],
        discrepancies: List[Discrepancy],
        context: Dict[str, Any],
    ) -> tuple[CheckVerdict, float, str]:
        # Check if any detection is uncertain/ambiguous
        ambiguous_items = [d for d in detected_items if d.is_ambiguous]
        if ambiguous_items:
            return (
                CheckVerdict.UNCERTAIN,
                0.50,
                f"Cannot confidently match order lines because {len(ambiguous_items)} item(s) have ambiguous visual signatures."
            )

        expected_pool = []
        for line in order.line_items:
            for _ in range(line.expected_quantity):
                expected_pool.append(line.sku)

        detected_pool = [d.matched_sku for d in detected_items if d.matched_sku]
        unmatched_detections = [d for d in detected_items if not d.matched_sku]

        if unmatched_detections:
            return (
                CheckVerdict.FAIL,
                0.90,
                f"Detected {len(unmatched_detections)} item(s) that could not be mapped to any valid SKU in the product catalogue."
            )

        if sorted(expected_pool) != sorted(detected_pool):
            exp_counter = Counter(expected_pool)
            det_counter = Counter(detected_pool)
            return (
                CheckVerdict.FAIL,
                0.95,
                f"Order line mapping failure. Expected SKU set: {dict(exp_counter)}, Observed SKU set: {dict(det_counter)}."
            )

        avg_confidence = sum(d.confidence for d in detected_items) / len(detected_items) if detected_items else 1.0
        return (
            CheckVerdict.PASS,
            round(avg_confidence, 4),
            f"100% bijective mapping confirmed between all {len(order.line_items)} order line items and {len(detected_items)} observed package items."
        )
