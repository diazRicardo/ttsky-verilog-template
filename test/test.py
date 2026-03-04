# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

# Opcode definitions
OP_ADD = 0b000
OP_SUB = 0b001
OP_AND = 0b010
OP_OR  = 0b011
OP_XOR = 0b100
OP_SHL = 0b101
OP_SHR = 0b110
OP_CMP = 0b111

# Control bit positions in uio_in
LOAD_A_BIT = 3  # uio_in[3]
LOAD_B_BIT = 4  # uio_in[4]


async def reset_dut(dut):
    """Apply reset to the DUT."""
    dut.rst_n.value = 0
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def load_operand_a(dut, value, opcode=0):
    """Load an 8-bit value into register A."""
    dut.ui_in.value = value & 0xFF
    dut.uio_in.value = (1 << LOAD_A_BIT) | (opcode & 0x07)
    await ClockCycles(dut.clk, 1)
    # Deassert load_a
    dut.uio_in.value = opcode & 0x07
    await ClockCycles(dut.clk, 1)


async def load_operand_b(dut, value, opcode=0):
    """Load an 8-bit value into register B."""
    dut.ui_in.value = value & 0xFF
    dut.uio_in.value = (1 << LOAD_B_BIT) | (opcode & 0x07)
    await ClockCycles(dut.clk, 1)
    # Deassert load_b
    dut.uio_in.value = opcode & 0x07
    await ClockCycles(dut.clk, 1)


async def set_opcode(dut, opcode):
    """Set the opcode on uio_in[2:0] without loading."""
    dut.uio_in.value = opcode & 0x07
    await ClockCycles(dut.clk, 1)


def get_result(dut):
    """Read the 8-bit result from uo_out."""
    return int(dut.uo_out.value)


def get_flags(dut):
    """Read flags from uio_out[3:0]. Returns (carry, zero, negative, overflow)."""
    flags = int(dut.uio_out.value) & 0x0F
    carry    = (flags >> 0) & 1
    zero     = (flags >> 1) & 1
    negative = (flags >> 2) & 1
    overflow = (flags >> 3) & 1
    return carry, zero, negative, overflow


async def alu_operation(dut, a, b, opcode):
    """Load A, load B, set opcode, and return (result, carry, zero, negative, overflow)."""
    await load_operand_a(dut, a, opcode)
    await load_operand_b(dut, b, opcode)
    await set_opcode(dut, opcode)
    result = get_result(dut)
    carry, zero, negative, overflow = get_flags(dut)
    return result, carry, zero, negative, overflow


@cocotb.test()
async def test_reset(dut):
    """Test that reset clears the registers and output is zero."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # After reset with opcode=ADD, result should be 0+0=0
    await set_opcode(dut, OP_ADD)
    result = get_result(dut)
    _, zero, _, _ = get_flags(dut)
    assert result == 0, f"After reset, expected result=0, got {result}"
    assert zero == 1, f"After reset, expected zero flag=1, got {zero}"
    dut._log.info("PASS: Reset test")


@cocotb.test()
async def test_add_basic(dut):
    """Test basic addition operations."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # 5 + 3 = 8
    result, carry, zero, neg, ovf = await alu_operation(dut, 5, 3, OP_ADD)
    assert result == 8, f"5+3: expected 8, got {result}"
    assert carry == 0, f"5+3: expected carry=0, got {carry}"
    assert zero == 0, f"5+3: expected zero=0, got {zero}"
    dut._log.info("PASS: 5 + 3 = 8")

    # 0 + 0 = 0 (zero flag)
    result, carry, zero, neg, ovf = await alu_operation(dut, 0, 0, OP_ADD)
    assert result == 0, f"0+0: expected 0, got {result}"
    assert zero == 1, f"0+0: expected zero=1, got {zero}"
    dut._log.info("PASS: 0 + 0 = 0 (zero flag set)")

    # 200 + 100 = 300 -> 44 with carry (unsigned overflow)
    result, carry, zero, neg, ovf = await alu_operation(dut, 200, 100, OP_ADD)
    assert result == (300 & 0xFF), f"200+100: expected {300 & 0xFF}, got {result}"
    assert carry == 1, f"200+100: expected carry=1, got {carry}"
    dut._log.info("PASS: 200 + 100 = 44 with carry")

    # 255 + 1 = 0 with carry
    result, carry, zero, neg, ovf = await alu_operation(dut, 255, 1, OP_ADD)
    assert result == 0, f"255+1: expected 0, got {result}"
    assert carry == 1, f"255+1: expected carry=1, got {carry}"
    assert zero == 1, f"255+1: expected zero=1, got {zero}"
    dut._log.info("PASS: 255 + 1 = 0 with carry and zero")


