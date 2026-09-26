"""End-to-End Minimal Working Example (MWE) Test.

Verifies a correct single-order pack verification workflow:
1. Ingests Order (SKU-MUG-001 x 2, SKU-NOTE-002 x 1)
2. Ingests Product Catalog with reference attributes
3. Ingests PackPhoto of open box
4. Runs PackVerifier
5. Asserts:
   - Decision is SEAL
   - All 7 checks return PASS
   - Quantity comparison table is 100% MATCH
   - Cryptographic SHA-256 hash is computed and valid
   - Strict EvidenceContract schema compliance
"""

import pytest
from pack_manager import (
    PackVerifier,
    Order,
    OrderLineItem,
    CatalogItem,
    PackPhoto,
    DecisionEnum,
    CheckVerdict,
)
from pack_manager.engine.hasher import compute_evidence_hash


def test_minimal_working_example_correct_order():
    # 1. Product Catalog
    catalog = {
        "SKU-MUG-001": CatalogItem(
            sku="SKU-MUG-001",
            product_name="Ceramic Coffee Mug - Matte Black",
            category="Kitchenware",
            attributes={"color": "matte black", "material": "ceramic", "volume": "350ml"},
            visual_identifiers=["matte black finish", "cylindrical body", "ergonomic handle"],
        ),
        "SKU-NOTE-002": CatalogItem(
            sku="SKU-NOTE-002",
            product_name="Hardcover Dot Grid Notebook - Navy",
            category="Stationery",
            attributes={"color": "navy", "size": "A5", "pages": 192},
            visual_identifiers=["navy textured cover", "elastic band closure", "ribbon bookmark"],
        ),
    }

    # 2. Customer Order
    order = Order(
        order_id="ORD-2026-9812",
        package_id="PKG-BOX-401",
        client_id="MERCHANT-APEX-01",
        organization_id="3PL-LOGISTICS-HUB",
        line_items=[
            OrderLineItem(
                line_item_id="LI-01",
                sku="SKU-MUG-001",
                product_name="Ceramic Coffee Mug - Matte Black",
                expected_quantity=2,
            ),
            OrderLineItem(
                line_item_id="LI-02",
                sku="SKU-NOTE-002",
                product_name="Hardcover Dot Grid Notebook - Navy",
                expected_quantity=1,
            ),
        ],
    )

    # 3. Pack Photo
    photo = PackPhoto(
        photo_id="PHOTO-CAM-01-9812",
        image_uri="evidence/photos/pkg_401_topdown.jpg",
        camera_angle="top_down",
        lighting_condition="standard",
    )

    # 4. Run Pack Verifier Agent
    verifier = PackVerifier()
    result = verifier.verify(
        order=order,
        catalog=catalog,
        photos=[photo],
        operator_label="station-bay-03",
    )

    # 5. Assertions
    # Decision must be SEAL
    assert result.decision == DecisionEnum.SEAL
    assert result.evidence_record.outcome.decision == DecisionEnum.SEAL
    assert result.evidence_record.agent == "pack-manager"
    assert result.evidence_record.schema_version == "1.0.0"
    assert result.evidence_record.subject["order_id"] == "ORD-2026-9812"
    assert result.evidence_record.subject["package_id"] == "PKG-BOX-401"
    assert result.evidence_record.operator_label == "station-bay-03"

    # All 7 checks must be PASS
    assert len(result.evidence_record.checks) == 7
    for check in result.evidence_record.checks:
        assert check.verdict == CheckVerdict.PASS
        assert check.confidence >= 0.70
        assert len(check.detail) > 10
        assert check.latency_ms >= 0.0

    # Quantity comparison table
    assert len(result.quantity_table) == 2
    assert result.quantity_table[0].expected_qty == 2
    assert result.quantity_table[0].observed_qty == 2
    assert result.quantity_table[0].status == "MATCH"
    assert result.quantity_table[1].expected_qty == 1
    assert result.quantity_table[1].observed_qty == 1
    assert result.quantity_table[1].status == "MATCH"

    # Discrepancies list must be empty
    assert len(result.discrepancies) == 0

    # Verify SHA-256 Content Hash is valid and tamper-evident
    computed_hash = compute_evidence_hash(result.evidence_record.dict())
    assert result.evidence_record.content_hash == computed_hash
    print("\n[MWE PASS] Minimal Working Example passed all checks with verified SHA-256 hash:", computed_hash)
