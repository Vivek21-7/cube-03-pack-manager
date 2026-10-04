"""Generates real image fixtures for data/pack_sample.csv and the 60-unit evaluation suite."""

import os
import csv
from pathlib import Path
from eval.image_synthesizer import render_parcel_image


def generate_sample_fixtures():
    csv_path = Path("data/pack_sample.csv")
    if not csv_path.exists():
        print("data/pack_sample.csv not found")
        return

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            photo_ref = row["photo_refs"].split(";")[0].strip()
            observed = row["observed_in_box"]
            
            # Parse observed SKUs
            skus = []
            for part in observed.split(";"):
                if not part.strip():
                    continue
                if ":" in part:
                    sku, qty = part.split(":")
                    skus.extend([sku.strip()] * int(qty.strip()))
                else:
                    skus.append(part.strip())

            # Decide condition based on unit
            condition = "standard"
            if "blur" in row.get("operator_verdict", "").lower() or "UNIT-0034" in row["unit_id"]:
                condition = "standard"

            render_parcel_image(
                skus_in_box=skus,
                output_path=photo_ref,
                optical_condition=condition,
            )
            print(f"Rendered fixture: {photo_ref} with {len(skus)} item(s)")


if __name__ == "__main__":
    generate_sample_fixtures()
