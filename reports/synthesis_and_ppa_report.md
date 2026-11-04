# CNN Hardware Accelerator: Synthesis & PPA Benchmark Report

## 1. Executive Summary
- **Module Name**: `cnn_accel`
- **Target Technology**: Generic Standard Cell CMOS Gate Library (via Yosys 0.70 + ABC)
- **Gate-Level Netlist**: `src/cnn_accel_synth.v`
- **Functional Verification**: 100% Bit-Exact Match against Python Software Reference Model (36/36 pixels)

---

## 2. Hardware Resource & Gate Utilization (Yosys Synthesis)

| Metric | Measured Value |
| :--- | :--- |
| **Total Standard Cells** | **2,270 cells** |
| **Number of Wires** | **3,565** |
| **Number of Wire Bits** | **4,142 bits** |
| **Datapath Multiplier** | 1 Dedicated $8 \times 8$-bit unsigned MAC Multiplier |
| **Accumulator Register Width** | 24 bits (Prevents overflow up to $585,225$) |
| **Control State Machine** | 3-state Mealy/Moore FSM (`IDLE`, `COMPUTE`, `DONE`) |

### Standard Cell Breakdown:
```

 /----------------------------------------------------------------------------\
 |  yosys -- Yosys Open SYnthesis Suite                                       |
 |  Copyright (C) 2012 - 2026  Claire Xenia Wolf <claire@yosyshq.com>         |
 |  Distributed under an ISC-like license, type "license" to see terms        |
 \----------------------------------------------------------------------------/
 Yosys 0.70 (git sha1 28ba3cb92, Release, Clang /workspace/YoWASP/yosys/wasi-sdk-33.0-x86_64-linux/share/cmake/../..//bin/clang++ 22.1.0)

-- Running command `read_verilog cnn_accel_synth.v; stat' --

1. Executing Verilog-2005 frontend: cnn_accel_synth.v
Parsing Verilog input from `cnn_accel_synth.v' to AST representation.
Generating RTLIL representation for module `\cnn_accel'.
Successfully finished Verilog frontend.

2. Printing statistics.

=== cnn_accel ===

        +----------Local Count, excluding submodules.
        | 
     3565 wires
     4142 wire bits
     1233 public wires
     1810 public wire bits
       10 ports
       55 port bits
       62 processes
     2270 cells
      486   $and
     1294   $not
      490   $or

End of script. Logfile hash: 1590b91a01, time: 0.22s, user: 0.22s, system: 0.00s
Yosys 0.70 (git sha1 28ba3cb92, Release, Clang /workspace/YoWASP/yosys/wasi-sdk-33.0-x86_64-linux/share/cmake/../..//bin/clang++ 22.1.0)
Time spent: 98% 2x read_verilog (0 sec), 1% 1x stat (0 sec), ...

```

---

## 3. Power, Performance, and Area (PPA) Benchmarks

| Metric | Specification / Result | Context |
| :--- | :--- | :--- |
| **Target Clock Frequency ($F_{\max}$)** | **100.0 MHz** (10 ns period) | Conservative ASIC/FPGA target |
| **Total Latency** | **330 clock cycles** ($3.30\,\mu\text{s}$) | 3-cycle reset + 324 compute + 3 cleanup |
| **Inference Throughput** | **303,030 Feature Maps / sec** | Processing $8 \times 8$ images with $3 \times 3$ kernel |
| **Arithmetic Performance** | **196.4 MOPS** (Million Ops / sec) | $648$ arithmetic operations per feature map |
| **Cycle Efficiency** | **9.17 cycles / output pixel** | 9 MAC cycles per $3 \times 3$ dot product |

---

## 4. Key Architectural Insights for Interviews & Presentations
1. **Zero-Memory Redundancy**: Rather than loading all 64 image pixels into internal SRAM flip-flops, the accelerator calculates 2D memory addresses combinationally (`(row << 3) + col`), pulling data cycle-by-cycle and minimizing silicon area.
2. **Dynamic Range Safety**: An accumulator width of 24 bits guarantees that the maximum theoretical convolution sum ($9 \times 255 \times 255 = 585,225$) uses only 20 bits, preventing saturation or overflow without requiring floating-point overhead.
3. **Pipelined Upgrade Potential**: Upgrading the single serial MAC to a 9-multiplier parallel dot-product tree would reduce latency from 330 cycles to **36 cycles** ($9.17\times$ speedup) at the cost of $8$ additional multipliers.
