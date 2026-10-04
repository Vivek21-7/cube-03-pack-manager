"""Real Image Synthesizer and Fixture Generator.

Renders realistic top-down warehouse packing box images with:
- Corrugated kraft box cartons and internal padding
- Distinct SKU visual assets, colors, barcodes, and bounding labels
- Photorealistic optical effects: standard focus, Gaussian blur, specular glare, low-light darkness, and occlusion flaps.
"""

import os
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance


# Visual catalog attributes for rendering real item shapes and colors
SKU_VISUAL_PROPERTIES = {
    "SKU-CABLE-USBC": {"color": (30, 30, 30), "accent": (255, 255, 255), "shape": "coiled_cable", "label": "USB-C CABLE 1M"},
    "SKU-BOTTLE-750": {"color": (70, 130, 180), "accent": (200, 200, 200), "shape": "cylinder", "label": "SS BOTTLE 750ml"},
    "SKU-PUZZLE-500": {"color": (178, 34, 34), "accent": (255, 215, 0), "shape": "box_rect", "label": "PUZZLE 500-PC"},
    "SKU-TOWEL-BLU": {"color": (30, 144, 255), "accent": (240, 248, 255), "shape": "folded_fabric", "label": "GYM TOWEL (BLUE)"},
    "SKU-SERUM-30": {"color": (218, 165, 32), "accent": (255, 255, 255), "shape": "dropper_box", "label": "VIT-C SERUM 30ml"},
    "SKU-PROT-1KG": {"color": (40, 40, 40), "accent": (220, 20, 60), "shape": "large_tub", "label": "WHEY PROTEIN 1kg"},
    "SKU-CANDLE-3": {"color": (238, 232, 170), "accent": (139, 69, 19), "shape": "candle_trio", "label": "CANDLE 3-PACK"},
    "SKU-LAMP-LED": {"color": (245, 245, 245), "accent": (0, 0, 0), "shape": "elongated_box", "label": "LED DESK LAMP"},
    "SKU-MUG-11": {"color": (240, 240, 240), "accent": (70, 70, 70), "shape": "mug_circle", "label": "CERAMIC MUG 11oz"},
    "SKU-LEASH-6FT": {"color": (255, 69, 0), "accent": (50, 50, 50), "shape": "dog_leash", "label": "DOG LEASH 6FT"},
    # Foreign / unmanifested item variants
    "EXTRA_BOX_CUTTER": {"color": (255, 215, 0), "accent": (192, 192, 192), "shape": "utility_knife", "label": "[TOOL] BOX CUTTER"},
    "WRONG_MUG_RED": {"color": (220, 20, 60), "accent": (255, 255, 255), "shape": "mug_circle", "label": "RED MUG (WRONG SKU)"},
    "WRONG_CABLE_LIGHTNING": {"color": (220, 220, 220), "accent": (0, 120, 215), "shape": "coiled_cable", "label": "LIGHTNING CABLE (WRONG)"},
}


