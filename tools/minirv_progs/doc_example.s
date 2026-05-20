# Doc example program from docs-md/2407/f/6.md
# Expected: a0 = 30, halt at PC=0xc
_start:
    addi a0, zero, 20
    jalr ra, 16(zero)     # call fun
    jalr ra, 12(zero)     # call halt (also tail-call)
halt:
    jalr zero, 12(zero)   # self loop at 0xc
fun:
    addi a0, a0, 10
    jalr zero, 0(ra)
