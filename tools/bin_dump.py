#!/usr/bin/env python3
"""bin_dump.py - standalone dumper for Loquendo TTS 7 `LOQUENDOTTS7` .bin containers.

No dependencies outside the standard library.  See specs/ELQBin.md for the format.

Usage:
    python3 tools/bin_dump.py [FILE] [--offset N] [--length N] [--key N] [--no-frames]

With no FILE argument it dumps the Jorge voice database shipped in this repo.

Layout summary (see specs/ELQBin.md):
    [0]        key byte A                      (raw)
    [1]        key byte B                      (raw)
    [2..14)    "LOQUENDOTTS7"                  (XOR key = A ^ B)
    [14..16)   u16 LE format_version (=1)      (XOR)
    [16..18)   u16 LE header_size              (XOR)
    [18..hs)   TLV list: u16 tag, u16 size, data[size]   (XOR)
    [hs..EOF)  data region - NOT obfuscated (codec payload; for LTTS7Codec210 a
               28-byte BE-u32 sub-header followed by nframes * bpf bytes)
"""

import argparse
import os
import struct
import sys

TAG_NAMES = {
    1: "Name",
    2: "Label",
    3: "Comment",
    4: "Freq",
    5: "Coding",
    6: "BitRate",
    7: "Rank",
    8: "Version",
}

SIGNATURE = b"LOQUENDOTTS7"
PREFIX_LEN = 0x12  # 18-byte fixed prefix

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FILE = os.path.join(
    _REPO,
    "jorge/pf/Loquendo/LTTS7/data/voices/Jorge",
    "Jorge.32000.LTTS7Codec210.44000.10.bin",
)


def hexdump(data, base=0, width=16):
    """Yield 'offset  hex  |ascii|' lines for data starting at file offset base."""
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        hexpart = " ".join("%02x" % b for b in chunk)
        hexpart = "%-*s" % (width * 3 - 1, hexpart)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        yield "%08x  %s  |%s|" % (base + off, hexpart, asc)


def printable(b):
    if b[:1] == b"":
        return "<empty>"
    try:
        s = b.rstrip(b"\x00").decode("ascii")
    except UnicodeDecodeError:
        return None
    return s


def parse_header(buf, key_override=None):
    """Parse the container header.  Returns (info dict) or prints an error and exits."""
    if len(buf) < PREFIX_LEN:
        sys.exit("error: file shorter than the 18-byte prefix (%d bytes)" % len(buf))

    a, b = buf[0], buf[1]
    key = a ^ b if key_override is None else key_override

    body = bytes(x ^ key for x in buf[2:PREFIX_LEN])
    sig = body[:12]
    fmt = struct.unpack_from("<H", body, 12)[0]
    hs = struct.unpack_from("<H", body, 14)[0]

    info = {
        "key_a": a, "key_b": b, "key": key,
        "signature": sig, "format_version": fmt, "header_size": hs,
        "tlvs": [], "problems": [],
    }

    if sig != SIGNATURE:
        info["problems"].append(
            "signature mismatch: decoded %r, expected %r" % (sig, SIGNATURE))
        return info
    if not (PREFIX_LEN <= hs <= len(buf)):
        info["problems"].append(
            "header_size %d out of range (file is %d bytes)" % (hs, len(buf)))
        return info

    dec = bytes(x ^ key for x in buf[:hs])
    off = PREFIX_LEN
    while off + 4 <= hs:
        tag, size = struct.unpack_from("<HH", dec, off)
        val = dec[off + 4:off + 4 + size]
        if len(val) < size:
            info["problems"].append(
                "TLV at 0x%x truncated (size %d, only %d bytes available)"
                % (off, size, len(val)))
            break
        info["tlvs"].append((off, tag, size, val))
        off += 4 + size
    if off != hs:
        info["problems"].append(
            "TLV list ended at 0x%x but header_size is 0x%x" % (off, hs))
    return info


def parse_codec_subheader(buf, hs):
    """Try the 7 x BE u32 sub-header used by LTTS7Codec210 voices."""
    if hs + 28 > len(buf):
        return None
    vals = struct.unpack_from(">7I", buf, hs)
    fields = [
        ("bitrate", vals[0]), ("rank", vals[1]),
        ("samples_per_frame", vals[2]), ("freq", vals[3]),
        ("bytes_per_frame", vals[4]), ("frames", vals[5]),
        ("cookie", vals[6]),
    ]
    bpf = vals[4]
    frames = vals[5]
    if bpf == 0 or hs + 28 + frames * bpf != len(buf):
        return {"fields": fields, "exact": False, "bpf": bpf, "frames": frames}
    return {"fields": fields, "exact": True, "bpf": bpf, "frames": frames,
            "expr": "%d + 28 + %d*%d = %d" % (hs, frames, bpf, hs + 28 + frames * bpf)}


def resolve(path):
    """Return an existing path; if `path` is missing but exactly one `<path>*` exists, use it."""
    if os.path.exists(path):
        return path
    import glob as _glob
    hits = sorted(_glob.glob(path + "*"))
    if len(hits) == 1:
        print("note: %r not found; using the single name-variant %r" % (path, hits[0]))
        return hits[0]
    return path


