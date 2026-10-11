#!/usr/bin/env python3
"""Extract the static tables / constants used by LTTS7Codec210.dll (Jorge build).

Writes tools/codec210_tables.json.  All addresses are VA (image base 0x10000000);
both VA and file offset are recorded so the values can be re-read without Ghidra.

Usage:  python3 tools/codec210_extract.py [path/to/LTTS7Codec210.dll] [out.json]
"""

import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_ROOT = _os.path.dirname(_HERE)
def _p(env, *parts):
    """Path helper: $env wins, else <repo>/<parts...> (put your unpacked voice package under voice/)."""
    v = _os.environ.get(env)
    return v if v else _os.path.join(_ROOT, *parts)
VOICE = _os.environ.get("LTTS7_VOICE", _os.path.join(_ROOT, "voice"))
DLL = _p("LTTS7_DLL", "voice", "bin", "LTTS7Codec210.dll")
BIN = _p("LTTS7_BIN", "voice", "data", "voices", "Jorge",
         "Jorge.32000.LTTS7Codec210.44000.10.bin")

import json
import os
import re
import struct
import sys

import pefile

BASE = 0x10000000
DEFAULT_DLL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "jorge/pf/Loquendo/LTTS7/bin/LTTS7Codec210.dll",
)
DECOMP_CANDIDATES = ["/tmp/c210/decomp_codec210_jorge.txt", "jorge_re/decomp_codec210_jorge.txt"]


class Dll:
    def __init__(self, path):
        self.path = path
        self.pe = pefile.PE(path, fast_load=True)
        self.data = open(path, "rb").read()
        self.secs = [
            (s.Name.rstrip(b"\0").decode(), s.VirtualAddress, s.PointerToRawData,
             s.Misc_VirtualSize, s.SizeOfRawData)
            for s in self.pe.sections
        ]

    def off(self, va):
        rva = va - BASE
        for nm, sv, pr, vsz, rsz in self.secs:
            if sv <= rva < sv + max(vsz, rsz):
                return pr + (rva - sv)
        return None

    def raw(self, va, n):
        o = self.off(va)
        if o is None:
            return None
        return self.data[o:o + n]

    def u32(self, va):
        return struct.unpack("<I", self.raw(va, 4))[0]

    def f32(self, va):
        return struct.unpack("<f", self.raw(va, 4))[0]

    def f64(self, va):
        return struct.unpack("<d", self.raw(va, 8))[0]

    def cstr(self, va):
        o = self.off(va)
        if o is None:
            return None
        e = self.data.find(b"\0", o)
        return self.data[o:e].decode("latin1", "replace")


def classify(dll, va):
    """Heuristic: decide whether a 4/8-byte global is a double/float/int."""
    raw = dll.raw(va, 8) or b""
    if len(raw) < 8:
        return {}
    d = struct.unpack("<d", raw)[0]
    fi = struct.unpack("<f", raw[:4])[0]
    ii = struct.unpack("<I", raw[:4])[0]
    out = {"u32": ii, "i32": ii - (1 << 32) if ii >= 0x80000000 else ii,
           "f32": fi, "f64": d}
    return out


