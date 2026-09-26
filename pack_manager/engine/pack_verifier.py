"""Pack Verifier Orchestrator.

Main entrypoint for outbound pack verification, executing the complete pipeline:
Input Validation -> Vision Extraction -> 7 Discrete Checks -> Quantity Comparison Table
-> Evidence Record Synthesis -> Cryptographic Hashing.
"""

import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from pack_manager.models.inputs import Order, CatalogItem, PackPhoto
from pack_manager.models.detection import DetectedItem, Discrepancy, DiscrepancyType, QuantityRow
from pack_manager.models.evidence import (
    CheckRecord,
    CheckVerdict,
    DecisionEnum,
    EvidenceRecord,
    OutcomeRecord,
    OverrideRecord,
)
from pack_manager.checks import (
    ObjectIdentificationCheck,
    QuantityCountingCheck,
    OrderMatchingCheck,
    WrongItemDetectionCheck,
    MissingItemDetectionCheck,
    ExtraItemDetectionCheck,
    DecisionSynthesisCheck,
)
from pack_manager.engine.vision_extractor import VisionExtractor
from pack_manager.engine.hasher import compute_evidence_hash


class PackVerificationResult(BaseModel):
    """Complete verification payload returned by the Pack Manager agent."""
    evidence_record: EvidenceRecord
    quantity_table: List[QuantityRow]
    discrepancies: List[Discrepancy]
    detected_items: List[DetectedItem]
    decision: DecisionEnum
    summary: str


