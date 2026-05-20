# F6 memory test: lw / sw / lbu / sb following the doc hint.
# Data address = 0x100 (sp). Builds 0x12345678, verifies lbu byte split,
# overwrites with sb to form 0x90abcdef, re-verifies via lbu.
# Result: a0 == 0 iff every byte matched.
_start:
    addi sp, zero, 0x100         # data address
    lui  t0, 0x12345             # t0 = 0x12345000
    addi t0, t0, 0x678           # t0 = 0x12345678
    sw   t0, 0(sp)               # mem[0x100] = 0x12345678
    add  a0, zero, zero          # success accumulator

    # Read bytes back via lbu; each should match the expected byte.
    lbu  t2, 0(sp)
    addi t2, t2, -0x78
    add  a0, a0, t2
    lbu  t2, 1(sp)
    addi t2, t2, -0x56
    add  a0, a0, t2
    lbu  t2, 2(sp)
    addi t2, t2, -0x34
    add  a0, a0, t2
    lbu  t2, 3(sp)
    addi t2, t2, -0x12
    add  a0, a0, t2

    # sb writes to form 0x90abcdef.
    addi t1, zero, 0xef
    sb   t1, 0(sp)
    addi t1, zero, 0xcd
    sb   t1, 1(sp)
    addi t1, zero, 0xab
    sb   t1, 2(sp)
    addi t1, zero, 0x90
    sb   t1, 3(sp)

    # Verify each byte.
    lbu  t2, 0(sp)
    addi t2, t2, -0xef
    add  a0, a0, t2
    lbu  t2, 1(sp)
    addi t2, t2, -0xcd
    add  a0, a0, t2
    lbu  t2, 2(sp)
    addi t2, t2, -0xab
    add  a0, a0, t2
    lbu  t2, 3(sp)
    addi t2, t2, -0x90
    add  a0, a0, t2
done:
    jalr zero, done(zero)