def main():
    dll_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DLL
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "codec210_tables.json")
    d = Dll(dll_path)
    import hashlib
    md5 = hashlib.md5(open(dll_path, "rb").read()).hexdigest()

    res = {
        "meta": {
            "dll": dll_path,
            "md5": md5,
            "image_base": BASE,
            "sections": [{"name": n, "va": hex(BASE + sv), "file_off": hex(pr),
                          "vsize": hex(vsz), "rawsize": hex(rsz)}
                         for n, sv, pr, vsz, rsz in d.secs],
            "note": "All addresses are VA. file_off = VA - image_base + section file offset.",
        }
    }

    # ---- dispatch table (exported plugin ABI) ----
    disp = []
    for i in range(8):
        nptr = d.u32(0x1002E028 + i * 8)
        fptr = d.u32(0x1002E02C + i * 8)
        disp.append({"index": i, "name": d.cstr(nptr), "name_va": hex(nptr),
                     "func_va": hex(fptr)})
    res["plugin_dispatch_table"] = {"table_va": "0x1002e028", "stride": 8, "entries": disp}

    # ---- util symbols bound by LoadUtilSymbols ----
    us = []
    for i in range(5):
        nptr = d.u32(0x1002E000 + i * 8)
        sptr = d.u32(0x1002E004 + i * 8)
        us.append({"name": d.cstr(nptr), "slot_va": hex(sptr)})
    res["util_symbols"] = {"table_va": "0x1002e000", "entries": us}

    # ---- per-sample-rate class descriptors & their sub-structs ----
    def ptrs(va, n):
        out = []
        for i in range(n):
            v = d.u32(va + 4 * i)
            out.append({"off": hex(4 * i), "va": hex(v)})
        return out

    res["vtables"] = {}
    for rate, vt in ((8000, 0x1002393C), (16000, 0x10023AB4), (32000, 0x10023B2C)):
        res["vtables"][str(rate)] = {
            "descriptor_va": hex(vt),
            "entries": ptrs(vt, 24),
            "rate_index": d.u32(vt + 0x0C),
            "field_0x10": d.u32(vt + 0x10),
        }
    # structs pointed to by +0x00 and +0x08 of each descriptor
    named = {}
    for va, label in ((0x10023CA8, "class_sub_32k"), (0x10023BF8, "class_sub_16k"),
                      (0x10023A70, "band_desc_32k"), (0x10023A90, "band_desc_16k"),
                      (0x10023CD0, "mode_array_32k"), (0x10023C38, "mode_array_16k")):
        raw = d.raw(va, 4 * 20)
        if raw is None:
            continue
        named[label] = {
            "va": hex(va),
            "dwords": [hex(struct.unpack_from("<I", raw, 4 * i)[0]) for i in range(20)],
            "ints": [struct.unpack_from("<I", raw, 4 * i)[0] for i in range(20)],
            "floats": [struct.unpack_from("<f", raw, 4 * i)[0] for i in range(20)],
        }
    res["class_substructures"] = named

    # ---- scalar globals referenced by the decompiled code ----
    # ---- int8 DSP codebooks / filter coefficients (identified in the pipeline analysis) ----
    def i8table(va, n):
        raw = d.raw(va, n)
        if raw is None:
            return None
        return {
            "va": hex(va), "file_off": hex(d.off(va)), "bytes": n,
            "int8": list(struct.unpack("<%db" % n, raw)),
            "u8_hex": raw.hex(),
        }

    def f32table(va, n):
        raw = d.raw(va, 4 * n)
        if raw is None:
            return None
        return {
            "va": hex(va), "file_off": hex(d.off(va)), "count": n,
            "f32": list(struct.unpack("<%df" % n, raw)),
            "hex": raw.hex(),
        }

    res["codebooks"] = {
        "lsf_vq": {
            "stage1_10d_x1_256": i8table(0x10022E60, 640),
            "stage2_lo_5d_x1_512": i8table(0x100230E0, 320),
            "stage3_lo_5d_x1_1024": i8table(0x10023220, 320),
            "stage2_hi_5d_x1_512": i8table(0x10023360, 320),
            "stage3_hi_5d_x1_1024": i8table(0x100234A0, 320),
            "lsf2_stage1_8d_x1_256": i8table(0x10022870, 512),
            "lsf2_stage2_8d_x1_512": i8table(0x10022A70, 512),
        },
        "innovation": {
            "cb_16x10": i8table(0x10021278, 160),
            "cb_32x10": i8table(0x10021318, 320),
            "cb_32x20": i8table(0x10021458, 640),
            "cb_256x5": i8table(0x10021BD8, 320),
            "cb_256x5b": i8table(0x100216D8, 1280),
            "cb_256x8": i8table(0x10021D18, 2048),
            "cb_128x8_16k": i8table(0x10022470, 1024),
        },
        "pitch_gain_3tap_x1_64": {
            # descriptors declare 7 index bits => 128 entries x 3 gains
            "tbl_a": i8table(0x100222D0, 3 * 128),
            "tbl_b": i8table(0x10022150, 3 * 128),
            "tbl_extra1": i8table(0x10022330, 3 * 128),
        },
    }
    res["band_filters_qmf"] = {
        "bandA_64tap": f32table(0x100240A8, 64),
        "bandB_64tap": f32table(0x100241A8, 64),
    }

    # ---- group descriptors (pointers into the tables above) ----
    def desc(va, n=8):
        raw = d.raw(va, 4 * n)
        return {"va": hex(va),
                "dwords": [struct.unpack_from("<I", raw, 4 * i)[0] for i in range(n)]}

    res["fixed_codebook_descriptors"] = {
        hex(v): desc(v) for v in
        (0x10023708, 0x1002376C, 0x100237D0, 0x10023834, 0x1002388C, 0x100238E4)
    }
    res["pitch_descriptors"] = {
        hex(v): desc(v) for v in (0x100236FC, 0x1002371C, 0x100237C4, 0x100237E4)
    }
    res["mode_table_32k"] = {
        "table_va": "0x100239f0",
        "mode_objects": [hex(d.u32(0x100239F0 + 4 * i)) for i in range(8)],
    }
    res["mode_objects"] = {
        m: {hex(4 * i): hex(d.u32(m + 4 * i)) for i in range(16)}
        for m in (d.u32(0x100239F0 + 4 * i) for i in range(8))
    }

    # ---- annotations for the scalars whose *type* matters ----
    res["annotations"] = {
        "note": "0x10022exx and 0x1002127x are IEEE doubles; 0x10023exx/0x10024xxx are floats. "
                "referenced_globals lists all interpretations; the correct one is named here.",
        "doubles": {
            "0x10021260": 0.03125, "0x10021270": 0.5, "0x10022e08": 0.003,
            "0x10022e10": 10.0, "0x10022e18": 3.141592653589793, "0x10022e40": 1.5707963268,
            "0x10022e48": 0.2, "0x10022e50": 0.9, "0x10022e58": 2.0,
            "0x10023658": 32767.0, "0x1002364c": -32768.0, "0x10023e88": 2.0,
        },
        "floats": {
            "0x10023ec0": 0.002, "0x10023ec4": 0.05, "0x10023ed8": 0.7,
            "0x10023628": 0.95, "0x10024070": 0.1, "0x100235e0": -16.0,
            "0x10023648": 0.2,
        },
    }

    gl = {}
    src = None
    for c in DECOMP_CANDIDATES:
        if os.path.exists(c):
            src = c
            break
    if src:
        txt = open(src, encoding="latin1").read()
        for m in sorted(set(re.findall(r"_?(DAT_[0-9a-fA-F]{8})", txt))):
            va = int(m[4:], 16)
            if not (BASE <= va < BASE + 0x40000):
                continue
            info = classify(d, va)
            if info:
                info["va"] = hex(va)
                info["file_off"] = hex(d.off(va)) if d.off(va) is not None else None
                gl[m] = info
    res["referenced_globals"] = gl
    res["referenced_globals_source"] = src

    with open(out_path, "w") as f:
        json.dump(res, f, indent=1, sort_keys=False)
    print("wrote", out_path, len(gl), "globals,", len(disp), "dispatch entries")


if __name__ == "__main__":
    main()
