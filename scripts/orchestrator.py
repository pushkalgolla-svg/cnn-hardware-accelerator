#!/usr/bin/env python3
"""
scripts/orchestrator.py
AI Hardware Architect, Testbench Generator, and Secure Candidate Promotion Pipeline.

Features:
  - Secure Candidate Promotion: AI-generated RTL is compiled and simulated in isolation.
    It is rigorously validated against the independent Python golden model across all 5 test patterns:
      1. random (deterministic pseudo-random, seed 42)
      2. all_zeros (boundary minimum)
      3. all_max (boundary maximum, 24-bit dynamic range)
      4. checkerboard (high-frequency pattern)
      5. impulse (spatial impulse response)
    Requires exactly 36 correct outputs for each pattern.
    Never overwrites validated RTL unless every check passes and --promote is specified.
  - Offline-first: Runs verification suites locally without requiring API keys.
"""

import os
import sys
import re
import argparse
import subprocess
from pathlib import Path
from typing import Tuple

# Optional dotenv support
try:
    from dotenv import load_dotenv
    load_dotenv()
    script_dir = Path(__file__).resolve().parent
    load_dotenv(script_dir.parent / ".env")
    load_dotenv(script_dir.parent.parent / "ai_verification" / ".env")
except ImportError:
    pass

# Configure directories
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
TB_DIR = PROJECT_ROOT / "tb"
DATA_DIR = PROJECT_ROOT / "data"
SIM_DIR = PROJECT_ROOT / "sim"
CANDIDATES_DIR = SRC_DIR / "candidates"

SRC_DIR.mkdir(parents=True, exist_ok=True)
TB_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
SIM_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

# Import independent Python golden model & verification tools
from golden_model import generate_test_vectors, export_hex_files
from run_verification import run_full_suite


def clean_verilog_code(raw_text: str) -> str:
    """Extracts pure Verilog code from LLM response, stripping markdown fences and fixing common syntax traps."""
    pattern = r"```(?:verilog)?\s*(.*?)```"
    matches = re.findall(pattern, raw_text, re.DOTALL | re.IGNORECASE)
    code = max(matches, key=len).strip() if matches else raw_text.strip()

    code = re.sub(r"\bposedge\s+cllk\b", "posedge clk", code)
    code = re.sub(r"\bnegedge\s+cllk\b", "negedge clk", code)
    code = re.sub(r"\b3'd8\b", "6'd8", code)
    code = re.sub(r"\bwire\s+(\[\d+:\d+\]\s+)?next_state", r"reg \1next_state", code)

    if "assign img_data" in code:
        code = re.sub(r"\breg\s+\[7:0\]\s+img_data\b", "wire [7:0] img_data", code)
    if "assign kernel_data" in code:
        code = re.sub(r"\breg\s+\[7:0\]\s+kernel_data\b", "wire [7:0] kernel_data", code)
    if "assign out_data" in code:
        code = re.sub(r"\boutput\s+reg\s+(\[23:0\]\s+)?out_data\b", r"output wire \1out_data", code)
    if "assign out_valid" in code:
        code = re.sub(r"\boutput\s+reg\s+out_valid\b", "output wire out_valid", code)
    if "assign done" in code:
        code = re.sub(r"\boutput\s+reg\s+done\b", "output wire done", code)

    return code


def validate_candidate_rtl(candidate_file: Path) -> Tuple[bool, str]:
    """
    Validates a candidate RTL module in strict isolation against all 5 golden model patterns:
    random, all_zeros, all_max, checkerboard, and impulse.
    Requires exactly 36 correct outputs for each pattern.
    """
    print(f"\n==============================================================")
    print(f"   Candidate Security Audit: Validating {candidate_file.name} ")
    print(f"==============================================================")

    if not candidate_file.exists():
        return False, f"Candidate file not found: {candidate_file}"

    # 1. Compile in isolation with tb_cnn.v
    cand_sim_bin = SIM_DIR / "cnn_cand_sim"
    compile_cmd = [
        "iverilog", "-g2001", "-o", str(cand_sim_bin.name),
        str(candidate_file.resolve()),
        str((TB_DIR / "tb_cnn.v").resolve())
    ]

    print("Step 1: Compiling candidate RTL with Icarus Verilog in isolation...")
    proc = subprocess.run(compile_cmd, cwd=str(SIM_DIR), capture_output=True, text=True)
    if proc.returncode != 0:
        return False, f"Candidate compilation failed:\n{proc.stderr}"
    print("  -> Compilation successful (0 errors).")

    # 2. Test across all 5 test vector suites
    vectors = generate_test_vectors()
    suite_names = ["random", "all_zeros", "all_max", "checkerboard", "impulse"]
    hw_output_path = DATA_DIR / "hw_output.hex"

    print(f"Step 2: Simulating candidate across all {len(suite_names)} test patterns...")

    for pattern_name in suite_names:
        export_hex_files(pattern_name)
        expected_vals = vectors[pattern_name]["expected"]

        # Run candidate simulation
        run_proc = subprocess.run(["vvp", str(cand_sim_bin.name)], cwd=str(SIM_DIR), capture_output=True, text=True)
        if run_proc.returncode != 0:
            export_hex_files("random")
            return False, f"Simulation crashed on pattern '{pattern_name}':\n{run_proc.stderr}"

        # Validate outputs
        if not hw_output_path.exists():
            export_hex_files("random")
            return False, f"Hardware output file not generated on pattern '{pattern_name}'"

        tokens = hw_output_path.read_text(encoding="utf-8").split()
        if len(tokens) != 36:
            export_hex_files("random")
            return False, f"Pattern '{pattern_name}' produced {len(tokens)} outputs, expected exactly 36!"

        hw_vals = [int(tok, 16) for tok in tokens]
        for idx in range(36):
            if hw_vals[idx] != expected_vals[idx]:
                r, c = idx // 6, idx % 6
                export_hex_files("random")
                return False, (
                    f"Pattern '{pattern_name}' mismatch at pixel [{r},{c}] (idx {idx}): "
                    f"Candidate=0x{hw_vals[idx]:06x} ({hw_vals[idx]}), Expected=0x{expected_vals[idx]:06x} ({expected_vals[idx]})"
                )

        print(f"  [{pattern_name:<13}] PASS: 36/36 bit-exact outputs match Python golden model.")

    # Restore primary test vectors
    export_hex_files("random")
    return True, "All 5 test patterns passed with 36/36 bit-exact outputs."


