#!/usr/bin/env python3
"""
scripts/orchestrator.py
Automated AI Hardware Architect, Testbench Generator, and Verification Pipeline.
Uses google-generativeai SDK to prompt Gemini for Verilog RTL & Testbench,
compiles and simulates with Icarus Verilog, and verifies mathematical equivalence.
"""

import os
import sys
import re
import subprocess
from pathlib import Path

# Optional dotenv support to load local .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
    # Also check parent and sibling directories for .env
    script_dir = Path(__file__).resolve().parent
    load_dotenv(script_dir.parent / ".env")
    load_dotenv(script_dir.parent.parent / "ai_verification" / ".env")
except ImportError:
    pass

import google.generativeai as genai

# Configure directories
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
TB_DIR = PROJECT_ROOT / "tb"
DATA_DIR = PROJECT_ROOT / "data"
SIM_DIR = PROJECT_ROOT / "sim"

SRC_DIR.mkdir(parents=True, exist_ok=True)
TB_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
SIM_DIR.mkdir(parents=True, exist_ok=True)


def clean_verilog_code(raw_text: str) -> str:
    """Extracts pure Verilog code from LLM response, stripping markdown fences and fixing common syntax traps."""
    # Find code within ```verilog ... ``` or ``` ... ```
    pattern = r"```(?:verilog)?\s*(.*?)```"
    matches = re.findall(pattern, raw_text, re.DOTALL | re.IGNORECASE)
    code = max(matches, key=len).strip() if matches else raw_text.strip()

    # Normalize common accidental typos or Verilog bit-width traps
    code = re.sub(r"\bposedge\s+cllk\b", "posedge clk", code)
    code = re.sub(r"\bnegedge\s+cllk\b", "negedge clk", code)
    code = re.sub(r"\b3'd8\b", "6'd8", code)

    # Fix wire vs reg l-value assignments in always blocks
    code = re.sub(r"\bwire\s+(\[\d+:\d+\]\s+)?next_state", r"reg \1next_state", code)
    code = re.sub(r"\bwire\s+(\[\d+:\d+\]\s+)?next_state_wire", r"reg \1next_state_wire", code)

    # Fix continuous assignment to reg in testbench: 'reg [7:0] img_data' -> 'wire [7:0] img_data'
    if "assign img_data" in code:
        code = re.sub(r"\breg\s+\[7:0\]\s+img_data\b", "wire [7:0] img_data", code)
    if "assign kernel_data" in code:
        code = re.sub(r"\breg\s+\[7:0\]\s+kernel_data\b", "wire [7:0] kernel_data", code)

    # Fix continuous assignment to output reg in RTL: 'output reg [23:0] out_data' -> 'output wire [23:0] out_data'
    if "assign out_data" in code:
        code = re.sub(r"\boutput\s+reg\s+(\[23:0\]\s+)?out_data\b", r"output wire \1out_data", code)
    if "assign out_valid" in code:
        code = re.sub(r"\boutput\s+reg\s+out_valid\b", "output wire out_valid", code)
    if "assign done" in code:
        code = re.sub(r"\boutput\s+reg\s+done\b", "output wire done", code)

    return code


def fix_with_gemini(model, file_path: Path, code: str, error_msg: str) -> str:
    """Prompts Gemini to fix any compilation error automatically."""
    print(f"\n[Self-Healing] Asking Gemini to fix compiler error in {file_path.name} ...")
    prompt = f"""The following Verilog file ({file_path.name}) failed compilation with Icarus Verilog:

```verilog
{code}
```

Icarus Verilog compiler error:
{error_msg}

Please fix the error and output ONLY the complete corrected Verilog code in a ```verilog block."""
    resp = model.generate_content(prompt)
    fixed_code = clean_verilog_code(resp.text)
    file_path.write_text(fixed_code + "\n", encoding="utf-8")
    print(f"[Self-Healing] Updated {file_path.name} with AI-corrected code.")
    return fixed_code


def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)
    genai.configure(api_key=api_key)
    # Use gemini-2.5-flash for fast and accurate code generation
    return genai.GenerativeModel("gemini-2.5-flash")


