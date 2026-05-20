# Test addi sign-extension.
# After all ops, a0 should be 0 (success), else non-zero.
# addi sign-extends a 12-bit immediate; -1 must become 0xFFFFFFFF, not 0x00000FFF.
_start:
    addi a0, zero, -1        # a0 = 0xFFFFFFFF if sign-ext correct, else 0x0FFF
    addi a0, a0, 1           # a0 = 0 (overflow wraps to 0)
    addi a1, zero, -2048     # most-negative 12-bit imm: -2048
    addi a1, a1, 2047        # a1 = -1
    addi a1, a1, 1           # a1 = 0
    add  a0, a0, a1          # a0 still 0 if both worked
    addi a2, zero, 0x7ff     # +2047 (max positive)
    addi a2, a2, -2047       # a2 = 0
    add  a0, a0, a2          # a0 still 0
    # Halt: self-loop at this PC.
done:
    jalr zero, done(zero)
