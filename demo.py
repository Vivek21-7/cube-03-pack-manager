"""Pack Manager — CLI Interactive Demo.

Runs end-to-end verification demonstrations directly in terminal,
printing color-coded diagnostic tables, 7-check steps, SHA-256 hashes,
and final operational decisions (SEAL or STOP & FIX).
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ensure Windows terminal handles UTF-8 safely
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pack_manager import PackVerifier, DecisionEnum, CheckVerdict
from eval.dataset_generator import build_evaluation_catalog, generate_evaluation_dataset


def run_cli_demo(scenario_filter: str = "all"):
    catalog = build_evaluation_catalog()
    dataset = generate_evaluation_dataset(num_units=60, seed=42)
    verifier = PackVerifier()

    # Filter units
    if scenario_filter == "all":
        # Select 1 representative unit per scenario type
        seen = set()
        test_units = []
        for u in dataset:
            if u["scenario_type"] not in seen:
                seen.add(u["scenario_type"])
                test_units.append(u)
    else:
        test_units = [u for u in dataset if scenario_filter.lower() in u["scenario_type"].lower()]

    if not test_units:
        print(f"No test units found matching filter '{scenario_filter}'. Available types:")
        print("  correct, missing, wrong, extra, quantity, identical, similar, ambiguous, all")
        return

    print("=" * 80)
    print("  PACK MANAGER — OUTBOUND PACK VERIFICATION AGENT (TRACK 03)")
    print("=" * 80)

    for unit in test_units:
        order = unit["order"]
        photos = unit["photos"]

        print(f"\n📦 TEST UNIT: {unit['unit_id']} | SCENARIO: {unit['scenario_type']}")
        print(f"   Order ID: {order.order_id} | Package: {order.package_id} | Client: {order.client_id}")
        print("   Expected Order Lines:")
        for li in order.line_items:
            print(f"     - [{li.sku}] {li.product_name} (Expected Qty: {li.expected_quantity})")

        print(f"   Photo Capture: {photos[0].photo_id} (Lighting: {photos[0].lighting_condition})")

        # Execute agent verification
        result = verifier.verify(order, catalog, photos, operator_label="CLI-DEMO-STATION")

        print("\n   🔍 EXPECTED VS. OBSERVED QUANTITY COMPARISON:")
        print("   " + "-" * 74)
        print(f"   {'SKU':<18} | {'Product Name':<30} | {'Exp':<4} | {'Obs':<4} | {'Status'}")
        print("   " + "-" * 74)
        for r in result.quantity_table:
            name_trunc = r.product_name[:28] + ".." if len(r.product_name) > 30 else r.product_name
            print(f"   {r.sku:<18} | {name_trunc:<30} | {r.expected_qty:<4} | {r.observed_qty:<4} | {r.status}")
        print("   " + "-" * 74)

        print("\n   📋 7-CHECK VERIFICATION STEPPER:")
        for c in result.evidence_record.checks:
            verdict_symbol = "✅" if c.verdict == CheckVerdict.PASS else ("⚠️" if c.verdict == CheckVerdict.UNCERTAIN else "❌")
            print(f"     {verdict_symbol} {c.check_key:<24} [{c.verdict.value:<9}] (Conf: {c.confidence:.2f} | Latency: {c.latency_ms:.2f}ms)")
            print(f"        Reasoning: {c.detail}")

        print(f"\n   🔒 SHA-256 CONTENT HASH: {result.evidence_record.content_hash}")
        
        # Decision Banner
        if result.decision == DecisionEnum.SEAL:
            print("\n   🎯 FINAL OPERATIONAL DECISION: [ ✅ SEAL PACKAGE ]")
        else:
            is_unc = any(c.verdict == CheckVerdict.UNCERTAIN for c in result.evidence_record.checks)
            if is_unc:
                print("\n   🎯 FINAL OPERATIONAL DECISION: [ ⚠️ STOP & FIX — AMBIGUOUS PHOTO (RE-CAPTURE) ]")
            else:
                print("\n   🎯 FINAL OPERATIONAL DECISION: [ 🛑 STOP & FIX — PACKING DEFECT DETECTED ]")
        print("   " + "=" * 76)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pack Manager CLI Demo")
    parser.add_argument(
        "--scenario",
        type=str,
        default="all",
        help="Scenario filter: correct, missing, wrong, extra, quantity, identical, similar, ambiguous, or all",
    )
    args = parser.parse_args()
    run_cli_demo(args.scenario)