# ==============================================================================
# PART 1: The AI Hardware Architect (RTL Generator)
# ==============================================================================
def generate_rtl(model) -> str:
    print("\n[Part 1] Asking Gemini to act as Digital Design Engineer to create /src/cnn_accel.v ...")

    prompt = """You are an expert Senior Digital Design Engineer and ASIC Architect.
Write synthesizable Verilog-2001 RTL for a basic Convolutional Neural Network (CNN) 2D Convolution Accelerator.

Specifications:
1. Module Name: cnn_accel
2. Functionality:
   - Computes valid 2D convolution of an 8x8 input image with a 3x3 filter kernel.
   - Output feature map size is 6x6 (36 output pixels: row 0..5, col 0..5).
   - Stride is 1, no padding.
   - Pixel formula for output pixel (out_row, out_col):
     out_data = sum_{kr=0..2, kc=0..2} (image[(out_row + kr)*8 + (out_col + kc)] * kernel[kr*3 + kc])
3. Architecture:
   - Contains a Multiply-Accumulate (MAC) unit: product = img_data * kernel_data, added to an accumulator register (at least 24 bits wide).
   - Contains a Finite State Machine (FSM) with states: IDLE, COMPUTE, and DONE.
   - Computes cycle-by-cycle: for each of the 36 output positions, it iterates through the 9 kernel weights/pixel pairs (kr in 0..2, kc in 0..2).
   - In IDLE: wait for start signal. When start is asserted (active-high), initialize counters and accumulator, transition to COMPUTE.
   - In COMPUTE:
     - Output img_addr and kernel_addr combinationally based on current out_row, out_col, kr, kc:
       Use bit-shift or 6-bit multiplication:
       assign img_addr = ((out_row + kr) << 3) + (out_col + kc);
       assign kernel_addr = (kr * 3) + kc;
       IMPORTANT: DO NOT write 3'd8 because 8 requires 4 bits; writing 3'd8 evaluates to 0 in Verilog.
     - On each clock cycle, accumulate: acc <= acc + (img_data * kernel_data);
     - When the 9th MAC step (kr==2 && kc==2) is evaluated:
       assert out_valid for 1 cycle, drive out_data with the complete sum of 9 products, and reset accumulator for next output pixel.
     - Advance coordinates: kc (0..2), kr (0..2), out_col (0..5), out_row (0..5).
     - When all 36 output pixels are computed, transition to DONE.
   - In DONE:
     - Assert done signal high.
     - Transition back to IDLE on next cycle.

4. Module Port Interface:
   module cnn_accel (
       input  wire        clk,
       input  wire        rst,        // Synchronous active-high reset
       input  wire        start,      // 1-cycle active-high pulse to start
       output reg         done,       // High when all 36 outputs finished
       // Memory access ports (requesting data from testbench / memory)
       output wire [5:0]  img_addr,   // 0 to 63
       input  wire [7:0]  img_data,   // 8-bit unsigned pixel
       output wire [3:0]  kernel_addr,// 0 to 8
       input  wire [7:0]  kernel_data,// 8-bit unsigned weight
       // Convolution Output
       output reg  [23:0] out_data,   // 24-bit convolved result
       output reg         out_valid   // 1-cycle pulse when out_data is valid
   );

Rules:
- Output ONLY valid, synthesizable Verilog-2001 code enclosed in a ```verilog code block.
- Do NOT use SystemVerilog syntax (keep it compatible with Icarus Verilog).
- Ensure all registers are properly reset on `rst`.
- Verilog Syntax Rules:
  - DO NOT use continuous `assign` on ports declared as `output reg`. Either assign them directly in `always @(posedge clk)` or declare them as `output wire`.
  - In `always @(*)` combinational blocks, the assigned target MUST be declared as `reg` (e.g., `reg [1:0] next_state;`), NEVER as `wire`.
"""

    response = model.generate_content(prompt)
    rtl_code = clean_verilog_code(response.text)

    rtl_file = SRC_DIR / "cnn_accel.v"
    rtl_file.write_text(rtl_code + "\n", encoding="utf-8")
    print(f"[Part 1] Successfully saved Verilog RTL to {rtl_file}")
    return rtl_code