@cocotb.test()
async def test_add_signed_overflow(dut):
    """Test signed overflow detection in addition."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # 127 + 1 = 128 (0x80) -> signed overflow (pos + pos = neg)
    result, carry, zero, neg, ovf = await alu_operation(dut, 127, 1, OP_ADD)
    assert result == 128, f"127+1: expected 128, got {result}"
    assert ovf == 1, f"127+1: expected overflow=1, got {ovf}"
    assert neg == 1, f"127+1: expected negative=1, got {neg}"
    dut._log.info("PASS: 127 + 1 signed overflow detected")

    # (-128) + (-1) = (-129) -> signed overflow (neg + neg = pos)
    # In unsigned: 0x80 + 0xFF = 0x17F -> lower 8 bits = 0x7F = 127
    result, carry, zero, neg, ovf = await alu_operation(dut, 0x80, 0xFF, OP_ADD)
    assert result == 0x7F, f"0x80+0xFF: expected 0x7F, got {result:#x}"
    assert ovf == 1, f"0x80+0xFF: expected overflow=1, got {ovf}"
    dut._log.info("PASS: -128 + -1 signed overflow detected")


@cocotb.test()
async def test_sub_basic(dut):
    """Test basic subtraction operations."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # 10 - 3 = 7
    result, carry, zero, neg, ovf = await alu_operation(dut, 10, 3, OP_SUB)
    assert result == 7, f"10-3: expected 7, got {result}"
    assert carry == 0, f"10-3: expected carry(borrow)=0, got {carry}"
    dut._log.info("PASS: 10 - 3 = 7")

    # 5 - 5 = 0 (zero flag)
    result, carry, zero, neg, ovf = await alu_operation(dut, 5, 5, OP_SUB)
    assert result == 0, f"5-5: expected 0, got {result}"
    assert zero == 1, f"5-5: expected zero=1, got {zero}"
    dut._log.info("PASS: 5 - 5 = 0 (zero flag set)")

    # 3 - 10 = -7 (unsigned: 249, borrow set)
    result, carry, zero, neg, ovf = await alu_operation(dut, 3, 10, OP_SUB)
    expected = (3 - 10) & 0xFF  # 249
    assert result == expected, f"3-10: expected {expected}, got {result}"
    assert carry == 1, f"3-10: expected borrow=1, got {carry}"
    assert neg == 1, f"3-10: expected negative=1, got {neg}"
    dut._log.info("PASS: 3 - 10 = 249 (borrow, negative)")


@cocotb.test()
async def test_sub_signed_overflow(dut):
    """Test signed overflow detection in subtraction."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # 127 - (-1) = 128 -> signed overflow
    # 0x7F - 0xFF: result 0x80
    result, carry, zero, neg, ovf = await alu_operation(dut, 0x7F, 0xFF, OP_SUB)
    assert result == 0x80, f"0x7F-0xFF: expected 0x80, got {result:#x}"
    assert ovf == 1, f"0x7F-0xFF: expected overflow=1, got {ovf}"
    dut._log.info("PASS: 127 - (-1) signed overflow detected")

    # (-128) - 1 = -129 -> signed overflow
    # 0x80 - 0x01: result 0x7F
    result, carry, zero, neg, ovf = await alu_operation(dut, 0x80, 0x01, OP_SUB)
    assert result == 0x7F, f"0x80-0x01: expected 0x7F, got {result:#x}"
    assert ovf == 1, f"0x80-0x01: expected overflow=1, got {ovf}"
    dut._log.info("PASS: -128 - 1 signed overflow detected")


@cocotb.test()
async def test_and(dut):
    """Test bitwise AND operation."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    test_cases = [
        (0xFF, 0x0F, 0x0F),
        (0xAA, 0x55, 0x00),
        (0xFF, 0xFF, 0xFF),
        (0x00, 0xFF, 0x00),
        (0b10110100, 0b11010110, 0b10010100),
    ]
    for a, b, expected in test_cases:
        result, carry, zero, neg, ovf = await alu_operation(dut, a, b, OP_AND)
        assert result == expected, f"{a:#x} AND {b:#x}: expected {expected:#x}, got {result:#x}"
        assert carry == 0, f"AND should not set carry"
        if expected == 0:
            assert zero == 1, f"AND result 0 should set zero flag"
    dut._log.info("PASS: AND operations")


