# miniRV test programs (F6)

These programs exercise the 8 instructions of the miniRV ISA
(`add`, `addi`, `lui`, `lw`, `lbu`, `sw`, `sb`, `jalr`).

Each pair `<name>.s` (assembly source) and `<name>.hex` (Logisim
`v3.0 hex words plain` image) is checked together by `test_runner/F6.sh`:

1. The .hex is loaded into the reference simulator `tools/minirv_sim.py`,
   which steps the miniRV semantics deterministically.
2. The simulator is asked to assert end-state properties (a0 value, halt PC,
   memory locations) so that the *direction* of any deviation is named.
3. `F6.sh` separately re-assembles each .s with `tools/minirv_asm.py` and
   bit-compares to the committed .hex.  A bare edit to the .hex would be
   caught by this round trip.

The same .hex images are intended to be `Load Image`d into the ROM/RAM of
the Logisim circuit `ysyx-workbench/logisim/miniRV.circ`.  Running the
circuit and stopping at its halt loop should reproduce the simulator's
end-state.

## Test programs

| Program        | Purpose                                                                         | Expected end-state                                |
| -------------- | ------------------------------------------------------------------------------- | ------------------------------------------------- |
| `doc_example`  | The exact 5-instruction example from the F6 manual (RTFM section).              | `a0 = 30`, halts at PC `0xc`.                     |
| `addi_sign`    | Sign-extension boundary cases: `-1`, `-2048`, `+2047` immediates.               | `a0 = 0` (all sign-ext arithmetic cancels).       |
| `mem`          | The byte-load / byte-store hint from the F6 doc: 0x12345678 -> 0x90abcdef.       | `a0 = 0`, mem `[0x100] = 0x90abcdef`.             |
| `lui_add`      | `lui`/`add`/`lbu`: build 0x24680cf0, store with sw, read back each byte.         | `a0 = 0`, mem `[0x200] = 0x24680cf0`.             |

## Why this is the validation, and where the implementation lives

The Logisim circuit `ysyx-workbench/logisim/miniRV.circ` is the actual F6
deliverable.  It is the OSCPU ysyx workbench (a separate upstream repo
checked out under `ysyx-workbench/`) and is gitignored from the autoysyx
orchestrator repo on purpose — we do not push private Logisim files
back upstream.

That separation means the diff this task produces is the **validation
infrastructure** (this directory plus `test_runner/F6.sh`), not the
circuit.  The circuit's existence and structural integrity is verified
live by `test_runner/F6.sh` section (A), which parses the .circ XML and
asserts component types, count, opcode constants, and 15 GPR labels.

## Round-trip an individual program

```bash
# Re-assemble (must produce the committed .hex byte-for-byte)
python3 tools/minirv_asm.py tools/minirv_progs/mem.s -o /tmp/mem.hex
diff /tmp/mem.hex tools/minirv_progs/mem.hex   # silent on success

# Simulate (must exit 0)
python3 tools/minirv_sim.py tools/minirv_progs/mem.hex \
    --expect-a0 0 --expect-halt --expect-mem 0x100=0x90abcdef
```