# ==============================================================================
# PART 2: The AI Testbench Generator (TB Generator)
# ==============================================================================
def generate_testbench(model, rtl_code: str) -> str:
    print("\n[Part 2] Asking Gemini to generate Verilog testbench /tb/tb_cnn.v ...")

    prompt = f"""You are an expert Digital Verification Engineer.
Write an Icarus Verilog testbench for the CNN Accelerator module `cnn_accel`.

Here is the exact Verilog RTL for `cnn_accel.v`:
```verilog
{rtl_code}
```

Requirements for the testbench (`tb_cnn.v`):
1. Module Name: `tb_cnn`.
2. Clocks & Resets:
   - Generate `clk` with a period of 10 time units (e.g., `always #5 clk = ~clk;`).
   - Drive synchronous `rst` active high for 3 clock cycles, then deassert.
   - After reset, assert `start` for 1 clock cycle to trigger the CNN accelerator.
3. Memory & Stimulus:
   - Declare memories:
     `reg [7:0] image_mem [0:63];`
     `reg [7:0] kernel_mem [0:8];`
   - Declare `img_data` and `kernel_data` as `wire [7:0]` (NOT reg), because they are driven by continuous assignments:
     `wire [7:0] img_data = image_mem[img_addr];`
     `wire [7:0] kernel_data = kernel_mem[kernel_addr];`
   - Use `$readmemh` to load memory arrays from hex files:
     ```verilog
     initial begin
         $readmemh("../data/image.hex", image_mem);
         $readmemh("../data/kernel.hex", kernel_mem);
     end
     ```
   - Feed data into the accelerator cycle-by-cycle based on `img_addr` and `kernel_addr`:
     `assign img_data = image_mem[img_addr];`
     `assign kernel_data = kernel_mem[kernel_addr];`
4. Output Capture & File Writing:
   - Open output file: `outfile = $fopen("../data/hw_output.hex", "w");`
   - On every `posedge clk`:
     If `out_valid` is high:
       Write the output pixel value to `outfile` as space-separated or newline-separated hex:
       `$fdisplay(outfile, "%06x", out_data);`
   - When `done` is asserted high:
     `$fclose(outfile);`
     `$display("Hardware simulation finished successfully.");`
     `$finish;`
5. Safety Timeout:
   - Add a timeout mechanism (e.g. `#50000; $display("Error: Simulation Timeout!"); $finish;`) to prevent infinite loops.
6. Provide VCD dumping for waveform debugging:
   `$dumpfile("cnn_sim.vcd"); $dumpvars(0, tb_cnn);`

Rules:
- Output ONLY clean Verilog-2001 code enclosed in a ```verilog code block.
- Compatible with Icarus Verilog (`iverilog`).
"""

    response = model.generate_content(prompt)
    tb_code = clean_verilog_code(response.text)

    tb_file = TB_DIR / "tb_cnn.v"
    tb_file.write_text(tb_code + "\n", encoding="utf-8")
    print(f"[Part 2] Successfully saved Verilog Testbench to {tb_file}")
    return tb_code


# ==============================================================================
# PART 3: Automated Simulation & Verification
# ==============================================================================
def run_simulation(model=None, rtl_code: str = "", tb_code: str = "") -> bool:
    print("\n[Part 3] Compiling and running simulation with Icarus Verilog (iverilog & vvp) ...")

    # The simulation commands run inside SIM_DIR so relative paths ../src, ../tb, ../data match
    compile_cmd = ["iverilog", "-o", "cnn_sim", "../src/cnn_accel.v", "../tb/tb_cnn.v"]
    run_cmd = ["vvp", "cnn_sim"]

    for attempt in range(3):
        print(f"Running compilation (attempt {attempt + 1}): {' '.join(compile_cmd)} in {SIM_DIR}")
        compile_proc = subprocess.run(
            compile_cmd,
            cwd=str(SIM_DIR),
            capture_output=True,
            text=True
        )

        if compile_proc.returncode == 0:
            break

        print("ERROR: iverilog compilation failed!")
        print("--- stderr ---")
        print(compile_proc.stderr)

        if model and attempt < 2:
            err = compile_proc.stderr
            # Fix both files independently if either has errors!
            if "cnn_accel.v" in err:
                rtl_file = SRC_DIR / "cnn_accel.v"
                rtl_code = fix_with_gemini(model, rtl_file, rtl_file.read_text(encoding="utf-8"), err)
            if "tb_cnn.v" in err:
                tb_file = TB_DIR / "tb_cnn.v"
                tb_code = fix_with_gemini(model, tb_file, tb_file.read_text(encoding="utf-8"), err)
        else:
            return False

    print("Compilation successful! Running simulation executable: vvp cnn_sim ...")
    run_proc = subprocess.run(
        run_cmd,
        cwd=str(SIM_DIR),
        capture_output=True,
        text=True
    )

    print("--- Simulation Output ---")
    print(run_proc.stdout.strip())
    if run_proc.stderr:
        print("--- Simulation Stderr ---")
        print(run_proc.stderr.strip())

    if run_proc.returncode != 0:
        print(f"ERROR: vvp simulation failed with return code {run_proc.returncode}")
        return False

    return True