class PackVerifier:
    """Outbound pack verification agent."""

    def __init__(self, vision_extractor: Optional[VisionExtractor] = None):
        self.vision = vision_extractor or VisionExtractor()
        
        # Instantiate the 7 discrete check modules
        self.check_ident = ObjectIdentificationCheck()
        self.check_qty = QuantityCountingCheck()
        self.check_match = OrderMatchingCheck()
        self.check_wrong = WrongItemDetectionCheck()
        self.check_missing = MissingItemDetectionCheck()
        self.check_extra = ExtraItemDetectionCheck()
        self.check_synthesis = DecisionSynthesisCheck()

    def verify(
        self,
        order: Order,
        catalog: Dict[str, CatalogItem],
        photos: List[PackPhoto],
        operator_label: str = "pack-station-01",
        organization_id: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> PackVerificationResult:
        """Executes full verification workflow for an outbound package."""
        org_id = organization_id or order.organization_id
        cli_id = client_id or order.client_id
        record_id = str(uuid.uuid4())

        # Step 1: Extract visual objects from photos
        detected_items = self.vision.extract(order=order, catalog=catalog, photos=photos)

        # Step 2: Compute Quantity Table and Discrepancies
        quantity_table, discrepancies = self._compute_quantity_table_and_discrepancies(
            order=order, catalog=catalog, detected_items=detected_items
        )

        # Step 3: Run Discrete Verification Checks 1 through 6
        check_records: List[CheckRecord] = []
        ctx = {"discrepancies": discrepancies}

        check_records.append(
            self.check_ident.run(order, catalog, photos, detected_items, discrepancies, ctx)
        )
        check_records.append(
            self.check_qty.run(order, catalog, photos, detected_items, discrepancies, ctx)
        )
        check_records.append(
            self.check_match.run(order, catalog, photos, detected_items, discrepancies, ctx)
        )
        check_records.append(
            self.check_wrong.run(order, catalog, photos, detected_items, discrepancies, ctx)
        )
        check_records.append(
            self.check_missing.run(order, catalog, photos, detected_items, discrepancies, ctx)
        )
        check_records.append(
            self.check_extra.run(order, catalog, photos, detected_items, discrepancies, ctx)
        )

        # Step 4: Run Decision Synthesis (Check 7)
        synth_ctx = {"prior_checks": check_records}
        decision_record = self.check_synthesis.run(
            order, catalog, photos, detected_items, discrepancies, synth_ctx
        )
        check_records.append(decision_record)

        # Synthesize final operational outcome
        decision, _, _, summary_reason = self.check_synthesis.evaluate_prior_checks(check_records)

        outcome = OutcomeRecord(
            decision=decision,
            decided_by="pack-manager",
            decided_at=datetime.utcnow(),
        )

        # Step 5: Format images metadata
        images_meta = []
        for p in photos:
            images_meta.append({
                "photo_id": p.photo_id,
                "image_uri": p.image_uri,
                "camera_angle": p.camera_angle,
                "lighting_condition": p.lighting_condition,
                "captured_at": p.captured_at.isoformat(),
            })

        # Step 6: Assemble EvidenceRecord payload and compute cryptographic hash
        evidence_dict = {
            "record_id": record_id,
            "schema_version": "1.0.0",
            "organization_id": org_id,
            "client_id": cli_id,
            "agent": "pack-manager",
            "subject": {
                "order_id": order.order_id,
                "package_id": order.package_id,
            },
            "captured_at": datetime.utcnow().isoformat(),
            "operator_label": operator_label,
            "images": images_meta,
            "checks": [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in check_records],
            "outcome": outcome.model_dump() if hasattr(outcome, "model_dump") else outcome.dict(),
            "overrides": [],
            "status": "PROCESSED" if decision == DecisionEnum.SEAL else "FLAGGED_FOR_REVIEW",
        }

        content_hash = compute_evidence_hash(evidence_dict)
        evidence_dict["content_hash"] = content_hash

        evidence_record = EvidenceRecord(**evidence_dict)

        return PackVerificationResult(
            evidence_record=evidence_record,
            quantity_table=quantity_table,
            discrepancies=discrepancies,
            detected_items=detected_items,
            decision=decision,
            summary=summary_reason,
        )

    def _compute_quantity_table_and_discrepancies(
        self,
        order: Order,
        catalog: Dict[str, CatalogItem],
        detected_items: List[DetectedItem],
    ) -> tuple[List[QuantityRow], List[Discrepancy]]:
        """Builds expected vs observed table and explicit discrepancies."""
        detected_counts: Counter = Counter()
        for d in detected_items:
            if d.matched_sku:
                detected_counts[d.matched_sku] += 1
            elif d.is_ambiguous:
                detected_counts["AMBIGUOUS"] += 1
            else:
                detected_counts["UNKNOWN"] += 1

        quantity_table: List[QuantityRow] = []
        discrepancies: List[Discrepancy] = []

        expected_skus = {line.sku for line in order.line_items}

        # 1. Process expected order line items
        for line in order.line_items:
            obs_qty = detected_counts.get(line.sku, 0)
            status = "MATCH"
            conf = 0.98

            if obs_qty == line.expected_quantity:
                status = "MATCH"
            elif obs_qty < line.expected_quantity:
                status = "SHORTAGE"
                discrepancies.append(
                    Discrepancy(
                        discrepancy_type=DiscrepancyType.MISSING,
                        sku=line.sku,
                        expected_quantity=line.expected_quantity,
                        observed_quantity=obs_qty,
                        detail=f"Missing {line.expected_quantity - obs_qty} unit(s) of '{line.product_name}'",
                        confidence=0.95,
                    )
                )
            else:
                status = "SURPLUS"
                discrepancies.append(
                    Discrepancy(
                        discrepancy_type=DiscrepancyType.EXTRA_ITEM,
                        sku=line.sku,
                        expected_quantity=line.expected_quantity,
                        observed_quantity=obs_qty,
                        detail=f"Surplus {obs_qty - line.expected_quantity} unit(s) of '{line.product_name}'",
                        confidence=0.95,
                    )
                )

            quantity_table.append(
                QuantityRow(
                    sku=line.sku,
                    product_name=line.product_name,
                    expected_qty=line.expected_quantity,
                    observed_qty=obs_qty,
                    status=status,
                    confidence=conf,
                )
            )

        # 2. Process unexpected detected items
        for d in detected_items:
            if d.matched_sku and d.matched_sku not in expected_skus:
                prod_name = catalog[d.matched_sku].product_name if d.matched_sku in catalog else d.detected_label
                if not any(row.sku == d.matched_sku for row in quantity_table):
                    quantity_table.append(
                        QuantityRow(
                            sku=d.matched_sku,
                            product_name=f"[WRONG / UNORDERED] {prod_name}",
                            expected_qty=0,
                            observed_qty=detected_counts[d.matched_sku],
                            status="WRONG_ITEM",
                            confidence=0.96,
                        )
                    )
                    discrepancies.append(
                        Discrepancy(
                            discrepancy_type=DiscrepancyType.WRONG_ITEM,
                            sku=d.matched_sku,
                            detected_label=d.detected_label,
                            expected_quantity=0,
                            observed_quantity=detected_counts[d.matched_sku],
                            detail=f"Wrong/Unordered item '{prod_name}' (SKU: {d.matched_sku}) found in parcel",
                            confidence=0.96,
                        )
                    )

        return quantity_table, discrepancies