def run_ai_generation(model, promote: bool = False) -> bool:
    print("\n[AI Architect] Prompting Gemini for candidate Verilog RTL...")
    prompt_rtl = """You are an expert Senior Digital Design Engineer and ASIC Architect.
Write synthesizable Verilog-2001 RTL for a basic Convolutional Neural Network (CNN) 2D Convolution Accelerator.
Specifications:
1. Module Name: cnn_accel
2. Fixed-shape 2D convolution of an 8x8 unsigned 8-bit image with a 3x3 unsigned 8-bit kernel -> 6x6 output (36 pixels).
3. Area-minimal serial MAC unit with 24-bit accumulator and 3-state FSM (IDLE, COMPUTE, DONE).
4. Memory ports: img_addr [5:0], img_data [7:0], kernel_addr [3:0], kernel_data [7:0].
5. Output ports: out_data [23:0], out_valid (1 cycle pulse per pixel), done (1 cycle pulse after 36th pixel).
6. Robust 2D address generation:
   assign img_addr = {out_row + kr, out_col + kc};
   assign kernel_addr = (kr * 3) + kc;
7. Ensure clean synchronous active-high reset on clk.
Output ONLY valid, synthesizable Verilog-2001 code enclosed in a ```verilog code block."""

    resp_rtl = model.generate_content(prompt_rtl)
    cand_rtl_code = clean_verilog_code(resp_rtl.text)
    cand_rtl_file = CANDIDATES_DIR / "cnn_accel_candidate.v"
    cand_rtl_file.write_text(cand_rtl_code + "\n", encoding="utf-8")
    print(f"[AI Architect] Candidate RTL saved to isolated candidate directory: {cand_rtl_file}")

    # Validate candidate in strict isolation
    passed, msg = validate_candidate_rtl(cand_rtl_file)
    if not passed:
        print(f"\n[PROMOTION BLOCKED] Candidate failed validation: {msg}")
        print("[SAFETY GUARD] Validated RTL in src/cnn_accel.v was NOT modified.")
        return False

    print(f"\n>>> CANDIDATE FULLY VERIFIED: {msg} <<<")
    if promote:
        validated_file = SRC_DIR / "cnn_accel.v"
        validated_file.write_text(cand_rtl_code + "\n", encoding="utf-8")
        print(f"[PROMOTION SUCCESSFUL] Candidate promoted to validated RTL: {validated_file}")
    else:
        print("[ISOLATION PRESERVED] Candidate passed all 5 test patterns.")
        print("Candidate retained in src/candidates/. Pass --promote to explicitly replace validated RTL.")

    return True


def main():
    parser = argparse.ArgumentParser(description="CNN Accelerator AI Orchestrator & Candidate Promotion Pipeline")
    parser.add_argument("--offline", action="store_true", help="Run local offline regression suite on validated RTL")
    parser.add_argument("--validate-candidate", type=str, help="Validate an existing candidate RTL file against all 5 golden model patterns")
    parser.add_argument("--promote", action="store_true", help="Promote candidate only if all 5 golden model tests pass 100%")
    args = parser.parse_args()

    # Manual candidate validation option (works 100% offline)
    if args.validate_candidate:
        cand_path = Path(args.validate_candidate)
        passed, msg = validate_candidate_rtl(cand_path)
        if passed:
            print(f"\n>>> VALIDATION SUCCESS: {msg}")
            if args.promote:
                validated_file = SRC_DIR / "cnn_accel.v"
                validated_file.write_text(cand_path.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"[PROMOTION SUCCESSFUL] Promoted {cand_path.name} to {validated_file.name}")
            sys.exit(0)
        else:
            print(f"\n>>> VALIDATION FAILED: {msg}")
            print("[SAFETY GUARD] Validated RTL was NOT modified.")
            sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if args.offline or not api_key:
        if not api_key and not args.offline:
            print("Notice: GEMINI_API_KEY environment variable not set.")
        print("[Offline Mode] Executing offline multi-vector verification suite on validated RTL...")
        ok = run_full_suite()
        sys.exit(0 if ok else 1)

    print("==============================================================")
    print("   AI CNN Hardware Accelerator Pipeline (Gemini + Verilog)   ")
    print("==============================================================")

    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    ok = run_ai_generation(model, promote=args.promote)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
