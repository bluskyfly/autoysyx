# Test lui + add (R-type) chains: build constants > 12 bits and accumulate.
# At halt, a0 should be 0.
_start:
    # 12-bit signed imm max is +0x7ff = 2047, so use 0x678 to stay safe.
    lui  t0, 0x12340           # t0 = 0x12340000
    addi t0, t0, 0x678         # t0 = 0x12340678
    lui  t1, 0x12340
    addi t1, t1, 0x678         # t1 = 0x12340678

    add  t0, t0, t1            # t0 = 0x24680cf0 (overflow-safe in 32 bits)
    addi sp, zero, 0x200
    sw   t0, 0(sp)
    lw   t2, 0(sp)
    # Expected bytes (little-endian): 0xf0, 0x0c, 0x68, 0x24.
    add  a0, zero, zero
    lbu  a1, 0(sp)
    addi a1, a1, -0xf0
    add  a0, a0, a1
    lbu  a1, 1(sp)
    addi a1, a1, -0x0c
    add  a0, a0, a1
    lbu  a1, 2(sp)
    addi a1, a1, -0x68
    add  a0, a0, a1
    lbu  a1, 3(sp)
    addi a1, a1, -0x24
    add  a0, a0, a1
done:
    jalr zero, done(zero)
