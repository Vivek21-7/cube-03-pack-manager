"""Intermediate Detection and Analysis Models.

Represents visually extracted objects, bounding boxes, attributes,
and discrepancy classifications detected during pack verification.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Normalized bounding box coordinates (0.0 to 1.0)."""
    ymin: float = Field(..., ge=0.0, le=1.0)
    xmin: float = Field(..., ge=0.0, le=1.0)
    ymax: float = Field(..., ge=0.0, le=1.0)
    xmax: float = Field(..., ge=0.0, le=1.0)


class DetectedItem(BaseModel):
    """Item identified visually in the open package photograph."""
    detection_id: str = Field(..., description="Unique detection instance identifier")
    detected_label: str = Field(..., description="Human-readable visual description or product label")
    matched_sku: Optional[str] = Field(None, description="Catalog SKU matched by visual/attribute comparison")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection and match confidence score")
    bounding_box: Optional[BoundingBox] = Field(None, description="Spatial coordinates in image")
    visual_attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted traits: color, read_text, brand, packaging, condition"
    )
    is_ambiguous: bool = Field(False, description="True if image blur, occlusion, or lighting causes ambiguity")
    ambiguity_reason: Optional[str] = Field(None, description="Specific reason why detection is ambiguous")


class DiscrepancyType(str, Enum):
    MISSING = "MISSING"
    WRONG_ITEM = "WRONG_ITEM"
    EXTRA_ITEM = "EXTRA_ITEM"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    VISUALLY_AMBIGUOUS = "VISUALLY_AMBIGUOUS"


class Discrepancy(BaseModel):
    """Specific discrepancy found between expected order and visually observed contents."""
    discrepancy_type: DiscrepancyType
    sku: Optional[str] = Field(None, description="Expected or related SKU")
    detected_label: Optional[str] = Field(None, description="Detected visual label or substitute description")
    expected_quantity: int = Field(0, description="Quantity expected in order")
    observed_quantity: int = Field(0, description="Quantity visually counted in pack")
    detail: str = Field(..., description="Grounded explanation of the discrepancy")
    confidence: float = Field(..., ge=0.0, le=1.0)


class QuantityRow(BaseModel):
    """Expected vs Observed comparison row for the output report."""
    sku: str
    product_name: str
    expected_qty: int
    observed_qty: int
    status: str = Field(..., description="MATCH | SHORTAGE | SURPLUS | WRONG_ITEM | UNCERTAIN")
    confidence: float = Field(..., ge=0.0, le=1.0)
