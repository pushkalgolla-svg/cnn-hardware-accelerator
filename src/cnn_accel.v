`timescale 1ns / 1ps

module cnn_accel (
    input  wire        clk,
    input  wire        rst,        // Synchronous active-high reset
    input  wire        start,      // 1-cycle active-high pulse to start
    output reg         done,       // High when all 36 outputs finished
    // Memory access ports (requesting data from testbench / memory)
    output wire [5:0]  img_addr,   // 0 to 63
    input  wire [7:0]  img_data,   // 8-bit unsigned pixel
    output wire [3:0]  kernel_addr,// 0 to 8
    input  wire [7:0]  kernel_data,// 8-bit unsigned weight
    // Convolution Output
    output reg  [23:0] out_data,   // 24-bit convolved result
    output reg         out_valid   // 1-cycle pulse when out_data is valid
);

    // FSM States
    parameter IDLE    = 2'b00;
    parameter COMPUTE = 2'b01;
    parameter DONE    = 2'b10;

    // FSM State registers
    reg [1:0] current_state;
    reg [1:0] next_state;

    // Internal Registers for convolution loop counters and accumulator
    // out_row_r: 0 to 5 (6 values), requires 3 bits (e.g., 3'd5)
    reg [2:0] out_row_r;
    // out_col_r: 0 to 5 (6 values), requires 3 bits (e.g., 3'd5)
    reg [2:0] out_col_r;
    // kr_r:      0 to 2 (3 values), requires 2 bits (e.g., 2'd2)
    reg [1:0] kr_r;
    // kc_r:      0 to 2 (3 values), requires 2 bits (e.g., 2'd2)
    reg [1:0] kc_r;

    // Accumulator for MAC unit. Max product: 255*255 = 65025 (16 bits)
    // Max sum of 9 products: 9 * 65025 = 585225.
    // log2(585225) approx 19.16 bits. 24 bits specified is sufficient.
    reg [23:0] acc_r;

    // Intermediate product for MAC unit
    // 8-bit unsigned * 8-bit unsigned = 16-bit unsigned product
    wire [15:0] product_w;

    // MAC operation: Combinational multiplication
    assign product_w = img_data * kernel_data;

    // FSM State Register update logic (Sequential)
    always @(posedge clk) begin
        if (rst) begin
            current_state <= IDLE;
        end else begin
            current_state <= next_state;
        end
    end

    // FSM Next State Logic (Combinational)
    always @(*) begin
        next_state = current_state; // Default: stay in current state
        case (current_state)
            IDLE: begin
                if (start) begin
                    next_state = COMPUTE;
                end
            end
            COMPUTE: begin
                // Transition to DONE when the last MAC for the last output pixel
                // (out_row=5, out_col=5, kr=2, kc=2) is being processed.
                if (out_row_r == 3'd5 && out_col_r == 3'd5 && kr_r == 2'd2 && kc_r == 2'd2) begin
                    next_state = DONE;
                end
            end
            DONE: begin
                next_state = IDLE; // Return to IDLE after one cycle in DONE
            end
            default: begin
                next_state = IDLE; // Failsafe
            end
        endcase
    end

    // Output and Counter Control Logic (Sequential)
    always @(posedge clk) begin
        if (rst) begin
            done        <= 1'b0;
            out_valid   <= 1'b0;
            out_data    <= 24'd0; // Reset output data
            out_row_r   <= 3'd0;
            out_col_r   <= 3'd0;
            kr_r        <= 2'd0;
            kc_r        <= 2'd0;
            acc_r       <= 24'd0; // Reset accumulator
        end else begin
            // Default assignments for outputs not asserted
            done      <= 1'b0;
            out_valid <= 1'b0;
            out_data  <= 24'd0;

            case (current_state)
                IDLE: begin
                    if (start) begin
                        // Initialize counters and accumulator for the start of computation
                        out_row_r   <= 3'd0;
                        out_col_r   <= 3'd0;
                        kr_r        <= 2'd0;
                        kc_r        <= 2'd0;
                        acc_r       <= 24'd0;
                    end
                end
                COMPUTE: begin
                    if (kr_r == 2'd2 && kc_r == 2'd2) begin // This is the 9th MAC step for the current output pixel
                        out_valid <= 1'b1;
                        // Accumulate the final product and output the complete sum
                        out_data  <= acc_r + product_w;
                        acc_r     <= 24'd0; // Reset accumulator for the next output pixel

                        // Advance out_col, out_row for the next output pixel
                        if (out_col_r == 3'd5) begin // End of current output row
                            out_col_r <= 3'd0; // Reset column counter
                            if (out_row_r == 3'd5) begin // End of all output rows (last pixel of last row)
                                // All output pixels computed, counters remain at their last value
                                // until next start or reset. Resetting to 0 here for clarity.
                                out_row_r <= 3'd0;
                            end else begin
                                out_row_r <= out_row_r + 3'd1; // Next output row
                            end
                        end else begin
                            out_col_r <= out_col_r + 3'd1; // Next output column
                        end

                        // Reset kr, kc for the start of the next output pixel's 9 MACs
                        kr_r <= 2'd0;
                        kc_r <= 2'd0;
                    end else begin // Not the last MAC step for the current output pixel
                        acc_r <= acc_r + product_w; // Accumulate product

                        // Advance kc, kr for the next MAC operation within the same output pixel
                        if (kc_r == 2'd2) begin // End of kernel column loop
                            kc_r <= 2'd0; // Reset kernel column counter
                            kr_r <= kr_r + 2'd1; // Next kernel row
                        end else begin
                            kc_r <= kc_r + 2'd1; // Next kernel column
                        end
                    end
                end
                DONE: begin
                    done <= 1'b1; // Assert done signal
                end
                default: begin
                    // Failsafe assignments
                    out_row_r   <= 3'd0;
                    out_col_r   <= 3'd0;
                    kr_r        <= 2'd0;
                    kc_r        <= 2'd0;
                    acc_r       <= 24'd0;
                end
            endcase
        end
    end

    // Combinational Address Generation for Image Data
    // img_addr = ((out_row + kr) * 8) + (out_col + kc)
    // (out_row_r + kr_r) maximum value: (5 + 2) = 7 (fits in 3 bits)
    // (out_col_r + kc_r) maximum value: (5 + 2) = 7 (fits in 3 bits)
    // (7 << 3) + 7 = 56 + 7 = 63 (fits in 6 bits, 0-63)
    assign img_addr = ((out_row_r + kr_r) << 3) + (out_col_r + kc_r);

    // Combinational Address Generation for Kernel Data
    // kernel_addr = (kr * 3) + kc
    // (kr_r * 3'd3) maximum value: (2 * 3) = 6 (fits in 3 bits)
    // (kc_r) maximum value: 2 (fits in 2 bits)
    // 6 + 2 = 8 (fits in 4 bits, 0-8)
    assign kernel_addr = (kr_r * 3'd3) + kc_r;

endmodule
