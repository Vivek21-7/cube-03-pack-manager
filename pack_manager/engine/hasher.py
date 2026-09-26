"""Cryptographic hashing utilities for Evidence Contract integrity.

Ensures every generated EvidenceRecord is tamper-evident via canonical JSON SHA-256 hashing.
"""

import hashlib
import json
from typing import Any, Dict


def compute_evidence_hash(evidence_payload: Dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 hash of the evidence record payload.

    Excludes the 'content_hash' key itself to prevent circularity.
    Uses sorted keys and compact JSON separators for canonical serialization.
    """
    clean_payload = {k: v for k, v in evidence_payload.items() if k != "content_hash"}
    
    # Custom serializer for datetime or non-standard objects
    def default_serializer(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        return str(obj)

    canonical_json = json.dumps(
        clean_payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=default_serializer
    )
    
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
