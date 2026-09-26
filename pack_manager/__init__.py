"""Pack Manager — Outbound Pack Verification Agent (Track 03).

Production-grade agent that compares photographs of open packages against
expected customer orders and outputs traceable, cryptographically signed
SEAL or STOP & FIX decisions.
"""

__version__ = "1.0.0"

from pack_manager.engine.pack_verifier import PackVerifier, PackVerificationResult
from pack_manager.models.inputs import Order, OrderLineItem, CatalogItem, PackPhoto
from pack_manager.models.evidence import EvidenceRecord, CheckVerdict, DecisionEnum

__all__ = [
    "PackVerifier",
    "PackVerificationResult",
    "Order",
    "OrderLineItem",
    "CatalogItem",
    "PackPhoto",
    "EvidenceRecord",
    "CheckVerdict",
    "DecisionEnum",
]
