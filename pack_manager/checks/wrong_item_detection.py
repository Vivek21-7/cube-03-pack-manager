"""Check 4: Wrong Item Detection.

Identifies substituted, incorrect, or mismatched variants (e.g., Blue Cap expected vs. Red Cap packed,
wrong size, or adjacent SKU mix-up).
"""

from typing import Any, Dict, List
from pack_manager.checks.base import BaseCheck
from pack_manager.models.evidence import CheckVerdict
from pack_manager.models.inputs import Order, CatalogItem, PackPhoto
from pack_manager.models.detection import DetectedItem, Discrepancy, DiscrepancyType


class WrongItemDetectionCheck(BaseCheck):
    check_key = "wrong_item_detection"
    model_version = "wrong-item-guard-v1.0"

    def evaluate(
        self,
        order: Order,
        catalog: Dict[str, CatalogItem],
        photos: List[PackPhoto],
        detected_items: List[DetectedItem],
        discrepancies: List[Discrepancy],
        context: Dict[str, Any],
    ) -> tuple[CheckVerdict, float, str]:
        expected_skus = {li.sku for li in order.line_items}
        wrong_items: List[str] = []

        for d in detected_items:
            # If item is ambiguous, flag as UNCERTAIN
            if d.is_ambiguous:
                return (
                    CheckVerdict.UNCERTAIN,
                    0.50,
                    f"Visual ambiguity on '{d.detected_label}' prevents confirming if it is a wrong item or correct item."
                )

            # If matched SKU is known and not in expected SKUs
            if d.matched_sku and d.matched_sku not in expected_skus:
                matched_name = catalog.get(d.matched_sku).product_name if d.matched_sku in catalog else d.detected_label
                wrong_items.append(f"Found '{matched_name}' (SKU: {d.matched_sku})")

            # If item does not match any catalog SKU at all
            elif not d.matched_sku:
                wrong_items.append(f"Unrecognized item '{d.detected_label}'")

        # Also inspect explicit WRONG_ITEM discrepancies
        wrong_discrepancies = [d for d in discrepancies if d.discrepancy_type == DiscrepancyType.WRONG_ITEM]
        for wd in wrong_discrepancies:
            if wd.detail not in wrong_items:
                wrong_items.append(wd.detail)

        if wrong_items:
            return (
                CheckVerdict.FAIL,
                0.96,
                f"Wrong/Substituted item(s) detected in parcel: {'; '.join(wrong_items)}."
            )

        return (
            CheckVerdict.PASS,
            0.98,
            "No wrong, substituted, or incorrect variants detected. All items match expected order specifications."
        )
