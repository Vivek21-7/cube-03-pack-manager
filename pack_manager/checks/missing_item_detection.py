"""Check 5: Missing Item Detection.

Identifies line items requested in customer order that have zero or fewer than expected items
visually identified in the parcel photograph.
"""

from collections import Counter
from typing import Any, Dict, List
from pack_manager.checks.base import BaseCheck
from pack_manager.models.evidence import CheckVerdict
from pack_manager.models.inputs import Order, CatalogItem, PackPhoto
from pack_manager.models.detection import DetectedItem, Discrepancy


class MissingItemDetectionCheck(BaseCheck):
    check_key = "missing_item_detection"
    model_version = "missing-item-guard-v1.0"

    def evaluate(
        self,
        order: Order,
        catalog: Dict[str, CatalogItem],
        photos: List[PackPhoto],
        detected_items: List[DetectedItem],
        discrepancies: List[Discrepancy],
        context: Dict[str, Any],
    ) -> tuple[CheckVerdict, float, str]:
        # Check if lighting/quality prevents verifying missing items
        for p in photos:
            if p.lighting_condition in ["blur", "occluded", "dark"]:
                return (
                    CheckVerdict.UNCERTAIN,
                    0.45,
                    f"Photograph '{p.photo_id}' has obstruction/lighting issues ({p.lighting_condition}). Cannot verify absence/presence of items."
                )

        detected_counts: Counter = Counter()
        for d in detected_items:
            if d.matched_sku:
                detected_counts[d.matched_sku] += 1

        missing_items = []
        for line in order.line_items:
            observed_qty = detected_counts.get(line.sku, 0)
            if observed_qty < line.expected_quantity:
                shortage = line.expected_quantity - observed_qty
                missing_items.append(f"{line.product_name} (SKU: {line.sku}, Short: {shortage})")

        if missing_items:
            return (
                CheckVerdict.FAIL,
                0.97,
                f"Missing item(s) detected. The following required line items are absent or under-packed: {'; '.join(missing_items)}."
            )

        return (
            CheckVerdict.PASS,
            0.99,
            "All ordered line items are confirmed present in the parcel with complete expected quantities."
        )
