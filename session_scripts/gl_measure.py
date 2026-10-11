#!/usr/bin/env python3
"""Exact 8k innovation gain law: measure CB1/CB2 increments per sub-frame.

Captures the excitation buffer (EXC = 0x30012364, 160 floats) byte-wise at the
four writer sites, reproduces the port's codebook vector for the same sub-frame
indices and solves gain = <inc, v>/<v, v>.  Also reads the real gain local at the
FUN_10002da0 call sites and X = the exp() term.
"""
import sys, struct, json, collections
sys.path.insert(0, "/home/asdf/Downloads/ltts_re/tools")
import codec210_oracle as O
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ESI

START = int(sys.argv[1]) if len(sys.argv) > 1 else 30
END = int(sys.argv[2]) if len(sys.argv) > 2 else 70
OUT = sys.argv[3] if len(sys.argv) > 3 else "/tmp/gl_meas.json"

EXC = 0x30012364
N = 160
CODES = {0x10009B6F: "clear", 0x10009F3E: "cb1", 0x10009FF1: "cb2"}
# the LTP output is stored by four unrolled FIR stores inside FUN_10006bb0
LTP_SITES = {0x10009C0D, 0x10006F94, 0x10006FB2, 0x10006FD4, 0x10006FF7}

d = open(O.BIN, "rb").read()
o = O.Oracle()
ctx = o.open_decoder(32000, 0x6D)
blocks = [d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE]
          for i in range(END + 1)]
for i in range(START):
    o.decode(ctx, blocks[i])

last = {"a": 0}
recs = []
ALL = []
stage = {}


def h_code(uc, a, s, u):
    last["a"] = a
    if a == 0x10009D56:
        esp = uc.reg_read(UC_X86_REG_ESP)
        cur["gain"] = struct.unpack("<f", bytes(uc.mem_read(esp + 0x1C, 4)))[0]
        cur["X"] = struct.unpack("<f", bytes(uc.mem_read(esp + 0x5C, 4)))[0]
    elif a == 0x10009D94:
        esp = uc.reg_read(UC_X86_REG_ESP)
        cur["cb1_gain"] = struct.unpack("<f", bytes(uc.mem_read(esp + 0x1C, 4)))[0]
    elif a == 0x10009FB6:
        esp = uc.reg_read(UC_X86_REG_ESP)
        g = struct.unpack("<f", bytes(uc.mem_read(esp + 0x30, 4)))[0]
        cur["cb2_gain_pre"] = g
        cur["cb2_gain"] = g * 0.45454545454545453
        recs.append(dict(cur))
        cur.clear()
    elif a == 0x10009D18:
        cur["path"], cur["idx"] = "read3", uc.reg_read(UC_X86_REG_EAX)
    elif a == 0x10009D38:
        cur["path"], cur["idx"] = "read1", uc.reg_read(UC_X86_REG_EAX)
    elif a == 0x10009D48:
        cur["path"], cur["idx"] = "else", -1
    elif a == 0x10009D08:
        cur["desc8"] = uc.reg_read(UC_X86_REG_EAX)


def h_write(uc, acc, addr, size, val, u):
    a = last["a"]
    name = "ltp" if a in LTP_SITES else CODES.get(a)
    if name and EXC <= addr and addr + size <= EXC + 4 * N:
        nbytes = size
        stage.setdefault(name, {})[addr - EXC] = (
            val & ((1 << (8 * nbytes)) - 1)).to_bytes(nbytes, "little")


o.uc.hook_add(UC_HOOK_CODE, h_code)
o.uc.hook_add(UC_HOOK_MEM_WRITE, h_write)

import codec210 as C
dec = C.Codec210()
meta = None
for fr in range(START, END + 1):
    stage = {}
    recs = []
    cur = {}
    o.decode(ctx, blocks[fr])
    f = dec.parse_frame(blocks[fr])
    # reconstruct the 160 floats of each stage
    arr = {}
    for name in ("clear", "ltp", "cb1", "cb2"):
        b = bytearray(4 * N)
        seen = bytearray(4 * N)
        for off, raw in stage.get(name, {}).items():
            b[off:off + len(raw)] = raw
            for k in range(len(raw)):
                seen[off + k] = 1
        arr[name] = list(struct.unpack("<%df" % N, bytes(b)))
        arr[name + "_seen"] = sum(seen) / 4.0
    for sf in range(4):
        g8 = f["energy8"]
        lag_d, idx7, b3, cbi = f["sub8"][sf]
        v1 = dec.codebook(cbi[0:8], 0)
        v2 = dec.codebook(cbi[8:16], 0)
        i0, i1 = 40 * sf, 40 * sf + 40
        inc1 = [arr["cb1"][i] - arr["ltp"][i] for i in range(i0, i1)]
        inc2 = [arr["cb2"][i] - arr["cb1"][i] for i in range(i0, i1)]

        def proj(inc, v):
            num = sum(a * b for a, b in zip(inc, v))
            den = sum(a * a for a in v)
            g = num / den
            r = sum((a - g * b) ** 2 for a, b in zip(inc, v)) ** 0.5
            n = sum(a * a for a in inc) ** 0.5
            return g, (r / n if n else 0.0)

        gm1, res1 = proj(inc1, v1)
        gm2, res2 = proj(inc2, v2)
        r = recs[sf] if sf < len(recs) else {}
        ALL.append(dict(frame=fr, sf=sf, g8=g8, b3=b3, idx7=idx7,
                        cb1_ratio=gm2 / gm1 if gm1 else None,
                        gain_law=r.get("gain"), X=r.get("X"), path=r.get("path"),
                        idx_read=r.get("idx"), cb1_gain=r.get("cb1_gain"),
                        cb2_gain=r.get("cb2_gain"), desc8=r.get("desc8"),
                        gain_meas_cb1=gm1, gain_meas_cb2=gm2,
                        resid_cb1=res1, resid_cb2=res2,
                        rms_inc1=(sum(a * a for a in inc1) / 40) ** 0.5,
                        rms_v1=(sum(a * a for a in v1) / 40) ** 0.5,
                        seen=arr["clear_seen"], seen_ltp=arr["ltp_seen"]))
    if fr == START:
        print("stage coverage (floats seen):",
              {k: arr[k + "_seen"] for k in ("clear", "ltp", "cb1", "cb2")})
        print("sample:", json.dumps(ALL[0], default=str)[:400])

json.dump(ALL, open(OUT, "w"))
print("done", len(ALL))
