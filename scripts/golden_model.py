#!/usr/bin/env python3
"""
scripts/golden_model.py
Independent Python Software Golden Reference Model for 2D CNN Hardware Accelerators.

Validates 8x8 image (64 unsigned 8-bit integers) convolved with 3x3 kernel
(9 unsigned 8-bit weights) producing a 6x6 output feature map (36 outputs).
Supports multiple test vectors: normal random, all zeros, all max, checkerboard, impulse.
"""

import sys
import random
from pathlib import Path
from typing import List, Tuple, Dict, Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def conv2d_reference(image: List[List[int]], kernel: List[List[int]]) -> List[int]:
    """
    Computes bit-exact 2D valid convolution of 8x8 image with 3x3 kernel.
    Returns 36 flattened output values (row-major order).
    """
    if len(image) != 8 or any(len(row) != 8 for row in image):
        raise ValueError("Image must be an 8x8 matrix.")
    if len(kernel) != 3 or any(len(row) != 3 for row in kernel):
        raise ValueError("Kernel must be a 3x3 matrix.")

    for r in range(8):
        for c in range(8):
            val = image[r][c]
            if not (0 <= val <= 255):
                raise ValueError(f"Image pixel at ({r},{c}) is {val}, outside unsigned 8-bit range [0, 255].")

    for kr in range(3):
        for kc in range(3):
            val = kernel[kr][kc]
            if not (0 <= val <= 255):
                raise ValueError(f"Kernel weight at ({kr},{kc}) is {val}, outside unsigned 8-bit range [0, 255].")

    out_h = 8 - 3 + 1  # 6
    out_w = 8 - 3 + 1  # 6
    outputs = []

    for r in range(out_h):
        for c in range(out_w):
            accum = 0
            for ki in range(3):
                for kj in range(3):
                    accum += image[r + ki][c + kj] * kernel[ki][kj]
            outputs.append(accum)

    assert len(outputs) == 36, f"Expected 36 outputs, got {len(outputs)}"
    return outputs


def generate_test_vectors() -> Dict[str, Dict[str, Any]]:
    """Generates a comprehensive suite of normal and boundary test vectors."""
    vectors = {}

    # 1. Deterministic Random (Normal case, seed 42)
    rng = random.Random(42)
    img_rand = [[rng.randint(0, 255) for _ in range(8)] for _ in range(8)]
    krn_rand = [[rng.randint(0, 255) for _ in range(3)] for _ in range(3)]
    vectors["random"] = {
        "description": "Deterministic pseudo-random 8-bit distribution (seed 42)",
        "image": img_rand,
        "kernel": krn_rand,
        "expected": conv2d_reference(img_rand, krn_rand),
    }

    # 2. Boundary: All Zeros
    img_zeros = [[0 for _ in range(8)] for _ in range(8)]
    krn_zeros = [[0 for _ in range(3)] for _ in range(3)]
    vectors["all_zeros"] = {
        "description": "Boundary condition: All zeros (Image=0, Kernel=0)",
        "image": img_zeros,
        "kernel": krn_zeros,
        "expected": conv2d_reference(img_zeros, krn_zeros),
    }

    # 3. Boundary: All Max (255) - Tests maximum dynamic range without accumulator overflow
    img_max = [[255 for _ in range(8)] for _ in range(8)]
    krn_max = [[255 for _ in range(3)] for _ in range(3)]
    vectors["all_max"] = {
        "description": "Boundary condition: Maximum range (All 255, tests 24-bit accumulator)",
        "image": img_max,
        "kernel": krn_max,
        "expected": conv2d_reference(img_max, krn_max),
    }

    # 4. Pattern: Alternating Checkerboard (0xAA = 170, 0x55 = 85)
    img_check = [[170 if (r + c) % 2 == 0 else 85 for c in range(8)] for r in range(8)]
    krn_check = [[85 if (r + c) % 2 == 0 else 170 for c in range(3)] for r in range(3)]
    vectors["checkerboard"] = {
        "description": "High-frequency switching checkerboard pattern (0xAA / 0x55)",
        "image": img_check,
        "kernel": krn_check,
        "expected": conv2d_reference(img_check, krn_check),
    }

    # 5. Impulse: Single non-zero center pixel and single center weight
    img_impulse = [[0 for _ in range(8)] for _ in range(8)]
    img_impulse[3][3] = 128
    krn_impulse = [[0 for _ in range(3)] for _ in range(3)]
    krn_impulse[1][1] = 64
    vectors["impulse"] = {
        "description": "Spatial impulse response test (single non-zero pixel & weight)",
        "image": img_impulse,
        "kernel": krn_impulse,
        "expected": conv2d_reference(img_impulse, krn_impulse),
    }

    # 6. Deterministic Random Suite 2 (seed 100) - Diverse dynamic range
    rng100 = random.Random(100)
    img_r100 = [[rng100.randint(0, 255) for _ in range(8)] for _ in range(8)]
    krn_r100 = [[rng100.randint(0, 255) for _ in range(3)] for _ in range(3)]
    vectors["random_seed100"] = {
        "description": "Deterministic pseudo-random distribution (seed 100)",
        "image": img_r100,
        "kernel": krn_r100,
        "expected": conv2d_reference(img_r100, krn_r100),
    }

    # 7. Deterministic Random Suite 3 (seed 2024) - High-entropy distribution
    rng2024 = random.Random(2024)
    img_r2024 = [[rng2024.randint(0, 255) for _ in range(8)] for _ in range(8)]
    krn_r2024 = [[rng2024.randint(0, 255) for _ in range(3)] for _ in range(3)]
    vectors["random_seed2024"] = {
        "description": "Deterministic pseudo-random distribution (seed 2024)",
        "image": img_r2024,
        "kernel": krn_r2024,
        "expected": conv2d_reference(img_r2024, krn_r2024),
    }

    # 8. Deterministic Random Suite 4 (seed 9999) - Stress-test distribution
    rng9999 = random.Random(9999)
    img_r9999 = [[rng9999.randint(0, 255) for _ in range(8)] for _ in range(8)]
    krn_r9999 = [[rng9999.randint(0, 255) for _ in range(3)] for _ in range(3)]
    vectors["random_seed9999"] = {
        "description": "Deterministic pseudo-random distribution (seed 9999)",
        "image": img_r9999,
        "kernel": krn_r9999,
        "expected": conv2d_reference(img_r9999, krn_r9999),
    }

    return vectors


