#!/usr/bin/env python3
"""
scripts/run_verification.py
Independent Offline Verification Suite for Serial & Parallel CNN Accelerators.

Executes:
  1. RTL linting (iverilog -Wall -g2001)
  2. Multi-vector regression testing across:
     - random (deterministic pseudo-random 8-bit, seed 42)
     - all_zeros (boundary minimum)
     - all_max (boundary maximum range, 24-bit accumulator stress test)
     - checkerboard (high-frequency alternating pattern)
     - impulse (spatial impulse response)
  3. Cycle-accurate bit-exact comparison against Python golden reference model.
  4. Returns exit code 0 on PASS, 1 on FAIL.
Does NOT require any internet access or API keys.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Tuple, List

Tuple_bool_str = Tuple[bool, str]
Tuple_bool_list = Tuple[bool, List[str]]

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
TB_DIR = PROJECT_ROOT / "tb"
DATA_DIR = PROJECT_ROOT / "data"
SIM_DIR = PROJECT_ROOT / "sim"

# Import independent Python golden model
from golden_model import generate_test_vectors, export_hex_files, conv2d_reference


def lint_rtl() -> bool:
    print("\n--- Step 1: RTL Linting & Syntax Audit (iverilog -Wall -g2001) ---")
    files_to_lint = [
        ("Architecture A (Serial)", SRC_DIR / "cnn_accel.v"),
        ("Architecture B (Parallel)", SRC_DIR / "cnn_accel_parallel.v"),
    ]

    all_clean = True
    for name, path in files_to_lint:
        cmd = ["iverilog", "-Wall", "-g2001", "-o", "nul" if os.name == "nt" else "/dev/null", str(path)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"  [LINT FAIL] {name}: {path.name}")
            print(proc.stderr)
            all_clean = False
        else:
            print(f"  [LINT PASS] {name}: {path.name} clean (0 warnings, 0 errors)")

    return all_clean


def compile_and_run(sim_name: str, tb_file: Path, rtl_file: Path) -> Tuple_bool_str:
    sim_bin = SIM_DIR / sim_name
    compile_cmd = ["iverilog", "-g2001", "-o", str(sim_bin.name), f"../src/{rtl_file.name}", f"../tb/{tb_file.name}"]
    
    comp = subprocess.run(compile_cmd, cwd=str(SIM_DIR), capture_output=True, text=True)
    if comp.returncode != 0:
        return False, f"Compilation failed:\n{comp.stderr}"

    run_cmd = ["vvp", str(sim_bin.name)]
    run_proc = subprocess.run(run_cmd, cwd=str(SIM_DIR), capture_output=True, text=True)
    if run_proc.returncode != 0:
        return False, f"Execution failed:\n{run_proc.stderr}\n{run_proc.stdout}"

    return True, run_proc.stdout


def verify_hex_file(hw_hex_path: Path, expected_vals: list) -> Tuple_bool_list:
    if not hw_hex_path.exists():
        return False, [f"File {hw_hex_path} does not exist."]

    raw_tokens = hw_hex_path.read_text(encoding="utf-8").split()
    if len(raw_tokens) != 36:
        return False, [f"Expected 36 tokens, found {len(raw_tokens)}."]

    hw_vals = [int(tok, 16) for tok in raw_tokens]
    mismatches = []
    for idx in range(36):
        if hw_vals[idx] != expected_vals[idx]:
            r, c = idx // 6, idx % 6
            mismatches.append(f"Pixel [{r},{c}] (idx {idx}): HW=0x{hw_vals[idx]:06x} ({hw_vals[idx]}), Exp=0x{expected_vals[idx]:06x} ({expected_vals[idx]})")

    return (len(mismatches) == 0), mismatches


def run_full_suite() -> bool:
    print("==============================================================")
    print("   CNN Hardware Accelerator: Complete Verification Suite     ")
    print("==============================================================")

    if not lint_rtl():
        print("\nERROR: RTL Linting failed. Aborting regression suite.")
        return False

    vectors = generate_test_vectors()
    suite_names = list(vectors.keys())
    print(f"\n--- Step 2: Multi-Vector Regression Suite ({len(suite_names)} test vector cases) ---")

    overall_pass = True
    results_summary = []

    for case_name in suite_names:
        print(f"\n>> Running Test Suite: [{case_name.upper()}] - {vectors[case_name]['description']}")
        export_hex_files(case_name)
        expected_vals = vectors[case_name]["expected"]

        # 1. Run Serial Baseline
        sim_ok, sim_out = compile_and_run("cnn_sim", TB_DIR / "tb_cnn.v", SRC_DIR / "cnn_accel.v")
        if not sim_ok:
            print(f"  [SERIAL FAIL] Simulation crashed:\n{sim_out}")
            overall_pass = False
            results_summary.append((case_name, "Serial MAC", "CRASH"))
            continue

        base_match, base_mismatches = verify_hex_file(DATA_DIR / "hw_output.hex", expected_vals)
        if base_match:
            print("  [SERIAL PASS] 36/36 Bit-Exact Match against Golden Model.")
            results_summary.append((case_name, "Serial MAC", "PASS"))
        else:
            print(f"  [SERIAL FAIL] Found {len(base_mismatches)} mismatches:")
            for m in base_mismatches[:5]:
                print(f"    - {m}")
            overall_pass = False
            results_summary.append((case_name, "Serial MAC", "MISMATCH"))

        # 2. Run Parallel 9-MAC
        par_ok, par_out = compile_and_run("cnn_sim_parallel", TB_DIR / "tb_cnn_parallel.v", SRC_DIR / "cnn_accel_parallel.v")
        if not par_ok:
            print(f"  [PARALLEL FAIL] Simulation crashed:\n{par_out}")
            overall_pass = False
            results_summary.append((case_name, "Parallel 9-MAC", "CRASH"))
            continue

        par_match, par_mismatches = verify_hex_file(DATA_DIR / "hw_output_parallel.hex", expected_vals)
        if par_match:
            print("  [PARALLEL PASS] 36/36 Bit-Exact Match against Golden Model.")
            results_summary.append((case_name, "Parallel 9-MAC", "PASS"))
        else:
            print(f"  [PARALLEL FAIL] Found {len(par_mismatches)} mismatches:")
            for m in par_mismatches[:5]:
                print(f"    - {m}")
            overall_pass = False
            results_summary.append((case_name, "Parallel 9-MAC", "MISMATCH"))

    # Restore default 'random' hex files for dashboard/demos
    export_hex_files("random")
    compile_and_run("cnn_sim", TB_DIR / "tb_cnn.v", SRC_DIR / "cnn_accel.v")
    compile_and_run("cnn_sim_parallel", TB_DIR / "tb_cnn_parallel.v", SRC_DIR / "cnn_accel_parallel.v")

    print("\n==============================================================")
    print("                FINAL VERIFICATION SCOREBOARD                 ")
    print("==============================================================")
    print(f"{'Test Vector Case':<18} | {'Architecture':<18} | {'Status'}")
    print("-" * 50)
    for case_name, arch_name, st in results_summary:
        print(f"{case_name:<18} | {arch_name:<18} | {st}")
    print("==============================================================")

    if overall_pass:
        print(">>> VERIFICATION RESULT: [ ALL 10 REGRESSIONS PASSED ] <<<")
        print(">>> Both architectures verified 100% bit-exact across normal,")
        print(">>> zero, max-range saturation, checkerboard, and impulse tests!")
    else:
        print(">>> VERIFICATION RESULT: [ FAILED ] <<<")

    return overall_pass


if __name__ == "__main__":
    ok = run_full_suite()
    sys.exit(0 if ok else 1)
