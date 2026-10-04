"""Tests for Tenancy Isolation (Row-Level Security), data/pack_sample.csv, and real image processing."""

import os
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image

from pack_manager.api.app import app
from pack_manager.engine.vision_extractor import VisionExtractor
from pack_manager.models.inputs import PackPhoto, Order, OrderLineItem
from eval.dataset_generator import build_evaluation_catalog
from eval.image_synthesizer import render_parcel_image


client = TestClient(app)


def test_tenancy_isolation_security_rule_1():
    """Verifies that org_demo_bravo CANNOT access org_demo_alpha's records (Engineering Rule #1)."""
    # 1. Create a verification under org_demo_alpha
    order_payload = {
        "order": {
            "order_id": "ORD-ALPHA-1001",
            "package_id": "PKG-ALPHA-1001",
            "organization_id": "org_demo_alpha",
            "client_id": "shopify",
            "line_items": [
                {"line_item_id": "li_1", "sku": "SKU-MUG-11", "product_name": "Ceramic Mug", "expected_quantity": 1}
            ]
        },
        "photos": [
            {"photo_id": "PHOTO-A1", "camera_angle": "top_down", "lighting_condition": "standard"}
        ],
        "operator_label": "station-alpha"
    }

    res = client.post(
        "/api/verify",
        json=order_payload,
        headers={"X-Organization-Id": "org_demo_alpha"}
    )
    assert res.status_code == 200
    record_id = res.json()["evidence_record"]["record_id"]

    # 2. org_demo_alpha CAN fetch their own record
    res_alpha = client.get(
        f"/api/evidence/{record_id}",
        headers={"X-Organization-Id": "org_demo_alpha"}
    )
    assert res_alpha.status_code == 200
    assert res_alpha.json()["record_id"] == record_id

    # 3. org_demo_bravo CANNOT fetch org_demo_alpha's record (Forbidden 403)
    res_bravo = client.get(
        f"/api/evidence/{record_id}",
        headers={"X-Organization-Id": "org_demo_bravo"}
    )
    assert res_bravo.status_code == 403
    assert "Tenancy isolation" in res_bravo.json()["detail"]


def test_sample_csv_data_endpoint():
    """Verifies retrieval and filtering of data/pack_sample.csv units."""
    # Fetch all for alpha
    res = client.get("/api/sample-data", headers={"X-Organization-Id": "org_demo_alpha"})
    assert res.status_code == 200
    units = res.json()
    assert len(units) > 0
    assert all(u["org_id"] == "org_demo_alpha" for u in units)

    # Verify a specific sample unit
    unit_id = units[0]["unit_id"]
    res_verify = client.post(
        f"/api/verify-sample-unit/{unit_id}",
        headers={"X-Organization-Id": "org_demo_alpha"}
    )
    assert res_verify.status_code == 200
    data = res_verify.json()
    assert "evidence_record" in data
    assert data["evidence_record"]["organization_id"] == "org_demo_alpha"


def test_real_image_blur_mathematical_detection(tmp_path):
    """Verifies that mathematical edge gradient variance on real image bytes flags blur."""
    extractor = VisionExtractor()
    catalog = build_evaluation_catalog()

    # Generate a real blurred image file
    blurred_img_path = str(tmp_path / "blurred_box.jpg")
    render_parcel_image(
        skus_in_box=["SKU-MUG-11"],
        output_path=blurred_img_path,
        optical_condition="blur",
    )

    photo = PackPhoto(
        photo_id="PHOTO-BLUR-TEST",
        image_uri=blurred_img_path,
        camera_angle="top_down",
        lighting_condition="standard",
    )

    order = Order(
        order_id="ORD-TEST-BLUR",
        package_id="PKG-BLUR",
        organization_id="org_demo_alpha",
        client_id="shopify",
        line_items=[OrderLineItem(line_item_id="1", sku="SKU-MUG-11", product_name="Ceramic Mug", expected_quantity=1)],
    )

    detected = extractor.extract(order, catalog, [photo])
    assert len(detected) > 0
    assert detected[0].is_ambiguous is True
    assert "blur" in detected[0].ambiguity_reason.lower()
