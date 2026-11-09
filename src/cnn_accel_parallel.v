// ==============================================================================
// cnn_accel_parallel.v
// Architecture B: High-Throughput 2D CNN Hardware Accelerator
// Features:
//   - 9 Parallel Spatial Multipliers (8-bit unsigned x 8-bit unsigned -> 16-bit)
//   - Single-Cycle Combinational Adder Tree (Non-pipelined, 3 stages of combinational adders)
//   - ReLU Non-linear Activation Function: max(0, X)
//   - Internal Multi-Port Storage Arrays for 64-pixel Image and 9-weight Kernel
//   - Hardware Write-Protection: Buffer writes blocked during COMPUTE state
//   - Array Address Validation: Prevents out-of-bounds memory indexing
// Standard Verilog-2001 synthesizable RTL.
// ==============================================================================

`timescale 1ns / 1ps

module cnn_accel_parallel (
    input  wire        clk,
    input  wire        rst,            // Synchronous active-high reset
    input  wire        start,          // 1-cycle active-high pulse to trigger convolution
    
    // Image buffer write port (for loading 64-pixel 8x8 image into internal registers)
    input  wire        img_wr_en,
    input  wire [5:0]  img_wr_addr,    // 0 to 63
    input  wire [7:0]  img_wr_data,

    // Kernel buffer write port (for loading 9-weight 3x3 filter into internal registers)
    input  wire        kernel_wr_en,
    input  wire [3:0]  kernel_wr_addr, // 0 to 8 (guarded against > 8)
    input  wire [7:0]  kernel_wr_data,

    // Convolution Output Stream
    output reg  [23:0] out_data,       // Convolved & ReLU-activated pixel (24-bit)
    output reg         out_valid,      // High for 1 cycle when out_data is valid
    output reg         done            // Pulses high for 1 cycle when all 36 outputs are complete
);

    // FSM State Encoding
    localparam [1:0] IDLE    = 2'b00;
    localparam [1:0] COMPUTE = 2'b01;
    localparam [1:0] DONE_ST = 2'b10;

    reg [1:0] state;

    // Internal Multi-Port Storage Arrays
    reg [7:0] img_buf    [0:63];
    reg [7:0] kernel_buf [0:8];

    // Coordinate Counters for 6x6 Output Feature Map (0 to 5)
    reg [2:0] out_row;
    reg [2:0] out_col;

    // Synchronous Buffer Write Logic with Safety Guards
    integer i;
    always @(posedge clk) begin
        if (rst) begin
            for (i = 0; i < 64; i = i + 1) img_buf[i] <= 8'd0;
            for (i = 0; i < 9;  i = i + 1) kernel_buf[i] <= 8'd0;
        end else begin
            // SAFETY RULE: Protect internal buffers from writes during COMPUTE
            // Only allow writes when accelerator is in IDLE state.
            if (state == IDLE) begin
                if (img_wr_en) begin
                    img_buf[img_wr_addr] <= img_wr_data; // img_wr_addr is [5:0] (0..63)
                end
                // Validate address bounds: only write if kernel_wr_addr <= 8
                if (kernel_wr_en && kernel_wr_addr < 4'd9) begin
                    kernel_buf[kernel_wr_addr] <= kernel_wr_data;
                end
            end
        end
    end

    // Combinational Receptive Field Extraction (9 concurrent spatial pixels)
    // Sized base row addresses: out_row is 0..5, so (out_row + offset) is 0..7.
    // Row base = row * 8 = {row[2:0], 3'b000}.
    wire [2:0] r0 = out_row + 3'd0;
    wire [2:0] r1 = out_row + 3'd1;
    wire [2:0] r2 = out_row + 3'd2;

    wire [5:0] row0_base = {r0, 3'b000};
    wire [5:0] row1_base = {r1, 3'b000};
    wire [5:0] row2_base = {r2, 3'b000};

    // Columns within 3x3 receptive window (out_col is 0..5, so +0..2 is 0..7)
    wire [5:0] c0 = {3'b000, out_col} + 6'd0;
    wire [5:0] c1 = {3'b000, out_col} + 6'd1;
    wire [5:0] c2 = {3'b000, out_col} + 6'd2;

    // Row 0 pixels:
    wire [7:0] p0 = img_buf[row0_base + c0];
    wire [7:0] p1 = img_buf[row0_base + c1];
    wire [7:0] p2 = img_buf[row0_base + c2];
    // Row 1 pixels:
    wire [7:0] p3 = img_buf[row1_base + c0];
    wire [7:0] p4 = img_buf[row1_base + c1];
    wire [7:0] p5 = img_buf[row1_base + c2];
    // Row 2 pixels:
    wire [7:0] p6 = img_buf[row2_base + c0];
    wire [7:0] p7 = img_buf[row2_base + c1];
    wire [7:0] p8 = img_buf[row2_base + c2];

    // Kernel Filter Weights (9 concurrent weights)
    wire [7:0] k0 = kernel_buf[0];
    wire [7:0] k1 = kernel_buf[1];
    wire [7:0] k2 = kernel_buf[2];
    wire [7:0] k3 = kernel_buf[3];
    wire [7:0] k4 = kernel_buf[4];
    wire [7:0] k5 = kernel_buf[5];
    wire [7:0] k6 = kernel_buf[6];
    wire [7:0] k7 = kernel_buf[7];
    wire [7:0] k8 = kernel_buf[8];

    // 9 Parallel Multipliers (8-bit unsigned x 8-bit unsigned -> 16-bit unsigned)
    wire [15:0] prod0 = p0 * k0;
    wire [15:0] prod1 = p1 * k1;
    wire [15:0] prod2 = p2 * k2;
    wire [15:0] prod3 = p3 * k3;
    wire [15:0] prod4 = p4 * k4;
    wire [15:0] prod5 = p5 * k5;
    wire [15:0] prod6 = p6 * k6;
    wire [15:0] prod7 = p7 * k7;
    wire [15:0] prod8 = p8 * k8;

    // Single-Cycle Combinational Adder Tree (Non-pipelined, 3 stages of logic)
    // Stage 1: 4 parallel pairwise adders (16-bit + 16-bit -> 17-bit) + 1 pass-through
    wire [16:0] sum_s1_0 = prod0 + prod1;
    wire [16:0] sum_s1_1 = prod2 + prod3;
    wire [16:0] sum_s1_2 = prod4 + prod5;
    wire [16:0] sum_s1_3 = prod6 + prod7;
    wire [16:0] sum_s1_4 = {1'b0, prod8};

    // Stage 2: 2 parallel adders (17-bit + 17-bit -> 18-bit) + 1 pass-through
    wire [17:0] sum_s2_0 = sum_s1_0 + sum_s1_1;
    wire [17:0] sum_s2_1 = sum_s1_2 + sum_s1_3;
    wire [17:0] sum_s2_2 = {1'b0, sum_s1_4};

    // Stage 3: Final accumulation (18-bit + 18-bit -> 19-bit; + 18-bit -> 20-bit)
    wire [18:0] sum_s3_0 = sum_s2_0 + sum_s2_1;
    wire [19:0] raw_conv_sum = sum_s3_0 + {1'b0, sum_s2_2};

    // ReLU Activation Function: f(x) = max(0, x)
    // For unsigned 8-bit operands, raw_conv_sum is always non-negative.
    // Zero-extended to 24 bits for interface consistency with serial architecture.
    wire [23:0] relu_output = {4'b0000, raw_conv_sum};

    // Main Control FSM & Output Pipeline (Synchronous Reset)
    always @(posedge clk) begin
        if (rst) begin
            state     <= IDLE;
            out_row   <= 3'd0;
            out_col   <= 3'd0;
            out_data  <= 24'd0;
            out_valid <= 1'b0;
            done      <= 1'b0;
        end else begin
            // Default single-cycle pulse deassertions
            out_valid <= 1'b0;
            done      <= 1'b0;

            case (state)
                IDLE: begin
                    out_data <= 24'd0;
                    if (start) begin
                        state   <= COMPUTE;
                        out_row <= 3'd0;
                        out_col <= 3'd0;
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

                default: begin
                    state <= IDLE;
                end
            endcase
        end
    end

endmodule
