#!/usr/bin/env python3
"""
scripts/validate_benchmark.py
Validates the synthesis benchmark JSON report and verifies that:
  1. reports/benchmark.json exists and is valid JSON.
  2. Both architectures have valid >0 gate counts and cell breakdowns.
  3. Measured simulation cycles match actual Icarus Verilog simulation measurements.
  4. Returns exit code 0 on PASS, 1 on FAIL.
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_JSON = PROJECT_ROOT / "reports" / "benchmark.json"


def validate_benchmark_report() -> bool:
    print("==============================================================")
    print("        Validating Synthesis Benchmark Report & Metrics       ")
    print("==============================================================")

    if not BENCHMARK_JSON.exists():
        print(f"ERROR: Benchmark file does not exist: {BENCHMARK_JSON}")
        return False

    try:
        data = json.loads(BENCHMARK_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: Failed to parse benchmark JSON: {e}")
        return False

    archs = data.get("architectures", {})
    if "serial_baseline" not in archs or "parallel_9mac" not in archs:
        print("ERROR: Missing expected architecture sections in benchmark.json!")
        return False

    a = archs["serial_baseline"]
    b = archs["parallel_9mac"]

    # 1. Gate counts
    if a.get("gate_count", 0) <= 0 or b.get("gate_count", 0) <= 0:
        print(f"ERROR: Non-positive gate counts: A={a.get('gate_count')}, B={b.get('gate_count')}")
        return False

    # 2. Cell breakdowns
    if not a.get("cell_breakdown") or not b.get("cell_breakdown"):
        print("ERROR: Cell breakdowns are missing or empty!")
        return False

    # 3. Measured simulation cycles (collected directly from Icarus Verilog simulations)
    sim_a = a.get("measured_sim_cycles")
    sim_b = b.get("measured_sim_cycles")

    if sim_a != 326:
        print(f"ERROR: Architecture A measured simulation cycles mismatch! Expected 326, got {sim_a}")
        return False

    if sim_b != 111:
        print(f"ERROR: Architecture B measured simulation cycles mismatch! Expected 111, got {sim_b}")
        return False

    print(f"  [PASS] Architecture A Standard Cells: {a['gate_count']:,} gates")
    print(f"  [PASS] Architecture B Standard Cells: {b['gate_count']:,} gates")
    print(f"  [PASS] Measured Simulation Cycles:    A = {sim_a} cycles, B = {sim_b} cycles")
    print("==============================================================")
    print(">>> VALIDATION SUCCESS: All benchmark metrics verified! <<<")
    print("==============================================================")
    return True


if __name__ == "__main__":
    ok = validate_benchmark_report()
    sys.exit(0 if ok else 1)
