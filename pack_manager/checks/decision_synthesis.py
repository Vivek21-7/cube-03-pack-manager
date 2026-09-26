"""Check 7: Decision Synthesis Engine.

Aggregates discrete verification check records into the final operational verdict:
SEAL or STOP_AND_FIX.

Strict Decision Rule:
- SEAL: Requires ALL verification checks to be strictly PASS with adequate confidence.
- STOP_AND_FIX: Triggered immediately if ANY check is FAIL or UNCERTAIN.
  Auto-SEAL is strictly prohibited whenever any check is UNCERTAIN.
"""

from typing import Any, Dict, List
from pack_manager.checks.base import BaseCheck
from pack_manager.models.evidence import CheckRecord, CheckVerdict, DecisionEnum
from pack_manager.models.inputs import Order, CatalogItem, PackPhoto
from pack_manager.models.detection import DetectedItem, Discrepancy


class DecisionSynthesisCheck(BaseCheck):
    check_key = "decision_synthesis"
    model_version = "synthesis-rules-v1.0"

    def evaluate_prior_checks(
        self,
        checks: List[CheckRecord]
    ) -> tuple[DecisionEnum, CheckVerdict, float, str]:
        """Synthesizes prior checks into final decision."""
        fails = [c for c in checks if c.verdict == CheckVerdict.FAIL]
        uncertains = [c for c in checks if c.verdict == CheckVerdict.UNCERTAIN]
        passes = [c for c in checks if c.verdict == CheckVerdict.PASS]

        # 1. Any FAIL -> STOP_AND_FIX
        if fails:
            fail_reasons = [f"[{c.check_key}]: {c.detail}" for c in fails]
            avg_conf = sum(c.confidence for c in fails) / len(fails)
            decision = DecisionEnum.STOP_AND_FIX
            verdict = CheckVerdict.FAIL
            detail = f"STOP & FIX: {len(fails)} verification check(s) failed: {' | '.join(fail_reasons)}"
            return decision, verdict, avg_conf, detail

        # 2. Any UNCERTAIN -> STOP_AND_FIX (with UNCERTAIN verdict)
        if uncertains:
            uncertain_reasons = [f"[{c.check_key}]: {c.detail}" for c in uncertains]
            min_conf = min(c.confidence for c in uncertains)
            decision = DecisionEnum.STOP_AND_FIX
            verdict = CheckVerdict.UNCERTAIN
            detail = (
                f"STOP & FIX (ACTION REQUIRED: HUMAN INSPECTION / RE-PHOTOGRAPH): "
                f"{len(uncertains)} check(s) produced UNCERTAIN verdict: {' | '.join(uncertain_reasons)}"
            )
            return decision, verdict, min_conf, detail

        # 3. All PASS -> SEAL
        avg_conf = sum(c.confidence for c in passes) / len(passes) if passes else 1.0
        decision = DecisionEnum.SEAL
        verdict = CheckVerdict.PASS
        detail = (
            f"SEAL: All {len(passes)} verification checks passed successfully with full grounded evidence. "
            f"Order is 100% verified for outbound dispatch."
        )
        return decision, verdict, avg_conf, detail

    def evaluate(
        self,
        order: Order,
        catalog: Dict[str, CatalogItem],
        photos: List[PackPhoto],
        detected_items: List[DetectedItem],
        discrepancies: List[Discrepancy],
        context: Dict[str, Any],
    ) -> tuple[CheckVerdict, float, str]:
        prior_checks: List[CheckRecord] = context.get("prior_checks", [])
        _, verdict, confidence, detail = self.evaluate_prior_checks(prior_checks)
        return verdict, confidence, detail
