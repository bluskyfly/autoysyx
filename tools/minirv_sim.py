#!/usr/bin/env python3
"""miniRV reference simulator.

miniRV is an 8-instruction subset of RV32I used by ysyx F6:
  add, addi, lui, lw, lbu, sw, sb, jalr.

State (matches RV32E layout):
  - 32-bit PC, starting at 0, word-aligned.
  - 16 general purpose registers x0..x15 (x0 hardwired to 0).
  - Byte-addressable little-endian memory.
  - Optional VGA framebuffer mapped at [0x20000000, 0x20040000).

This module is the reference model F6 uses to validate the Logisim circuit.
The same hex programs are loaded into both; equivalent end-states prove the
hardware design is consistent with the ISA semantics.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


VGA_BASE = 0x20000000
VGA_END = 0x20040000  # exclusive
MASK32 = 0xFFFFFFFF


def sext(value: int, bits: int) -> int:
    """Sign-extend `value` (which is `bits`-bit wide) to a signed Python int."""
    sign = 1 << (bits - 1)
    return (value & ((1 << bits) - 1)) - ((value & sign) << 1)


def u32(value: int) -> int:
    return value & MASK32


class Memory:
    """Sparse byte-addressable little-endian memory, plus VGA MMIO frame."""

    def __init__(self) -> None:
        # dict word_addr -> 32-bit value, default 0
        self._words: Dict[int, int] = {}
        # VGA: dict (x, y) -> 24-bit RGB value
        self.vga: Dict[Tuple[int, int], int] = {}
        # Trace store/load addresses for debugging.
        self.last_store: Optional[Tuple[int, int, int]] = None  # (addr, value, mask)

    def _read_word(self, addr: int) -> int:
        return self._words.get(addr & ~3, 0) & MASK32

    def _write_word(self, addr: int, value: int, byte_mask: int) -> None:
        base = addr & ~3
        old = self._words.get(base, 0)
        merged = 0
        for i in range(4):
            byte_sel = (byte_mask >> i) & 1
            src = value if byte_sel else old
            merged |= ((src >> (i * 8)) & 0xFF) << (i * 8)
        self._words[base] = merged & MASK32

    def load_word(self, addr: int) -> int:
        # Word-aligned load expected (F6 doc explicitly excludes misaligned).
        assert addr % 4 == 0, f"lw misaligned addr=0x{addr:08x}"
        if VGA_BASE <= addr < VGA_END:
            # The VGA region is write-only in our model; reads return 0 like
            # an undefined memory-mapped area.
            return 0
        return self._read_word(addr)

    def load_byte_unsigned(self, addr: int) -> int:
        word = self._read_word(addr)
        off = addr & 3
        return (word >> (off * 8)) & 0xFF

    def store_word(self, addr: int, value: int) -> None:
        assert addr % 4 == 0, f"sw misaligned addr=0x{addr:08x}"
        value = u32(value)
        if VGA_BASE <= addr < VGA_END:
            # 256x256 framebuffer; each pixel takes 4 bytes (3 used).
            rel = (addr - VGA_BASE) >> 2
            x = rel & 0xFF
            y = (rel >> 8) & 0xFF
            self.vga[(x, y)] = value & 0xFFFFFF
            self.last_store = (addr, value, 0xF)
            return
        self._write_word(addr, value, 0xF)
        self.last_store = (addr, value, 0xF)

    def store_byte(self, addr: int, value: int) -> None:
        value = u32(value) & 0xFF
        off = addr & 3
        mask = 1 << off
        # Replicate the byte to the right lane.
        word_val = (value & 0xFF) << (off * 8)
        if VGA_BASE <= addr < VGA_END:
            # Byte store into VGA is not part of our spec (sw only) — but the
            # operation is still well-defined: merge into existing word.
            base = addr & ~3
            rel = (base - VGA_BASE) >> 2
            x = rel & 0xFF
            y = (rel >> 8) & 0xFF
            old = self.vga.get((x, y), 0)
            old &= ~(0xFF << (off * 8))
            old |= word_val
            self.vga[(x, y)] = old & 0xFFFFFF
            self.last_store = (addr, value, mask)
            return
        self._write_word(addr & ~3, word_val, mask)
        self.last_store = (addr, value, mask)

    def fetch(self, pc: int) -> int:
        # ROM and RAM are aliased in our model — same word read.
        assert pc % 4 == 0, f"fetch misaligned pc=0x{pc:08x}"
        return self._read_word(pc)

    def load_hex(self, path: str, base: int = 0) -> None:
        """Load a Logisim 'v3.0 hex words plain' (or 'v2.0 raw') style file."""
        with open(path, "r", encoding="utf-8") as fp:
            text = fp.read()
        addr = base
        for raw in text.splitlines():
            # Strip comments and Logisim header line.
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if line.lower().startswith("v2.0") or line.lower().startswith("v3.0"):
                continue
            for tok in line.split():
                # Logisim supports run-length like "4*deadbeef".
                m = re.match(r"^(\d+)\*([0-9a-fA-F]+)$", tok)
                if m:
                    count = int(m.group(1))
                    val = int(m.group(2), 16)
                    for _ in range(count):
                        self._words[addr] = val & MASK32
                        addr += 4
                    continue
                val = int(tok, 16)
                self._words[addr] = val & MASK32
                addr += 4


@dataclass
class CPU:
    mem: Memory = field(default_factory=Memory)
    pc: int = 0
    gpr: List[int] = field(default_factory=lambda: [0] * 16)
    cycles: int = 0
    halted: bool = False
    halt_pc: Optional[int] = None
    trace: bool = False
    instr_log: List[str] = field(default_factory=list)

    def reg(self, idx: int) -> int:
        # x0 hardwired to 0.
        return 0 if idx == 0 else self.gpr[idx & 0xF]

    def set_reg(self, idx: int, value: int) -> None:
        if idx == 0:
            return
        self.gpr[idx & 0xF] = u32(value)

    def step(self) -> None:
        if self.halted:
            return
        pc = self.pc
        inst = self.mem.fetch(pc)
        opcode = inst & 0x7F
        rd = (inst >> 7) & 0x1F
        funct3 = (inst >> 12) & 0x7
        rs1 = (inst >> 15) & 0x1F
        rs2 = (inst >> 20) & 0x1F
        # rd/rs1/rs2 in miniRV must fit in 4 bits (RV32E); we still tolerate
        # the encoded 5 bits and mask, matching the hardware design.
        imm_i = sext((inst >> 20) & 0xFFF, 12)
        imm_s = sext((((inst >> 25) & 0x7F) << 5) | ((inst >> 7) & 0x1F), 12)
        imm_u = inst & 0xFFFFF000  # already shifted into the high 20 bits

        next_pc = u32(pc + 4)
        mnem = "???"

        if opcode == 0x33 and funct3 == 0x0:
            # add (R-type): we don't decode funct7 separately because only
            # add is supported; sub is intentionally not part of miniRV.
            self.set_reg(rd, u32(self.reg(rs1) + self.reg(rs2)))
            mnem = f"add x{rd}, x{rs1}, x{rs2}"
        elif opcode == 0x13 and funct3 == 0x0:
            # addi
            self.set_reg(rd, u32(self.reg(rs1) + imm_i))
            mnem = f"addi x{rd}, x{rs1}, {imm_i}"
        elif opcode == 0x37:
            # lui
            self.set_reg(rd, u32(imm_u))
            mnem = f"lui x{rd}, 0x{imm_u >> 12:x}"
        elif opcode == 0x03 and funct3 == 0x2:
            # lw
            addr = u32(self.reg(rs1) + imm_i)
            self.set_reg(rd, self.mem.load_word(addr))
            mnem = f"lw x{rd}, {imm_i}(x{rs1})"
        elif opcode == 0x03 and funct3 == 0x4:
            # lbu
            addr = u32(self.reg(rs1) + imm_i)
            self.set_reg(rd, self.mem.load_byte_unsigned(addr))
            mnem = f"lbu x{rd}, {imm_i}(x{rs1})"
        elif opcode == 0x23 and funct3 == 0x2:
            # sw
            addr = u32(self.reg(rs1) + imm_s)
            self.mem.store_word(addr, self.reg(rs2))
            mnem = f"sw x{rs2}, {imm_s}(x{rs1})"
        elif opcode == 0x23 and funct3 == 0x0:
            # sb
            addr = u32(self.reg(rs1) + imm_s)
            self.mem.store_byte(addr, self.reg(rs2))
            mnem = f"sb x{rs2}, {imm_s}(x{rs1})"
        elif opcode == 0x67 and funct3 == 0x0:
            # jalr: rd <- pc+4 ; pc <- (rs1+imm) & ~1
            target = u32((self.reg(rs1) + imm_i) & ~1)
            self.set_reg(rd, next_pc)
            # Halt detection: jalr-to-self (canonical halt() in ysyx tests).
            if target == pc:
                self.halted = True
                self.halt_pc = pc
            next_pc = target
            mnem = f"jalr x{rd}, {imm_i}(x{rs1})"
        else:
            raise RuntimeError(
                f"illegal instruction at pc=0x{pc:08x}: 0x{inst:08x} "
                f"opcode=0x{opcode:02x} funct3=0x{funct3:x}"
            )

        if self.trace:
            self.instr_log.append(f"{self.cycles:6d} 0x{pc:08x} {inst:08x}  {mnem}")

        self.pc = next_pc
        self.cycles += 1

    def run(self, max_cycles: int = 100000) -> str:
        while not self.halted and self.cycles < max_cycles:
            self.step()
        if self.halted:
            return "halted"
        return "cycle-limit"


def dump_state(cpu: CPU) -> str:
    lines = [f"pc=0x{cpu.pc:08x} cycles={cpu.cycles} halted={cpu.halted}"]
    abi = [
        "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
        "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
    ]
    for i in range(16):
        lines.append(f"  x{i:<2} ({abi[i]:>4}) = 0x{cpu.reg(i):08x}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="miniRV reference simulator")
    p.add_argument("hex", help="Program hex image (Logisim v2.0/v3.0 format)")
    p.add_argument("--max-cycles", type=int, default=100000)
    p.add_argument("--trace", action="store_true", help="Print every instruction")
    p.add_argument("--expect-a0", type=lambda x: int(x, 0), default=None,
                   help="Required a0 (x10) value at end of run; non-match -> exit 2")
    p.add_argument("--expect-halt", action="store_true",
                   help="Require the program reached a jalr-to-self halt")
    p.add_argument("--expect-halt-pc", type=lambda x: int(x, 0), default=None,
                   help="Required PC value at halt (e.g. address of `halt:`)")
    p.add_argument("--expect-mem", action="append", default=[],
                   help="Memory assertion ADDR=VALUE (both hex). May be repeated")
    p.add_argument("--load-data", action="append", default=[],
                   help="Pre-load memory: ADDR=HEXWORD (e.g. 0x100=0x12345678). May be repeated")
    args = p.parse_args(argv)

    cpu = CPU(trace=args.trace)
    cpu.mem.load_hex(args.hex)
    for spec in args.load_data:
        addr_s, val_s = spec.split("=")
        cpu.mem._words[int(addr_s, 0) & ~3] = int(val_s, 0) & MASK32

    status = cpu.run(max_cycles=args.max_cycles)

    if args.trace:
        for line in cpu.instr_log[-40:]:
            print(line)

    print(dump_state(cpu))
    print(f"status: {status}")

    failures: List[str] = []
    if args.expect_halt and not cpu.halted:
        failures.append("expected halt, but cycle-limit was reached")
    if args.expect_halt_pc is not None:
        if cpu.halt_pc != args.expect_halt_pc:
            failures.append(
                f"halt pc 0x{cpu.halt_pc or 0:08x} != expected 0x{args.expect_halt_pc:08x}")
    if args.expect_a0 is not None:
        if cpu.reg(10) != (args.expect_a0 & MASK32):
            failures.append(
                f"a0=0x{cpu.reg(10):08x} != expected 0x{args.expect_a0 & MASK32:08x}")
    for spec in args.expect_mem:
        addr_s, val_s = spec.split("=")
        addr = int(addr_s, 0)
        want = int(val_s, 0) & MASK32
        got = cpu.mem._read_word(addr)
        if got != want:
            failures.append(
                f"mem[0x{addr:08x}]=0x{got:08x} != expected 0x{want:08x}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 2
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
