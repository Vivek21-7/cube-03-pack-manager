"""Mandatory Evidence Contract Data Models.

Every evaluated pack must produce a structured, immutable evidence record
strictly compliant with Section 4 of the specification.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CheckVerdict(str, Enum):
    """Strict Semantics:
    - PASS: Evidence positively supports condition is met.
    - FAIL: Evidence positively supports condition is NOT met.
    - UNCERTAIN: Evidence is insufficient or ambiguous. Never force PASS/FAIL.
    """
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"


class DecisionEnum(str, Enum):
    """Final pack decision."""
    SEAL = "SEAL"
    STOP_AND_FIX = "STOP_AND_FIX"


class CheckRecord(BaseModel):
    """Individual verification check record."""
    check_key: str = Field(
        ...,
        description="e.g. object_identification, quantity_counting, order_matching, "
                    "wrong_item_detection, missing_item_detection, extra_item_detection, decision_synthesis"
    )
    verdict: CheckVerdict = Field(..., description="PASS | FAIL | UNCERTAIN")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0 - 1.0")
    detail: str = Field(..., description="Human-readable reasoning strictly grounded in image and order evidence")
    model_version: str = Field(..., description="Model name or algorithmic version executing check")
    latency_ms: float = Field(..., ge=0.0, description="Execution duration in milliseconds")


class OutcomeRecord(BaseModel):
    """Final decision outcome record."""
    decision: DecisionEnum = Field(..., description="SEAL | STOP_AND_FIX")
    decided_by: str = Field(default="pack-manager", description="Agent ID or operator identifier")
    decided_at: datetime = Field(default_factory=datetime.utcnow, description="UTC decision timestamp")


class OverrideRecord(BaseModel):
    """Audit log of human override applied to the pack decision."""
    override_id: str = Field(..., description="Unique ID of the override event")
    original_decision: DecisionEnum = Field(..., description="System decision before override")
    new_decision: DecisionEnum = Field(..., description="Operator assigned decision")
    reason: str = Field(..., description="Mandatory justification for override")
    authorized_by: str = Field(..., description="Supervisor / QA badge or ID")
    overridden_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of override")


class EvidenceRecord(BaseModel):
    """Mandatory Evidence Contract schema.

    Represents the complete, cryptographically signed, immutable audit record
    for an outbound packing verification event.
    """
    record_id: str = Field(..., description="Unique UUID for this evidence record")
    schema_version: str = Field(default="1.0.0", description="Evidence Contract schema version")
    organization_id: str = Field(..., description="3PL / Organization identifier")
    client_id: str = Field(..., description="Seller / Merchant identifier")
    agent: str = Field(default="pack-manager", description="Fixed agent identifier: 'pack-manager'")
    subject: Dict[str, str] = Field(
        ...,
        description="Subject identifiers, e.g. {'order_id': '...', 'package_id': '...'}"
    )
    captured_at: datetime = Field(default_factory=datetime.utcnow, description="Time photograph was captured")
    operator_label: str = Field(..., description="Station or operator identifier")
    images: List[Dict[str, Any]] = Field(..., description="References to evidence photograph(s) with hashes/metadata")
    checks: List[CheckRecord] = Field(..., description="Complete list of verification checks")
    outcome: OutcomeRecord = Field(..., description="Synthesized decision outcome")
    overrides: List[OverrideRecord] = Field(default_factory=list, description="List of any manual overrides")
    status: str = Field(
        default="PROCESSED",
        description="PROCESSED | FLAGGED_FOR_REVIEW | OVERRIDDEN | ERROR"
    )
    content_hash: str = Field(
        ...,
        description="SHA-256 digest of checks, subject, and outcome for tamper-proofing"
    )
