import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_ROOT = _os.path.dirname(_HERE)                      # repo root (tools/ or probes/ are one level down)
def _p(env, *parts):
    """Path helper: $env wins, else <repo>/<parts...> (put your unpacked voice package under voice/)."""
    v = _os.environ.get(env)
    return v if v else _os.path.join(_ROOT, *parts)

VOICE = _os.environ.get("LTTS7_VOICE", _os.path.join(_ROOT, "voice"))
DLL = _p("LTTS7_DLL", "voice", "bin", "LTTS7Codec210.dll")
BIN = _p("LTTS7_BIN", "voice", "data", "voices", "Jorge",
         "Jorge.32000.LTTS7Codec210.44000.10.bin")


#!/usr/bin/env python3
"""Reference PCM oracle for LTTS7Codec210.dll (Jorge build) via x86 emulation.

Runs the *real* DLL decoder in-process with Unicorn so the pure-Python port in
`codec210.py` can be validated against ground truth.  This is a verification
tool, not part of the re-implementation (the project goal is a binary-free
synthesizer).

Requires:  pip install unicorn pefile

Usage:
    python3 codec210_oracle.py [first_frame] [count] [key] [out.raw]

Writes `count` frames of 640 int16 (little-endian) starting at `first_frame`;
with no outfile it prints per-frame RMS instead.

Emulation notes (all needed to make the MSVC-2008 binary run):
  * the DLL imports only KERNEL32; the five Loquendo util entry points are
    bound at load time by `LoadUtilSymbols` — we fill the five slots at
    0x1002f624..0x1002f634 with Python implementations;
  * `__SEH_prolog4` reads fs:[0]; Unicorn 2.x ignores FS_BASE writes, so we map
    page 0 and leave the segment base at 0;
  * Unicorn starts with FPCW = 0 (all x87 exceptions unmasked) which makes the
    MSVC math helpers raise; we set FPCW = 0x037F before every call;
  * the internal CRT allocator entry points (0x100071e0, 0x10011111,
    0x10011151, 0x100071f0, 0x1001136c, 0x10007200) are replaced by a Python
    allocator because their SEH prologues do not emulate correctly;
  * the decode driver FUN_10004290 is a register-based function
    (ESI = context, EDI = 110-byte block) and writes 640 int16 to ctx+0x11D4.
"""
import os
import struct
import sys

import pefile
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_PROT_ALL
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,

                               UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI,
                               UC_X86_REG_ESP, UC_X86_REG_EIP,
                               UC_X86_REG_FPCW, UC_X86_REG_FPSW)

DLL = _p("LTTS7_DLL", "voice", "bin", "LTTS7Codec210.dll")
BIN = _p("LTTS7_BIN", "voice", "data", "voices", "Jorge",
         "Jorge.32000.LTTS7Codec210.44000.10.bin")

BASE = 0x10000000
IMAGE_LO, IMAGE_HI = 0x10000000, 0x10040000
STACK = 0x20000000
STACK_SIZE = 0x200000
HEAP = 0x30000000
STUB = 0x71000000
BLOCK_OFFSET = 150          # first frame in the Jorge DB
BLOCK_SIZE = 110


