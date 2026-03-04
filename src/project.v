/*
 * Copyright (c) 2025 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_alu (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // will go high when the design is enabled
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    // =========================================================================
    // 8-Bit ALU with Registered Operands and Status Flags
    // =========================================================================
    //
    // Pin Mapping:
    //   ui_in[7:0]  - Data bus (used to load operand A and operand B)
    //   uio_in[2:0] - Opcode select (3 bits, 8 operations)
    //   uio_in[3]   - load_a: when high on rising clock edge, load ui_in into reg_a
    //   uio_in[4]   - load_b: when high on rising clock edge, load ui_in into reg_b
    //                  (result is computed combinationally once both operands are loaded)
    //   uio_in[7:5] - Reserved (directly unused)
    //
    //   uo_out[7:0] - ALU result (lower 8 bits)
    //   uio_out[0]  - Carry/borrow flag
    //   uio_out[1]  - Zero flag
    //   uio_out[2]  - Negative flag (sign bit of result)
    //   uio_out[3]  - Overflow flag (signed overflow)
    //   uio_out[7:4]- Tied to 0
    //
    //   uio_oe      - Lower 4 bits are outputs (flags), upper 4 bits are inputs
    //
    // Opcode Table:
    //   000 - ADD:  A + B
    //   001 - SUB:  A - B
    //   010 - AND:  A & B
    //   011 - OR:   A | B
    //   100 - XOR:  A ^ B
    //   101 - SHL:  A << B[2:0]  (logical shift left, shift amount = B[2:0])
    //   110 - SHR:  A >> B[2:0]  (logical shift right, shift amount = B[2:0])
    //   111 - CMP:  Compare (result = A - B, only flags are meaningful)
    // =========================================================================

    // -- Bidirectional IO direction: lower 4 bits output (flags), upper 4 bits input
    assign uio_oe = 8'b0000_1111;

    // -- Control signals from uio_in
    wire [2:0] opcode  = uio_in[2:0];
    wire       load_a  = uio_in[3];
    wire       load_b  = uio_in[4];

    // -- Registered operands
    reg [7:0] reg_a;
    reg [7:0] reg_b;

    always @(posedge clk) begin
        if (!rst_n) begin
            reg_a <= 8'b0;
            reg_b <= 8'b0;
        end else if (ena) begin
            if (load_a)
                reg_a <= ui_in;
            if (load_b)
                reg_b <= ui_in;
        end
    end

    // -- ALU combinational logic
    reg  [8:0] alu_result;  // 9 bits to capture carry
    reg        overflow;

    always @(*) begin
        alu_result = 9'b0;
        overflow   = 1'b0;

        case (opcode)
            3'b000: begin  // ADD
                alu_result = {1'b0, reg_a} + {1'b0, reg_b};
                // Signed overflow: both operands same sign, result different sign
                overflow = (reg_a[7] == reg_b[7]) && (alu_result[7] != reg_a[7]);
            end
            3'b001: begin  // SUB
                alu_result = {1'b0, reg_a} - {1'b0, reg_b};
                // Signed overflow: operands different sign, result sign != A's sign
                overflow = (reg_a[7] != reg_b[7]) && (alu_result[7] != reg_a[7]);
            end
            3'b010: begin  // AND
                alu_result = {1'b0, reg_a & reg_b};
            end
            3'b011: begin  // OR
                alu_result = {1'b0, reg_a | reg_b};
            end
            3'b100: begin  // XOR
                alu_result = {1'b0, reg_a ^ reg_b};
            end
            3'b101: begin  // SHL (logical shift left)
                alu_result = {1'b0, reg_a} << reg_b[2:0];
            end
            3'b110: begin  // SHR (logical shift right)
                alu_result = {1'b0, reg_a >> reg_b[2:0]};
            end
            3'b111: begin  // CMP (same as SUB, result used for flags)
                alu_result = {1'b0, reg_a} - {1'b0, reg_b};
                overflow = (reg_a[7] != reg_b[7]) && (alu_result[7] != reg_a[7]);
            end
        endcase
    end

    // -- Output assignments
    assign uo_out = alu_result[7:0];

    // -- Flag outputs on uio_out[3:0]
    assign uio_out[0] = alu_result[8];             // Carry / borrow
    assign uio_out[1] = (alu_result[7:0] == 8'b0); // Zero
    assign uio_out[2] = alu_result[7];              // Negative (sign bit)
    assign uio_out[3] = overflow;                   // Overflow
    assign uio_out[7:4] = 4'b0;                    // Unused outputs tied low

endmodule
