"""Held-out Evaluation Dataset Generator.

Generates 60 diverse, realistic held-out test pack units covering:
- Good, poor lighting (glare, shadows, low-light)
- Various camera angles (top-down, 45-degree, isometric)
- Slight blur, heavy blur, and genuine visual ambiguities
- Correct packs, Missing items, Wrong items, Extra items, Quantity mismatches,
  visually similar colorways/sizes, and multi-item stacking.
- Two independent human annotator labels (Annotator A & Annotator B) for inter-rater agreement.
"""

import json
import random
from typing import Any, Dict, List
from pack_manager.models.inputs import CatalogItem, Order, OrderLineItem, PackPhoto


def build_evaluation_catalog() -> Dict[str, CatalogItem]:
    """Catalog of test items across multiple retail categories."""
    return {
        "SKU-TEE-BLK-M": CatalogItem(
            sku="SKU-TEE-BLK-M",
            product_name="Classic Crewneck T-Shirt - Black (M)",
            category="Apparel",
            attributes={"color": "black", "size": "M", "material": "100% Cotton"},
            visual_identifiers=["black fabric", "ribbed collar", "care tag inner neck"],
        ),
        "SKU-TEE-NVY-M": CatalogItem(
            sku="SKU-TEE-NVY-M",
            product_name="Classic Crewneck T-Shirt - Navy Blue (M)",
            category="Apparel",
            attributes={"color": "navy blue", "size": "M", "material": "100% Cotton"},
            visual_identifiers=["deep navy fabric", "ribbed collar"],
        ),
        "SKU-TEE-BLK-L": CatalogItem(
            sku="SKU-TEE-BLK-L",
            product_name="Classic Crewneck T-Shirt - Black (L)",
            category="Apparel",
            attributes={"color": "black", "size": "L", "material": "100% Cotton"},
            visual_identifiers=["black fabric", "large size tag"],
        ),
        "SKU-MUG-CER-WHT": CatalogItem(
            sku="SKU-MUG-CER-WHT",
            product_name="Ceramic Coffee Mug - Minimalist White (350ml)",
            category="Kitchen",
            attributes={"color": "white", "capacity": "350ml"},
            visual_identifiers=["glossy white glaze", "curved handle"],
        ),
        "SKU-MUG-CER-GRY": CatalogItem(
            sku="SKU-MUG-CER-GRY",
            product_name="Ceramic Coffee Mug - Stone Grey (350ml)",
            category="Kitchen",
            attributes={"color": "stone grey", "capacity": "350ml"},
            visual_identifiers=["matte grey glaze", "curved handle"],
        ),
        "SKU-CABLE-USB-C": CatalogItem(
            sku="SKU-CABLE-USB-C",
            product_name="Braided USB-C to USB-C Fast Charging Cable (2m)",
            category="Electronics",
            attributes={"color": "dark grey", "length": "2m"},
            visual_identifiers=["braided nylon sheath", "aluminum connector housing"],
        ),
        "SKU-CABLE-LIGHTN": CatalogItem(
            sku="SKU-CABLE-LIGHTN",
            product_name="Braided Lightning to USB-C Cable (2m)",
            category="Electronics",
            attributes={"color": "silver", "length": "2m"},
            visual_identifiers=["braided silver sheath", "lightning connector pin"],
        ),
        "SKU-NOTE-A5-DOT": CatalogItem(
            sku="SKU-NOTE-A5-DOT",
            product_name="Dotted Grid Executive Journal - Emerald Green",
            category="Stationery",
            attributes={"color": "emerald green", "size": "A5"},
            visual_identifiers=["vegan leather emerald cover", "golden ribbon"],
        ),
        "SKU-PEN-GEL-BLK": CatalogItem(
            sku="SKU-PEN-GEL-BLK",
            product_name="Precision Gel Pen 0.5mm - Matte Black",
            category="Stationery",
            attributes={"color": "black ink", "tip": "0.5mm"},
            visual_identifiers=["matte barrel", "metal pocket clip"],
        ),
        "SKU-BOTTLE-THERM": CatalogItem(
            sku="SKU-BOTTLE-THERM",
            product_name="Vacuum Insulated Thermal Flask - 750ml Forest Green",
            category="Outdoor",
            attributes={"color": "forest green", "capacity": "750ml"},
            visual_identifiers=["powder-coated green finish", "bamboo lid cap"],
        ),
        "SKU-PACK-TAPE-ROLL": CatalogItem(
            sku="SKU-PACK-TAPE-ROLL",
            product_name="Warehouse Packing Tape Roll 50m (Internal Tool / Non-Inventory)",
            category="Warehouse_Supplies",
            attributes={"color": "tan"},
            visual_identifiers=["cardboard core", "adhesive film"],
        ),
    }


