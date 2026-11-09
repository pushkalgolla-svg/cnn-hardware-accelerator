# Parameterized CNN Hardware Accelerators & Microarchitecture Trade-off Study

[![Verilog-2001](https://img.shields.io/badge/Verilog-2001-blue.svg)](https://en.wikipedia.org/wiki/Verilog)
[![Simulator](https://img.shields.io/badge/Simulator-Icarus_Verilog_12.0-green.svg)](https://steveicarus.github.io/iverilog/)
[![Synthesis](https://img.shields.io/badge/Synthesis-Yosys_0.70_+_ABC-orange.svg)](https://yosyshq.net/yosys/)
[![Regression](https://img.shields.io/badge/Regression-10%2F10_Bit--Exact_Pass-brightgreen.svg)]()
[![Live Demo](https://img.shields.io/badge/Live_Dashboard-cnn--hardware--accelerator.vercel.app-000000?style=flat&logo=vercel&logoColor=white)](https://cnn-hardware-accelerator.vercel.app)

> 🌐 **Interactive Dashboard & Exploration**: [https://cnn-hardware-accelerator.vercel.app](https://cnn-hardware-accelerator.vercel.app)  
> *Notice: The web dashboard is a client-side visual simulation and architectural exploration interface. Full cycle-accurate digital simulations were executed locally using Icarus Verilog (`iverilog`/`vvp`), and ASIC gate-level standard cell benchmarks were generated using Yosys Open Synthesis Suite + ABC.*

---

## 🌟 Overview & Engineering Highlights

This repository contains synthesizable Verilog-2001 RTL designs, race-free verification testbenches, and open-source EDA synthesis automation for two contrasting integer 2D Convolution CNN Accelerators:

1. **Architecture A (Serial Baseline)**:
   - **Datapath**: 1 dedicated $8 \times 8$-bit unsigned hardware multiplier and a 24-bit accumulator register.
   - **Address Generation**: Dynamic 2D address generator calculating memory addresses combinationally (`{row[2:0], col[2:0]}`), streaming data cycle-by-cycle without internal SRAM buffers.
   - **Area Footprint**: Ultra-compact silicon footprint of **2,474 standard CMOS gates**.
   - **Latency**: 324 active compute cycles (9 cycles/pixel $\times$ 36 pixels) + 1 cycle done pulse = 325 total execution cycles.

2. **Architecture B (Parallel 9-MAC + Combinational Tree)**:
   - **Datapath**: 9 parallel spatial multipliers ($8\text{-bit} \times 8\text{-bit} \to 16\text{-bit}$) feeding a **single-cycle combinational adder tree** (non-pipelined, 3 stages of combinational adders) and ReLU activation ($\max(0, X)$).
   - **Internal Buffers**: Multi-port register storage for a 64-pixel image ($64 \times 8\text{-bit}$) and 9-weight filter ($9 \times 8\text{-bit}$).
   - **Hardware Safety Guards**:
     - *Buffer Write-Protection*: Buffer writes are strictly prohibited during the `COMPUTE` state.
     - *Address Validation*: Address decoding prevents out-of-bounds array access (guarding `kernel_wr_addr < 9`).
   - **Throughput & Speedup**: Computes 1 output pixel per clock cycle. Emits all 36 pixels in **36 active compute cycles** (**$9.00\times$ active compute speedup**).
   - **Area Footprint**: **28,522 standard CMOS gates** ($11.53\times$ area investment for $9.0\times$ arithmetic throughput).

---

## 📊 Rigorous PPA Benchmark Comparison (Yosys 0.70 Synthesis)

All synthesis metrics are extracted reproducibly under identical Yosys + ABC settings using generic CMOS gate mapping (`cmos2` standard cell library: NOT, AND, OR):

| Architectural Metric | Architecture A (Serial Baseline) | Architecture B (Parallel 9-MAC) | Scaling / Speedup Factor |
| :--- | :--- | :--- | :--- |
| **Arithmetic Units** | 1 Serial Multiplier + Acc | **9 Parallel Multipliers + Adder Tree** | $9.0\times$ Datapath Parallelism |
| **Adder Tree Microarchitecture** | Sequential Accumulator | **Single-Cycle Combinational Tree** | Non-pipelined (3 stages logic) |
| **Buffer Preload Cycles** | **0 cycles** (Streaming memory reads) | **73 cycles** (64 image + 9 kernel) | Preload required for parallel array |
| **Active Compute Cycles** | **324 cycles** (9 cycles / pixel) | **36 cycles** (1 cycle / pixel) | **$9.00\times$ Compute Speedup** |
| **Total Execution Cycles** | **325 cycles** | **110 cycles** (73 load + 36 compute + 1) | **$2.95\times$ Total Speedup** |
| **Compute Latency (@ 100 MHz\*)** | $3.24\,\mu\text{s}$ | **$0.36\,\mu\text{s}$** | $9.00\times$ Latency Reduction |
| **Total Latency (@ 100 MHz\*)** | $3.25\,\mu\text{s}$ | **$1.10\,\mu\text{s}$** | $2.95\times$ Latency Reduction |
| **Inference Throughput (Compute)** | $308,642$ frames/sec | **$2,777,778$ frames/sec** | $9.00\times$ Higher Throughput |
| **Inference Throughput (Total)** | $307,692$ frames/sec | **$909,091$ frames/sec** | $2.95\times$ Higher Throughput |
| **Peak Arithmetic Density** | $200.0$ MOPS | **$1,800.0$ MOPS ($1.80$ GOPS)** | $9.00\times$ Compute Density |
| **Standard Cell Gates (Yosys)** | **2,474 gates** | **28,522 gates** | $11.53\times$ Silicon Area Investment |
| **Interconnect Wires** | $3,882$ wires | $43,694$ wires | $11.26\times$ Wiring Complexity |
| **Total Wire Bits** | $4,115$ wire bits | $46,085$ wire bits | $11.20\times$ Interconnect Density |
| **Gate Breakdown** | $569$ AND, $1,355$ NOT, $550$ OR | $7,795$ AND, $14,926$ NOT, $5,217$ OR | Optimized via ABC technology mapping |
| **Multi-Vector Regression** | **100% Bit-Exact PASS (5 suites)** | **100% Bit-Exact PASS (5 suites)** | Verified against Python reference |

*\*Note: 100 MHz is a nominal reference clock for architectural cycle-time conversion ($10\,\text{ns}$ period), not a signed-off physical Static Timing Analysis (STA) timing closure, which requires foundry-specific standard cell PDKs and parasitic extraction.*

---

## 🧪 Comprehensive Multi-Vector Verification Suite

The verification environment strictly drives testbench inputs on `negedge clk` to eliminate all sampling race hazards, and validates against an independent Python golden reference model across 5 distinct stimulus suites:

1. **Random (`random`)**: Deterministic pseudo-random distribution (seed 42).
2. **Boundary Minimum (`all_zeros`)**: All image pixels = 0, all weights = 0 $\to$ Output = all 0.
3. **Boundary Maximum (`all_max`)**: All image pixels = 255, all weights = 255 $\to$ Output = all $585,225$ (`0x08EE09`). Tests 24-bit accumulator dynamic range without saturation or overflow.
4. **High-Frequency Pattern (`checkerboard`)**: Alternating `0xAA` ($170$) and `0x55` ($85$).
5. **Impulse Response (`impulse`)**: Single non-zero center pixel ($128$) and center weight ($64$).
6. **Hardware Buffer Protection**: Actively attempts write to `img_buf` during `COMPUTE`; verifies that writes are blocked and outputs remain bit-exact.
7. **Restart & Mid-Computation Reset**: Verifies clean abort and recovery on synchronous reset mid-computation, and back-to-back start without hardware reset.

---

## 🗂️ Directory Layout

```
cnn_accelerator/
├── src/
│   ├── cnn_accel.v                # Architecture A: Serial MAC RTL
│   ├── cnn_accel_synth.v          # Architecture A: Synthesized CMOS gate netlist
│   ├── cnn_accel_parallel.v       # Architecture B: Parallel 9-MAC + Combinational Tree RTL
│   ├── cnn_accel_parallel_synth.v # Architecture B: Synthesized CMOS gate netlist
│   └── candidates/                # Isolated directory for AI-generated candidates
├── tb/
│   ├── tb_cnn.v                   # Race-free testbench for Architecture A
│   └── tb_cnn_parallel.v          # Race-free testbench for Architecture B
├── scripts/
│   ├── golden_model.py            # Independent Python golden reference model
│   ├── run_verification.py        # Offline multi-vector regression suite
│   ├── synth_benchmark.py         # Yosys synthesis & PPA benchmark runner
│   ├── compare_architectures.py   # Dual-architecture comparison runner
│   └── orchestrator.py            # AI hardware architect & verification orchestrator
├── data/
│   ├── image.hex                  # Primary 8x8 input image matrix (64 bytes)
│   ├── kernel.hex                 # Primary 3x3 filter kernel matrix (9 bytes)
│   ├── expected_output.hex        # 6x6 software reference output (36 words)
│   ├── hw_output.hex              # Hardware output from Architecture A
│   └── hw_output_parallel.hex     # Hardware output from Architecture B
├── reports/
│   ├── benchmark.json             # Machine-readable PPA and verification results
│   ├── synthesis_and_ppa_report.md# Detailed synthesis benchmark report
│   └── architecture_tradeoff_study.md # Architectural trade-off analysis
├── dashboard/
│   └── index.html                 # Interactive visual animated 2D convolution GUI
├── .github/workflows/
│   └── ci.yml                     # GitHub Actions CI for linting and simulation
└── README.md
```

---

## 🚀 Execution & Reproduction Guide

### 1. Run Offline RTL Verification (No API key needed)
Runs RTL linting (`iverilog -Wall -g2001`) and all 10 multi-vector regressions:
```bash
python scripts/run_verification.py
```

### 2. Run ASIC Gate-Level Synthesis & PPA Benchmark
Runs Yosys 0.70 + ABC synthesis on both architectures and regenerates `reports/benchmark.json`:
```bash
python scripts/synth_benchmark.py
```

### 3. Run Architectural Trade-off Comparison
```bash
python scripts/compare_architectures.py
```

### 4. Optional: Run AI Hardware Architect (Gemini API)
Generates and isolates candidate RTL in `src/candidates/` without modifying validated RTL:
```bash
# Set your API key
export GEMINI_API_KEY="your_api_key_here"

# Run generator in isolated candidate mode
python scripts/orchestrator.py

# To promote verified candidate to active RTL:
python scripts/orchestrator.py --promote
```

### 5. Launch Interactive Visual Dashboard
Open `dashboard/index.html` (or root `index.html`) in any modern web browser to view the interactive 2D convolution dataflow, step-by-step arithmetic, and verified trade-off metrics.
