// ==============================================================================
// tb_cnn.v
// Robust, Race-Free Testbench for Architecture A (Serial Baseline CNN Accelerator)
// Features:
//   - Zero clock-edge race conditions (all inputs driven on negedge clk)
//   - Measures clock cycles and verifies against analytical cycle formulas:
//       Measured cycles from start to done = 325 clock cycles (324 compute + 1 done)
//   - Verifies exactly 36 output pixels for fixed-shape 8x8 image convolved with 3x3 kernel
//   - Multi-phase verification:
//       Phase 1: Normal full-frame computation with cycle measurement
//       Phase 2: Restart test (back-to-back start without reset)
//       Phase 3: Mid-computation synchronous reset abort and recovery
//   - Strict error assertions and timeout watchdog
// Standard Verilog-2001 testbench.
// ==============================================================================

`timescale 1ns / 1ps

module tb_cnn;

    // Clock and Reset Signals
    reg         clk;
    reg         rst;
    reg         start;

    // DUT Output/Control Signals
    wire        done;
    wire [5:0]  img_addr;
    wire [7:0]  img_data;
    wire [3:0]  kernel_addr;
    wire [7:0]  kernel_data;
    wire [23:0] out_data;
    wire        out_valid;

    // Memory Models (loaded from .hex test vectors)
    reg [7:0]  image_mem    [0:63];
    reg [7:0]  kernel_mem   [0:8];
    reg [23:0] expected_mem [0:35];

    // Tracking and Cycle Measurement Variables
    integer outfile;
    integer output_count;
    integer frame_count;
    integer total_errors;
    integer phase_val_errors;
    integer current_phase;
    integer cycle_counter;
    integer start_cycle;
    integer end_cycle;
    integer measured_cycles;

    // DUT Instantiation
    cnn_accel uut (
        .clk         (clk),
        .rst         (rst),
        .start       (start),
        .done        (done),
        .img_addr    (img_addr),
        .img_data    (img_data),
        .kernel_addr (kernel_addr),
        .kernel_data (kernel_data),
        .out_data    (out_data),
        .out_valid   (out_valid)
    );

    // Memory Read Ports driven combinationally based on DUT address requests
    assign img_data    = image_mem[img_addr];
    assign kernel_data = kernel_mem[kernel_addr];

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
        #200000; // 200 us max (20,000 clock cycles)
        $display("\n==============================================================");
        $display("FATAL: Simulation Timeout Watchdog Expired!");
        $display("==============================================================");
        $finish(1);
    end

    // Main Test Stimulus Sequencer
    initial begin
        $dumpfile("cnn_sim.vcd");
        $dumpvars(0, tb_cnn);

        $display("==============================================================");
        $display("   tb_cnn: Verification of Serial MAC CNN Accelerator        ");
        $display("==============================================================");

        total_errors  = 0;
        output_count  = 0;
        frame_count   = 0;
        start_cycle   = 0;
        end_cycle     = 0;

        // Load primary test stimulus and reference outputs
        $readmemh("../data/image.hex", image_mem);
        $readmemh("../data/kernel.hex", kernel_mem);
        $readmemh("../data/expected_output.hex", expected_mem);
        outfile = $fopen("../data/hw_output.hex", "w");
        if (outfile == 0) begin
            $display("ERROR: Could not open ../data/hw_output.hex for writing.");
            $finish(1);
        end

        // -------------------------------------------------------------
        // Phase 1: Power-on Synchronous Reset & Normal Frame Execution
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
        $display("[Phase 1] Reset deasserted. Triggering frame 1 start...");

        @(negedge clk);
        start = 1'b1;
        @(posedge clk);               // DUT samples start on this rising clock edge
        start_cycle = cycle_counter; // Baseline cycle reference
        @(negedge clk);
        start = 1'b0;

        // Wait for frame 1 done pulse
        @(posedge done);
        end_cycle = cycle_counter;   // Rising clock edge where done asserts
        @(negedge clk);
        frame_count = frame_count + 1;

        measured_cycles = end_cycle - start_cycle;
        $display("[Phase 1 Cycle Audit]");
        $display("  - Measured Simulation Cycles (start to done): %0d cycles", measured_cycles);
        $display("  - Analytical Formulation: 1 (start FSM) + 36*9 (compute) + 1 (done) = 326 cycles");
        if (measured_cycles == 326) begin
            $display("  - Cycle Check: PASS (Measured cycles match analytical formulation exactly)");
        end else begin
            $display("ERROR: Cycle Check FAILED! Measured %0d cycles vs expected 326 cycles", measured_cycles);
            total_errors = total_errors + 1;
        end
        $display("[SIM_CYCLE_AUDIT] serial_cycles=%0d", measured_cycles);

        if (output_count != 36) begin
            $display("ERROR: Phase 1 output count mismatch! Expected 36, got %0d", output_count);
            total_errors = total_errors + 1;
        end else if (phase_val_errors != 0) begin
            $display("ERROR: Phase 1 output value mismatch! %0d errors detected.", phase_val_errors);
            total_errors = total_errors + 1;
        end else begin
            $display("[Phase 1 PASS] Frame 1 completed: Exactly 36/36 bit-exact outputs verified.");
        end

        $fclose(outfile);

        // -------------------------------------------------------------
        // Phase 2: Restart Verification (Start without Reset)
        // -------------------------------------------------------------
        $display("\n[Phase 2] Testing restart from IDLE without hardware reset...");
        current_phase = 2;
        phase_val_errors = 0;
        output_count = 0;
        repeat (3) @(negedge clk); // Idle for 3 cycles

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

        // Run partially through computation (45 clock cycles)
        repeat (45) @(negedge clk);
        $display("[Phase 3] Asserting synchronous reset mid-computation...");
        rst = 1'b1;
        repeat (3) @(negedge clk);
        rst = 1'b0;

        // Verify that DUT aborted to IDLE and is not asserting out_valid
        repeat (5) @(negedge clk);
        if (out_valid != 1'b0 || done != 1'b0) begin
            $display("ERROR: Phase 3 DUT did not cleanly abort to IDLE after reset!");
            total_errors = total_errors + 1;
        end else begin
            $display("[Phase 3 PASS] DUT aborted cleanly to IDLE after reset.");
        end

        // Re-start after abort and verify complete clean execution with full output validation
        current_phase = 3;
        phase_val_errors = 0;
        output_count = 0;
        $display("[Phase 3] Restarting frame after abort recovery...");
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
            $display(">>> tb_cnn: ALL TEST PHASES PASSED (0 ERRORS) <<<");
            $display("==============================================================");
            $finish(0);
        end else begin
            $display(">>> tb_cnn: FAILED WITH %0d ERRORS <<<", total_errors);
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
                    if (out_data !== expected_mem[output_count]) begin
                        $display("ERROR: [Phase %0d Value Mismatch] Pixel %0d: Expected 0x%06x (%0d), got 0x%06x (%0d)",
                                 current_phase, output_count, expected_mem[output_count], expected_mem[output_count], out_data, out_data);
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
