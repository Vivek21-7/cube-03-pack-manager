"""Base check abstract class and execution wrapper for Pack Manager checks."""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pack_manager.models.evidence import CheckRecord, CheckVerdict
from pack_manager.models.inputs import Order, CatalogItem, PackPhoto
from pack_manager.models.detection import DetectedItem, Discrepancy


class BaseCheck(ABC):
    """Abstract Base Class for discrete pack verification checks."""

    check_key: str = "base_check"
    model_version: str = "pack-verifier-v1.0"

    def run(
        self,
        order: Order,
        catalog: Dict[str, CatalogItem],
        photos: List[PackPhoto],
        detected_items: List[DetectedItem],
        discrepancies: List[Discrepancy],
        context: Optional[Dict[str, Any]] = None,
    ) -> CheckRecord:
        """Executes the check with latency profiling and exception safety."""
        start_time = time.perf_counter()
        try:
            verdict, confidence, detail = self.evaluate(
                order=order,
                catalog=catalog,
                photos=photos,
                detected_items=detected_items,
                discrepancies=discrepancies,
                context=context or {},
            )
        except Exception as exc:
            verdict = CheckVerdict.UNCERTAIN
            confidence = 0.0
            detail = f"Internal evaluation error: {str(exc)}"

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return CheckRecord(
            check_key=self.check_key,
            verdict=verdict,
            confidence=round(confidence, 4),
            detail=detail,
            model_version=self.model_version,
            latency_ms=round(elapsed_ms, 2),
        )

    @abstractmethod
    def evaluate(
        self,
        order: Order,
        catalog: Dict[str, CatalogItem],
        photos: List[PackPhoto],
        detected_items: List[DetectedItem],
        discrepancies: List[Discrepancy],
        context: Dict[str, Any],
    ) -> tuple[CheckVerdict, float, str]:
        """Perform domain evaluation logic.

        Returns:
            tuple: (CheckVerdict, confidence: float, detail: str)
        """
        pass
