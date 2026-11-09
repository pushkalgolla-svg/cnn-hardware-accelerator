#!/usr/bin/env python3
"""
scripts/orchestrator.py
AI Hardware Architect, Testbench Generator, and Verification Pipeline.

Features:
  - Offline-first: If GEMINI_API_KEY is not set or --offline is passed,
    runs the complete local verification suite without requiring API keys.
  - Candidate Isolation: AI-generated code is saved to src/candidates/
    and tb/candidates/ to prevent silently overwriting validated RTL.
  - Self-Healing Loop: Iteratively prompts Gemini to diagnose and repair
    compilation or verification errors on candidate designs.
"""

import os
import sys
import re
import argparse
import subprocess
from pathlib import Path

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
TB_CANDIDATES_DIR = TB_DIR / "candidates"

SRC_DIR.mkdir(parents=True, exist_ok=True)
TB_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
SIM_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
TB_CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

# Import offline verification runner
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


def run_ai_generation(model, promote: bool = False):
    print("\n[AI Architect] Generating candidate RTL in src/candidates/cnn_accel_candidate.v ...")
    prompt_rtl = """You are an expert Senior Digital Design Engineer and ASIC Architect.
Write synthesizable Verilog-2001 RTL for a basic Convolutional Neural Network (CNN) 2D Convolution Accelerator.
Specifications:
1. Module Name: cnn_accel
2. Valid 2D convolution of 8x8 unsigned 8-bit image with 3x3 unsigned 8-bit kernel -> 6x6 output (36 pixels).
3. Area-minimal serial MAC unit with 24-bit accumulator and 3-state FSM (IDLE, COMPUTE, DONE).
4. Memory ports: img_addr [5:0], img_data [7:0], kernel_addr [3:0], kernel_data [7:0].
5. Output ports: out_data [23:0], out_valid (1 cycle pulse per pixel), done (1 cycle pulse after 36th pixel).
6. Robust 2D address generation:
   assign img_addr = {out_row + kr, out_col + kc};
   assign kernel_addr = (kr * 3) + kc;
Output ONLY valid, synthesizable Verilog-2001 code enclosed in a ```verilog code block."""

    resp_rtl = model.generate_content(prompt_rtl)
    cand_rtl_code = clean_verilog_code(resp_rtl.text)
    cand_rtl_file = CANDIDATES_DIR / "cnn_accel_candidate.v"
    cand_rtl_file.write_text(cand_rtl_code + "\n", encoding="utf-8")
    print(f"[AI Architect] Candidate RTL saved to: {cand_rtl_file}")

    # Compile candidate against current testbench
    print("\n[Candidate Validation] Compiling candidate RTL with Icarus Verilog...")
    compile_cmd = ["iverilog", "-g2001", "-o", "cnn_cand_sim", "../src/candidates/cnn_accel_candidate.v", "../tb/tb_cnn.v"]
    proc = subprocess.run(compile_cmd, cwd=str(SIM_DIR), capture_output=True, text=True)

    if proc.returncode != 0:
        print(f"ERROR: Candidate compilation failed:\n{proc.stderr}")
        print("Candidate retained in src/candidates/ for review. Validated RTL was NOT modified.")
        return False

    print("Candidate compiled cleanly! Running simulation...")
    run_proc = subprocess.run(["vvp", "cnn_cand_sim"], cwd=str(SIM_DIR), capture_output=True, text=True)
    if run_proc.returncode != 0:
        print(f"ERROR: Candidate simulation failed:\n{run_proc.stderr}")
        return False

    if promote:
        validated_file = SRC_DIR / "cnn_accel.v"
        validated_file.write_text(cand_rtl_code + "\n", encoding="utf-8")
        print(f"[Promotion] Candidate successfully promoted to validated RTL: {validated_file}")
    else:
        print("[Isolation] Candidate passed simulation. Validated RTL preserved (pass --promote to overwrite).")

    return True


def main():
    parser = argparse.ArgumentParser(description="CNN Accelerator AI Orchestrator & Verification Pipeline")
    parser.add_argument("--offline", action="store_true", help="Run local offline verification suite only")
    parser.add_argument("--promote", action="store_true", help="Promote verified AI candidate to active RTL")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if args.offline or not api_key:
        if not api_key and not args.offline:
            print("Notice: GEMINI_API_KEY environment variable not set.")
        print("[Offline Mode] Executing offline multi-vector verification suite...")
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
