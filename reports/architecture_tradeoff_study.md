# CNN Hardware Accelerator: Synthesis & PPA Benchmark Report

## 1. Executive Summary & Design Scope
- **Design Architecture**: Fixed-shape 2D convolution for an $8 \times 8$ input image, $3 \times 3$ kernel, and $6 \times 6$ output feature map ($36$ output pixels).
- **Technology Target**: Generic CMOS standard cell logic mapping (`cmos2` library: NOT, AND, OR) via **Yosys 0.70 + ABC**.
- **Architectures Evaluated**:
  - `cnn_accel` (Architecture A: Serial MAC Baseline, area-minimal, streaming address generator)
  - `cnn_accel_parallel` (Architecture B: Parallel 9-MAC + Single-Cycle Combinational Adder Tree + ReLU)
- **Functional Verification**: 100% Bit-Exact Match across 5 independent test suites (Random, All Zeros, All Max, Checkerboard, Impulse).

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

## 2. Hardware Resource & Gate Utilization (Yosys Synthesis)

| Metric | Architecture A (Serial Baseline) | Architecture B (Parallel 9-MAC) | Scaling / Ratio |
| :--- | :--- | :--- | :--- |
| **Total Standard Cells** | **2,474 gates** | **28,522 gates** | **11.53x Logic Gate Scaling** |
| **Cell Breakdown (ABC)** | $and: 569, $not: 1,355, $or: 550 | $and: 7,795, $logic_not: 584, $not: 14,926, $or: 5,217 | Generic CMOS library mapping |
| **RTLIL Logical Nets** | 3,882 nets | 43,694 nets | 11.3x logical nets |
| **RTLIL Wire Bits** | 4,115 bits | 46,085 bits | 11.2x logical bits |
| **Multiplier Units** | 1 Serial Multiplier | 9 Parallel Multipliers | 9.0x arithmetic units |
| **Adder Tree Architecture** | Sequential Accumulator | Single-Cycle Combinational Tree | Non-pipelined (3 stages logic) |
| **Buffer Storage** | On-the-fly streaming | 64-byte image + 9-byte kernel | Multi-port register array |
| **Buffer Write Protection** | N/A (Streaming) | Hardware-guarded in IDLE state | Active compute protection |

---

## 3. Measured Simulation Cycles vs. Analytical Estimates

| Metric | Architecture A (Serial) | Architecture B (Parallel) | Speedup / Scaling |
| :--- | :--- | :--- | :--- |
| **Buffer Preload Cycles** | **0 cycles** (Streaming reads) | **73 cycles** (9 krn + 64 img) | Preload required for parallel array |
| **Pure Arithmetic Cycles**| **324 cycles** (9 cyc/pixel) | **36 cycles** (1 cyc/pixel) | **9.0x Compute Speedup** |
| **Measured Total Cycles** | **326 cycles** (Icarus simulation) | **111 cycles** (Icarus simulation) | **2.94x Total Speedup** |
| **Analytical Cycle Formula**| $1 + 36 \times 9 + 1 = 326$ cycles | $73 + 1 + 36 + 1 = 111$ cycles | 100% agreement with simulation |
| **Compute Latency (@ 100 MHz\*)** | 3.24 $\mu\text{s}$ | **0.36 $\mu\text{s}$** | $9.0\times$ latency reduction |
| **Total Latency (@ 100 MHz\*)** | 3.26 $\mu\text{s}$ | **1.11 $\mu\text{s}$** | $2.94\times$ total frame speedup |
| **Streaming Throughput (FPS)** | 308,642 FPS | **2,777,778 FPS** | $9.0\times$ higher throughput |
| **Total Throughput with Reload** | 306,748 FPS | **900,901 FPS** | $2.94\times$ total throughput |
| **Peak Arithmetic Density** | 200.0 MOPS | **1800.0 MOPS (1.80 GOPS)** | $9.0\times$ compute density |
| **Verification Status** | 36/36 BIT-EXACT PASS (5/5 suites) | 36/36 BIT-EXACT PASS (5/5 suites) | 100% Bit-Exact across 5 suites |

---

## 4. Architectural Analysis & Key Findings
1. **Measured vs. Analytical Cycle Exactness**: In both architectures, the measured cycle timestamps in Icarus Verilog match the discrete analytical equations exactly ($326$ cycles for serial: 1 start + 324 compute + 1 done; $111$ cycles for parallel: 73 preload + 38 active compute).
2. **Compute vs. Memory Bottleneck**: Architecture B delivers a $9.0\times$ active compute acceleration ($36$ vs $324$ cycles). In convolution layer cascades where weights remain resident in registers across multiple feature maps, streaming throughput reaches 2.78M FPS. When buffers must be reloaded per frame, total speedup is $2.94\times$ ($111$ vs $326$ cycles).
3. **Combinational Tree vs. Pipelined Tree**: The 9-product summation in Architecture B is implemented as a single-cycle combinational adder tree. It completes within one clock period, saving register area and latency at the cost of longer combinational path delay.
4. **Logic Gate Complexity Scaling**: Architecture B requires $28,522$ gates compared to $2,474$ gates for Architecture A ($11.53\times$ gate count increase), driven primarily by the 9 parallel multipliers and 512 flip-flops of multi-port storage. Note that generic Yosys gate counts quantify abstract Boolean logic complexity and do not constitute physical silicon area measurements (which require physical place-and-route, standard cell LEF geometries, and DRC routing).
