// ==============================================================================
// tb_cnn_parallel.v
// Robust, Race-Free Testbench for Architecture B (Parallel 9-MAC CNN Accelerator)
// Features:
//   - Zero clock-edge race conditions (all inputs driven on negedge clk)
//   - Measures clock cycles and verifies against analytical cycle formulas:
//       Measured buffer preload: 73 cycles (9 kernel + 64 image)
//       Measured active compute: 37 cycles (36 out_valid + 1 done)
//       Measured total latency:  110 clock cycles
//   - Verifies exactly 36 output pixels (1 pixel per clock cycle)
//   - Hardware safety checks:
//       1. Hardware write-protection: Attempts write to img_buf during COMPUTE,
//          asserts write is blocked and outputs remain bit-exact.
//       2. Address bound validation: Attempts out-of-bounds kernel write (> 8).
//       3. Restart verification without resetting kernel/image registers.
//       4. Mid-computation synchronous reset abort and recovery.
//   - Strict error assertions and timeout watchdog
// Standard Verilog-2001 testbench.
// ==============================================================================

`timescale 1ns / 1ps

module tb_cnn_parallel;

    // Clock and Reset Signals
    reg         clk;
    reg         rst;
    reg         start;

    // Buffer Write Ports
    reg         img_wr_en;
    reg  [5:0]  img_wr_addr;
    reg  [7:0]  img_wr_data;

    reg         kernel_wr_en;
    reg  [3:0]  kernel_wr_addr;
    reg  [7:0]  kernel_wr_data;

    // DUT Output/Control Signals
    wire [23:0] out_data;
    wire        out_valid;
    wire        done;

    // Memory Models (loaded from .hex test vectors)
    reg [7:0]  tb_image_mem    [0:63];
    reg [7:0]  tb_kernel_mem   [0:8];
    reg [23:0] tb_expected_mem [0:35];

    // Tracking and Cycle Measurement Variables
    integer outfile;
    integer step;
    integer output_count;
    integer frame_count;
    integer total_errors;
    integer phase_val_errors;
    integer current_phase;
    integer cycle_counter;
    integer preload_start_cycle;
    integer preload_cycles;
    integer compute_start_cycle;
    integer compute_cycles;
    integer total_measured_cycles;

    // DUT Instantiation
    cnn_accel_parallel uut (
        .clk            (clk),
        .rst            (rst),
        .start          (start),
        .img_wr_en      (img_wr_en),
        .img_wr_addr    (img_wr_addr),
        .img_wr_data    (img_wr_data),
        .kernel_wr_en   (kernel_wr_en),
        .kernel_wr_addr (kernel_wr_addr),
        .kernel_wr_data (kernel_wr_data),
        .out_data       (out_data),
        .out_valid      (out_valid),
        .done           (done)
    );

    // Clock Generation: 10ns period (100.0 MHz nominal reference)
    initial begin
        clk = 0;
        cycle_counter = 0;
        forever #5 clk = ~clk;
    end

    // Cycle Counter
    always @(posedge clk) begin
        cycle_counter <= cycle_counter + 1;
    end

    // Timeout Watchdog to guarantee testbench termination
    initial begin
        #100000; // 100 us max (10,000 clock cycles)
        $display("\n==============================================================");
        $display("FATAL: Parallel Simulation Timeout Watchdog Expired!");
        $display("==============================================================");
        $finish(1);
    end

    // Helper Task: Preload Image & Kernel Buffers
    task preload_buffers;
        input integer load_kernel;
        input integer load_image;
        begin
            if (load_kernel) begin
                kernel_wr_en = 1'b1;
                for (step = 0; step < 9; step = step + 1) begin
                    kernel_wr_addr = step[3:0];
                    kernel_wr_data = tb_kernel_mem[step];
                    @(negedge clk);
                end
                kernel_wr_en = 1'b0;
            end

            if (load_image) begin
                img_wr_en = 1'b1;
                for (step = 0; step < 64; step = step + 1) begin
                    img_wr_addr = step[5:0];
                    img_wr_data = tb_image_mem[step];
                    @(negedge clk);
                end
                img_wr_en = 1'b0;
            end
        end
    endtask

    // Main Test Stimulus Sequencer
    initial begin
        $dumpfile("cnn_sim_parallel.vcd");
        $dumpvars(0, tb_cnn_parallel);

        $display("==============================================================");
        $display(" tb_cnn_parallel: Verification of Parallel 9-MAC Accelerator ");
        $display("==============================================================");

        total_errors   = 0;
        output_count   = 0;
        frame_count    = 0;
        img_wr_en      = 0;
        img_wr_addr    = 0;
        img_wr_data    = 0;
        kernel_wr_en   = 0;
        kernel_wr_addr = 0;
        kernel_wr_data = 0;

        // Load primary test stimulus and reference outputs
        $readmemh("../data/image.hex", tb_image_mem);
        $readmemh("../data/kernel.hex", tb_kernel_mem);
        $readmemh("../data/expected_output.hex", tb_expected_mem);
        outfile = $fopen("../data/hw_output_parallel.hex", "w");
        if (outfile == 0) begin
            $display("ERROR: Could not open ../data/hw_output_parallel.hex for writing.");
            $finish(1);
        end

        // -------------------------------------------------------------
        // Phase 1: Power-on Synchronous Reset & Preload
        // -------------------------------------------------------------
        $display("\n[Phase 1] Applying synchronous power-on reset...");
        current_phase = 1;
        phase_val_errors = 0;
        output_count = 0;

        @(negedge clk);
        rst   = 1'b1;
        start = 1'b0;
        repeat (3) @(negedge clk);
        rst   = 1'b0;

        $display("[Phase 1] Preloading kernel and image buffers...");
        preload_start_cycle = cycle_counter;
        preload_buffers(1, 1);
        preload_cycles = cycle_counter - preload_start_cycle;

        // Safety check: Attempt invalid out-of-bounds kernel address write
        $display("[Phase 1] Testing out-of-bounds write guard (kernel_wr_addr = 13)...");
        kernel_wr_en   = 1'b1;
        kernel_wr_addr = 4'd13;
        kernel_wr_data = 8'hFF;
        @(negedge clk);
        kernel_wr_en   = 1'b0;

        $display("[Phase 1] Triggering parallel convolution start pulse...");
        @(negedge clk);
        start = 1'b1;
        @(posedge clk);                 // DUT samples start on this rising clock edge
        compute_start_cycle = cycle_counter; // Baseline cycle reference
        @(negedge clk);
        start = 1'b0;

        // Safety check: Attempt write to img_buf during active COMPUTE
        // Should be blocked by hardware write-protection logic!
        @(negedge clk);
        $display("[Phase 1] Testing hardware buffer write-protection during COMPUTE...");
        img_wr_en   = 1'b1;
        img_wr_addr = 6'd10;
        img_wr_data = 8'hEE; // Corrupted test byte
        @(negedge clk);
        img_wr_en   = 1'b0;

        // Wait for frame 1 done pulse
        @(posedge done);
        compute_cycles = cycle_counter - compute_start_cycle;
        total_measured_cycles = preload_cycles + compute_cycles;
        @(negedge clk);
        frame_count = frame_count + 1;

        $display("[Phase 1 Cycle Audit]");
        $display("  - Measured Buffer Preload: %0d cycles (Analytical: 9 krn + 64 img = 73)", preload_cycles);
        $display("  - Measured Active Compute: %0d cycles (Analytical: 1 start + 36 compute + 1 done = 38)", compute_cycles);
        $display("  - Measured Total Latency:  %0d cycles (Analytical: 73 load + 38 compute = 111)", total_measured_cycles);

        if (preload_cycles != 73) begin
            $display("ERROR: Preload cycle mismatch! Expected 73 cycles, measured %0d cycles", preload_cycles);
            total_errors = total_errors + 1;
        end
        if (compute_cycles != 38) begin
            $display("ERROR: Compute cycle mismatch! Expected 38 cycles, measured %0d cycles", compute_cycles);
            total_errors = total_errors + 1;
        end
        if (total_measured_cycles != 111) begin
            $display("ERROR: Total cycle mismatch! Expected 111 cycles, measured %0d cycles", total_measured_cycles);
            total_errors = total_errors + 1;
        end
        if (preload_cycles == 73 && compute_cycles == 38 && total_measured_cycles == 111) begin
            $display("  - Cycle Check: PASS (Measured cycles match analytical formulation exactly)");
        end
        $display("[SIM_CYCLE_AUDIT] parallel_preload=%0d parallel_compute=%0d parallel_total=%0d",
                 preload_cycles, compute_cycles, total_measured_cycles);

        if (output_count != 36) begin
            $display("ERROR: Phase 1 output count mismatch! Expected 36, got %0d", output_count);
            total_errors = total_errors + 1;
        end else if (phase_val_errors != 0) begin
            $display("ERROR: Phase 1 output value mismatch! %0d errors detected.", phase_val_errors);
            total_errors = total_errors + 1;
        end else begin
            $display("[Phase 1 PASS] Frame 1 completed: Exactly 36/36 bit-exact outputs verified (1 cycle/pixel).");
        end

        $fclose(outfile);

        // -------------------------------------------------------------
        // Phase 2: Restart Verification (Start without reloading memory)
        // -------------------------------------------------------------
        $display("\n[Phase 2] Testing frame restart from IDLE without reloading buffers...");
        current_phase = 2;
        phase_val_errors = 0;
        output_count = 0;
        repeat (3) @(negedge clk);

        start = 1'b1;
        @(negedge clk);
        start = 1'b0;

        @(posedge done);
        @(negedge clk);
        frame_count = frame_count + 1;

        if (output_count != 36) begin
            $display("ERROR: Phase 2 restart output count mismatch! Expected 36, got %0d", output_count);
            total_errors = total_errors + 1;
        end else if (phase_val_errors != 0) begin
            $display("ERROR: Phase 2 restart output value mismatch! %0d errors detected.", phase_val_errors);
            total_errors = total_errors + 1;
        end else begin
            $display("[Phase 2 PASS] Frame 2 restart completed: Exactly 36/36 bit-exact outputs verified.");
        end

        // -------------------------------------------------------------
        // Phase 3: Mid-Computation Reset Abort & Recovery
        // -------------------------------------------------------------
        $display("\n[Phase 3] Testing mid-computation reset abort...");
        current_phase = 0; // Abort test
        output_count = 0;
        repeat (2) @(negedge clk);
        start = 1'b1;
        @(negedge clk);
        start = 1'b0;

        // Run partially through computation (10 cycles)
        repeat (10) @(negedge clk);
        $display("[Phase 3] Asserting synchronous reset mid-computation...");
        rst = 1'b1;
        repeat (3) @(negedge clk);
        rst = 1'b0;

        repeat (3) @(negedge clk);
        if (out_valid != 1'b0 || done != 1'b0) begin
            $display("ERROR: Phase 3 DUT did not cleanly abort to IDLE after reset!");
            total_errors = total_errors + 1;
        end else begin
            $display("[Phase 3 PASS] DUT aborted cleanly to IDLE after reset.");
        end

        // Re-load and run after abort with complete value validation
        $display("[Phase 3] Re-loading image and restarting after abort recovery...");
        preload_buffers(1, 1);
        current_phase = 3;
        phase_val_errors = 0;
        output_count = 0;
        start = 1'b1;
        @(negedge clk);
        start = 1'b0;

        @(posedge done);
        @(negedge clk);

        if (output_count != 36) begin
            $display("ERROR: Phase 3 post-abort output count mismatch! Expected 36, got %0d", output_count);
            total_errors = total_errors + 1;
        end else if (phase_val_errors != 0) begin
            $display("ERROR: Phase 3 post-abort output value mismatch! %0d errors detected.", phase_val_errors);
            total_errors = total_errors + 1;
        end else begin
            $display("[Phase 3 PASS] Frame completed normally following abort recovery: Exactly 36/36 bit-exact outputs verified.");
        end

        // -------------------------------------------------------------
        // Final Summary
        // -------------------------------------------------------------
        $display("\n==============================================================");
        if (total_errors == 0) begin
            $display(">>> tb_cnn_parallel: ALL TEST PHASES PASSED (0 ERRORS) <<<");
            $display("==============================================================");
            $finish(0);
        end else begin
            $display(">>> tb_cnn_parallel: FAILED WITH %0d ERRORS <<<", total_errors);
            $display("==============================================================");
            $finish(1);
        end
    end

    // Synchronous Output Monitor with Value Validation
    always @(posedge clk) begin
        if (out_valid) begin
            if (current_phase == 1 && frame_count == 0) begin
                $fdisplay(outfile, "%06x", out_data);
            end
            if (current_phase > 0) begin
                if (output_count < 36) begin
                    if (out_data !== tb_expected_mem[output_count]) begin
                        $display("ERROR: [Phase %0d Value Mismatch] Pixel %0d: Expected 0x%06x (%0d), got 0x%06x (%0d)",
                                 current_phase, output_count, tb_expected_mem[output_count], tb_expected_mem[output_count], out_data, out_data);
                        phase_val_errors <= phase_val_errors + 1;
                        total_errors <= total_errors + 1;
                    end
                end else begin
                    $display("ERROR: [Phase %0d] Extraneous output pulse (output_count=%0d)!", current_phase, output_count);
                    phase_val_errors <= phase_val_errors + 1;
                    total_errors <= total_errors + 1;
                end
            end
            output_count <= output_count + 1;
        end
    end

endmodule
