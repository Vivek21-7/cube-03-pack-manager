"""Test suite for FastAPI REST API endpoints."""

import pytest
from fastapi.testclient import TestClient
from pack_manager.api.app import app
from pack_manager.models.inputs import Order, OrderLineItem, PackPhoto

client = TestClient(app)


def test_api_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert data["agent"] == "pack-manager"
    assert "Track 03" in data["track"]


def test_api_catalog():
    resp = client.get("/api/catalog")
    assert resp.status_code == 200
    catalog = resp.json()
    assert len(catalog) > 0
    assert any(item["sku"] == "SKU-TEE-BLK-M" for item in catalog)


def test_api_scenarios():
    resp = client.get("/api/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()
    assert len(scenarios) >= 7
    types = [s["scenario_type"] for s in scenarios]
    assert "CORRECT_ORDER" in types
    assert "MISSING_ITEM" in types
    assert "WRONG_ITEM" in types


def test_api_verify_and_override_flow():
    # 1. Post a verification request
    payload = {
        "order": {
            "order_id": "ORD-API-001",
            "package_id": "PKG-API-001",
            "client_id": "MERCHANT-TEST",
            "organization_id": "ORG-3PL",
            "line_items": [
                {
                    "line_item_id": "L1",
                    "sku": "SKU-MUG-CER-WHT",
                    "product_name": "White Mug",
                    "expected_quantity": 1,
                }
            ],
        },
        "photos": [
            {
                "photo_id": "PH-API-001",
                "image_uri": "eval/photos/test.jpg",
                "camera_angle": "top_down",
                "lighting_condition": "standard",
                "metadata": {
                    "simulated_detections": [
                        {
                            "detected_label": "White Mug",
                            "matched_sku": "SKU-MUG-CER-WHT",
                            "confidence": 0.98,
                        }
                    ]
                },
            }
        ],
        "operator_label": "bay-10",
    }

    resp = client.post("/api/verify", json=payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["decision"] == "SEAL"
    evidence_rec = res_data["evidence_record"]
    record_id = evidence_rec["record_id"]
    original_hash = evidence_rec["content_hash"]
    assert len(original_hash) == 64

    # 2. Test Override endpoint
    override_payload = {
        "record_id": record_id,
        "new_decision": "STOP_AND_FIX",
        "reason": "Customer called to cancel order before sealing",
        "authorized_by": "QA_SUPERVISOR_99",
    }
    ovr_resp = client.post("/api/override", json=override_payload)
    assert ovr_resp.status_code == 200
    ovr_data = ovr_resp.json()
    assert ovr_data["status"] == "OVERRIDE_APPLIED"
    assert ovr_data["new_decision"] == "STOP_AND_FIX"
    assert ovr_data["evidence_record"]["status"] == "OVERRIDDEN"
    # Content hash must update
    assert ovr_data["content_hash"] != original_hash


def test_api_eval_summary():
    resp = client.get("/api/eval-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_units_evaluated"] == 60
    assert data["accuracy"] >= 0.95
    assert data["inter_human_kappa"] >= 0.80


def test_api_static_ui():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Pack Manager" in resp.text
    assert "STATION-BAY-04" in resp.text
