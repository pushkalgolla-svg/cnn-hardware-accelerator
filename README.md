# Autonomous AI-Designed CNN Hardware Accelerator & Architecture Trade-off Study

[![Live Demo](https://img.shields.io/badge/Live_Demo-cnn--hardware--accelerator.vercel.app-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://cnn-hardware-accelerator.vercel.app)
[![Verilog-2001](https://img.shields.io/badge/Verilog-2001-blue.svg)](https://en.wikipedia.org/wiki/Verilog)
[![Simulation](https://img.shields.io/badge/Simulator-Icarus_Verilog_12.0-green.svg)](https://steveicarus.github.io/iverilog/)
[![Synthesis](https://img.shields.io/badge/Synthesis-Yosys_0.70-orange.svg)](https://yosyshq.net/yosys/)
[![Verification](https://img.shields.io/badge/Verification-100%25_Bit--Exact_Pass-brightgreen.svg)]()
[![AI-Orchestrator](https://img.shields.io/badge/AI_EDA-Google_Gemini_Flash-purple.svg)](https://ai.google.dev/)

> 🚀 **Live Interactive Visualizer**: [https://cnn-hardware-accelerator.vercel.app](https://cnn-hardware-accelerator.vercel.app)

An autonomous, closed-loop AI Electronic Design Automation (EDA) framework where Google Gemini acts as both the **Digital Hardware Architect** and **Verification Engineer** to design, simulate, self-heal, synthesize, and benchmark two contrasting integer 2D Convolution CNN Accelerators in Verilog.

---

## 🌟 Key Project Highlights

- **Dual Microarchitecture Implementation**:
  - **Architecture A (Serial Baseline)**: 1 serial MAC core with dynamic 2D address generation. Ultra-compact ($2,270$ gates), ideal for IoT/edge devices.
  - **Architecture B (Parallel 9-MAC Engine)**: 9 concurrent spatial multipliers + 3-stage adder tree + ReLU activation. Computes 1 output per clock cycle (**$9.17\times$ speedup**, $1.80$ GOPS).
- **Self-Healing EDA Orchestration**: Real-time compiler feedback loop using Python and the Gemini API that intercepts Icarus Verilog (`iverilog`) syntax/elaboration diagnostics and automatically repairs RTL and testbench code without human intervention.
- **Bit-Exact Verification**: 100% mathematical regression match ($36/36$ output feature pixels) across both architectures against a NumPy/Python software golden reference model.
- **ASIC Gate-Level Synthesis**: Synthesized to a generic CMOS standard cell library using **Yosys 0.70 + ABC**, extracting cell area, wire counts, and PPA metrics.
- **Interactive Visual Dashboard**: Modern, self-contained HTML5 dashboard visualizing real-time sliding 2D convolution and the PPA trade-off curve.

---

## 📊 Side-by-Side PPA Benchmark Comparison (Yosys 0.70 Synthesis)

| Architectural Metric | Baseline Architecture (Serial MAC) | High-Throughput (Parallel 9-MAC) | Scaling / Speedup Factor |
| :--- | :--- | :--- | :--- |
| **MAC Datapath Units** | 1 Serial Multiplier | **9 Parallel Multipliers + Adder Tree** | $9.0\times$ arithmetic parallelism |
| **Active Compute Latency** | 324 clock cycles | **36 clock cycles** | **$9.0\times$ Latency Reduction** |
| **Output Rate** | 1 pixel / 9 cycles | **1 pixel / 1 cycle** | **$9.0\times$ Rate Improvement** |
| **Frame Latency (@ 100 MHz)** | $3.30\,\mu\text{s}$ | **$0.36\,\mu\text{s}$** (compute window) | **$9.17\times$ Faster** |
| **Inference Throughput** | $303,030$ frames/sec | **$2,777,778$ frames/sec** | **$9.17\times$ Higher Throughput** |
| **Compute Performance** | $196.4$ MOPS | **$1,800.0$ MOPS ($1.80$ GOPS)** | **$9.17\times$ Compute Density** |
| **Standard Cell Gate Count** | **2,270 gates** | **43,741 gates** | $19.2\times$ area investment |
| **Logic Breakdown** | $486$ AND, $1,294$ NOT, $490$ OR | $9,297$ AND, $24,687$ NOT, $9,757$ OR | Optimized via ABC technology mapping |
| **Verification Status** | **100% Bit-Exact PASS** | **100% Bit-Exact PASS** | Verified against Python reference |

---

## 🗂️ Repository Directory Structure

```
cnn_accelerator/
├── src/
│   ├── cnn_accel.v                # Architecture A: Serial MAC RTL
│   ├── cnn_accel_synth.v          # Architecture A: Gate-level netlist (Yosys)
│   ├── cnn_accel_parallel.v       # Architecture B: Parallel 9-MAC + ReLU RTL
│   └── cnn_accel_parallel_synth.v # Architecture B: Gate-level netlist (Yosys)
├── tb/
│   ├── tb_cnn.v                   # Testbench for Serial Baseline
│   └── tb_cnn_parallel.v          # Testbench for Parallel 9-MAC
├── scripts/
│   ├── golden_model.py            # Python 2D convolution reference model
│   ├── orchestrator.py            # Autonomous AI generator & verification loop
│   ├── synth_benchmark.py         # Yosys synthesis runner for Baseline
│   └── compare_architectures.py   # Dual-architecture verification & trade-off study
├── data/
│   ├── image.hex                  # 8x8 input image matrix (64 hex values)
│   ├── kernel.hex                 # 3x3 filter kernel matrix (9 hex values)
│   ├── expected_output.hex        # 6x6 software reference output (36 hex values)
│   ├── hw_output.hex              # Hardware output from Architecture A
│   └── hw_output_parallel.hex     # Hardware output from Architecture B
├── sim/
│   ├── cnn_sim.vcd                # Serial architecture waveform dump
│   └── cnn_sim_parallel.vcd       # Parallel architecture waveform dump
├── dashboard/
│   └── index.html                 # Interactive visual animated 2D convolution GUI
└── reports/
    ├── synthesis_and_ppa_report.md# Baseline PPA report
    └── architecture_tradeoff_study.md # Comparative trade-off study
```

---

## 🚀 Quickstart & Execution

### 1. Run the Full Automated AI Pipeline
```powershell
python scripts/orchestrator.py
```

### 2. Run Comparative Architecture Verification & Trade-off Study
```powershell
python scripts/compare_architectures.py
```

### 3. Open Interactive Visual Dashboard
Double-click or open `dashboard/index.html` in any web browser to see the interactive animated 2D convolution visualizer and side-by-side trade-off study.

---

## 💼 Resume Bullet Points

- **AI Silicon Co-Design & Microarchitecture**: Designed and synthesized two parameterized 2D CNN Hardware Accelerators in Verilog-2001—a compact serial MAC architecture (2,270 gates) and a high-throughput 9-MAC parallel architecture (43,741 gates, ReLU activation)—achieving a **9.17x latency reduction (36 cycles, 1.80 GOPS)**.
- **Autonomous Verification Pipeline**: Developed an automated AI-in-the-loop verification orchestrator in Python using Gemini API and Icarus Verilog (`iverilog`/`vvp`), integrating compiler error diagnostic self-healing to achieve 100% bit-exact mathematical verification (36/36 pixels) against a NumPy software golden reference model.
- **ASIC Gate-Level Synthesis & PPA Benchmarking**: Conducted gate-level synthesis targeting a CMOS standard cell library using Yosys 0.70 and ABC, evaluating the silicon area vs. throughput trade-off curve across clock frequencies up to 100 MHz.
