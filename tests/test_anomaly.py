"""Tests for Statistical & ML Anomaly/Outlier Detection Subsystem."""

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
from pack_manager.models.detection import BoundingBox


@pytest.fixture
def test_catalog():
    return {
        "SKU-MUG-001": CatalogItem(
            sku="SKU-MUG-001",
            product_name="Ceramic Mug",
            category="Kitchen",
            attributes={"weight_grams": 350},
        )
    }


def test_anomaly_detection_nominal(test_catalog):
    """Nominal weight matches baseline distribution -> PASS."""
    order = Order(
        order_id="ORD-NOMINAL",
        package_id="PKG-01",
        client_id="MERCHANT-01",
        organization_id="3PL-01",
        line_items=[OrderLineItem(line_item_id="1", sku="SKU-MUG-001", product_name="Ceramic Mug", expected_quantity=2)],
    )
    # Expected weight = 700g, Observed = 710g (within normal 5% variance)
    photo = PackPhoto(
        photo_id="PH-NOMINAL",
        metadata={
            "scale_weight_grams": 710.0,
            "simulated_detections": [
                {"detected_label": "Ceramic Mug", "matched_sku": "SKU-MUG-001", "confidence": 0.98},
                {"detected_label": "Ceramic Mug", "matched_sku": "SKU-MUG-001", "confidence": 0.98},
            ],
        },
    )
    verifier = PackVerifier()
    res = verifier.verify(order, test_catalog, [photo])
    
    anomaly_check = next(c for c in res.evidence_record.checks if c.check_key == "anomaly_outlier_detection")
    assert anomaly_check.verdict == CheckVerdict.PASS
    assert res.decision == DecisionEnum.SEAL


def test_anomaly_detection_global_weight_outlier(test_catalog):
    """Extreme global weight outlier (> 3.0 sigma) -> FAIL & STOP_AND_FIX."""
    order = Order(
        order_id="ORD-OUTLIER",
        package_id="PKG-02",
        client_id="MERCHANT-01",
        organization_id="3PL-01",
        line_items=[OrderLineItem(line_item_id="1", sku="SKU-MUG-001", product_name="Ceramic Mug", expected_quantity=2)],
    )
    # Expected weight = 700g, Observed = 1500g (massive weight anomaly)
    photo = PackPhoto(
        photo_id="PH-OUTLIER",
        metadata={
            "scale_weight_grams": 1500.0,
            "simulated_detections": [
                {"detected_label": "Ceramic Mug", "matched_sku": "SKU-MUG-001", "confidence": 0.98},
                {"detected_label": "Ceramic Mug", "matched_sku": "SKU-MUG-001", "confidence": 0.98},
            ],
        },
    )
    verifier = PackVerifier()
    res = verifier.verify(order, test_catalog, [photo])
    
    anomaly_check = next(c for c in res.evidence_record.checks if c.check_key == "anomaly_outlier_detection")
    assert anomaly_check.verdict == CheckVerdict.FAIL
    assert "Z-Score" in anomaly_check.detail
    assert res.decision == DecisionEnum.STOP_AND_FIX
