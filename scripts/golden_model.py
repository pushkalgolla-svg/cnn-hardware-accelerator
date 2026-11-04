#!/usr/bin/env python3
"""
scripts/golden_model.py
Generates random 8x8 image and 3x3 kernel (8-bit unsigned integers),
computes 2D valid convolution reference output, and exports hex data files.
"""

import os
import random
from pathlib import Path

def generate_and_save():
    # Set seed for deterministic reproducibility
    random.seed(42)

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate 8x8 image (64 elements, 8-bit unsigned: 0 to 255)
    image = [[random.randint(0, 255) for _ in range(8)] for _ in range(8)]

    # 2. Generate 3x3 kernel (9 elements, 8-bit unsigned: 0 to 255)
    kernel = [[random.randint(0, 255) for _ in range(3)] for _ in range(3)]

    # 3. Compute 2D valid convolution: (8 - 3 + 1) x (8 - 3 + 1) = 6x6 output
    out_height = 8 - 3 + 1
    out_width = 8 - 3 + 1
    expected_output = []

    for r in range(out_height):
        row_out = []
        for c in range(out_width):
            acc = 0
            for ki in range(3):
                for kj in range(3):
                    acc += image[r + ki][c + kj] * kernel[ki][kj]
            row_out.append(acc)
        expected_output.append(row_out)

    # 4. Flatten arrays
    flat_image = [pixel for row in image for pixel in row]
    flat_kernel = [weight for row in kernel for weight in row]
    flat_expected = [val for row in expected_output for val in row]

    # 5. Format as space-separated hexadecimal strings
    image_hex_str = " ".join(f"{val:02x}" for val in flat_image)
    kernel_hex_str = " ".join(f"{val:02x}" for val in flat_kernel)
    # Output values can exceed 16-bit (max = 9 * 255 * 255 = 585225 = 0x8EE09), 6 hex digits covers it
    expected_hex_str = " ".join(f"{val:06x}" for val in flat_expected)

    # 6. Save to data directory
    image_path = data_dir / "image.hex"
    kernel_path = data_dir / "kernel.hex"
    expected_path = data_dir / "expected_output.hex"

    image_path.write_text(image_hex_str + "\n", encoding="utf-8")
    kernel_path.write_text(kernel_hex_str + "\n", encoding="utf-8")
    expected_path.write_text(expected_hex_str + "\n", encoding="utf-8")

    print("========================================")
    print("CNN Golden Model Data Generation")
    print("========================================")
    print(f"Generated 8x8 Image (64 elements) -> {image_path}")
    print(f"Generated 3x3 Kernel (9 elements)  -> {kernel_path}")
    print(f"Computed 6x6 Output (36 elements) -> {expected_path}")
    print("\n--- 3x3 Kernel (Decimal) ---")
    for row in kernel:
        print("  " + " ".join(f"{v:3d}" for v in row))
    print("\n--- 8x8 Image Sample (First 3 rows) ---")
    for row in image[:3]:
        print("  " + " ".join(f"{v:3d}" for v in row))
    print("\n--- 6x6 Expected Output (First row, Decimal & Hex) ---")
    print("  Dec: " + " ".join(f"{v:7d}" for v in expected_output[0]))
    print("  Hex: " + " ".join(f"{v:06x}" for v in expected_output[0]))
    print("========================================")

if __name__ == "__main__":
    generate_and_save()