@cocotb.test()
async def test_or(dut):
    """Test bitwise OR operation."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    test_cases = [
        (0xFF, 0x0F, 0xFF),
        (0xAA, 0x55, 0xFF),
        (0x00, 0x00, 0x00),
        (0x00, 0xFF, 0xFF),
        (0b10100000, 0b00000101, 0b10100101),
    ]
    for a, b, expected in test_cases:
        result, carry, zero, neg, ovf = await alu_operation(dut, a, b, OP_OR)
        assert result == expected, f"{a:#x} OR {b:#x}: expected {expected:#x}, got {result:#x}"
        if expected == 0:
            assert zero == 1, f"OR result 0 should set zero flag"
    dut._log.info("PASS: OR operations")


@cocotb.test()
async def test_xor(dut):
    """Test bitwise XOR operation."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    test_cases = [
        (0xFF, 0xFF, 0x00),
        (0xAA, 0x55, 0xFF),
        (0x00, 0x00, 0x00),
        (0xFF, 0x00, 0xFF),
        (0b11001100, 0b10101010, 0b01100110),
    ]
    for a, b, expected in test_cases:
        result, carry, zero, neg, ovf = await alu_operation(dut, a, b, OP_XOR)
        assert result == expected, f"{a:#x} XOR {b:#x}: expected {expected:#x}, got {result:#x}"
        if expected == 0:
            assert zero == 1, f"XOR result 0 should set zero flag"
    dut._log.info("PASS: XOR operations")


@cocotb.test()
async def test_shift_left(dut):
    """Test logical shift left operation."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Shift by 0 (no change)
    result, _, _, _, _ = await alu_operation(dut, 0x55, 0, OP_SHL)
    assert result == 0x55, f"0x55 << 0: expected 0x55, got {result:#x}"

    # Shift by 1
    result, _, _, _, _ = await alu_operation(dut, 0x01, 1, OP_SHL)
    assert result == 0x02, f"0x01 << 1: expected 0x02, got {result:#x}"

    # Shift by 4
    result, _, _, _, _ = await alu_operation(dut, 0x0F, 4, OP_SHL)
    assert result == 0xF0, f"0x0F << 4: expected 0xF0, got {result:#x}"

    # Shift by 7 (maximum useful shift)
    result, _, _, _, _ = await alu_operation(dut, 0x01, 7, OP_SHL)
    assert result == 0x80, f"0x01 << 7: expected 0x80, got {result:#x}"

    # Shift causes bits to fall off
    result, _, _, _, _ = await alu_operation(dut, 0xFF, 4, OP_SHL)
    assert result == 0xF0, f"0xFF << 4: expected 0xF0, got {result:#x}"

    dut._log.info("PASS: Shift left operations")


@cocotb.test()
async def test_shift_right(dut):
    """Test logical shift right operation."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Shift by 0
    result, _, _, _, _ = await alu_operation(dut, 0xAA, 0, OP_SHR)
    assert result == 0xAA, f"0xAA >> 0: expected 0xAA, got {result:#x}"

    # Shift by 1
    result, _, _, _, _ = await alu_operation(dut, 0x80, 1, OP_SHR)
    assert result == 0x40, f"0x80 >> 1: expected 0x40, got {result:#x}"

    # Shift by 4
    result, _, _, _, _ = await alu_operation(dut, 0xF0, 4, OP_SHR)
    assert result == 0x0F, f"0xF0 >> 4: expected 0x0F, got {result:#x}"

    # Shift by 7
    result, _, _, _, _ = await alu_operation(dut, 0x80, 7, OP_SHR)
    assert result == 0x01, f"0x80 >> 7: expected 0x01, got {result:#x}"

    dut._log.info("PASS: Shift right operations")


