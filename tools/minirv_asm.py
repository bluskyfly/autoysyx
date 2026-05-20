#!/usr/bin/env python3
"""Tiny assembler for miniRV (the 8-instruction RV32I subset used in F6).

Output is a Logisim "v3.0 hex words plain" file, ready to be `Load Image`d
into the ROM/RAM of the Logisim miniRV circuit. The same image is also fed
to tools/minirv_sim.py for the verifier.

Supported instructions (all RV32I-compatible encodings):
  add  rd, rs1, rs2
  addi rd, rs1, imm
  lui  rd, imm20
  lw   rd, imm(rs1)
  lbu  rd, imm(rs1)
  sw   rs2, imm(rs1)
  sb   rs2, imm(rs1)
  jalr rd, imm(rs1)

Pseudo / convenience:
  li   rd, imm32   -> lui+addi (or just addi if it fits 12-bit signed)
  halt              -> jalr zero, 0(zero) -- ONLY when label "halt:" undefined
  .word HEX         -> embed a raw word at current address

Labels supported in branch/jalr targets only via numeric resolution after
two passes; jalr operand is `imm(reg)`, so use `<label>-<base>` if needed.
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Dict, List, Tuple


ABI_TO_X = {
    "zero": 0, "ra": 1, "sp": 2, "gp": 3, "tp": 4,
    "t0": 5, "t1": 6, "t2": 7,
    "s0": 8, "fp": 8, "s1": 9,
    "a0": 10, "a1": 11, "a2": 12, "a3": 13, "a4": 14, "a5": 15,
}


def parse_reg(s: str) -> int:
    s = s.strip().lower()
    if s in ABI_TO_X:
        return ABI_TO_X[s]
    if s.startswith("x"):
        n = int(s[1:])
        if 0 <= n <= 15:
            return n
    raise ValueError(f"bad register: {s!r}")


def parse_imm(s: str) -> int:
    s = s.strip()
    return int(s, 0)


def fits_signed(value: int, bits: int) -> bool:
    lo = -(1 << (bits - 1))
    hi = (1 << (bits - 1)) - 1
    return lo <= value <= hi


def enc_r(rd: int, rs1: int, rs2: int, funct3: int, funct7: int, opcode: int) -> int:
    return ((funct7 & 0x7F) << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) \
        | ((funct3 & 0x7) << 12) | ((rd & 0x1F) << 7) | (opcode & 0x7F)


def enc_i(rd: int, rs1: int, imm: int, funct3: int, opcode: int) -> int:
    imm12 = imm & 0xFFF
    return (imm12 << 20) | ((rs1 & 0x1F) << 15) | ((funct3 & 0x7) << 12) \
        | ((rd & 0x1F) << 7) | (opcode & 0x7F)


def enc_s(rs1: int, rs2: int, imm: int, funct3: int, opcode: int) -> int:
    imm12 = imm & 0xFFF
    imm_hi = (imm12 >> 5) & 0x7F
    imm_lo = imm12 & 0x1F
    return (imm_hi << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) \
        | ((funct3 & 0x7) << 12) | (imm_lo << 7) | (opcode & 0x7F)


def enc_u(rd: int, imm20: int, opcode: int) -> int:
    # `imm20` is the upper 20 bits as stored in the instruction (already shifted).
    return (imm20 & 0xFFFFF000) | ((rd & 0x1F) << 7) | (opcode & 0x7F)


MEM_OFFSET_RE = re.compile(r"^\s*(.+?)\s*\(\s*([a-zA-Z0-9]+)\s*\)\s*$")


def parse_mem_operand(s: str, labels=None, here: int = 0) -> Tuple[int, int]:
    m = MEM_OFFSET_RE.match(s)
    if not m:
        raise ValueError(f"bad memory operand: {s!r}; expected imm(reg)")
    imm_str = m.group(1).strip()
    if labels is not None:
        imm = resolve_imm(imm_str, labels, here)
    else:
        imm = parse_imm(imm_str)
    return imm, parse_reg(m.group(2))


def split_operands(args: str) -> List[str]:
    # Split top-level commas (no nested parens here).
    out: List[str] = []
    depth = 0
    cur: List[str] = []
    for ch in args:
        if ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur).strip())
    return out


def assemble_line(addr: int, mnem: str, ops: List[str], labels: Dict[str, int]) -> List[int]:
    """Returns a list of 32-bit instruction words (most are 1; li is 1 or 2)."""
    if mnem == ".word":
        return [int(ops[0], 0) & 0xFFFFFFFF]
    if mnem == "add":
        rd = parse_reg(ops[0]); rs1 = parse_reg(ops[1]); rs2 = parse_reg(ops[2])
        return [enc_r(rd, rs1, rs2, funct3=0, funct7=0, opcode=0x33)]
    if mnem == "addi":
        rd = parse_reg(ops[0]); rs1 = parse_reg(ops[1])
        imm = resolve_imm(ops[2], labels, addr)
        if not fits_signed(imm, 12):
            raise ValueError(f"addi imm {imm} out of 12-bit signed range")
        return [enc_i(rd, rs1, imm, funct3=0, opcode=0x13)]
    if mnem == "lui":
        rd = parse_reg(ops[0])
        imm20 = resolve_imm(ops[1], labels, addr) & 0xFFFFF
        return [enc_u(rd, imm20 << 12, opcode=0x37)]
    if mnem == "lw":
        rd = parse_reg(ops[0]); imm, rs1 = parse_mem_operand(ops[1], labels, addr)
        return [enc_i(rd, rs1, imm, funct3=0x2, opcode=0x03)]
    if mnem == "lbu":
        rd = parse_reg(ops[0]); imm, rs1 = parse_mem_operand(ops[1], labels, addr)
        return [enc_i(rd, rs1, imm, funct3=0x4, opcode=0x03)]
    if mnem == "sw":
        rs2 = parse_reg(ops[0]); imm, rs1 = parse_mem_operand(ops[1], labels, addr)
        return [enc_s(rs1, rs2, imm, funct3=0x2, opcode=0x23)]
    if mnem == "sb":
        rs2 = parse_reg(ops[0]); imm, rs1 = parse_mem_operand(ops[1], labels, addr)
        return [enc_s(rs1, rs2, imm, funct3=0x0, opcode=0x23)]
    if mnem == "jalr":
        rd = parse_reg(ops[0]); imm, rs1 = parse_mem_operand(ops[1], labels, addr)
        return [enc_i(rd, rs1, imm, funct3=0x0, opcode=0x67)]
    if mnem == "li":
        rd = parse_reg(ops[0])
        imm = resolve_imm(ops[1], labels, addr)
        if fits_signed(imm, 12):
            return [enc_i(rd, 0, imm, funct3=0, opcode=0x13)]
        # Two-instruction sequence: lui rd, hi20; addi rd, rd, lo12_signed.
        lo12 = imm & 0xFFF
        if lo12 & 0x800:  # sign-extending lo12 would yield negative — compensate.
            hi20 = ((imm + 0x1000) >> 12) & 0xFFFFF
        else:
            hi20 = (imm >> 12) & 0xFFFFF
        lo12_signed = lo12 - 0x1000 if (lo12 & 0x800) else lo12
        return [
            enc_u(rd, hi20 << 12, opcode=0x37),
            enc_i(rd, rd, lo12_signed, funct3=0, opcode=0x13),
        ]
    if mnem == "halt":
        # Convenient self-halt: jalr zero, 0(zero) only halts when PC == 0.
        # Most callers want "halt here" -> jalr zero, addr(zero).
        return [enc_i(0, 0, addr & 0xFFF, funct3=0, opcode=0x67)]
    raise ValueError(f"unknown mnemonic: {mnem!r}")


def resolve_imm(token: str, labels: Dict[str, int], here: int) -> int:
    token = token.strip()
    # Allow `label`, `label-here`, or numeric.
    if token in labels:
        return labels[token]
    if "-" in token and not token.startswith("-"):
        a, b = token.split("-", 1)
        a = a.strip(); b = b.strip()
        av = labels[a] if a in labels else int(a, 0)
        bv = labels[b] if b in labels else int(b, 0)
        return av - bv
    return int(token, 0)


def assemble(source: str) -> List[int]:
    # Pass 1: collect labels.
    pc = 0
    pending: List[Tuple[int, str, List[str], int]] = []  # (addr, mnem, ops, line_no)
    labels: Dict[str, int] = {}
    for line_no, raw in enumerate(source.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        # Label?  "label:"
        m = re.match(r"^([A-Za-z_]\w*)\s*:\s*(.*)$", line)
        if m:
            labels[m.group(1)] = pc
            line = m.group(2).strip()
            if not line:
                continue
        parts = line.split(None, 1)
        mnem = parts[0].lower()
        ops = split_operands(parts[1]) if len(parts) > 1 else []
        # Estimate size for `li` (1 or 2 words).
        if mnem == "li":
            # Pessimistic: 2 words, refine in pass 2.
            try:
                v = int(ops[1], 0)
                size = 1 if fits_signed(v, 12) else 2
            except (ValueError, IndexError):
                size = 2
        else:
            size = 1
        pending.append((pc, mnem, ops, line_no))
        pc += size * 4

    # Pass 2: emit.
    words: List[int] = []
    for addr, mnem, ops, line_no in pending:
        try:
            insts = assemble_line(addr, mnem, ops, labels)
        except Exception as e:
            raise SystemExit(f"line {line_no}: {mnem} {ops}: {e}") from e
        words.extend(insts)
    return words


def write_logisim_hex(words: List[int], path: str, header: str = "v3.0 hex words plain") -> None:
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(header + "\n")
        for w in words:
            fp.write(f"{w:08x}\n")


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(description="miniRV assembler")
    p.add_argument("src", help="Assembly source file")
    p.add_argument("-o", "--output", required=True, help="Output hex file")
    p.add_argument("--listing", help="Write disassembly listing to this file")
    args = p.parse_args(argv)

    with open(args.src, "r", encoding="utf-8") as fp:
        source = fp.read()

    words = assemble(source)
    write_logisim_hex(words, args.output)

    if args.listing:
        with open(args.listing, "w", encoding="utf-8") as fp:
            fp.write(f"# disassembly of {args.src}\n")
            for i, w in enumerate(words):
                fp.write(f"{i*4:08x}: {w:08x}\n")

    print(f"assembled {len(words)} words -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
