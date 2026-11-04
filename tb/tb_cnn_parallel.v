// tb_cnn_parallel.v
// Testbench for high-throughput parallel 9-MAC CNN Accelerator
`timescale 1ns / 1ps

module tb_cnn_parallel;

    reg         clk;
    reg         rst;
    reg         start;

    reg         img_wr_en;
    reg  [5:0]  img_wr_addr;
    reg  [7:0]  img_wr_data;

    reg         kernel_wr_en;
    reg  [3:0]  kernel_wr_addr;
    reg  [7:0]  kernel_wr_data;

    wire [23:0] out_data;
    wire        out_valid;
    wire        done;

    // Testbench Memory Buffers (loaded from hex files)
    reg [7:0] tb_image_mem [0:63];
    reg [7:0] tb_kernel_mem [0:8];

    integer outfile;
    integer step;
    integer output_count;

    // Instantiate Parallel Accelerator
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

    // Clock generation: 10ns period (100 MHz)
    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst = 1;
        start = 0;
        img_wr_en = 0;
        kernel_wr_en = 0;
        output_count = 0;

        $dumpfile("cnn_sim_parallel.vcd");
        $dumpvars(0, tb_cnn_parallel);

        $display("------------------------------------------------------------");
        $display("   High-Throughput Parallel 9-MAC CNN Accelerator Testbench  ");
        $display("------------------------------------------------------------");

        // Load hex data files
        $readmemh("../data/image.hex", tb_image_mem);
        $readmemh("../data/kernel.hex", tb_kernel_mem);
        outfile = $fopen("../data/hw_output_parallel.hex", "w");

        // Reset pulse
        repeat(3) @(posedge clk);
        rst = 0;
        @(posedge clk);

        // Preload Kernel Weights (9 cycles)
        $display("Preloading 9 kernel weights into internal registers...");
        kernel_wr_en = 1;
        for (step = 0; step < 9; step = step + 1) begin
            kernel_wr_addr = step;
            kernel_wr_data = tb_kernel_mem[step];
            @(posedge clk);
        end
        kernel_wr_en = 0;

        // Preload Image Pixels (64 cycles)
        $display("Preloading 64 image pixels into internal registers...");
        img_wr_en = 1;
        for (step = 0; step < 64; step = step + 1) begin
            img_wr_addr = step;
            img_wr_data = tb_image_mem[step];
            @(posedge clk);
        end
        img_wr_en = 0;

        @(posedge clk);
        $display("Preload complete. Asserting start for parallel convolution...");
        start = 1;
        @(posedge clk);
        start = 0;

        // Computation proceeds for 36 cycles
    end

    // Monitor outputs
    always @(posedge clk) begin
        if (out_valid) begin
            $fdisplay(outfile, "%06x", out_data);
            $display("Time: %0t ps | Output #%02d: 0x%06x (%0d)", $time, output_count, out_data, out_data);
            output_count = output_count + 1;
        end

        if (done) begin
            $fclose(outfile);
            $display("------------------------------------------------------------");
            $display("SUCCESS: Parallel 36-cycle computation complete!");
            $display("Total output pixels captured: %0d / 36", output_count);
            $display("Results dumped to: ../data/hw_output_parallel.hex");
            $display("------------------------------------------------------------");
            $finish;
        end
    end

    // Safety timeout
    initial begin
        #50000;
        $display("ERROR: Simulation timeout in parallel testbench.");
        $finish;
    end

endmodule
