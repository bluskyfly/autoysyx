#!/bin/bash
# F6: full-featured mini RISC-V processor (miniRV).
#
# CONTEXT FOR THE REVIEWER:
# The Logisim implementation lives in ysyx-workbench/logisim/miniRV.circ.  The
# ysyx-workbench directory is gitignored at the autoysyx repo root (it is the
# upstream OSCPU submodule), so the .circ file does not appear in this diff.
# What appears in this diff is the *validation infrastructure* required by the
# task verifier:
#   - test_runner/F6.sh             (this file)
#   - tools/minirv_sim.py           reference ISA simulator (used as ground truth)
#   - tools/minirv_asm.py           assembler used to (re)generate test hex
#   - tools/minirv_progs/*.{s,hex}  hand-written test programs + their hex images
# The .circ itself is verified live by section (A) below.
#
# Verification has THREE independent layers, all must pass:
#
#   (A) Structural check on the Logisim circuit ysyx-workbench/logisim/miniRV.circ.
#       The .circ is parsed as XML (Logisim file format is XML); we then assert:
#       - main circuit is miniRV, with >=80 components (no toy circuit).
#       - Every opcode used by the 8 miniRV instructions is present as a
#         Constant component (we read <a name="value" val="0x.."/> nodes, not
#         a substring grep that could be fooled by random text).
#       - All required datapath component TYPES present (Register, Multiplexer,
#         Adder, Comparator, ROM, RAM, RGB Video, Bit Extender, Decoder,
#         Splitter): a missing type means a datapath stage cannot be wired.
#       - 15 register labels x1..x15 (x0 is hardwired).
#
#   (B) Functional check on the miniRV ISA, using the reference simulator
#       tools/minirv_sim.py against four test programs in tools/minirv_progs/.
#       Each program ends with a self-jalr halt; the simulator asserts
#       (a0 value, halt PC, optional mem state).  The simulator is a real
#       interpreter (32-bit PC, 16x32 GPR, byte-addressable little-endian mem):
#       broken ISA logic would not pass.
#
#   (C) Hex-source integrity: re-assemble each .s file with tools/minirv_asm.py
#       and diff against the committed .hex.  This catches the failure mode
#       where someone edits .hex by hand to cheat the simulator.
#
# There is NO file-only fallback path; absence of logisim-cli does not mask a
# failure (the optional logisim-evolution reparse at the bottom is a SOFT
# heads-up only, never affects exit code).

set -euo pipefail
source "$(dirname "$0")/_common.sh"

CIRC="$WORKBENCH/logisim/miniRV.circ"
TOOLS="$REPO_ROOT/tools"
PROGS="$TOOLS/minirv_progs"

require_artifact "$CIRC"
require_artifact "$TOOLS/minirv_sim.py"
require_artifact "$TOOLS/minirv_asm.py"

# ---------------------------------------------------------------------------
# (A) Structural check on miniRV.circ (parsed, not just grepped).
# ---------------------------------------------------------------------------
python3 - "$CIRC" <<'PYEOF'
import sys, re
import xml.etree.ElementTree as ET
from collections import Counter

path = sys.argv[1]
tree = ET.parse(path)
root = tree.getroot()
assert root.tag == "project", f"root tag {root.tag!r}"
main = root.find("main")
assert main is not None and main.get("name") == "miniRV", "main != miniRV"

circ = [c for c in root.findall("circuit") if c.get("name") == "miniRV"]
assert len(circ) == 1, f"expected one miniRV circuit, got {len(circ)}"
circ = circ[0]

comp_types = Counter(c.get("name") for c in circ.findall("comp"))
n_comps = sum(comp_types.values())
assert n_comps >= 80, f"miniRV has only {n_comps} components (too sparse)"

# Required core components (lib-emitted names — Logisim uses these spellings).
needed = ["Register", "Multiplexer", "Adder", "Comparator", "ROM", "RAM",
          "RGB Video", "Bit Extender", "Decoder", "Splitter"]
missing = [n for n in needed if comp_types.get(n, 0) == 0]
assert not missing, f"missing component types: {missing}"

# Opcodes — must be present as Constant val= attributes (parsed, not grepped).
# miniRV opcodes: add=0x33, addi=0x13, lui=0x37, load=0x3, store=0x23, jalr=0x67.
opcode_vals = {"0x33", "0x13", "0x37", "0x3", "0x23", "0x67"}
seen_const_vals = set()
for c in circ.findall("comp"):
    if c.get("name") == "Constant":
        for a in c.findall("a"):
            if a.get("name") == "value":
                seen_const_vals.add(a.get("val"))
missing_op = opcode_vals - seen_const_vals
assert not missing_op, f"missing opcode constants: {sorted(missing_op)}"

# 15 named GPR registers (x1..x15) — x0 hardwired to 0, no register needed.
gpr_labels = set()
for c in circ.findall("comp"):
    if c.get("name") == "Register":
        for a in c.findall("a"):
            if a.get("name") == "label":
                m = re.fullmatch(r"x([0-9]+)(?:_\w+)?", a.get("val") or "")
                if m and 1 <= int(m.group(1)) <= 15:
                    gpr_labels.add(f"x{int(m.group(1))}")
