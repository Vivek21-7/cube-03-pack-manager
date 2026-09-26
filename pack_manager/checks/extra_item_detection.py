"""Check 6: Extra Item Detection.

Identifies unmanifested, surplus, or foreign objects placed inside the box that do not belong
to the customer's purchase order.
"""

from collections import Counter
from typing import Any, Dict, List
from pack_manager.checks.base import BaseCheck
from pack_manager.models.evidence import CheckVerdict
from pack_manager.models.inputs import Order, CatalogItem, PackPhoto
from pack_manager.models.detection import DetectedItem, Discrepancy


class ExtraItemDetectionCheck(BaseCheck):
    check_key = "extra_item_detection"
    model_version = "extra-item-guard-v1.0"

    def evaluate(
        self,
        order: Order,
        catalog: Dict[str, CatalogItem],
        photos: List[PackPhoto],
        detected_items: List[DetectedItem],
        discrepancies: List[Discrepancy],
        context: Dict[str, Any],
    ) -> tuple[CheckVerdict, float, str]:
        expected_counts = {item.sku: item.expected_quantity for item in order.line_items}
        
        detected_counts: Counter = Counter()
        extra_items: List[str] = []

        for d in detected_items:
            if d.is_ambiguous:
                return (
                    CheckVerdict.UNCERTAIN,
                    0.50,
                    f"Visual ambiguity on '{d.detected_label}' prevents determining whether it is an extra item."
                )

            if d.matched_sku:
                detected_counts[d.matched_sku] += 1
                if d.matched_sku not in expected_counts:
                    product_name = catalog[d.matched_sku].product_name if d.matched_sku in catalog else d.detected_label
                    extra_items.append(f"Unordered SKU '{product_name}' ({d.matched_sku})")
                elif detected_counts[d.matched_sku] > expected_counts[d.matched_sku]:
                    product_name = catalog[d.matched_sku].product_name if d.matched_sku in catalog else d.detected_label
                    extra_items.append(f"Surplus count for '{product_name}' (count {detected_counts[d.matched_sku]} > expected {expected_counts[d.matched_sku]})")
            else:
                extra_items.append(f"Foreign / Uncataloged item '{d.detected_label}'")

        if extra_items:
            return (
                CheckVerdict.FAIL,
                0.96,
                f"Extra / Unmanifested item(s) detected in package: {'; '.join(extra_items)}."
            )

        return (
            CheckVerdict.PASS,
            0.99,
            "No extra, surplus, or foreign items detected in the parcel."
        )
