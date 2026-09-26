"""Check 1: Object / Product Identification.

Validates that visual evidence is clear and identifiable, inspecting for visual quality,
lighting anomalies, blur, occlusions, and unresolved visual ambiguities.
"""

from typing import Any, Dict, List
from pack_manager.checks.base import BaseCheck
from pack_manager.models.evidence import CheckVerdict
from pack_manager.models.inputs import Order, CatalogItem, PackPhoto
from pack_manager.models.detection import DetectedItem, Discrepancy


class ObjectIdentificationCheck(BaseCheck):
    check_key = "object_identification"
    model_version = "vision-ident-v1.0"

    def evaluate(
        self,
        order: Order,
        catalog: Dict[str, CatalogItem],
        photos: List[PackPhoto],
        detected_items: List[DetectedItem],
        discrepancies: List[Discrepancy],
        context: Dict[str, Any],
    ) -> tuple[CheckVerdict, float, str]:
        # 1. Inspect photo capture quality and lighting conditions
        for p in photos:
            if p.lighting_condition in ["blur", "severe_glare", "dark", "occluded"]:
                return (
                    CheckVerdict.UNCERTAIN,
                    0.40,
                    f"Photo capture '{p.photo_id}' has degraded quality ({p.lighting_condition}). Visual evidence is ambiguous."
                )

        # 2. Check if no items at all were detected
        if not detected_items:
            expected_total = sum(li.expected_quantity for li in order.line_items)
            if expected_total > 0:
                return (
                    CheckVerdict.FAIL,
                    0.95,
                    f"Empty parcel detected. 0 items visually identified, expected {expected_total} items."
                )

        # 3. Check for visually ambiguous detections
        ambiguous_items = [d for d in detected_items if d.is_ambiguous or d.confidence < 0.65]
        if ambiguous_items:
            reasons = [
                d.ambiguity_reason or f"Low visual confidence ({d.confidence:.2f}) for '{d.detected_label}'"
                for d in ambiguous_items
            ]
            return (
                CheckVerdict.UNCERTAIN,
                min(d.confidence for d in ambiguous_items),
                f"Visual ambiguity detected in {len(ambiguous_items)} item(s): {'; '.join(reasons)}."
            )

        # 4. Check whether items match known catalog definitions or unrecognizable artifacts
        unknown_items = [d for d in detected_items if d.matched_sku is None and not d.is_ambiguous]
        avg_conf = sum(d.confidence for d in detected_items) / len(detected_items)

        if unknown_items:
            # Unidentified physical items in parcel
            labels = [d.detected_label for d in unknown_items]
            return (
                CheckVerdict.FAIL,
                avg_conf,
                f"Visually identified {len(detected_items)} object(s), but {len(unknown_items)} item(s) do not match catalog items: {', '.join(labels)}."
            )

        labels_summary = ", ".join(f"{d.detected_label} (SKU: {d.matched_sku})" for d in detected_items)
        return (
            CheckVerdict.PASS,
            round(avg_conf, 4),
            f"Successfully identified {len(detected_items)} object(s) with high visual clarity: {labels_summary}."
        )