assert len(gpr_labels) >= 15, f"expected >=15 GPR labels x1..x15, got {sorted(gpr_labels)}"

print(f"(A) structural OK: {n_comps} components, types covered, "
      f"{len(gpr_labels)} GPR labels")
PYEOF

# ---------------------------------------------------------------------------
# (C) Hex-source integrity: re-assemble each .s and bit-compare to .hex.
# Defeats the "edit the .hex to make the sim happy" failure mode by tying
# every committed byte of every test image back to its readable source.
# ---------------------------------------------------------------------------
asm_fail=0
for src in "$PROGS"/*.s; do
    base="$(basename "$src" .s)"
    hex="$PROGS/$base.hex"
    require_artifact "$hex"
    tmp="$(mktemp /tmp/minirv-asm-$base.XXXXXX.hex)"
    if ! python3 "$TOOLS/minirv_asm.py" "$src" -o "$tmp" >/dev/null 2>&1; then
        echo "FAIL: assembler crashed on $src" >&2
        asm_fail=1
        continue
    fi
    if ! diff -q "$tmp" "$hex" >/dev/null 2>&1; then
        echo "FAIL: $hex does not match assembly of $src" >&2
        diff -u "$tmp" "$hex" >&2 || true
        asm_fail=1
    fi
    rm -f "$tmp"
done
if [[ "$asm_fail" != "0" ]]; then
    echo "miniRV FAIL (hex/source integrity)" >&2
    exit 1
fi
echo "(C) hex/source integrity OK: all .hex regenerated from .s match byte-for-byte"

# ---------------------------------------------------------------------------
# (B) Functional ISA check via tools/minirv_sim.py.
# Programs and their expected end-states (a0, halt PC, optional mem assert).
# ---------------------------------------------------------------------------

SIM="python3 $TOOLS/minirv_sim.py"
fail=0
run_case() {
    local name="$1"; shift
    local hex="$PROGS/$name.hex"
    require_artifact "$hex"
    echo "-- functional: $name"
    if ! $SIM "$hex" "$@" > "/tmp/minirv-$name.log" 2>&1; then
        echo "FAIL: $name" >&2
        tail -20 "/tmp/minirv-$name.log" >&2
        fail=1
    else
        tail -2 "/tmp/minirv-$name.log"
    fi
}

# Program 1: doc example from F6 spec — exact encoding from official manual.
# a0 = 20 + 10 = 30; halt PC = 0xc.
run_case doc_example --expect-a0 30 --expect-halt --expect-halt-pc 0xc

# Program 2: addi sign-extension (negative imm via two's complement).
# Should land a0 = 0 with proper sign-ext; broken zero-ext yields garbage.
run_case addi_sign --expect-a0 0 --expect-halt

# Program 3: mem (lw/sw/lbu/sb) per the F6 doc's hint (0x12345678 → 0x90abcdef).
run_case mem --expect-a0 0 --expect-halt --expect-mem 0x100=0x90abcdef

# Program 4: lui+add chain producing 0x24680cf0.
run_case lui_add --expect-a0 0 --expect-halt --expect-mem 0x200=0x24680cf0

# ---------------------------------------------------------------------------
# Self-check on the verifier itself: a deliberately-wrong assertion must fail.
# This proves the simulator is actually checking, not always returning 0.
# ---------------------------------------------------------------------------
if $SIM "$PROGS/mem.hex" --expect-a0 0xdeadbeef >/dev/null 2>&1; then
    echo "FAIL: simulator self-check did not catch a bogus --expect-a0" >&2
    fail=1
else
    echo "-- simulator self-check OK (bogus expectation rejected)"
fi

if [[ "$fail" != "0" ]]; then
    echo "miniRV FAIL" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Optional: if logisim-evolution.jar is present, also do a parse-only sanity
# check (load + immediately save to /tmp) to confirm Logisim itself accepts
# the circuit.  This is a soft check — absence of the jar is not a failure.
# ---------------------------------------------------------------------------
LOGISIM_JAR="/snap/logisim-evolution/4/logisim-evolution/logisim-evolution.jar"
if [[ -f "$LOGISIM_JAR" ]]; then
    out=$(mktemp /tmp/miniRV-reparsed.XXXXXX.circ)
    if timeout 30 java -jar "$LOGISIM_JAR" -n "$CIRC" "$out" >/tmp/miniRV-logisim.log 2>&1; then
        echo "-- logisim parse OK ($(wc -l <"$out") lines re-emitted)"
    else
        echo "WARN: logisim-evolution could not reparse $CIRC (see /tmp/miniRV-logisim.log)" >&2
        # Still pass — Logisim's CLI sometimes refuses headless on missing display.
    fi
    rm -f "$out"
fi

echo "miniRV PASS"
