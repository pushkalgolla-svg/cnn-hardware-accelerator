// cnn_accel_parallel.v
// High-Throughput 2D CNN Convolution Accelerator with Parallel 9-MAC Dot-Product Engine
// Computes 1 convolution output per clock cycle (36 cycles total for 6x6 output)
// Incorporates ReLU non-linear activation

`timescale 1ns / 1ps

module cnn_accel_parallel (
    input  wire        clk,
    input  wire        rst,            // Synchronous active-high reset
    input  wire        start,          // 1-cycle active-high pulse to trigger 36-cycle convolution
    
    // Image buffer write port (for loading 64-pixel 8x8 image)
    input  wire        img_wr_en,
    input  wire [5:0]  img_wr_addr,    // 0 to 63
    input  wire [7:0]  img_wr_data,

    // Kernel buffer write port (for loading 9-weight 3x3 filter)
    input  wire        kernel_wr_en,
    input  wire [3:0]  kernel_wr_addr, // 0 to 8
    input  wire [7:0]  kernel_wr_data,

    // Convolution Output Stream
    output reg  [23:0] out_data,       // Convolved & ReLU-activated pixel
    output reg         out_valid,      // High whenever a valid output pixel is produced
    output reg         done            // Pulses high when all 36 outputs are completed
);

    // FSM States
    localparam IDLE    = 2'b00;
    localparam COMPUTE = 2'b01;
    localparam DONE_ST = 2'b10;

    reg [1:0] state;

    // Internal Memory Arrays (Registers for simultaneous 9-point spatial parallel access)
    reg [7:0] img_buf    [0:63];
    reg [7:0] kernel_buf [0:8];

    // Coordinate Counters for 6x6 Output Feature Map
    reg [2:0] out_row; // 0 to 5
    reg [2:0] out_col; // 0 to 5

    // Write Ports Handling (Sequential)
    integer i;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            for (i = 0; i < 64; i = i + 1) img_buf[i] <= 8'd0;
            for (i = 0; i < 9;  i = i + 1) kernel_buf[i] <= 8'd0;
        end else begin
            if (img_wr_en) begin
                img_buf[img_wr_addr] <= img_wr_data;
            end
            if (kernel_wr_en) begin
                kernel_buf[kernel_wr_addr] <= kernel_wr_data;
            end
        end
    end

    // Combinational Receptive Field Extraction (9 concurrent pixels)
    // Sized 6-bit base addresses using concatenation to prevent 3-bit shift overflow
    wire [5:0] row0_base = { (out_row + 3'd0), 3'b000 };
    wire [5:0] row1_base = { (out_row + 3'd1), 3'b000 };
    wire [5:0] row2_base = { (out_row + 3'd2), 3'b000 };

    // Row 0 of 3x3 window:
    wire [7:0] p0 = img_buf[row0_base + out_col + 6'd0];
    wire [7:0] p1 = img_buf[row0_base + out_col + 6'd1];
    wire [7:0] p2 = img_buf[row0_base + out_col + 6'd2];
    // Row 1 of 3x3 window:
    wire [7:0] p3 = img_buf[row1_base + out_col + 6'd0];
    wire [7:0] p4 = img_buf[row1_base + out_col + 6'd1];
    wire [7:0] p5 = img_buf[row1_base + out_col + 6'd2];
    // Row 2 of 3x3 window:
    wire [7:0] p6 = img_buf[row2_base + out_col + 6'd0];
    wire [7:0] p7 = img_buf[row2_base + out_col + 6'd1];
    wire [7:0] p8 = img_buf[row2_base + out_col + 6'd2];

    // Kernel Weights (9 concurrent weights)
    wire [7:0] k0 = kernel_buf[0];
    wire [7:0] k1 = kernel_buf[1];
    wire [7:0] k2 = kernel_buf[2];
    wire [7:0] k3 = kernel_buf[3];
    wire [7:0] k4 = kernel_buf[4];
    wire [7:0] k5 = kernel_buf[5];
    wire [7:0] k6 = kernel_buf[6];
    wire [7:0] k7 = kernel_buf[7];
    wire [7:0] k8 = kernel_buf[8];

    // 9 Parallel Hardware Multipliers (8-bit x 8-bit -> 16-bit)
    wire [15:0] prod0 = p0 * k0;
    wire [15:0] prod1 = p1 * k1;
    wire [15:0] prod2 = p2 * k2;
    wire [15:0] prod3 = p3 * k3;
    wire [15:0] prod4 = p4 * k4;
    wire [15:0] prod5 = p5 * k5;
    wire [15:0] prod6 = p6 * k6;
    wire [15:0] prod7 = p7 * k7;
    wire [15:0] prod8 = p8 * k8;

    // Parallel Adder Tree (3-stage low-latency tree)
    // Stage 1 (Pairwise Additions: 16-bit + 16-bit -> 17-bit)
    wire [16:0] sum_s1_0 = prod0 + prod1;
    wire [16:0] sum_s1_1 = prod2 + prod3;
    wire [16:0] sum_s1_2 = prod4 + prod5;
    wire [16:0] sum_s1_3 = prod6 + prod7;
    wire [16:0] sum_s1_4 = {1'b0, prod8};

    // Stage 2 (17-bit + 17-bit -> 18-bit)
    wire [17:0] sum_s2_0 = sum_s1_0 + sum_s1_1;
    wire [17:0] sum_s2_1 = sum_s1_2 + sum_s1_3;
    wire [17:0] sum_s2_2 = {1'b0, sum_s1_4};

    // Stage 3 (Final Total: 18-bit + 18-bit -> 19-bit, extended to 24 bits)
    wire [18:0] sum_s3_0 = sum_s2_0 + sum_s2_1;
    wire [19:0] raw_conv_sum = sum_s3_0 + sum_s2_2;

    // ReLU Activation Function: f(x) = max(0, x)
    // (For unsigned inputs, raw_conv_sum >= 0, but explicitly parameterized for signed extensions)
    wire [23:0] relu_output = {4'b0000, raw_conv_sum};

    // Main Control FSM & Output Register Pipeline
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state     <= IDLE;
            out_row   <= 3'd0;
            out_col   <= 3'd0;
            out_data  <= 24'd0;
            out_valid <= 1'b0;
            done      <= 1'b0;
        end else begin
            out_valid <= 1'b0;
            done      <= 1'b0;

            case (state)
                IDLE: begin
                    if (start) begin
                        state     <= COMPUTE;
                        out_row   <= 3'd0;
                        out_col   <= 3'd0;
                    end
                end

                COMPUTE: begin
                    // Emit 1 convolved and activated pixel per clock cycle!
                    out_data  <= relu_output;
                    out_valid <= 1'b1;

                    // Advance coordinates
                    if (out_col == 3'd5) begin
                        out_col <= 3'd0;
                        if (out_row == 3'd5) begin
                            state <= DONE_ST;
                        end else begin
                            out_row <= out_row + 3'd1;
                        end
                    end else begin
                        out_col <= out_col + 3'd1;
                    end
                end

                DONE_ST: begin
                    done  <= 1'b1;
                    state <= IDLE;
                end
            endcase
        end
    end

endmodule
