# CNN Hardware Accelerator: Dual-Architecture Synthesis & PPA Benchmark Report

## 1. Executive Summary & Design Scope
- **Design Architecture**: Fixed-shape 2D convolution for an $8 \times 8$ input image, $3 \times 3$ kernel, and $6 \times 6$ output feature map ($36$ output pixels).
- **Arithmetic Precision**: Unsigned 8-bit image pixels ($[0, 255]$), unsigned 8-bit kernel weights ($[0, 255]$), 24-bit accumulation.
- **Technology Mapping Target**: Generic CMOS standard cell logic mapping (`cmos2` library: NOT, AND, OR) via **Yosys 0.71 + ABC**.
- **Architectures Evaluated**:
  - `cnn_accel` (Architecture A: Serial MAC Baseline, area-minimal, streaming address generator)
  - `cnn_accel_parallel` (Architecture B: Parallel 9-MAC + Single-Cycle Combinational Adder Tree + ReLU)
- **Functional Verification**: 100% Bit-Exact Match across 8 independent test suites (Random, All Zeros, All Max, Checkerboard, Impulse, Random Seed 100, 2024, 9999).

> **Engineering & Timing Disclaimer**:
> 100 MHz (10 ns period) is an assumed nominal reference clock for cycle-to-time conversions, NOT a signed-off Static Timing Analysis (STA) timing closure. Synthesis gate counts represent generic standard CMOS logic cells (cmos2: NOT, AND, OR) via Yosys 0.70 + ABC.
> 
> **Area & Silicon Disclaimer**:
> Standard cell counts represent generic Boolean logic gates (cmos2 library: NOT, AND, OR) mapped via Yosys + ABC. These quantify relative logical gate complexity, NOT physical silicon layout area (um^2/mm^2), which requires technology PDK standard cell libraries and physical place-and-route (P&R).
> 
> **Routing Note**:
> Wire counts and wire bits represent internal Yosys RTLIL logical netlist nets, NOT physical layout routing tracks or parasitic interconnect metrics.
> 
> **Mathematical Note on ReLU**:
> For unsigned 8-bit inputs and weights ([0, 255]), all products and sums are strictly non-negative (>= 0). Thus, ReLU(X) = max(0, X) == X is mathematically redundant for this unsigned datapath and serves as an architectural placeholder for signed extensions.

---

## 2. Hardware Resource & Gate Utilization (Yosys Synthesis Breakdown)

The table below explicitly distinguishes **combinational Boolean logic gates** from **sequential storage cells (flip-flops)** and quantifies **internal buffer storage overhead**:

| Metric | Architecture A (Serial Baseline) | Architecture B (Parallel 9-MAC) | Scaling / Ratio |
| :--- | :--- | :--- | :--- |
| **Combinational Logic Cells** | **2,474 gates** | **28,522 gates** | **11.53x Combinational Scaling** |
| **Sequential Cells (DFFs)** | **62 flip-flops** | **614 flip-flops** | **9.9x Sequential Scaling** |
| **Buffer Storage Overhead** | **0 flip-flops** (0% storage) | **584 flip-flops (95.1%)** | 512 image DFFs + 72 kernel DFFs |
| **Datapath / Control DFFs** | **62 flip-flops** | **30 flip-flops** | State, coordinate, & output registers |
| **Total Mapped Cells** | **2,536 cells** | **29,136 cells** | **11.49x Total Cell Scaling** |
| **Cell Breakdown (ABC)** | $and: 569, $not: 1,355, $or: 550 | $and: 7,795, $logic_not: 584, $not: 14,926, $or: 5,217 | Generic CMOS library mapping |
| **RTLIL Logical Nets** | 3,882 nets | 43,694 nets | 11.3x logical nets |
| **RTLIL Wire Bits** | 4,115 bits | 46,085 bits | 11.2x logical bits |
| **Multiplier Units** | 1 Serial Multiplier | 9 Parallel Multipliers | 9.0x arithmetic units |
| **Adder Tree Architecture** | Sequential Accumulator | Single-Cycle Combinational Tree | Non-pipelined (3 stages logic) |
| **Memory Implementation** | On-the-fly streaming reads | Multi-port register array (584 DFFs) | 9 concurrent reads preclude SRAM |
| **Buffer Write Protection** | N/A (Streaming) | Hardware-guarded in IDLE state | Active compute protection |

### Memory Implementation Analysis: Why Register Arrays Instead of SRAM Macros?
In Architecture B, 9 spatial multiplications occur simultaneously every clock cycle. This requires **9 concurrent 8-bit read accesses into `img_buf`** and **9 concurrent 8-bit read accesses into `kernel_buf`** within the very same clock period. Standard ASIC embedded memories (SRAM macros / Block RAMs) offer at most 1 or 2 read ports (single-port or dual-port). Mapping 9 read ports into standard memory macros would require 9-way bank replication or multi-pumping. Consequently, Yosys synthesizes both buffers into a **multi-port register array (584 discrete DFFs with multiplexer address decoders)**. This accounts for **95.1% of all sequential state** in the parallel design.

---

## 3. Measured Simulation Cycles vs. Analytical Estimates

Cycle measurements collected directly from Icarus Verilog simulations match the discrete analytical formulations with 100% precision:

