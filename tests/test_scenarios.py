"""Comprehensive Test Suite for all 8 Mandated Operational Scenarios.

Scenarios Covered:
1. Correct Order (should SEAL)
2. Missing Item (should STOP_AND_FIX, missing_item_detection FAIL)
3. Wrong Item (e.g. Blue Cap ordered, Red Cap packed — should STOP_AND_FIX, wrong_item_detection FAIL)
4. Extra Item (Unmanifested / Foreign item in parcel — should STOP_AND_FIX, extra_item_detection FAIL)
5. Wrong Quantity (Shortage or Surplus — should STOP_AND_FIX, quantity_counting FAIL)
6. Multiple Identical Products (Robust multi-instance counting — should SEAL)
7. Visually Similar Products (Multiple subtle colorways/variants — should SEAL on match, STOP_AND_FIX on mixup)
8. Ambiguous Photographs (Degraded lighting/blur/occlusion — should trigger UNCERTAIN, STOP_AND_FIX, never forced guess)
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


@pytest.fixture
def master_catalog():
    return {
        "SKU-CAP-BLU": CatalogItem(
            sku="SKU-CAP-BLU",
            product_name="Embroidered Baseball Cap - Royal Blue",
            category="Apparel",
            attributes={"color": "royal blue", "size": "adjustable", "logo": "White Emblem"},
            visual_identifiers=["royal blue cotton", "white embroidered front logo", "curved brim"],
        ),
        "SKU-CAP-RED": CatalogItem(
            sku="SKU-CAP-RED",
            product_name="Embroidered Baseball Cap - Crimson Red",
            category="Apparel",
            attributes={"color": "crimson red", "size": "adjustable", "logo": "White Emblem"},
            visual_identifiers=["crimson red cotton", "white embroidered front logo", "curved brim"],
        ),
        "SKU-TSHIRT-BLK-M": CatalogItem(
            sku="SKU-TSHIRT-BLK-M",
            product_name="Heavyweight Cotton T-Shirt - Pitch Black / Medium",
            category="Apparel",
            attributes={"color": "pitch black", "size": "M"},
        ),
        "SKU-TSHIRT-NVY-M": CatalogItem(
            sku="SKU-TSHIRT-NVY-M",
            product_name="Heavyweight Cotton T-Shirt - Deep Navy / Medium",
            category="Apparel",
            attributes={"color": "deep navy", "size": "M"},
        ),
        "SKU-BOTTLE-SS": CatalogItem(
            sku="SKU-BOTTLE-SS",
            product_name="Insulated Stainless Steel Water Bottle - 750ml",
            category="Outdoor",
            attributes={"color": "silver", "material": "stainless steel"},
        ),
        "SKU-SOCK-WHT-3PK": CatalogItem(
            sku="SKU-SOCK-WHT-3PK",
            product_name="Cushioned Athletic Crew Socks - 3-Pack White",
            category="Apparel",
            attributes={"color": "white", "pack_count": 3},
        ),
    }


def test_scenario_1_correct_order(master_catalog):
    """Scenario 1: Correct Order -> SEAL."""
    order = Order(
        order_id="ORD-001",
        package_id="PKG-001",
        client_id="MERCHANT-01",
        organization_id="3PL-WEST",
        line_items=[
            OrderLineItem(line_item_id="1", sku="SKU-CAP-BLU", product_name="Blue Cap", expected_quantity=1),
            OrderLineItem(line_item_id="2", sku="SKU-BOTTLE-SS", product_name="Water Bottle", expected_quantity=1),
        ],
    )
    photo = PackPhoto(
        photo_id="PH-001",
        metadata={
            "simulated_detections": [
                {"detected_label": "Embroidered Baseball Cap - Royal Blue", "matched_sku": "SKU-CAP-BLU", "confidence": 0.98},
                {"detected_label": "Insulated Stainless Steel Water Bottle - 750ml", "matched_sku": "SKU-BOTTLE-SS", "confidence": 0.97},
            ]
        },
    )

    verifier = PackVerifier()
    res = verifier.verify(order, master_catalog, [photo])

    assert res.decision == DecisionEnum.SEAL
    assert all(c.verdict == CheckVerdict.PASS for c in res.evidence_record.checks)
    assert len(res.discrepancies) == 0


def test_scenario_2_missing_item(master_catalog):
    """Scenario 2: Missing Item -> STOP_AND_FIX."""
    order = Order(
        order_id="ORD-002",
        package_id="PKG-002",
        client_id="MERCHANT-01",
        organization_id="3PL-WEST",
        line_items=[
            OrderLineItem(line_item_id="1", sku="SKU-CAP-BLU", product_name="Blue Cap", expected_quantity=1),
            OrderLineItem(line_item_id="2", sku="SKU-BOTTLE-SS", product_name="Water Bottle", expected_quantity=1),
        ],
    )
    # Only the bottle is present, Cap is missing
    photo = PackPhoto(
        photo_id="PH-002",
        metadata={
            "simulated_detections": [
                {"detected_label": "Insulated Stainless Steel Water Bottle - 750ml", "matched_sku": "SKU-BOTTLE-SS", "confidence": 0.97},
            ]
        },
    )

    verifier = PackVerifier()
    res = verifier.verify(order, master_catalog, [photo])

    assert res.decision == DecisionEnum.STOP_AND_FIX
    missing_check = next(c for c in res.evidence_record.checks if c.check_key == "missing_item_detection")
    assert missing_check.verdict == CheckVerdict.FAIL
    assert "Blue Cap" in missing_check.detail


def test_scenario_3_wrong_item(master_catalog):
    """Scenario 3: Wrong Item (Expected Blue Cap, Found Red Cap) -> STOP_AND_FIX."""
    order = Order(
        order_id="ORD-003",
        package_id="PKG-003",
        client_id="MERCHANT-01",
        organization_id="3PL-WEST",
        line_items=[
            OrderLineItem(line_item_id="1", sku="SKU-CAP-BLU", product_name="Blue Cap", expected_quantity=1),
        ],
    )
    # Red Cap packed instead of Blue Cap
    photo = PackPhoto(
        photo_id="PH-003",
        metadata={
            "simulated_detections": [
                {"detected_label": "Embroidered Baseball Cap - Crimson Red", "matched_sku": "SKU-CAP-RED", "confidence": 0.96},
            ]
        },
    )

    verifier = PackVerifier()
    res = verifier.verify(order, master_catalog, [photo])

    assert res.decision == DecisionEnum.STOP_AND_FIX
    wrong_check = next(c for c in res.evidence_record.checks if c.check_key == "wrong_item_detection")
    assert wrong_check.verdict == CheckVerdict.FAIL
    assert "SKU-CAP-RED" in wrong_check.detail


def test_scenario_4_extra_item(master_catalog):
    """Scenario 4: Extra Item in Box -> STOP_AND_FIX."""
    order = Order(
        order_id="ORD-004",
        package_id="PKG-004",
        client_id="MERCHANT-01",
        organization_id="3PL-WEST",
        line_items=[
            OrderLineItem(line_item_id="1", sku="SKU-BOTTLE-SS", product_name="Water Bottle", expected_quantity=1),
        ],
    )
    # Bottle + Unordered Socks packed
    photo = PackPhoto(
        photo_id="PH-004",
        metadata={
            "simulated_detections": [
                {"detected_label": "Insulated Stainless Steel Water Bottle - 750ml", "matched_sku": "SKU-BOTTLE-SS", "confidence": 0.97},
                {"detected_label": "Cushioned Athletic Crew Socks - 3-Pack White", "matched_sku": "SKU-SOCK-WHT-3PK", "confidence": 0.94},
            ]
        },
    )

    verifier = PackVerifier()
    res = verifier.verify(order, master_catalog, [photo])

    assert res.decision == DecisionEnum.STOP_AND_FIX
    extra_check = next(c for c in res.evidence_record.checks if c.check_key == "extra_item_detection")
    assert extra_check.verdict == CheckVerdict.FAIL
    assert "SKU-SOCK-WHT-3PK" in extra_check.detail


def test_scenario_5_wrong_quantity(master_catalog):
    """Scenario 5: Wrong Quantity (Ordered 3, Packed 2) -> STOP_AND_FIX."""
    order = Order(
        order_id="ORD-005",
        package_id="PKG-005",
        client_id="MERCHANT-01",
        organization_id="3PL-WEST",
        line_items=[
            OrderLineItem(line_item_id="1", sku="SKU-SOCK-WHT-3PK", product_name="Crew Socks 3PK", expected_quantity=3),
        ],
    )
    # Only 2 packed
    photo = PackPhoto(
        photo_id="PH-005",
        metadata={
            "simulated_detections": [
                {"detected_label": "Cushioned Athletic Crew Socks - 3-Pack White", "matched_sku": "SKU-SOCK-WHT-3PK", "confidence": 0.95},
                {"detected_label": "Cushioned Athletic Crew Socks - 3-Pack White", "matched_sku": "SKU-SOCK-WHT-3PK", "confidence": 0.95},
            ]
        },
    )

    verifier = PackVerifier()
    res = verifier.verify(order, master_catalog, [photo])

    assert res.decision == DecisionEnum.STOP_AND_FIX
    qty_check = next(c for c in res.evidence_record.checks if c.check_key == "quantity_counting")
    assert qty_check.verdict == CheckVerdict.FAIL
    assert "Expected: 3, Observed: 2" in qty_check.detail


def test_scenario_6_multiple_identical_products(master_catalog):
    """Scenario 6: Multiple Identical Products (5 of same item) -> SEAL."""
    order = Order(
        order_id="ORD-006",
        package_id="PKG-006",
        client_id="MERCHANT-01",
        organization_id="3PL-WEST",
        line_items=[
            OrderLineItem(line_item_id="1", sku="SKU-BOTTLE-SS", product_name="Water Bottle", expected_quantity=5),
        ],
    )
    # Exactly 5 detected
    photo = PackPhoto(
        photo_id="PH-006",
        metadata={
            "simulated_detections": [
                {"detected_label": "Insulated Stainless Steel Water Bottle - 750ml", "matched_sku": "SKU-BOTTLE-SS", "confidence": 0.96}
                for _ in range(5)
            ]
        },
    )

    verifier = PackVerifier()
    res = verifier.verify(order, master_catalog, [photo])

    assert res.decision == DecisionEnum.SEAL
    assert all(c.verdict == CheckVerdict.PASS for c in res.evidence_record.checks)
    assert res.quantity_table[0].observed_qty == 5
    assert res.quantity_table[0].status == "MATCH"


def test_scenario_7_visually_similar_products(master_catalog):
    """Scenario 7: Visually Similar Products (Black Shirt + Navy Shirt)."""
    order = Order(
        order_id="ORD-007",
        package_id="PKG-007",
        client_id="MERCHANT-01",
        organization_id="3PL-WEST",
        line_items=[
            OrderLineItem(line_item_id="1", sku="SKU-TSHIRT-BLK-M", product_name="Black T-Shirt", expected_quantity=1),
            OrderLineItem(line_item_id="2", sku="SKU-TSHIRT-NVY-M", product_name="Navy T-Shirt", expected_quantity=1),
        ],
    )
    # Case A: Correctly packed both distinct colorways -> SEAL
    photo_correct = PackPhoto(
        photo_id="PH-007A",
        metadata={
            "simulated_detections": [
                {"detected_label": "Black T-Shirt", "matched_sku": "SKU-TSHIRT-BLK-M", "confidence": 0.94},
                {"detected_label": "Navy T-Shirt", "matched_sku": "SKU-TSHIRT-NVY-M", "confidence": 0.93},
            ]
        },
    )

    verifier = PackVerifier()
    res_correct = verifier.verify(order, master_catalog, [photo_correct])
    assert res_correct.decision == DecisionEnum.SEAL

    # Case B: Picked two Black shirts instead of 1 Black + 1 Navy -> STOP_AND_FIX
    photo_swapped = PackPhoto(
        photo_id="PH-007B",
        metadata={
            "simulated_detections": [
                {"detected_label": "Black T-Shirt", "matched_sku": "SKU-TSHIRT-BLK-M", "confidence": 0.94},
                {"detected_label": "Black T-Shirt", "matched_sku": "SKU-TSHIRT-BLK-M", "confidence": 0.94},
            ]
        },
    )
    res_swapped = verifier.verify(order, master_catalog, [photo_swapped])
    assert res_swapped.decision == DecisionEnum.STOP_AND_FIX


def test_scenario_8_ambiguous_photographs(master_catalog):
    """Scenario 8: Ambiguous photograph (severe blur / occluded) -> UNCERTAIN, STOP_AND_FIX."""
    order = Order(
        order_id="ORD-008",
        package_id="PKG-008",
        client_id="MERCHANT-01",
        organization_id="3PL-WEST",
        line_items=[
            OrderLineItem(line_item_id="1", sku="SKU-CAP-BLU", product_name="Blue Cap", expected_quantity=1),
        ],
    )
    # Camera capture is marked blurry / degraded
    photo_blurry = PackPhoto(
        photo_id="PH-008",
        lighting_condition="blur",
        metadata={"camera_focus_score": 0.12},
    )

    verifier = PackVerifier()
    res = verifier.verify(order, master_catalog, [photo_blurry])

    # Must NEVER auto-seal an ambiguous photo
    assert res.decision == DecisionEnum.STOP_AND_FIX
    synthesis_check = next(c for c in res.evidence_record.checks if c.check_key == "decision_synthesis")
    assert synthesis_check.verdict == CheckVerdict.UNCERTAIN
    assert "UNCERTAIN" in res.summary
