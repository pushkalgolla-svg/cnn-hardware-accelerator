// ==============================================================================
// cnn_accel.v
// Architecture A: Baseline Serial Multiply-Accumulate (MAC) CNN Accelerator
// Computes valid 2D convolution of an 8x8 image with a 3x3 kernel (6x6 output).
// Operates on unsigned 8-bit image pixels and unsigned 8-bit kernel weights.
// Area-minimal design: 1 MAC unit, on-the-fly 2D address generation.
// Standard Verilog-2001 synthesizable RTL.
// ==============================================================================

`timescale 1ns / 1ps

module cnn_accel (
    input  wire        clk,
    input  wire        rst,         // Synchronous active-high reset
    input  wire        start,       // 1-cycle active-high pulse to start
    output reg         done,        // High for 1 cycle when all 36 outputs are finished
    // Memory access ports (requesting data cycle-by-cycle)
    output wire [5:0]  img_addr,    // 0 to 63
    input  wire [7:0]  img_data,    // 8-bit unsigned pixel
    output wire [3:0]  kernel_addr, // 0 to 8
    input  wire [7:0]  kernel_data, // 8-bit unsigned weight
    // Convolution Output Stream
    output reg  [23:0] out_data,    // 24-bit accumulated convolution result
    output reg         out_valid    // 1-cycle pulse when out_data is valid
);

    // FSM State Encoding
    localparam [1:0] IDLE    = 2'b00;
    localparam [1:0] COMPUTE = 2'b01;
    localparam [1:0] DONE    = 2'b10;

    reg [1:0] current_state;
    reg [1:0] next_state;

    // Output Feature Map coordinate counters (6x6 output -> 0 to 5)
    reg [2:0] out_row_r;
    reg [2:0] out_col_r;

    // Kernel coordinate counters (3x3 kernel -> 0 to 2)
    reg [1:0] kr_r;
    reg [1:0] kc_r;

    // 24-bit Accumulator register
    // Max theoretical product: 255 * 255 = 65,025 (16 bits)
    // Max sum of 9 products: 9 * 65,025 = 585,225 (requires 20 bits)
    // 24-bit width provides complete dynamic range headroom against overflow.
    reg [23:0] acc_r;

    // Dedicated 8-bit unsigned multiplier
    wire [15:0] product_w = img_data * kernel_data;

    // Robust 2D Address Generation
    // Image address = ((out_row + kr) * 8) + (out_col + kc)
    // For 8x8 row-major addressing, multiplying by 8 is equivalent to
    // placing the 3-bit row coordinate in bits [5:3] and col in [2:0].
    wire [2:0] cur_img_row = out_row_r + {1'b0, kr_r};
    wire [2:0] cur_img_col = out_col_r + {1'b0, kc_r};
    assign img_addr = {cur_img_row, cur_img_col};

    // Kernel address = (kr * 3) + kc (range 0 to 8, fits in 4 bits)
    wire [3:0] cur_kr = {2'b00, kr_r};
    wire [3:0] cur_kc = {2'b00, kc_r};
    assign kernel_addr = (cur_kr * 4'd3) + cur_kc;

    // FSM State Register (Synchronous Reset)
    always @(posedge clk) begin
        if (rst) begin
            current_state <= IDLE;
        end else begin
            current_state <= next_state;
        end
    end

    // FSM Next-State Logic (Combinational)
    always @(*) begin
        next_state = current_state;
        case (current_state)
            IDLE: begin
                if (start) begin
                    next_state = COMPUTE;
                end
            end

            COMPUTE: begin
                // Transition to DONE on the final MAC of the 36th output pixel
                if (out_row_r == 3'd5 && out_col_r == 3'd5 && kr_r == 2'd2 && kc_r == 2'd2) begin
                    next_state = DONE;
                end
            end

            DONE: begin
                next_state = IDLE;
            end

            default: begin
                next_state = IDLE;
            end
        endcase
    end

    // Datapath & Counter Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            done        <= 1'b0;
            out_valid   <= 1'b0;
            out_data    <= 24'd0;
            out_row_r   <= 3'd0;
            out_col_r   <= 3'd0;
            kr_r        <= 2'd0;
            kc_r        <= 2'd0;
            acc_r       <= 24'd0;
        end else begin
            // Default single-cycle pulses
            done      <= 1'b0;
            out_valid <= 1'b0;

            case (current_state)
                IDLE: begin
                    out_data <= 24'd0;
                    if (start) begin
                        out_row_r <= 3'd0;
                        out_col_r <= 3'd0;
                        kr_r      <= 2'd0;
                        kc_r      <= 2'd0;
                        acc_r     <= 24'd0;
                    end
                end

                COMPUTE: begin
                    // Check if this is the 9th MAC step for the current output pixel
                    if (kr_r == 2'd2 && kc_r == 2'd2) begin
                        out_valid <= 1'b1;
                        out_data  <= acc_r + {8'd0, product_w};
                        acc_r     <= 24'd0; // Reset accumulator for next pixel

                        // Reset kernel coordinate counters
                        kr_r <= 2'd0;
                        kc_r <= 2'd0;

                        // Advance output feature map coordinates
                        if (out_col_r == 3'd5) begin
                            out_col_r <= 3'd0;
                            if (out_row_r == 3'd5) begin
                                out_row_r <= 3'd0;
                            end else begin
                                out_row_r <= out_row_r + 3'd1;
                            end
                        end else begin
                            out_col_r <= out_col_r + 3'd1;
                        end
                    end else begin
                        // Accumulate product into register
                        acc_r <= acc_r + {8'd0, product_w};

                        // Advance kernel coordinate counters
                        if (kc_r == 2'd2) begin
                            kc_r <= 2'd0;
                            kr_r <= kr_r + 2'd1;
                        end else begin
                            kc_r <= kc_r + 2'd1;
                        end
                    end
                end

                DONE: begin
                    done <= 1'b1;
                end

                default: begin
                    out_row_r <= 3'd0;
                    out_col_r <= 3'd0;
                    kr_r      <= 2'd0;
                    kc_r      <= 2'd0;
                    acc_r     <= 24'd0;
                end
            endcase
        end
    end

endmodule