def export_hex_files(case_name: str = "random", prefix: str = ""):
    """Exports a specified test vector case to standard .hex format in the data directory."""
    vectors = generate_test_vectors()
    if case_name not in vectors:
        raise KeyError(f"Unknown test case '{case_name}'. Available: {list(vectors.keys())}")

    case = vectors[case_name]
    flat_img = [p for row in case["image"] for p in row]
    flat_krn = [w for row in case["kernel"] for w in row]
    flat_exp = case["expected"]

    pfx = f"{prefix}_" if prefix else ""
    img_path = DATA_DIR / f"{pfx}image.hex"
    krn_path = DATA_DIR / f"{pfx}kernel.hex"
    exp_path = DATA_DIR / f"{pfx}expected_output.hex"

    img_path.write_text(" ".join(f"{x:02x}" for x in flat_img) + "\n", encoding="utf-8")
    krn_path.write_text(" ".join(f"{x:02x}" for x in flat_krn) + "\n", encoding="utf-8")
    exp_path.write_text(" ".join(f"{x:06x}" for x in flat_exp) + "\n", encoding="utf-8")

    return img_path, krn_path, exp_path


def main():
    print("==============================================================")
    print("     CNN Accelerator Python Golden Model & Vector Generator    ")
    print("==============================================================")

    vectors = generate_test_vectors()
    print(f"Generated {len(vectors)} independent test suites:")
    for name, v in vectors.items():
        exp = v["expected"]
        print(f"  [{name:<13}] {v['description']}")
        print(f"                Outputs: min={min(exp):<7d} max={max(exp):<7d} (0x{max(exp):06x})")

    # Export default 'random' dataset into primary data files
    img_p, krn_p, exp_p = export_hex_files("random")
    print(f"\n[Export Complete] Primary hex files updated in {DATA_DIR}:")
    print(f"  - Image:    {img_p.name} (64 hex bytes)")
    print(f"  - Kernel:   {krn_p.name} (9 hex bytes)")
    print(f"  - Expected: {exp_p.name} (36 hex words)")
    print("==============================================================")


if __name__ == "__main__":
    main()
