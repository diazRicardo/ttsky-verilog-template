<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This project implements an 8-bit Arithmetic Logic Unit (ALU) with registered operands and status flags. The ALU supports eight operations selectable via a 3-bit opcode, and provides four condition flags (carry, zero, negative, overflow) for use in conditional branching or status monitoring.

### Architecture

The design uses a **load-store operand model** to work within the TinyTapeout I/O constraints (8 dedicated inputs, 8 dedicated outputs, 8 bidirectional I/Os). Two 8-bit operands (A and B) are loaded sequentially through the shared `ui_in` data bus, latched into internal registers on the rising clock edge. Once both operands are loaded, the ALU computes the result combinationally based on the selected opcode and presents it on `uo_out` along with status flags on `uio_out[3:0]`.

### Opcode Table

| Opcode (uio_in[2:0]) | Mnemonic | Operation | Description |
|---|---|---|---|
| 000 | ADD | A + B | Unsigned/signed addition |
| 001 | SUB | A − B | Unsigned/signed subtraction |
| 010 | AND | A & B | Bitwise AND |
| 011 | OR  | A \| B | Bitwise OR |
| 100 | XOR | A ^ B | Bitwise XOR |
| 101 | SHL | A << B[2:0] | Logical shift left (shift amount 0–7) |
| 110 | SHR | A >> B[2:0] | Logical shift right (shift amount 0–7) |
| 111 | CMP | A − B (flags only) | Compare: result = A − B, flags indicate relationship |

### Status Flags

| Flag | uio_out Bit | Description |
|---|---|---|
| Carry (C) | [0] | Set on unsigned overflow (ADD) or borrow (SUB/CMP) |
| Zero (Z) | [1] | Set when the 8-bit result equals zero |
| Negative (N) | [2] | Set when bit 7 of the result is 1 (sign bit in two's complement) |
| Overflow (V) | [3] | Set on signed overflow (result sign incorrect for the operand signs) |

### Internal Registers

The ALU contains two 8-bit registers (`reg_a` and `reg_b`) that are cleared on reset and loaded via the `load_a` and `load_b` control signals. The ALU output is purely combinational from the registered operands and the current opcode, so the result updates immediately when the opcode changes (no additional clock cycle needed after operands are loaded).

### Design Decisions

- **Registered operands** allow the two 8-bit values to be loaded sequentially through a single 8-bit data bus, working within the pin constraints.
- **Combinational output** means the result reflects the current opcode at all times. Changing the opcode with the same operands loaded will instantly produce the new result.
- The `ena` signal gates all register updates, supporting the TinyTapeout enable/disable mechanism.
- Shift operations use only the lower 3 bits of operand B as the shift amount (0–7), which covers the full useful range for an 8-bit value.
- The CMP operation is functionally identical to SUB but is provided as a distinct opcode for clarity in applications that only need the flag outputs.

## How to test

### Pin Mapping

**Inputs:**
- `ui_in[7:0]`: 8-bit data bus for loading operands A and B

**Bidirectional (Input):**
- `uio_in[2:0]`: 3-bit opcode select
- `uio_in[3]`: `load_a` — assert high for one clock cycle to latch `ui_in` into register A
- `uio_in[4]`: `load_b` — assert high for one clock cycle to latch `ui_in` into register B
- `uio_in[7:5]`: Reserved (active low, directly unused)

**Outputs:**
- `uo_out[7:0]`: 8-bit ALU result

**Bidirectional (Output):**
- `uio_out[0]`: Carry flag
- `uio_out[1]`: Zero flag
- `uio_out[2]`: Negative flag
- `uio_out[3]`: Overflow flag
- `uio_out[7:4]`: Tied low (unused)

### Test Procedure

1. **Reset**: Assert `rst_n` low for at least 2 clock cycles, then release. Both operand registers clear to zero.
2. **Load Operand A**: Place the desired 8-bit value on `ui_in`, assert `uio_in[3]` (load_a) high, and clock once.
3. **Load Operand B**: Place the desired 8-bit value on `ui_in`, assert `uio_in[4]` (load_b) high, set `uio_in[2:0]` to the desired opcode, and clock once.
4. **Read Result**: After deasserting load signals, the result appears on `uo_out` and flags on `uio_out[3:0]`.

### Testbench Summary

The cocotb testbench (`test.py`) contains 13 test cases that thoroughly verify the ALU:

- **test_reset**: Verifies registers clear to zero and the zero flag is set after reset.
- **test_add_basic**: Tests addition with zero, small values, unsigned carry, and wrap-around (255+1).
- **test_add_signed_overflow**: Verifies signed overflow detection for positive overflow (127+1) and negative overflow (−128 + −1).
- **test_sub_basic**: Tests subtraction producing positive results, zero, and borrow (underflow).
- **test_sub_signed_overflow**: Verifies signed overflow for SUB (127 − (−1) and −128 − 1).
- **test_and / test_or / test_xor**: Each tests 5 input combinations including all-ones, all-zeros, complementary patterns, and arbitrary bit patterns.
- **test_shift_left / test_shift_right**: Tests shift by 0, 1, 4, and 7 positions, including bit loss from shifting.
- **test_cmp**: Verifies zero flag for equality, no borrow for A > B, and borrow for A < B.
- **test_ena_gating**: Confirms that register loads are blocked when `ena` is deasserted.
- **test_exhaustive_add / test_exhaustive_sub**: Tests all 49 combinations of boundary values {0, 1, 2, 127, 128, 254, 255} for ADD and SUB, checking result, carry, and zero flag for each.

The testbench is self-checking — every test uses assertions to verify expected results and flags. Any mismatch causes an immediate test failure with a descriptive error message.

### Use of GenAI Tools
Claude (Anthropic) was used as a collaborative tool throughout the development of this project. The overall design concept — an 8-bit ALU with registered operands, a load-store interface to accommodate TinyTapeout's pin constraints, and combinational output with status flags — was developed through an iterative conversation with the AI. I described the assignment requirements and my goal of implementing a simple ALU, and Claude helped refine the architecture by suggesting the operand-loading protocol (using load_a and load_b control signals to sequentially latch two 8-bit values through a shared data bus), selecting the eight operations to support, and determining how to map control signals and flags onto the available bidirectional I/O pins. The Verilog source code for the top-level module was generated by Claude based on this jointly developed specification, and I reviewed the output for correctness and adherence to the TinyTapeout interface before integrating it into the repository.
Claude also designed and wrote the cocotb testbench. I requested comprehensive verification coverage, and the AI produced 13 self-checking test cases spanning reset behavior, each ALU operation, signed overflow detection for both addition and subtraction, enable-gating verification, and exhaustive boundary-value testing of ADD and SUB across 49 operand combinations using edge-case values (0, 1, 2, 127, 128, 254, 255). The testbench was validated by compiling the design with Icarus Verilog and running a standalone Verilog testbench to confirm all operations produced correct results and flags before committing. All test infrastructure, including the tb.v cocotb wrapper and the documentation in docs/info.md, was similarly generated with Claude's assistance and reviewed by me for accuracy.
