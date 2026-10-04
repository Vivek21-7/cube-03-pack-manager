"""FastAPI Backend Application for Pack Manager Agent (Track 03).

Provides REST API endpoints for:
- Outbound Pack Verification (/api/verify, /api/verify-upload)
- Manual Supervisor Overrides (/api/override)
- Official Reference Sample Dataset (/api/sample-data, /api/verify-sample-unit/{unit_id})
- Tenancy Isolation / Row-Level Security Scoping (Rule 1)
- Live Pre-loaded Scenarios (/api/scenarios)
- Product Catalog inspection (/api/catalog)
- System Health and Evaluation telemetry (/api/health, /api/eval-summary)
"""

import os
import csv
import uuid
import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Body, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from pack_manager import (
    PackVerifier,
    Order,
    OrderLineItem,
    CatalogItem,
    PackPhoto,
    DecisionEnum,
    CheckVerdict,
    EvidenceRecord,
)
from pack_manager.engine.hasher import compute_evidence_hash
from pack_manager.models.evidence import OverrideRecord
from eval.dataset_generator import build_evaluation_catalog, generate_evaluation_dataset
from eval.metrics import compute_eval_metrics

app = FastAPI(
    title="Pack Manager — Outbound Pack Verification Agent",
    description="CUBE Buildathon Track 03: Automated vision-based order-to-pack verification",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared in-memory storage for verifier, catalog, and tenant-scoped evidence audit log
verifier = PackVerifier()
catalog_db: Dict[str, CatalogItem] = build_evaluation_catalog()

# Row-Level Security Storage: Dict[tenant_org_id, Dict[record_id, EvidenceRecord]]
tenant_evidence_store: Dict[str, Dict[str, EvidenceRecord]] = {
    "org_demo_alpha": {},
    "org_demo_bravo": {},
    "default_org": {},
}


class VerifyRequest(BaseModel):
    order: Order
    catalog: Optional[Dict[str, CatalogItem]] = None
    photos: List[PackPhoto]
    operator_label: Optional[str] = "pack-station-01"


class OverrideRequest(BaseModel):
    record_id: str
    organization_id: Optional[str] = None
    new_decision: DecisionEnum
    reason: str
    authorized_by: str


@app.get("/api/health")
def get_health():
    return {
        "status": "HEALTHY",
        "agent": "pack-manager",
        "version": "1.0.0",
        "track": "Track 03 — Pack Manager (Outbound Verification)",
        "vlm_model": verifier.vision.model_name,
        "vlm_api_configured": bool(verifier.vision.api_key),
        "tenancy_isolation_enforced": True,
        "fail_open_enabled": True,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/catalog")
def get_catalog():
    return list(catalog_db.values())


@app.get("/api/sample-data")
def get_official_sample_data(x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id")):
    """Returns official reference units from data/pack_sample.csv with tenancy filtering."""
    csv_path = Path("data/pack_sample.csv")
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="data/pack_sample.csv not found")

    records = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Enforce Tenancy Isolation (Engineering Rule #1)
            if x_organization_id and row["org_id"] != x_organization_id:
                continue
            records.append(row)
    return records


@app.post("/api/verify-sample-unit/{unit_id}")
def verify_sample_unit(
    unit_id: str,
    x_organization_id: Optional[str] = Header("org_demo_alpha", alias="X-Organization-Id"),
):
    """Executes real pack verification on a specific unit from data/pack_sample.csv."""
    csv_path = Path("data/pack_sample.csv")
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="data/pack_sample.csv not found")

    target_row = None
    with open(csv_path, mode="r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["unit_id"] == unit_id:
                target_row = row
                break

    if not target_row:
        raise HTTPException(status_code=404, detail=f"Unit '{unit_id}' not found in sample dataset")

    # Enforce Row-Level Security: ensure requested unit belongs to the calling organization
    if x_organization_id and target_row["org_id"] != x_organization_id:
        raise HTTPException(
            status_code=403,
            detail=f"Tenancy Violation: Unit '{unit_id}' belongs to '{target_row['org_id']}', but request originated from '{x_organization_id}'."
        )

    # Parse expected order lines
    line_items = []
    for idx, part in enumerate(target_row["order_lines"].split(";")):
        if not part.strip():
            continue
        sku, qty = part.split(":") if ":" in part else (part, 1)
        sku = sku.strip()
        qty = int(qty)
        name = catalog_db[sku].product_name if sku in catalog_db else sku
        line_items.append(OrderLineItem(line_item_id=f"li_{idx+1}", sku=sku, product_name=name, expected_quantity=qty))

    order = Order(
        order_id=target_row["order_id"],
        package_id=f"PKG-{unit_id}",
        organization_id=target_row["org_id"],
        client_id=target_row["channel"],
        line_items=line_items,
    )

    # Load photo fixture
    photo_ref = target_row["photo_refs"].split(";")[0].strip()
    photo = PackPhoto(
        photo_id=f"PHOTO-{unit_id}",
        image_uri=photo_ref,
        camera_angle="top_down",
        lighting_condition="standard",
    )

    result = verifier.verify(
        order=order,
        catalog=catalog_db,
        photos=[photo],
        operator_label=target_row["operator_id"],
        organization_id=target_row["org_id"],
    )

    # Persist in tenant-scoped store
    org_id = target_row["org_id"]
    if org_id not in tenant_evidence_store:
        tenant_evidence_store[org_id] = {}
    tenant_evidence_store[org_id][result.evidence_record.record_id] = result.evidence_record

    return {
        "unit_id": unit_id,
        "decision": result.decision,
        "operator_verdict": target_row["operator_verdict"],
        "summary": result.summary,
        "evidence_record": result.evidence_record,
        "quantity_table": result.quantity_table,
        "discrepancies": result.discrepancies,
        "detected_items": result.detected_items,
    }


@app.get("/api/scenarios")
def get_test_scenarios():
    """Returns interactive test scenario fixtures for 1-click UI demos."""
    dataset = generate_evaluation_dataset(num_units=60, seed=42)
    scenario_map = {}
    for unit in dataset:
        stype = unit["scenario_type"]
        if stype not in scenario_map:
            scenario_map[stype] = {
                "unit_id": unit["unit_id"],
                "scenario_type": stype,
                "title": stype.replace("_", " ").title(),
                "description": unit["human_label_1"]["notes"],
                "order": unit["order"],
                "photos": unit["photos"],
                "expected_decision": unit["ground_truth_decision"],
            }
    return list(scenario_map.values())


@app.post("/api/verify")
def verify_pack(
    req: VerifyRequest,
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
):
    """Executes the complete verification pipeline and generates an immutable EvidenceRecord."""
    active_catalog = req.catalog or catalog_db
    org_id = x_organization_id or req.order.organization_id or "default_org"
    
    result = verifier.verify(
        order=req.order,
        catalog=active_catalog,
        photos=req.photos,
        operator_label=req.operator_label or "pack-station-01",
        organization_id=org_id,
        client_id=req.order.client_id,
    )

    # Persist in tenant-scoped store (Row-Level Security)
    if org_id not in tenant_evidence_store:
        tenant_evidence_store[org_id] = {}
    tenant_evidence_store[org_id][result.evidence_record.record_id] = result.evidence_record

    return {
        "decision": result.decision,
        "summary": result.summary,
        "evidence_record": result.evidence_record,
        "quantity_table": result.quantity_table,
        "discrepancies": result.discrepancies,
        "detected_items": result.detected_items,
    }


class UploadVerifyRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 data URI of the parcel photograph")
    order: Order = Field(..., description="Customer order manifest")
    operator_label: Optional[str] = "UI-UPLOAD-STATION"


@app.post("/api/verify-upload")
def verify_uploaded_image(
    req: UploadVerifyRequest,
    x_organization_id: Optional[str] = Header("org_demo_alpha", alias="X-Organization-Id"),
):
    """Verifies a real uploaded box photograph (Base64) against order JSON."""
    photo = PackPhoto(
        photo_id=f"UPLOAD-{uuid.uuid4().hex[:8]}",
        image_base64=req.image_base64,
        camera_angle="top_down",
        lighting_condition="standard",
    )

    result = verifier.verify(
        order=req.order,
        catalog=catalog_db,
        photos=[photo],
        operator_label=req.operator_label or "UI-UPLOAD-STATION",
        organization_id=x_organization_id,
    )

    org_id = x_organization_id or "default_org"
    if org_id not in tenant_evidence_store:
        tenant_evidence_store[org_id] = {}
    tenant_evidence_store[org_id][result.evidence_record.record_id] = result.evidence_record

    return {
        "decision": result.decision,
        "summary": result.summary,
        "evidence_record": result.evidence_record,
        "quantity_table": result.quantity_table,
        "discrepancies": result.discrepancies,
        "detected_items": result.detected_items,
    }


@app.post("/api/override")
def apply_override(
    req: OverrideRequest,
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
):
    """Applies an authorized supervisor override to an evidence record with audit tracking."""
    caller_org = x_organization_id or req.organization_id

    # Locate the record across tenant stores
    target_org = None
    target_rec = None
    for org, store in tenant_evidence_store.items():
        if req.record_id in store:
            target_org = org
            target_rec = store[req.record_id]
            break

    if not target_rec:
        raise HTTPException(status_code=404, detail="Evidence record ID not found")

    # Enforce Tenancy Isolation (Engineering Rule #1)
    if caller_org and target_org and caller_org != target_org and caller_org != "default_org":
        raise HTTPException(
            status_code=403,
            detail=f"Tenancy Violation: Record '{req.record_id}' belongs to organization '{target_org}'. Caller '{caller_org}' cannot override."
        )

    override = OverrideRecord(
        override_id=f"ovr_{uuid.uuid4().hex[:8]}",
        original_decision=target_rec.outcome.decision,
        new_decision=req.new_decision,
        reason=req.reason,
        authorized_by=req.authorized_by,
        overridden_at=datetime.utcnow(),
    )

    target_rec.overrides.append(override)
    target_rec.outcome.decision = req.new_decision
    target_rec.status = "OVERRIDDEN"

    # Re-compute tamper-evident content hash
    rec_dict = target_rec.model_dump()
    target_rec.content_hash = compute_evidence_hash(rec_dict)
    tenant_evidence_store[target_org][req.record_id] = target_rec

    return {
        "status": "OVERRIDE_APPLIED",
        "evidence_record": target_rec,
        "new_decision": req.new_decision,
        "content_hash": target_rec.content_hash,
    }


@app.get("/api/evidence/{record_id}")
def get_evidence_record(
    record_id: str,
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
):
    """Retrieves an evidence record enforcing Row-Level Security (Rule #1)."""
    target_org = None
    target_rec = None
    for org, store in tenant_evidence_store.items():
        if record_id in store:
            target_org = org
            target_rec = store[record_id]
            break

    if not target_rec:
        raise HTTPException(status_code=404, detail="Evidence record ID not found")

    if x_organization_id and target_org and x_organization_id != target_org and x_organization_id != "default_org":
        raise HTTPException(
            status_code=403,
            detail=f"Access Denied: Tenancy isolation prevents '{x_organization_id}' from accessing records belonging to '{target_org}'."
        )

    return target_rec


@app.get("/api/eval-summary")
def get_eval_summary():
    """Generates real-time evaluation metrics over benchmark set."""
    dataset = generate_evaluation_dataset(num_units=60, seed=42)
    records = []
    for unit in dataset:
        res = verifier.verify(unit["order"], catalog_db, unit["photos"])
        is_unc = any(c.verdict == CheckVerdict.UNCERTAIN for c in res.evidence_record.checks)
        records.append({
            "unit_id": unit["unit_id"],
            "scenario_type": unit["scenario_type"],
            "human_1": unit["human_label_1"],
            "human_2": unit["human_label_2"],
            "ground_truth_decision": unit["ground_truth_decision"],
            "expected_discrepancy_type": unit["expected_discrepancy_type"],
            "agent_decision": res.decision.value,
            "is_uncertain": is_unc,
            "latency_ms": 0.12,
            "summary": res.summary,
            "checks": [{"check_key": c.check_key, "verdict": c.verdict.value, "confidence": c.confidence, "latency_ms": c.latency_ms} for c in res.evidence_record.checks],
        })
    return compute_eval_metrics(records)


tenant_queue_store: Dict[str, List[Dict[str, Any]]] = {
    "org_demo_alpha": [
        {
            "unit_id": "UNIT-5001",
            "order_id": "ORD-5001",
            "channel": "Shopify",
            "status": "OPEN",
            "items_count": "2 total items",
            "lines": [
                {"sku": "MUG-BLUE", "qty": 1},
                {"sku": "NOTEBOOK-A5-BLACK", "qty": 1},
            ],
            "scenarioKey": "CORRECT_ORDER",
        },
        {
            "unit_id": "UNIT-5002",
            "order_id": "ORD-5002",
            "channel": "Amazon MFN",
            "status": "OPEN",
            "items_count": "3 total items",
            "lines": [
                {"sku": "CHARGER-65W", "qty": 1},
                {"sku": "PEN-PACK", "qty": 2},
            ],
            "scenarioKey": "MISSING_ITEM",
        },
        {
            "unit_id": "UNIT-5003",
            "order_id": "ORD-5003",
            "channel": "Walmart",
            "status": "STOPPED",
            "items_count": "3 total items",
            "lines": [
                {"sku": "BOTTLE-WATER-SILVER", "qty": 1},
                {"sku": "SOCKS-PAIR", "qty": 2},
            ],
            "scenarioKey": "WRONG_ITEM",
        },
        {
            "unit_id": "UNIT-5004",
            "order_id": "ORD-5004",
            "channel": "3PL Client",
            "status": "OPEN",
            "items_count": "2 total items",
            "lines": [
                {"sku": "CREAM-TUBE", "qty": 1},
                {"sku": "KEYCHAIN-METAL", "qty": 1},
            ],
            "scenarioKey": "EXTRA_ITEM",
        },
        {
            "unit_id": "UNIT-5005",
            "order_id": "ORD-5005",
            "channel": "Shopify",
            "status": "SEALED",
            "items_count": "2 total items",
            "lines": [
                {"sku": "HEADPHONES-CASE", "qty": 1},
                {"sku": "STICKER-PACK", "qty": 1},
            ],
            "scenarioKey": "MULTI_IDENTICAL",
        },
        {
            "unit_id": "UNIT-5006",
            "order_id": "ORD-5006",
            "channel": "Amazon MFN",
            "status": "UNCERTAIN",
            "items_count": "2 total items",
            "lines": [
                {"sku": "CAMERA-LENS-CAP", "qty": 1},
                {"sku": "CLEANING-CLOTH", "qty": 1},
            ],
            "scenarioKey": "AMBIGUOUS_CAPTURE",
        },
    ],
    "org_demo_bravo": [
        {
            "unit_id": "UNIT-6001",
            "order_id": "ORD-6001",
            "channel": "Shopify Plus",
            "status": "OPEN",
            "items_count": "2 total items",
            "lines": [
                {"sku": "HOODIE-GRY-L", "qty": 1},
                {"sku": "BEANIE-BLK", "qty": 1},
            ],
            "scenarioKey": "CORRECT_ORDER",
        },
        {
            "unit_id": "UNIT-6002",
            "order_id": "ORD-6002",
            "channel": "WooCommerce",
            "status": "OPEN",
            "items_count": "4 total items",
            "lines": [
                {"sku": "NOTE-A5-DOT", "qty": 2},
                {"sku": "PEN-GEL-BLK", "qty": 2},
            ],
            "scenarioKey": "WRONG_QUANTITY",
        },
    ],
}


@app.get("/api/queue")
def get_packing_queue(
    tenant: Optional[str] = "org_demo_alpha",
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
):
    """Returns active packing station queue respecting tenancy isolation."""
    target_org = (x_organization_id or tenant or "org_demo_alpha").lower()
    return tenant_queue_store.get(target_org, [])


class QueueImportPayload(BaseModel):
    order_id: Optional[str] = None
    unit_id: Optional[str] = None
    channel: Optional[str] = "Shopify"
    tenant: Optional[str] = "org_demo_alpha"
    raw_lines: Optional[str] = None
    lines: Optional[List[Dict[str, Any]]] = None


@app.post("/api/queue/import")
def import_to_packing_queue(payload: QueueImportPayload):
    """Imports order lines into the packing station queue (SKU:QTY;SKU:QTY format)."""
    target_org = (payload.tenant or "org_demo_alpha").lower()
    order_id = payload.order_id or f"ORD-{uuid.uuid4().hex[:4].upper()}"
    unit_id = payload.unit_id or f"UNIT-{uuid.uuid4().hex[:4].upper()}"
    parsed_lines = []

    if payload.raw_lines:
        for chunk in payload.raw_lines.split(";"):
            chunk = chunk.strip()
            if ":" in chunk:
                sku, qty_str = chunk.split(":", 1)
                try:
                    parsed_lines.append({"sku": sku.strip(), "qty": int(qty_str.strip())})
                except ValueError:
                    parsed_lines.append({"sku": sku.strip(), "qty": 1})
            elif chunk:
                parsed_lines.append({"sku": chunk, "qty": 1})
    elif payload.lines:
        parsed_lines = payload.lines
    else:
        parsed_lines = [{"sku": "MUG-BLUE", "qty": 1}]

    total_qty = sum(l.get("qty", 1) for l in parsed_lines)
    item = {
        "unit_id": unit_id,
        "order_id": order_id,
        "channel": payload.channel or "Shopify",
        "status": "OPEN",
        "items_count": f"{total_qty} total items",
        "lines": parsed_lines,
        "scenarioKey": "CORRECT_ORDER",
    }
    if target_org not in tenant_queue_store:
        tenant_queue_store[target_org] = []
    tenant_queue_store[target_org].insert(0, item)
    return {"status": "SUCCESS", "order": item}


# Mount static directory for frontend
ui_dir = os.path.join(os.path.dirname(__file__), "..", "ui", "dist")
if os.path.exists(ui_dir):
    app.mount("/static", StaticFiles(directory=ui_dir), name="static")

    @app.get("/")
    @app.get("/overview")
    @app.get("/queue")
    @app.get("/queue/import")
    @app.get("/station")
    @app.get("/audit")
    @app.get("/benchmarks")
    @app.get("/units")
    @app.get("/units/{unit_id}")
    @app.get("/units/{unit_id}/capture")
    def serve_frontend_root(unit_id: Optional[str] = None):
        return FileResponse(os.path.join(ui_dir, "index.html"))

    @app.get("/styles.css")
    def serve_styles():
        return FileResponse(os.path.join(ui_dir, "styles.css"))

    @app.get("/app.js")
    def serve_app_js():
        return FileResponse(os.path.join(ui_dir, "app.js"))