def render_parcel_image(
    skus_in_box: List[str],
    output_path: str,
    optical_condition: str = "standard",
    width: int = 800,
    height: int = 800,
) -> Dict[str, Any]:
    """Renders a real parcel photograph and saves it to disk."""
    # 1. Base Carton background (Corrugated cardboard brown)
    img = Image.new("RGB", (width, height), color=(188, 143, 96))
    draw = ImageDraw.Draw(img)

    # Outer carton flaps and tape lines
    draw.rectangle([10, 10, width - 10, height - 10], outline=(140, 95, 50), width=6)
    # Inner box void / shadow
    draw.rectangle([40, 40, width - 40, height - 40], fill=(210, 175, 130), outline=(130, 85, 40), width=4)
    
    # Internal kraft packing paper / crinkle fill
    for i in range(12):
        x1 = 50 + (i * 55) % (width - 120)
        y1 = 50 + (i * 65) % (height - 120)
        draw.arc([x1, y1, x1 + 100, y1 + 70], start=0, end=180, fill=(195, 155, 110), width=2)

    # 2. Render physical items inside the carton
    num_items = len(skus_in_box)
    cols = 2 if num_items <= 4 else 3
    rows = math.ceil(num_items / cols) if num_items > 0 else 1
    
    slot_w = (width - 120) // max(1, cols)
    slot_h = (height - 120) // max(1, rows)

    item_detections = []

    for idx, sku in enumerate(skus_in_box):
        r = idx // cols
        c = idx % cols
        
        cx = 60 + c * slot_w + slot_w // 2
        cy = 60 + r * slot_h + slot_h // 2
        
        props = SKU_VISUAL_PROPERTIES.get(sku, {
            "color": (120, 120, 120),
            "accent": (255, 255, 255),
            "shape": "box_rect",
            "label": sku,
        })

        color = props["color"]
        accent = props["accent"]
        label = props["label"]
        shape = props["shape"]

        item_w = min(slot_w - 30, 180)
        item_h = min(slot_h - 30, 180)

        bx0 = cx - item_w // 2
        by0 = cy - item_h // 2
        bx1 = cx + item_w // 2
        by1 = cy + item_h // 2

        # Draw item shadow
        draw.rectangle([bx0 + 6, by0 + 6, bx1 + 6, by1 + 6], fill=(150, 115, 80))

        # Draw shape based on item type
        if shape == "cylinder":
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=25, fill=color, outline=accent, width=3)
            draw.ellipse([bx0 + 10, by0 + 10, bx1 - 10, by0 + 40], fill=accent)
        elif shape == "mug_circle":
            draw.ellipse([bx0, by0, bx1, by1], fill=color, outline=accent, width=4)
            draw.ellipse([bx0 + 20, by0 + 20, bx1 - 20, by1 - 20], fill=(210, 175, 130), outline=accent, width=2)
            # handle
            draw.arc([bx1 - 15, cy - 20, bx1 + 25, cy + 20], start=270, end=90, fill=color, width=8)
        elif shape == "coiled_cable":
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=15, fill=(240, 240, 240), outline=(100, 100, 100), width=2)
            for loop in range(3):
                draw.ellipse([bx0 + 15 + loop * 10, by0 + 20 + loop * 8, bx1 - 15 - loop * 10, by1 - 20 - loop * 8], outline=color, width=6)
        elif shape == "utility_knife":
            draw.polygon([(bx0, cy), (bx1 - 20, by0), (bx1, by0 + 15), (bx0 + 20, by1)], fill=color, outline=accent)
        else:
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=10, fill=color, outline=accent, width=3)

        # Draw product label & barcode lines on package
        draw.rectangle([bx0 + 10, cy - 12, bx1 - 10, cy + 12], fill=(255, 255, 255, 220))
        draw.text((bx0 + 14, cy - 8), label[:18], fill=(0, 0, 0))
        
        # Simulated barcode
        for b_i in range(12):
            bx = bx0 + 15 + b_i * 8
            draw.line([(bx, cy + 16), (bx, cy + 32)], fill=(0, 0, 0), width=2 if b_i % 3 != 0 else 4)

        # Normalized coordinates (0.0 to 1.0)
        norm_ymin = round(by0 / height, 3)
        norm_xmin = round(bx0 / width, 3)
        norm_ymax = round(by1 / height, 3)
        norm_xmax = round(bx1 / width, 3)

        item_detections.append({
            "sku": sku,
            "label": label,
            "bbox": [norm_ymin, norm_xmin, norm_ymax, norm_xmax],
        })

    # 3. Apply Real Optical / Environmental Degradation
    if optical_condition == "blur":
        img = img.filter(ImageFilter.GaussianBlur(radius=7.5))
    elif optical_condition == "dark":
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.25)
    elif optical_condition in ["glare", "severe_glare"]:
        # Specular blowout spot
        glare_overlay = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        g_draw = ImageDraw.Draw(glare_overlay)
        g_draw.ellipse([width // 3, height // 3, width // 3 + 280, height // 3 + 280], fill=(255, 255, 255, 225))
        glare_overlay = glare_overlay.filter(ImageFilter.GaussianBlur(radius=20))
        img = Image.alpha_composite(img.convert("RGBA"), glare_overlay).convert("RGB")
    elif optical_condition == "occluded":
        # Box flap folded over bottom half
        draw = ImageDraw.Draw(img)
        draw.polygon([(40, height // 2), (width - 40, height // 2 - 40), (width - 40, height - 40), (40, height - 40)], fill=(155, 110, 65))

    # Ensure parent directories exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, quality=92)

    return {
        "image_path": output_path,
        "width": width,
        "height": height,
        "optical_condition": optical_condition,
        "detections": item_detections,
    }
