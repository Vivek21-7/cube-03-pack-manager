"""Input data models for Pack Manager.

Defines schemas for Outbound Customer Orders, Line Items, Product Master Catalog,
and Package Evidence Photographs.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ImageFormat(str, Enum):
    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"


class PackPhoto(BaseModel):
    """Photograph(s) of the open package capturing the packed items."""
    photo_id: str = Field(..., description="Unique ID for the photo capture")
    image_uri: Optional[str] = Field(None, description="URI or relative file path to the photograph")
    image_base64: Optional[str] = Field(None, description="Base64-encoded image string (if direct stream)")
    captured_at: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp of capture")
    camera_angle: Optional[str] = Field("top_down", description="e.g. top_down, 45_degree, isometric")
    resolution: Optional[str] = Field(None, description="e.g. 1920x1080")
    lighting_condition: Optional[str] = Field("standard", description="standard, low_light, glare, shadow, blur")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary camera or station metadata")


class CatalogItem(BaseModel):
    """Product master catalogue definition for visual and metadata matching."""
    sku: str = Field(..., description="Stock Keeping Unit (SKU)")
    asin: Optional[str] = Field(None, description="Amazon Standard Identification Number if applicable")
    product_name: str = Field(..., description="Full descriptive name of the product")
    category: str = Field(..., description="Product category (e.g. Apparel, Electronics, Kitchen, Office)")
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key visual/physical attributes: color, size, dimensions, packaging_type, barcode"
    )
    reference_images: List[str] = Field(
        default_factory=list,
        description="URIs/paths to reference images showing distinct features/colorways"
    )
    visual_identifiers: List[str] = Field(
        default_factory=list,
        description="Distinct visual traits: logos, text, shapes, markings, silhouette"
    )


class OrderLineItem(BaseModel):
    """Single SKU line item in an outbound customer order."""
    line_item_id: str = Field(..., description="Unique line item ID")
    sku: str = Field(..., description="Ordered SKU")
    product_name: str = Field(..., description="Product name for reference")
    expected_quantity: int = Field(..., ge=1, description="Quantity expected to be in the parcel")
    unit_price: Optional[float] = Field(None, description="Optional unit price")


class Order(BaseModel):
    """Outbound customer order to be verified before box sealing."""
    order_id: str = Field(..., description="Unique customer order ID")
    package_id: str = Field(..., description="Specific parcel / box / tote ID")
    client_id: str = Field(..., description="Seller / Merchant ID")
    organization_id: str = Field(..., description="3PL or Fulfillment Center Org ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Order timestamp")
    line_items: List[OrderLineItem] = Field(..., min_length=1, description="List of expected line items")
    packing_instructions: Optional[str] = Field(None, description="Special packing requirements")
