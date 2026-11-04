`timescale 1ns / 1ps

module tb_cnn;

    // Testbench signals for UUT ports
    reg         clk;
    reg         rst;
    reg         start;
    wire        done;
    wire [5:0]  img_addr;
    wire [7:0]  img_data; // Driven by image_mem
    wire [3:0]  kernel_addr;
    wire [7:0]  kernel_data; // Driven by kernel_mem
    wire [23:0] out_data;
    wire        out_valid;

    // Memory declarations for image and kernel data
    reg [7:0] image_mem [0:63];   // 64 8-bit pixels for 8x8 image
    reg [7:0] kernel_mem [0:8];   // 9 8-bit weights for 3x3 kernel

    // File handle for output
    integer outfile;

    // Clock generation
    initial begin
        clk = 0;
    end
    always #5 clk = ~clk; // 10ns period, 100MHz clock

    // UUT Instantiation
    cnn_accel uut (
        .clk(clk),
        .rst(rst),
        .start(start),
        .done(done),
        .img_addr(img_addr),
        .img_data(img_data),
        .kernel_addr(kernel_addr),
        .kernel_data(kernel_data),
        .out_data(out_data),
        .out_valid(out_valid)
    );

    // Continuous assignment to drive UUT's img_data and kernel_data inputs
    // based on addresses provided by the UUT.
    assign img_data = image_mem[img_addr];
    assign kernel_data = kernel_mem[kernel_addr];

    // Test sequence
    initial begin
        // Initialize inputs
        rst   = 1;
        start = 0;

        // Setup VCD dumping
        $dumpfile("cnn_sim.vcd");
        $dumpvars(0, tb_cnn);

        // Load image and kernel data from hex files
        $readmemh("../data/image.hex", image_mem);
        $readmemh("../data/kernel.hex", kernel_mem);
        $display("Loaded image.hex and kernel.hex.");

        // Open output file
        outfile = $fopen("../data/hw_output.hex", "w");
        if (outfile == 0) begin
            $display("Error: Could not open hw_output.hex for writing.");
            $finish;
        end

        // Apply reset for 3 clock cycles
        repeat (3) @(posedge clk);
        rst = 0;
        $display("Reset deasserted.");

        // Assert start pulse for 1 clock cycle
        @(posedge clk);
        start = 1;
        $display("Start asserted.");
        @(posedge clk);
        start = 0;
        $display("Start deasserted. CNN accelerator running...");

        // Safety timeout
        #50000; // Wait for max 50000 time units (5000 clocks)
        $display("Error: Simulation Timeout!");
        $finish;
    end

    // Monitor and capture output data
    always @(posedge clk) begin
        if (out_valid) begin
            $fdisplay(outfile, "%06x", out_data);
            $display("Time: %0t, Out_valid, Output: %06x", $time, out_data);
        end
        if (done) begin
            $fclose(outfile);
            $display("Time: %0t, Hardware simulation finished successfully. Output written to hw_output.hex", $time);
            $finish;
        end
    end

    // Optional: Monitor key internal signals for debugging (can be seen in VCD too)
    // initial begin
    //     $monitor("Time: %0t, State: %s, out_row: %d, out_col: %d, kr: %d, kc: %d, acc: %d, img_addr: %d, kernel_addr: %d",
    //              $time, uut.current_state == uut.IDLE ? "IDLE" : (uut.current_state == uut.COMPUTE ? "COMPUTE" : (uut.current_state == uut.DONE ? "DONE" : "UNKNOWN")),
    //              uut.out_row_r, uut.out_col_r, uut.kr_r, uut.kc_r, uut.acc_r, img_addr, kernel_addr);
    // end

endmodule