| Metric | Architecture A (Serial) | Architecture B (Parallel) | Speedup / Scaling |
| :--- | :--- | :--- | :--- |
| **Buffer Preload Cycles** | **0 cycles** (Streaming reads) | **73 cycles** (9 krn + 64 img) | Preload required for parallel array |
| **Pure Arithmetic Cycles**| **324 cycles** (9 cyc/pixel) | **36 cycles** (1 cyc/pixel) | **9.0x Compute Speedup** |
| **Active Compute Phase** | **324 cycles** | **38 cycles** (1 start + 36 + 1 done) | **8.58x Active Speedup** |
| **Measured Total Cycles** | **326 cycles** (Icarus simulation) | **111 cycles** (Icarus simulation) | **2.94x Total Speedup** |
| **Analytical Cycle Formula**| $1 + 36 \times 9 + 1 = 326$ cycles | $73 + 1 + 36 + 1 = 111$ cycles | 100% agreement with simulation |
| **Compute Latency (@ 100 MHz\*)** | 3.24 $\mu\text{s}$ | **0.36 $\mu\text{s}$** | $9.0\times$ latency reduction |
| **Total Latency (@ 100 MHz\*)** | 3.26 $\mu\text{s}$ | **1.11 $\mu\text{s}$** | $2.94\times$ total frame speedup |
| **Streaming Throughput (FPS)** | 308,642 FPS | **2,777,778 FPS** | $9.0\times$ higher throughput |
| **Total Throughput with Reload** | 306,748 FPS | **900,901 FPS** | $2.94\times$ total throughput |
| **Peak Arithmetic Density** | 200.0 MOPS | **1800.0 MOPS (1.80 GOPS)** | $9.0\times$ compute density |
| **Verification Status** | 36/36 BIT-EXACT PASS (8/8 suites, 16 regressions) | 36/36 BIT-EXACT PASS (8/8 suites, 16 regressions) | 100% Bit-Exact across 8 suites |

---

## 4. Timing Analysis & Critical Path Evidence

### Technology-Independent Logic Depth & Critical Path Comparison
- **Architecture A (Serial Baseline)**:
  - Critical Path: `clk` $\to$ Coordinate counters (`kr_r`, `kc_r`) $\to$ 2D address generation $\to$ $8 \times 8$ multiplier $\to$ 24-bit sequential accumulator adder $\to$ `acc_r` / `out_data` DFF input.
  - Combinational Stages: 1 Multiplier stage + 1 Accumulator Adder stage.
  - Estimated Gate Depth: **~35 gate levels**.
  - Timing Criticality: **Low** — Short combinational feedback loop.

- **Architecture B (Parallel 9-MAC)**:
  - Critical Path: `clk` $\to$ Coordinate counters (`out_row`, `out_col`) $\to$ Buffer read multiplexers $\to$ 9 parallel $8 \times 8$ multipliers $\to$ 3-stage combinational adder tree (Stage 1: 16-bit; Stage 2: 17-bit; Stage 3: 18-to-20-bit) $\to$ ReLU zero-extension $\to$ `out_data` DFF input.
  - Combinational Stages: 1 Multiplier stage + 3 Combinational Adder stages (Carry chain depth: ~71 bits).
  - Estimated Gate Depth: **~68 gate levels**.
  - Timing Criticality: **High** — The single-cycle 3-stage adder tree forms the primary clock frequency bottleneck.

### Static Timing Analysis (STA) Reproducibility Workflow
To enable physical sign-off timing analysis against commercial or open-source standard cell libraries (e.g., SkyWater 130nm or Nangate 45nm), the repository provides:
1. **SDC Timing Constraints**: `constraints/cnn_accel.sdc`
   - Defines a 100.0 MHz nominal reference clock ($10.0\text{ ns}$ period), $200\text{ ps}$ clock uncertainty margin, and $2.0\text{ ns}$ I/O boundary delays.
2. **OpenSTA Script**: `scripts/run_opensta.tcl`
   - Automated script to link synthesized netlists, apply SDC constraints, and report slack.
   - Run command:
     ```bash
     export LIB_FILE=/path/to/sky130_fd_sc_hd__tt_025C_1v80.lib
     sta scripts/run_opensta.tcl
     ```
3. **STA Auditor**: `python scripts/run_sta.py`

> **Note on 100 MHz Reference**:
> The 100 MHz ($10.0\text{ ns}$) operating frequency is an assumed nominal reference clock for throughput normalization. True physical timing closure requires static timing analysis against a concrete foundry Liberty library (.lib) with physical wire parasitics (SPEF).

---

## 5. Architectural Trade-offs & Deep Engineering Insights

1. **Arithmetic Speedup vs. System-Level Speedup (Amdahl's Law on Buffer Preload)**:
   - Architecture B delivers a **$9.00\times$ arithmetic speedup** during active computation ($36$ vs $324$ cycles).
   - However, when the 73-cycle buffer preload is included, total speedup drops to **$2.94\times$** ($111$ vs $326$ cycles). Preload accounts for **$65.8\%$** of total execution time in single-frame reload mode.
   - *Architectural Implication*: Architecture B is optimally suited for multi-channel CNN cascades where filter weights remain cached in registers across multiple incoming frames or feature maps.

2. **Combinational Tree vs. Pipelined Tree**:
   - Architecture B implements a **single-cycle combinational adder tree** (non-pipelined).
   - This decision eliminates intermediate pipeline registers, saving flip-flop area and ensuring zero initial pipeline latency.
   - The trade-off is a significantly longer combinational path (~68 gate levels vs ~35 gate levels), lowering the theoretical maximum achievable clock frequency ($F_{\max}$) compared to the serial baseline.

3. **Storage Overhead**:
   - Architecture B dedicates **584 flip-flops** ($95.1\%$ of its sequential elements) solely to internal buffer storage to enable single-cycle 9-point spatial convolution.
   - Architecture A achieves complete streaming convolution with **0 buffer storage flip-flops**, requiring only 62 flip-flops for the entire accelerator.