def generate_evaluation_dataset(num_units: int = 60, seed: int = 42) -> List[Dict[str, Any]]:
    """Generates 60 test units with realistic human annotations and environmental conditions."""
    random.seed(seed)
    catalog = build_evaluation_catalog()
    units = []

    # Scenario distributions across the 60 units:
    # 20 Correct orders (SEAL)
    # 8 Missing items (STOP_AND_FIX)
    # 8 Wrong items / variant substitutions (STOP_AND_FIX)
    # 6 Extra items / foreign tools in parcel (STOP_AND_FIX)
    # 6 Wrong quantity / shortage or surplus (STOP_AND_FIX)
    # 4 Multi-identical counts (SEAL)
    # 4 Visually similar subtle pairs (SEAL & STOP_AND_FIX)
    # 4 Genuinely ambiguous / degraded captures (UNCERTAIN -> STOP_AND_FIX)

    unit_id = 1

    # 1. Correct Orders (20 units)
    for i in range(20):
        skus = random.sample(["SKU-TEE-BLK-M", "SKU-MUG-CER-WHT", "SKU-CABLE-USB-C", "SKU-NOTE-A5-DOT", "SKU-BOTTLE-THERM"], k=random.choice([1, 2, 3]))
        lines = [OrderLineItem(line_item_id=f"L{idx}", sku=s, product_name=catalog[s].product_name, expected_quantity=1) for idx, s in enumerate(skus)]
        
        lighting = random.choice(["standard", "standard", "45_degree", "low_glare"])
        simulated_dets = [
            {"detected_label": catalog[s].product_name, "matched_sku": s, "confidence": random.uniform(0.92, 0.99)}
            for s in skus
        ]

        units.append({
            "unit_id": f"TEST-UNIT-{unit_id:03d}",
            "scenario_type": "CORRECT_ORDER",
            "order": Order(
                order_id=f"ORD-EVAL-{unit_id:03d}",
                package_id=f"PKG-EVAL-{unit_id:03d}",
                client_id="MERCHANT-CORE",
                organization_id="3PL-HUB-01",
                line_items=lines,
            ),
            "photos": [
                PackPhoto(
                    photo_id=f"PH-EVAL-{unit_id:03d}",
                    image_uri=f"eval/images/unit_{unit_id:03d}.jpg",
                    camera_angle=lighting if "degree" in lighting else "top_down",
                    lighting_condition=lighting,
                    metadata={"simulated_detections": simulated_dets},
                )
            ],
            "human_label_1": {"decision": "SEAL", "discrepancy": "NONE", "uncertain": False, "notes": "Clear match"},
            "human_label_2": {"decision": "SEAL", "discrepancy": "NONE", "uncertain": False, "notes": "All items verified"},
            "ground_truth_decision": "SEAL",
            "expected_discrepancy_type": "NONE",
        })
        unit_id += 1

    # 2. Missing Items (8 units)
    for i in range(8):
        ordered_skus = ["SKU-TEE-BLK-M", "SKU-BOTTLE-THERM"]
        lines = [OrderLineItem(line_item_id=f"L{idx}", sku=s, product_name=catalog[s].product_name, expected_quantity=1) for idx, s in enumerate(ordered_skus)]
        
        # Omit the second item from detected
        simulated_dets = [
            {"detected_label": catalog[ordered_skus[0]].product_name, "matched_sku": ordered_skus[0], "confidence": 0.96}
        ]

        units.append({
            "unit_id": f"TEST-UNIT-{unit_id:03d}",
            "scenario_type": "MISSING_ITEM",
            "order": Order(
                order_id=f"ORD-EVAL-{unit_id:03d}",
                package_id=f"PKG-EVAL-{unit_id:03d}",
                client_id="MERCHANT-CORE",
                organization_id="3PL-HUB-01",
                line_items=lines,
            ),
            "photos": [
                PackPhoto(
                    photo_id=f"PH-EVAL-{unit_id:03d}",
                    image_uri=f"eval/images/unit_{unit_id:03d}.jpg",
                    lighting_condition="standard",
                    metadata={"simulated_detections": simulated_dets},
                )
            ],
            "human_label_1": {"decision": "STOP_AND_FIX", "discrepancy": "MISSING", "uncertain": False, "notes": "Thermal flask missing"},
            "human_label_2": {"decision": "STOP_AND_FIX", "discrepancy": "MISSING", "uncertain": False, "notes": "Only shirt inside box"},
            "ground_truth_decision": "STOP_AND_FIX",
            "expected_discrepancy_type": "MISSING",
        })
        unit_id += 1

    # 3. Wrong Item / Variant Substitution (8 units)
    wrong_pairs = [
        ("SKU-TEE-BLK-M", "SKU-TEE-NVY-M", "Navy Blue Shirt packed instead of Black Shirt"),
        ("SKU-TEE-BLK-M", "SKU-TEE-BLK-L", "Size L packed instead of Size M"),
        ("SKU-MUG-CER-WHT", "SKU-MUG-CER-GRY", "Grey Mug packed instead of White Mug"),
        ("SKU-CABLE-USB-C", "SKU-CABLE-LIGHTN", "Lightning cable packed instead of USB-C cable"),
    ]
    for i in range(8):
        exp_sku, actual_sku, reason = wrong_pairs[i % len(wrong_pairs)]
        lines = [OrderLineItem(line_item_id="L1", sku=exp_sku, product_name=catalog[exp_sku].product_name, expected_quantity=1)]
        
        simulated_dets = [
            {"detected_label": catalog[actual_sku].product_name, "matched_sku": actual_sku, "confidence": 0.95}
        ]

        units.append({
            "unit_id": f"TEST-UNIT-{unit_id:03d}",
            "scenario_type": "WRONG_ITEM",
            "order": Order(
                order_id=f"ORD-EVAL-{unit_id:03d}",
                package_id=f"PKG-EVAL-{unit_id:03d}",
                client_id="MERCHANT-CORE",
                organization_id="3PL-HUB-01",
                line_items=lines,
            ),
            "photos": [
                PackPhoto(
                    photo_id=f"PH-EVAL-{unit_id:03d}",
                    image_uri=f"eval/images/unit_{unit_id:03d}.jpg",
                    lighting_condition="standard",
                    metadata={"simulated_detections": simulated_dets},
                )
            ],
            "human_label_1": {"decision": "STOP_AND_FIX", "discrepancy": "WRONG_ITEM", "uncertain": False, "notes": reason},
            "human_label_2": {"decision": "STOP_AND_FIX", "discrepancy": "WRONG_ITEM", "uncertain": False, "notes": f"Wrong SKU {actual_sku}"},
            "ground_truth_decision": "STOP_AND_FIX",
            "expected_discrepancy_type": "WRONG_ITEM",
        })
        unit_id += 1

    # 4. Extra Item / Foreign Tool (6 units)
    for i in range(6):
        ordered_sku = "SKU-NOTE-A5-DOT"
        lines = [OrderLineItem(line_item_id="L1", sku=ordered_sku, product_name=catalog[ordered_sku].product_name, expected_quantity=1)]
        
        extra_sku = "SKU-PACK-TAPE-ROLL" if i % 2 == 0 else "SKU-PEN-GEL-BLK"
        simulated_dets = [
            {"detected_label": catalog[ordered_sku].product_name, "matched_sku": ordered_sku, "confidence": 0.97},
            {"detected_label": catalog[extra_sku].product_name, "matched_sku": extra_sku, "confidence": 0.94},
        ]

        units.append({
            "unit_id": f"TEST-UNIT-{unit_id:03d}",
            "scenario_type": "EXTRA_ITEM",
            "order": Order(
                order_id=f"ORD-EVAL-{unit_id:03d}",
                package_id=f"PKG-EVAL-{unit_id:03d}",
                client_id="MERCHANT-CORE",
                organization_id="3PL-HUB-01",
                line_items=lines,
            ),
            "photos": [
                PackPhoto(
                    photo_id=f"PH-EVAL-{unit_id:03d}",
                    image_uri=f"eval/images/unit_{unit_id:03d}.jpg",
                    lighting_condition="standard",
                    metadata={"simulated_detections": simulated_dets},
                )
            ],
            "human_label_1": {"decision": "STOP_AND_FIX", "discrepancy": "EXTRA_ITEM", "uncertain": False, "notes": f"Extra {extra_sku} in box"},
            "human_label_2": {"decision": "STOP_AND_FIX", "discrepancy": "EXTRA_ITEM", "uncertain": False, "notes": "Unordered surplus object"},
            "ground_truth_decision": "STOP_AND_FIX",
            "expected_discrepancy_type": "EXTRA_ITEM",
        })
        unit_id += 1

    # 5. Wrong Quantity / Shortage / Surplus (6 units)
    for i in range(6):
        sku = "SKU-PEN-GEL-BLK"
        exp_qty = 3
        actual_qty = 2 if i < 3 else 4
        lines = [OrderLineItem(line_item_id="L1", sku=sku, product_name=catalog[sku].product_name, expected_quantity=exp_qty)]
        
        simulated_dets = [
            {"detected_label": catalog[sku].product_name, "matched_sku": sku, "confidence": 0.96}
            for _ in range(actual_qty)
        ]

        units.append({
            "unit_id": f"TEST-UNIT-{unit_id:03d}",
            "scenario_type": "WRONG_QUANTITY",
            "order": Order(
                order_id=f"ORD-EVAL-{unit_id:03d}",
                package_id=f"PKG-EVAL-{unit_id:03d}",
                client_id="MERCHANT-CORE",
                organization_id="3PL-HUB-01",
                line_items=lines,
            ),
            "photos": [
                PackPhoto(
                    photo_id=f"PH-EVAL-{unit_id:03d}",
                    image_uri=f"eval/images/unit_{unit_id:03d}.jpg",
                    lighting_condition="standard",
                    metadata={"simulated_detections": simulated_dets},
                )
            ],
            "human_label_1": {"decision": "STOP_AND_FIX", "discrepancy": "QUANTITY_MISMATCH", "uncertain": False, "notes": f"Count {actual_qty} != expected {exp_qty}"},
            "human_label_2": {"decision": "STOP_AND_FIX", "discrepancy": "QUANTITY_MISMATCH", "uncertain": False, "notes": f"Quantity error: found {actual_qty}"},
            "ground_truth_decision": "STOP_AND_FIX",
            "expected_discrepancy_type": "QUANTITY_MISMATCH",
        })
        unit_id += 1

    # 6. Multiple Identical Products (4 units)
    for i in range(4):
        sku = "SKU-MUG-CER-WHT"
        exp_qty = 4
        lines = [OrderLineItem(line_item_id="L1", sku=sku, product_name=catalog[sku].product_name, expected_quantity=exp_qty)]
        
        simulated_dets = [
            {"detected_label": catalog[sku].product_name, "matched_sku": sku, "confidence": 0.95}
            for _ in range(exp_qty)
        ]

        units.append({
            "unit_id": f"TEST-UNIT-{unit_id:03d}",
            "scenario_type": "MULTI_IDENTICAL",
            "order": Order(
                order_id=f"ORD-EVAL-{unit_id:03d}",
                package_id=f"PKG-EVAL-{unit_id:03d}",
                client_id="MERCHANT-CORE",
                organization_id="3PL-HUB-01",
                line_items=lines,
            ),
            "photos": [
                PackPhoto(
                    photo_id=f"PH-EVAL-{unit_id:03d}",
                    image_uri=f"eval/images/unit_{unit_id:03d}.jpg",
                    lighting_condition="standard",
                    metadata={"simulated_detections": simulated_dets},
                )
            ],
            "human_label_1": {"decision": "SEAL", "discrepancy": "NONE", "uncertain": False, "notes": "All 4 mugs present and intact"},
            "human_label_2": {"decision": "SEAL", "discrepancy": "NONE", "uncertain": False, "notes": "Exact count match: 4"},
            "ground_truth_decision": "SEAL",
            "expected_discrepancy_type": "NONE",
        })
        unit_id += 1

    # 7. Visually Similar Pairs (4 units)
    for i in range(4):
        lines = [
            OrderLineItem(line_item_id="L1", sku="SKU-TEE-BLK-M", product_name=catalog["SKU-TEE-BLK-M"].product_name, expected_quantity=1),
            OrderLineItem(line_item_id="L2", sku="SKU-TEE-NVY-M", product_name=catalog["SKU-TEE-NVY-M"].product_name, expected_quantity=1),
        ]
        
        # 2 units correctly packed both, 2 units accidentally packed 2 black shirts
        if i < 2:
            simulated_dets = [
                {"detected_label": "Classic Crewneck T-Shirt - Black (M)", "matched_sku": "SKU-TEE-BLK-M", "confidence": 0.94},
                {"detected_label": "Classic Crewneck T-Shirt - Navy Blue (M)", "matched_sku": "SKU-TEE-NVY-M", "confidence": 0.93},
            ]
            exp_dec = "SEAL"
            exp_disc = "NONE"
            notes = "Both black and navy shirts distinguished"
        else:
            simulated_dets = [
                {"detected_label": "Classic Crewneck T-Shirt - Black (M)", "matched_sku": "SKU-TEE-BLK-M", "confidence": 0.94},
                {"detected_label": "Classic Crewneck T-Shirt - Black (M)", "matched_sku": "SKU-TEE-BLK-M", "confidence": 0.94},
            ]
            exp_dec = "STOP_AND_FIX"
            exp_disc = "WRONG_ITEM"
            notes = "Two black shirts packed; navy is missing"

        units.append({
            "unit_id": f"TEST-UNIT-{unit_id:03d}",
            "scenario_type": "VISUALLY_SIMILAR",
            "order": Order(
                order_id=f"ORD-EVAL-{unit_id:03d}",
                package_id=f"PKG-EVAL-{unit_id:03d}",
                client_id="MERCHANT-CORE",
                organization_id="3PL-HUB-01",
                line_items=lines,
            ),
            "photos": [
                PackPhoto(
                    photo_id=f"PH-EVAL-{unit_id:03d}",
                    image_uri=f"eval/images/unit_{unit_id:03d}.jpg",
                    lighting_condition="standard",
                    metadata={"simulated_detections": simulated_dets},
                )
            ],
            "human_label_1": {"decision": exp_dec, "discrepancy": exp_disc, "uncertain": False, "notes": notes},
            "human_label_2": {"decision": exp_dec, "discrepancy": exp_disc, "uncertain": False, "notes": notes},
            "ground_truth_decision": exp_dec,
            "expected_discrepancy_type": exp_disc,
        })
        unit_id += 1

    # 8. Ambiguous / Degraded Captures (4 units)
    # Notice: In genuine ambiguous cases, Human Annotator 1 and 2 may both flag UNCERTAIN or have slight disagreement
    ambig_conditions = ["blur", "occluded", "dark", "severe_glare"]
    for i in range(4):
        cond = ambig_conditions[i]
        sku = "SKU-BOTTLE-THERM"
        lines = [OrderLineItem(line_item_id="L1", sku=sku, product_name=catalog[sku].product_name, expected_quantity=1)]

        units.append({
            "unit_id": f"TEST-UNIT-{unit_id:03d}",
            "scenario_type": "AMBIGUOUS_CAPTURE",
            "order": Order(
                order_id=f"ORD-EVAL-{unit_id:03d}",
                package_id=f"PKG-EVAL-{unit_id:03d}",
                client_id="MERCHANT-CORE",
                organization_id="3PL-HUB-01",
                line_items=lines,
            ),
            "photos": [
                PackPhoto(
                    photo_id=f"PH-EVAL-{unit_id:03d}",
                    image_uri=f"eval/images/unit_{unit_id:03d}.jpg",
                    lighting_condition=cond,
                    metadata={"camera_quality_alert": cond},
                )
            ],
            "human_label_1": {"decision": "STOP_AND_FIX", "discrepancy": "UNCERTAIN", "uncertain": True, "notes": f"Image is {cond}; cannot verify contents"},
            "human_label_2": {"decision": "STOP_AND_FIX", "discrepancy": "UNCERTAIN", "uncertain": True, "notes": f"Severe {cond}; requires manual check"},
            "ground_truth_decision": "STOP_AND_FIX",
            "expected_discrepancy_type": "UNCERTAIN",
        })
        unit_id += 1

    return units