@cocotb.test()
async def test_cmp(dut):
    """Test compare operation (flags only, same as SUB)."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # A == B -> zero flag set
    _, _, zero, _, _ = await alu_operation(dut, 42, 42, OP_CMP)
    assert zero == 1, f"CMP 42,42: expected zero=1, got {zero}"
    dut._log.info("PASS: CMP equal -> zero flag")

    # A > B (unsigned) -> no borrow, not zero
    _, carry, zero, neg, _ = await alu_operation(dut, 100, 50, OP_CMP)
    assert zero == 0, f"CMP 100,50: expected zero=0"
    assert carry == 0, f"CMP 100,50: expected borrow=0"
    dut._log.info("PASS: CMP greater -> no borrow")

    # A < B (unsigned) -> borrow set
    _, carry, zero, neg, _ = await alu_operation(dut, 10, 200, OP_CMP)
    assert carry == 1, f"CMP 10,200: expected borrow=1"
    assert zero == 0, f"CMP 10,200: expected zero=0"
    dut._log.info("PASS: CMP less -> borrow set")


@cocotb.test()
async def test_ena_gating(dut):
    """Test that loads are gated by the ena signal."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # First load A=0x42 normally
    await load_operand_a(dut, 0x42, OP_ADD)
    await load_operand_b(dut, 0x00, OP_ADD)
    await set_opcode(dut, OP_ADD)
    result = get_result(dut)
    assert result == 0x42, f"Initial load: expected 0x42, got {result:#x}"

    # Disable ena, try to load A=0xFF - should not take effect
    dut.ena.value = 0
    await load_operand_a(dut, 0xFF, OP_ADD)
    dut.ena.value = 1
    await load_operand_b(dut, 0x00, OP_ADD)
    await set_opcode(dut, OP_ADD)
    result = get_result(dut)
    assert result == 0x42, f"Ena gating: expected 0x42 (unchanged), got {result:#x}"
    dut._log.info("PASS: ena gating works")


@cocotb.test()
async def test_exhaustive_add(dut):
    """Exhaustive test of a subset of ADD operations for thorough coverage."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Test all boundary values and a selection of interior values
    test_values = [0, 1, 2, 127, 128, 254, 255]
    for a in test_values:
        for b in test_values:
            result, carry, zero, neg, ovf = await alu_operation(dut, a, b, OP_ADD)
            expected_full = a + b
            expected_result = expected_full & 0xFF
            expected_carry = 1 if expected_full > 255 else 0
            expected_zero = 1 if expected_result == 0 else 0

            assert result == expected_result, \
                f"ADD {a}+{b}: expected {expected_result}, got {result}"
            assert carry == expected_carry, \
                f"ADD {a}+{b}: expected carry={expected_carry}, got {carry}"
            assert zero == expected_zero, \
                f"ADD {a}+{b}: expected zero={expected_zero}, got {zero}"

    dut._log.info("PASS: Exhaustive ADD boundary tests (49 combinations)")


@cocotb.test()
async def test_exhaustive_sub(dut):
    """Exhaustive test of a subset of SUB operations for thorough coverage."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    test_values = [0, 1, 2, 127, 128, 254, 255]
    for a in test_values:
        for b in test_values:
            result, carry, zero, neg, ovf = await alu_operation(dut, a, b, OP_SUB)
            expected_full = a - b
            expected_result = expected_full & 0xFF
            expected_carry = 1 if expected_full < 0 else 0
            expected_zero = 1 if expected_result == 0 else 0

            assert result == expected_result, \
                f"SUB {a}-{b}: expected {expected_result}, got {result}"
            assert carry == expected_carry, \
                f"SUB {a}-{b}: expected carry={expected_carry}, got {carry}"
            assert zero == expected_zero, \
                f"SUB {a}-{b}: expected zero={expected_zero}, got {zero}"

    dut._log.info("PASS: Exhaustive SUB boundary tests (49 combinations)")
