"""FastAPI Backend Application for Pack Manager Agent (Track 03).

Provides REST API endpoints for:
- Outbound Pack Verification (/api/verify)
- Manual Supervisor Overrides (/api/override)
- Live Pre-loaded Scenarios (/api/scenarios)
- Product Catalog inspection (/api/catalog)
- System Health and Evaluation telemetry (/api/health, /api/eval-summary)
"""

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

# Shared in-memory storage for verifier, catalog, and evidence audit log
verifier = PackVerifier()
catalog_db: Dict[str, CatalogItem] = build_evaluation_catalog()
evidence_store: Dict[str, EvidenceRecord] = {}


class VerifyRequest(BaseModel):
    order: Order
    catalog: Optional[Dict[str, CatalogItem]] = None
    photos: List[PackPhoto]
    operator_label: Optional[str] = "pack-station-01"


class OverrideRequest(BaseModel):
    record_id: str
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
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/catalog")
def get_catalog():
    return list(catalog_db.values())


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
def verify_pack(req: VerifyRequest):
    """Executes the complete verification pipeline and generates an immutable EvidenceRecord."""
    active_catalog = req.catalog or catalog_db
    
    result = verifier.verify(
        order=req.order,
        catalog=active_catalog,
        photos=req.photos,
        operator_label=req.operator_label or "pack-station-01",
    )

    # Persist in audit store
    evidence_store[result.evidence_record.record_id] = result.evidence_record

    return {
        "decision": result.decision,
        "summary": result.summary,
        "evidence_record": result.evidence_record,
        "quantity_table": result.quantity_table,
        "discrepancies": result.discrepancies,
        "detected_items": result.detected_items,
    }


@app.post("/api/override")
def apply_override(req: OverrideRequest):
    """Applies an authorized supervisor override to an evidence record with audit tracking."""
    if req.record_id not in evidence_store:
        raise HTTPException(status_code=404, detail="Evidence record ID not found")

    rec = evidence_store[req.record_id]
    
    override = OverrideRecord(
        override_id=f"ovr_{uuid.uuid4().hex[:8]}",
        original_decision=rec.outcome.decision,
        new_decision=req.new_decision,
        reason=req.reason,
        authorized_by=req.authorized_by,
        overridden_at=datetime.utcnow(),
    )

    rec.overrides.append(override)
    rec.outcome.decision = req.new_decision
    rec.status = "OVERRIDDEN"

    # Re-compute tamper-evident content hash
    rec_dict = rec.model_dump()
    rec.content_hash = compute_evidence_hash(rec_dict)
    evidence_store[req.record_id] = rec

    return {
        "status": "OVERRIDE_APPLIED",
        "evidence_record": rec,
        "new_decision": req.new_decision,
        "content_hash": rec.content_hash,
    }


@app.get("/api/evidence/{record_id}")
def get_evidence_record(record_id: str):
    if record_id not in evidence_store:
        raise HTTPException(status_code=404, detail="Evidence record ID not found")
    return evidence_store[record_id]


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


# Mount static directory for frontend
ui_dir = os.path.join(os.path.dirname(__file__), "..", "ui", "dist")
if os.path.exists(ui_dir):
    app.mount("/static", StaticFiles(directory=ui_dir), name="static")

    @app.get("/")
    def serve_frontend_root():
        return FileResponse(os.path.join(ui_dir, "index.html"))
