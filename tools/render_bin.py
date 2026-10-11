#!/usr/bin/env python3
"""Read a Loquendo TTS 7 vocal database (*.bin) and render it to WAV.

Container spec: specs/ELQBin.md and REPORT.md S13.1 (verified on the Jorge package):
  u8 keyA, u8 keyB                 (plain)
  header (XOR k = keyA ^ keyB): 12-byte "LOQUENDOTTS7", u16 LE fmt=1, u16 LE header_size,
                                 TLV (u16 tag, u16 size, NUL-terminated ASCII) up to header_size
                                 tags 1..8 = Name,Label,Comment,Freq,Coding,BitRate,Rank,Version
  data region: 28-byte BE u32 sub-header [BitRate, Rank, samples_per_frame, Freq,
               bytes_per_frame, nframes, cookie] followed by nframes * bytes_per_frame frames;
               the sub-header is plain but EACH FRAME IS XOR-OBFUSCATED with a single key byte
               = sub-header byte 27 (the last byte of the cookie). Verified on all three Jorge DBs:
               de-obfuscated frame[0] always lands in {0x38..0x3F} (raw tags were 0x50..0x57 /
               0x28..0x2F / 0xA8..0xAF for keys 0x6D / 0x15 / 0x91).

Usage:
    python3 tools/render_bin.py <file.bin> [out.wav] [--frames N] [--offset N]

For codec210 databases the decoder module tools/codec210.py (written by the Codec210
work-package) is imported if present; otherwise the tool stops with a clear message.
"""
import struct
import sys
import wave

CODEC210 = "LTTS7Codec210"


def read_container(path):
    d = open(path, "rb").read()
    k = d[0] ^ d[1]
    h = bytes(b ^ k for b in d[:512])
    if h[2:14] != b"LOQUENDOTTS7":
        raise ValueError("not a LOQUENDOTTS7 container (sig=%r)" % h[2:14])
    fmt, header_size = struct.unpack_from("<HH", h, 14)
    tlv = {}
    off = 0x12
    while off + 4 <= header_size:
        tag, size = struct.unpack_from("<HH", h, off)
        off += 4
        if tag == 0 or off + size > header_size:
            break
        tlv[tag] = h[off:off + size].split(b"\0")[0].decode("latin1")
        off += size
    names = {1: "Name", 2: "Label", 3: "Comment", 4: "Freq", 5: "Coding",
             6: "BitRate", 7: "Rank", 8: "Version"}
    info = {"key": k, "format_version": fmt, "header_size": header_size,
            "fields": {names.get(t, t): v for t, v in tlv.items()},
            "raw": d}
    return info


def data_region(c):
    return c["raw"][c["header_size"]:]


def pcm_from_linear(c):
    """`linear` payload: raw signed 16-bit LE PCM."""
    freq = int(c["fields"]["Freq"])
    body = data_region(c)
    n = len(body) // 2
    return struct.unpack("<%dh" % n, body[:n * 2]), freq


def codec210_params(c):
    body = data_region(c)
    v = struct.unpack_from(">7I", body, 0)
    return {"bitrate": v[0], "rank": v[1], "samples_per_frame": v[2], "freq": v[3],
            "bytes_per_frame": v[4], "nframes": v[5], "cookie": v[6],
            "frame_xor": body[27],          # per-file key = last byte of the cookie (verified)
            "frames_off": c["header_size"] + 28}


def frame_bytes(c, p, i):
    """Raw stored frame i (still XORed with p['frame_xor'])."""
    o = p["frames_off"] + i * p["bytes_per_frame"]
    return c["raw"][o:o + p["bytes_per_frame"]]


def frame_plain(c, p, i):
    """Frame i after de-obfuscation: every byte ^= sub-header byte 27."""
    k = p["frame_xor"]
    return bytes(b ^ k for b in frame_bytes(c, p, i))


def write_wav(path, samples, freq):
    w = wave.open(path, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(freq)
    w.writeframes(struct.pack("<%dh" % len(samples), *samples))
    w.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    c = read_container(path)
    print("container: key=%#04x fmt=%d header_size=%d" % (c["key"], c["format_version"], c["header_size"]))
    for k, v in c["fields"].items():
        print("  %-8s %s" % (k, v))
    coding = c["fields"].get("Coding", "")
    if coding == "linear":
        pcm, freq = pcm_from_linear(c)
        print("linear PCM: %d samples @ %d Hz = %.1f s" % (len(pcm), freq, len(pcm) / freq))
        rms = (sum(float(s) * s for s in pcm[:freq]) / freq) ** 0.5 if pcm else 0
        print("first-second RMS = %.1f" % rms)
        if out:
            write_wav(out, pcm, freq)
            print("wrote", out)
        return 0
    if coding == CODEC210:
        p = codec210_params(c)
        print("codec210 sub-header:", p)
        try:
            import codec210  # from tools/ (Codec210 work-package)
        except ImportError:
            print("codec210 decoder module not present yet (tools/codec210.py); "
                  "frame bytes are available via frame_bytes()")
            return 2
        dec = codec210.Codec210()
        samples = []
        for i in range(p["nframes"]):
            samples.extend(dec.decode_frame(frame_bytes(c, p, i), key=p["frame_xor"]))
        if out:
            write_wav(out, samples, p["freq"])
            print("wrote", out)
        return 0
    print("unknown Coding %r" % coding)
    return 3


if __name__ == "__main__":
    sys.exit(main())