def dump(path, offset, length, key_override, show_frames):
    path = resolve(path)
    try:
        with open(path, "rb") as fh:
            buf = fh.read()
    except OSError as exc:
        sys.exit("error: cannot read %s: %s" % (path, exc))

    print("=" * 78)
    print("file            : %s" % path)
    print("size            : %d bytes" % len(buf))

    info = parse_header(buf, key_override)
    print("key bytes       : file[0]=0x%02x ^ file[1]=0x%02x -> key=0x%02x"
          % (info["key_a"], info["key_b"], info["key"]))
    print("signature       : %r" % info["signature"])
    print("format_version  : %d" % info["format_version"])
    print("header_size     : %d (0x%x)" % (info["header_size"], info["header_size"]))
    for p in info["problems"]:
        print("PROBLEM         : %s" % p)

    hs = info["header_size"] if info["signature"] == SIGNATURE else None

    if info["tlvs"]:
        print("-" * 78)
        print("TLV list (0x%02x .. 0x%x):" % (PREFIX_LEN, hs))
        for off, tag, size, val in info["tlvs"]:
            name = TAG_NAMES.get(tag, "<unknown tag %d>" % tag)
            s = printable(val)
            shown = repr(s) if s is not None else repr(val)
            print("  @0x%02x  tag %-2d %-8s size %-3d  %s" % (off, tag, name, size, shown))
        label = dict((t, printable(v)) for _, t, _, v in info["tlvs"])
        missing = [TAG_NAMES[t] for t in sorted(TAG_NAMES) if t not in label]
        if missing:
            print("  (absent tags: %s)" % ", ".join(missing))
    else:
        print("-" * 78)
        print("TLV list        : none parsed")

    if hs is None:
        print("-" * 78)
        print("first 64 raw bytes (not a LOQUENDOTTS7 container or bad key):")
        for line in hexdump(buf[:64]):
            print(line)
        return 1

    print("-" * 78)
    print("data region @ %d (0x%x): first 256 bytes (raw, NOT obfuscated):" % (hs, hs))
    for line in hexdump(buf[hs:hs + 256], hs):
        print(line)

    sub = parse_codec_subheader(buf, hs)
    print("-" * 78)
    if sub and sub["exact"]:
        print("codec sub-header @ %d (7 x BE u32):" % hs)
        for name, v in sub["fields"]:
            print("  %-18s = %d (0x%x)" % (name, v, v))
        print("  layout check    : %s == filesize %d  OK" % (sub["expr"], len(buf)))
    elif sub:
        reg = buf[hs:]
        print("codec sub-header: NONE - offset %d does not start a 28-byte BE-u32 sub-header."
              % hs)
        print("  data-region len : %d bytes (filesize %d - header %d)" % (len(reg), len(buf), hs))
        print("  first 7 BE u32  : " + " ".join("%d" % v for _, v in sub["fields"]))
        print("  (different/older payload variant: the container header above is still valid;")
        print("   see specs/ELQBin.md section 4.  If the region is 16-bit LE samples:")
        if len(reg) % 2 == 0 and len(reg) >= 2:
            n = min(len(reg), 1 << 20) & ~1
            smp = struct.unpack_from("<%dh" % (n // 2), reg, 0)
            print("    s16le over first %d bytes: %d values, min %d, max %d, mean %.1f"
                  % (n, n // 2, min(smp), max(smp), sum(smp) / len(smp)))
        print("  )")
    else:
        print("codec sub-header: file too short for the 28-byte sub-header at %d." % hs)
        print("                  data-region length = %d bytes" % (len(buf) - hs))

    if show_frames and sub and sub["exact"]:
        bpf = sub["bpf"]
        frames = sub["frames"]
        print("  frames          : %d records of %d bytes starting at 0x%x"
              % (frames, bpf, hs + 28))
        print("  frame 0         :")
        for line in hexdump(buf[hs + 28:hs + 28 + 32], hs + 28):
            print("    " + line)
        print("  last frame      : offset 0x%x" % (hs + 28 + (frames - 1) * bpf))
        print("  last 32 bytes   :")
        for line in hexdump(buf[-32:], len(buf) - 32):
            print("    " + line)

    print("-" * 78)
    print("bytes at offset 0x%x (%d bytes):" % (offset, length))
    for line in hexdump(buf[offset:offset + length], offset):
        print(line)
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Dump a Loquendo TTS 7 LOQUENDOTTS7 .bin container.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", default=DEFAULT_FILE,
                    help="path to the .bin file (default: the Jorge voice database)")
    ap.add_argument("-o", "--offset", type=lambda s: int(s, 0), default=0,
                    help="file offset for the extra byte dump (default 0)")
    ap.add_argument("-n", "--length", type=lambda s: int(s, 0), default=256,
                    help="number of bytes to dump at --offset (default 256)")
    ap.add_argument("-k", "--key", type=lambda s: int(s, 0), default=None,
                    help="override the XOR key (default: file[0] ^ file[1])")
    ap.add_argument("--no-frames", action="store_true",
                    help="do not print the codec frame geometry")
    args = ap.parse_args()
    return dump(args.file, args.offset, args.length, args.key, not args.no_frames)


if __name__ == "__main__":
    sys.exit(main())
