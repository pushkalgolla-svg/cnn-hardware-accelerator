#!/usr/bin/env python3
"""
scripts/compare_architectures.py
Dual-Architecture Comparative Analysis & Verification Orchestrator.

Loads the verified benchmark metrics from reports/benchmark.json,
runs the multi-vector hardware verification suite, and generates
the side-by-side architecture trade-off report.
"""

import sys
import json
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
BENCHMARK_JSON = REPORTS_DIR / "benchmark.json"

from run_verification import run_full_suite


def main():
    print("==================================================================")
    print("   CNN Hardware Architectures: Comprehensive Comparison & Study   ")
    print("==================================================================")

    # 1. Run multi-vector verification suite
    verif_pass = run_full_suite()
    if not verif_pass:
        print("ERROR: Multi-vector verification failed. Aborting trade-off comparison.")
        sys.exit(1)

    # 2. Check if benchmark.json exists; if not, invoke synth_benchmark
    if not BENCHMARK_JSON.exists():
        print("\n[Benchmark] reports/benchmark.json not found. Running Yosys synthesis...")
        import synth_benchmark
        synth_benchmark.main()

    bench = json.loads(BENCHMARK_JSON.read_text(encoding="utf-8"))
    a = bench["architectures"]["serial_baseline"]
    b = bench["architectures"]["parallel_9mac"]
    comp = bench["comparisons"]

    a_preload_str = f"{a['preload_cycles']} cycles (streaming)"
    b_preload_str = f"{b['preload_cycles']} cycles (preload)"
    a_compute_str = f"{a['compute_cycles']} cycles (9 cyc/px)"
    b_compute_str = f"{b['compute_cycles']} cycles (1 cyc/px)"
    a_total_str = f"{a['total_cycles']} cycles"
    b_total_str = f"{b['total_cycles']} cycles"
    a_mops_str = f"{a['compute_mops']} MOPS"
    b_mops_str = f"{b['compute_mops']} MOPS ({b['compute_mops']/1000.0:.2f} GOPS)"
    a_gates_str = f"{a['gate_count']:,} gates"
    b_gates_str = f"{b['gate_count']:,} gates ({comp['area_ratio']}x)"
    b_compute_spd_str = f"{comp['compute_speedup']}x Faster"
    b_total_spd_str = f"{comp['total_speedup_with_preload']}x Faster"

    print("\n==================================================================")
    print("             ARCHITECTURAL COMPARISON & PPA SUMMARY              ")
    print("==================================================================")
    print(f"{'Metric':<30} | {'Architecture A (Serial)':<24} | {'Architecture B (Parallel)':<24}")
    print("-" * 84)
    print(f"{'MAC Units':<30} | {'1 Serial Multiplier':<24} | {'9 Spatial Multipliers':<24}")
    print(f"{'Adder Tree Architecture':<30} | {'Sequential Accumulator':<24} | {'Single-Cycle Combinational':<24}")
    print(f"{'Buffer Preload Latency':<30} | {a_preload_str:<24} | {b_preload_str:<24}")
    print(f"{'Active Compute Latency':<30} | {a_compute_str:<24} | {b_compute_str:<24}")
    print(f"{'Total Execution Latency':<30} | {a_total_str:<24} | {b_total_str:<24}")
    print(f"{'Compute Speedup':<30} | {'1.00x (Baseline)':<24} | {b_compute_spd_str:<24}")
    print(f"{'Total Speedup (with Preload)':<30} | {'1.00x (Baseline)':<24} | {b_total_spd_str:<24}")
    print(f"{'Peak Compute Density':<30} | {a_mops_str:<24} | {b_mops_str:<24}")
    print(f"{'Standard Cell Count':<30} | {a_gates_str:<24} | {b_gates_str:<24}")
    print(f"{'Functional Verification':<30} | {a['verification_status']:<24} | {b['verification_status']:<24}")
    print("==================================================================")
    print(">>> All verification and architectural comparisons completed successfully! <<<")


if __name__ == "__main__":
    main()