class Oracle:
    def __init__(self, dll=DLL):
        self.pe = pefile.PE(dll)
        self.data = open(dll, "rb").read()
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc.mem_map(IMAGE_LO, IMAGE_HI - IMAGE_LO, UC_PROT_ALL)
        for s in self.pe.sections:
            raw = self.data[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData]
            if raw:
                self.uc.mem_write(BASE + s.VirtualAddress, raw)
        self.uc.mem_map(STACK, STACK_SIZE, UC_PROT_ALL)
        self.uc.mem_map(HEAP, 0x800000, UC_PROT_ALL)
        self.uc.mem_map(STUB, 0x1000, UC_PROT_ALL)
        self.uc.mem_map(0, 0x1000, UC_PROT_ALL)          # fs:[0] lives at 0
        self.uc.mem_write(0, b"\xff\xff\xff\xff")
        self.heap_ptr, self.blocks = HEAP, {}
        self._stubs, self._stub_funcs = {}, {}
        self._install_iat()
        self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=STUB, end=STUB + 0x1000)
        self._patched = {}
        for va, name in ((0x100071E0, "_calloc"), (0x10011111, "_calloc"),
                         (0x10011151, "_realloc"), (0x100071F0, "_realloc"),
                         (0x1001136C, "_free"), (0x10007200, "_free")):
            self.uc.mem_write(va, b"\xC3")
            self._patched[va] = name
        self.uc.hook_add(UC_HOOK_CODE, self._hook_patched,
                         begin=min(self._patched), end=max(self._patched))

    # ---- memory helpers ---------------------------------------------------
    def w32(self, a, v):
        self.uc.mem_write(a, struct.pack("<I", v & 0xFFFFFFFF))

    def r32(self, a):
        return struct.unpack("<I", self.uc.mem_read(a, 4))[0]

    def r16(self, a):
        return struct.unpack("<H", self.uc.mem_read(a, 2))[0]

    def w16(self, a, v):
        self.uc.mem_write(a, struct.pack("<H", v & 0xFFFF))

    def w8(self, a, v):
        self.uc.mem_write(a, bytes([v & 0xFF]))

    def malloc(self, size):
        size = (size + 15) & ~15
        p = self.heap_ptr
        self.heap_ptr += size
        self.blocks[p] = size
        return p

    def cstr(self, a):
        out = b""
        while True:
            c = bytes(self.uc.mem_read(a, 1))
            if c == b"\x00":
                return out.decode("latin1", "replace")
            out += c
            a += 1

    # ---- import / stub plumbing ------------------------------------------
    def _stubname(self, name):
        if name not in self._stubs:
            i = len(self._stubs)
            addr = STUB + i * 4
            self.uc.mem_write(addr, b"\xC3")
            self._stubs[name] = addr
            self._stub_funcs[i] = name
        return self._stubs[name]

    def _install_iat(self):
        for imp in self.pe.DIRECTORY_ENTRY_IMPORT:
            for i in imp.imports:
                nm = i.name.decode() if i.name else "ord_%d" % i.ordinal
                self.w32(i.address, self._stubname(nm))
        for nm, slot in (("ELQBinGetBuffer", 0x1002F624), ("ELQLogWrite", 0x1002F628),
                         ("ELQfree", 0x1002F62C), ("ELQmalloc", 0x1002F630),
                         ("ELQstricmp", 0x1002F634)):
            self.w32(slot, self._stubname(nm))

    def _hook(self, uc, address, size, user):
        name = self._stub_funcs.get((address - STUB) // 4)
        sp = uc.reg_read(UC_X86_REG_ESP)
        a0, a1, a2, a3 = (self.r32(sp + 4), self.r32(sp + 8),
                          self.r32(sp + 12), self.r32(sp + 16))
        if name == "ELQmalloc":
            uc.reg_write(UC_X86_REG_EAX, self.malloc(a0))
        elif name == "ELQBinGetBuffer":
            uc.reg_write(UC_X86_REG_EAX, 0x50000000 + 0x1000)
        elif name == "HeapAlloc":
            uc.reg_write(UC_X86_REG_EAX, self.malloc(a2))
        elif name == "HeapReAlloc":
            p = self.malloc(a3)
            if a2 in self.blocks:
                d = bytes(uc.mem_read(a2, min(self.blocks[a2], a3)))
                uc.mem_write(p, d)
            uc.reg_write(UC_X86_REG_EAX, p)
        elif name == "HeapSize":
            uc.reg_write(UC_X86_REG_EAX, self.blocks.get(a1, 0))
        elif name == "GetProcessHeap" or name == "HeapCreate":
            uc.reg_write(UC_X86_REG_EAX, 0x1234)
        elif name in ("HeapFree",):
            uc.reg_write(UC_X86_REG_EAX, 1)
        elif name in ("VirtualAlloc",):
            uc.reg_write(UC_X86_REG_EAX, self.malloc(a1))
        elif name == "ELQstricmp":
            uc.reg_write(UC_X86_REG_EAX,
                         0 if self.cstr(a0).lower() == self.cstr(a1).lower() else 1)
        else:
            uc.reg_write(UC_X86_REG_EAX, 0)

    def _hook_patched(self, uc, address, size, user):
        name = self._patched.get(address)
        if name is None:
            return
        sp = uc.reg_read(UC_X86_REG_ESP)
        a0, a1 = self.r32(sp + 4), self.r32(sp + 8)
        if name == "_calloc":
            cnt, size = (a0, 1) if address == 0x100071E0 else (a0, a1)
            p = self.malloc(max(1, cnt * size))
            uc.mem_write(p, b"\x00" * (cnt * size))
            uc.reg_write(UC_X86_REG_EAX, p)
        elif name == "_realloc":
            p = self.malloc(max(1, a1))
            if a0 in self.blocks:
                uc.mem_write(p, bytes(uc.mem_read(a0, min(self.blocks[a0], a1))))
            uc.reg_write(UC_X86_REG_EAX, p)
        else:
            uc.reg_write(UC_X86_REG_EAX, 0)

    # ---- calling ----------------------------------------------------------
    def call(self, addr, args, retaddr=0x2FF00000):
        self.uc.reg_write(UC_X86_REG_FPCW, 0x037F)
        self.uc.reg_write(UC_X86_REG_FPSW, 0)
        sp = STACK + STACK_SIZE - 0x1000
        for a in reversed(args):
            sp -= 4
            self.w32(sp, a)
        sp -= 4
        self.w32(sp, retaddr)
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        try:
            self.uc.emu_start(addr, retaddr, timeout=120 * 1000 * 1000)
        except UcError as ex:
            sys.stderr.write("FAULT %s at EIP=%08x\n" % (ex, self.uc.reg_read(UC_X86_REG_EIP)))
            raise
        return self.uc.reg_read(UC_X86_REG_EAX)

    def call_reg(self, addr, regs, retaddr=0x2FF00000):
        self.uc.reg_write(UC_X86_REG_FPCW, 0x037F)
        self.uc.reg_write(UC_X86_REG_FPSW, 0)
        sp = STACK + STACK_SIZE - 0x1000 - 4
        self.w32(sp, retaddr)
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        for r, v in regs.items():
            self.uc.reg_write(r, v)
        try:
            self.uc.emu_start(addr, retaddr, timeout=120 * 1000 * 1000)
        except UcError as ex:
            sys.stderr.write("FAULT %s at EIP=%08x\n" % (ex, self.uc.reg_read(UC_X86_REG_EIP)))
            raise
        return self.uc.reg_read(UC_X86_REG_EAX)

    # ---- high-level -------------------------------------------------------
    def open_decoder(self, sample_rate=32000, key=0x6D):
        pctx = self.malloc(4)
        if self.call(0x100045E0, [pctx, sample_rate, 0]) != 0:
            raise RuntimeError("ELQOpenDecoder failed")
        ctx = self.r32(pctx)
        self.w16(ctx + 0x11D0, BLOCK_SIZE)
        self.w8(ctx + 0x11E4, key)
        self.w8(ctx + 0x11E5, 1)
        self.call_reg(0x10004230, {UC_X86_REG_ESI: ctx})   # build the decoder object
        return ctx

    def decode(self, ctx, block):
        buf = self.malloc(BLOCK_SIZE + 16)
        self.uc.mem_write(buf, block)
        self.call_reg(0x10004290, {UC_X86_REG_ESI: ctx, UC_X86_REG_EDI: buf})
        return struct.unpack("<640h", bytes(self.uc.mem_read(self.r32(ctx + 0x11D4), 1280)))


def main(argv):
    first = int(argv[1]) if len(argv) > 1 else 0
    count = int(argv[2]) if len(argv) > 2 else 20
    key = int(argv[3], 0) if len(argv) > 3 else 0x6D
    out = argv[4] if len(argv) > 4 else None
    d = open(BIN, "rb").read()
    o = Oracle()
    ctx = o.open_decoder(32000, key)
    frames = [o.decode(ctx, d[BLOCK_OFFSET + i * BLOCK_SIZE:
                              BLOCK_OFFSET + (i + 1) * BLOCK_SIZE])
              for i in range(first, first + count)]
    if out:
        with open(out, "wb") as f:
            for s in frames:
                f.write(struct.pack("<640h", *s))
        print("wrote %s (%d samples)" % (out, len(frames) * 640))
    else:
        for i, s in enumerate(frames):
            print("frame %6d rms=%9.1f min=%6d max=%6d"
                  % (first + i, (sum(float(x) * x for x in s) / 640) ** 0.5,
                     min(s), max(s)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