def verify_results() -> bool:
    print("\n[Part 3] Comparing expected_output.hex vs hw_output.hex ...")

    expected_file = DATA_DIR / "expected_output.hex"
    hw_file = DATA_DIR / "hw_output.hex"

    # Also check if hw_output was written to sim/ or data/
    if not hw_file.exists():
        sim_hw_file = SIM_DIR / "hw_output.hex"
        if sim_hw_file.exists():
            hw_file = sim_hw_file
        else:
            print(f"ERROR: Hardware output file {hw_file} not found!")
            return False

    expected_tokens = expected_file.read_text(encoding="utf-8").split()
    hw_tokens = hw_file.read_text(encoding="utf-8").split()

    print(f"Tokens in expected_output.hex: {len(expected_tokens)}")
    print(f"Tokens in hw_output.hex:       {len(hw_tokens)}")

    if len(expected_tokens) != 36:
        print(f"WARNING: Expected exactly 36 outputs, got {len(expected_tokens)}")
    if len(hw_tokens) != 36:
        print(f"ERROR: Hardware output contains {len(hw_tokens)} values, expected 36!")

    expected_vals = [int(tok, 16) for tok in expected_tokens]
    hw_vals = [int(tok, 16) for tok in hw_tokens]

    all_matched = True
    mismatches = []

    print("\n==========================================================================")
    print("                    HARDWARE ACCELERATOR VERIFICATION REPORT              ")
    print("==========================================================================")
    print(f"{'Idx':<4} | {'Row':<3} {'Col':<3} | {'Expected (Hex)':<14} {'Expected (Dec)':<14} | {'HW (Hex)':<10} {'HW (Dec)':<10} | {'Status'}")
    print("-" * 74)

    min_len = min(len(expected_vals), len(hw_vals))
    for i in range(min_len):
        r = i // 6
        c = i % 6
        exp_v = expected_vals[i]
        hw_v = hw_vals[i]
        matched = (exp_v == hw_v)
        status = "PASS" if matched else "FAIL"

        if not matched:
            all_matched = False
            mismatches.append((i, r, c, exp_v, hw_v))

        print(f"{i:<4} | {r:<3} {c:<3} | 0x{exp_v:06x}       {exp_v:<14d} | 0x{hw_v:06x}   {hw_v:<10d} | {status}")

    if len(hw_vals) != len(expected_vals):
        all_matched = False

    print("==========================================================================")
    if all_matched and len(expected_vals) == 36:
        print(">>> VERIFICATION RESULT: [ PASS ]")
        print(">>> All 36 convolution outputs from the AI-generated hardware accelerator")
        print(">>> EXACTLY match the Python software reference model!")
    else:
        print(">>> VERIFICATION RESULT: [ FAIL ]")
        print(f">>> Found {len(mismatches)} mismatched values out of 36.")
    print("==========================================================================\n")

    return all_matched, mismatches


def fix_verification_with_gemini(model, rtl_code: str, mismatches: list) -> str:
    """Prompts Gemini to fix any numerical logic or addressing bugs."""
    print("\n[Self-Healing] Asking Gemini to diagnose and fix numerical logic bug in cnn_accel.v ...")
    diag = "\n".join(
        f"  - Pixel {m[0]} (Row {m[1]}, Col {m[2]}): Expected 0x{m[3]:06x} ({m[3]}), Got 0x{m[4]:06x} ({m[4]})"
        for m in mismatches[:10]
    )
    prompt = f"""The following Verilog CNN Accelerator RTL compiled and simulated, but the output did not match the golden model.

RTL Code:
```verilog
{rtl_code}
```

Verification Failure Diagnostic:
{diag}

Note: If outputs repeat identically across rows, check the image address calculation:
In Verilog, writing `3'd8` truncates 8 to 0 because 8 requires 4 bits!
Always use bit-shift or 6-bit multiplication:
`assign img_addr = ((out_row_reg + kr_reg) << 3) + (out_col_reg + kc_reg);`

Please fix the calculation and output ONLY the complete corrected Verilog RTL in a ```verilog block."""
    resp = model.generate_content(prompt)
    fixed_code = clean_verilog_code(resp.text)
    rtl_file = SRC_DIR / "cnn_accel.v"
    rtl_file.write_text(fixed_code + "\n", encoding="utf-8")
    print(f"[Self-Healing] Updated {rtl_file.name} with AI-corrected logic.")
    return fixed_code


def main():
    print("==============================================================")
    print("   AI CNN Hardware Accelerator Pipeline (Gemini + Verilog)   ")
    print("==============================================================")

    model = get_gemini_client()

    # Part 1: Generate RTL
    rtl_code = generate_rtl(model)

    # Part 2: Generate Testbench
    tb_code = generate_testbench(model, rtl_code)

    # Part 3: Compile, Simulate & Verify (with self-healing loop)
    for cycle in range(3):
        sim_ok = run_simulation(model=model, rtl_code=rtl_code, tb_code=tb_code)
        if not sim_ok:
            print("Simulation failed. Aborting verification.")
            sys.exit(1)

        verify_ok, mismatches = verify_results()
        if verify_ok:
            print("\n>>> PIPELINE SUCCESS: 100% Bit-Exact Verification Achieved! <<<")
            return

        if cycle < 2:
            print(f"\n[Self-Healing] Detected {len(mismatches)} calculation mismatches. Triggering AI logic repair...")
            rtl_file = SRC_DIR / "cnn_accel.v"
            rtl_code = fix_verification_with_gemini(model, rtl_file.read_text(encoding="utf-8"), mismatches)
        else:
            print("\nERROR: Verification failed after self-healing attempts.")
            sys.exit(1)


if __name__ == "__main__":
    main()
