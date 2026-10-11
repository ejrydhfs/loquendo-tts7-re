#!/usr/bin/env python3
"""Parser for Loquendo TTS 7 unit-inventory files (*.sde), both generations.

Formats reverse-engineered from LoqTTS7.dll / LTTS7Util.dll (see specs/SDE.md).
Every decode rule below is tied to a decompiled snippet.

Two generations, both consumed by the same engine reader (jorge FUN_10049f10 /
old FUN_1002a890):

  * Jorge generation  -- header `LTTSComponentVersion=7.0.0`
        N=<atoms>,<slots>
        U=<lctx> <p1>..<pK> <rctx>            (K = tokens-2)
        L<n> !<start> <dur> <val>             (base-93 numerals)
        R<n> <dur> <val>
        S=<flag>
  * Legacy ("sde13") generation -- header `VERSION=7`
        N=<atoms>,<slots>,<nD+1>
        U=<t0>..<tK-1>                        (no context tokens)
        D=<order>,<S|D>,<start>,<end>,<val>   (plain decimal, comma separated)

Usage:
    python3 tools/sde_parse.py <file.sde> [--limit N] [--tokens]
"""

import argparse
import collections
import sys

# ---------------------------------------------------------------------------
# Layer 0: bit-7 de-obfuscation
# ---------------------------------------------------------------------------
# Reader:  bVar20 = 0x7f < (byte)line[0];  if (bVar20) copy each char as c-0x80.
# Detected from the first character of the file.  In the shipped Jorge*.sde every
# byte has bit 7 SET except '\n' (0x0a).  Files stored plain (e.g.
# JorgeGildedParalinguistics.sde) take the other branch and are read verbatim.


def load_text(path):
    data = open(path, "rb").read()
    masked = (data[1] & 0x80) != 0 if len(data) > 1 else False
    if masked:
        text = bytes(b & 0x7F for b in data).decode("latin-1")
    else:
        text = data.decode("latin-1")
    return text, masked, data


# ---------------------------------------------------------------------------
# Layer 1: printable base-93 numerals  (LoqTTS7.dll FUN_10024440 / FUN_100436f0)
#
#   i = 0; b = *p;  while (0x21 < b) { p++; i = i*0x5d + (byte)(b - 0x22); b=*p; }
#
# Digit alphabet: bytes 0x22..0x7e ('"' == 0 ... '~' == 92), base 0x5d = 93.
# Terminated by space (0x20), '!' (0x21) or NUL.  '-' (0x2d) is a DIGIT (11).
# ---------------------------------------------------------------------------
BASE = 0x5D
OFF = 0x22


def base93(s):
    v = 0
    for ch in s:
        b = ord(ch)
        if b <= 0x21:
            break
        v = v * BASE + (b - OFF)
    return v


# ---------------------------------------------------------------------------
# Layer 2: U-line tokenizer  (LoqTTS7.dll FUN_10029230 / FUN_10049c10)
#
#   stop a token at 0x20, 0x2d, NUL, or after 5 chars
#   flag = ((next != '-') - 1U & 0xf7) + 0xf;   // 0x0f = ' ', 0x06 = '-'
#   id   = FUN_100190c0(phoneticTable, tok)
# ---------------------------------------------------------------------------
def u_tokens(body):
    """Return list of (token, sep_flag) for a U= line body (text after 'U=')."""
    out = []
    i, n = 0, len(body)
    while i < n:
        j, k = i, 0
        while j < n and body[j] not in " -\0" and k < 5:
            j += 1
            k += 1
        nxt = body[j] if j < n else "\0"
        out.append((body[i:j], 0x0F if nxt != "-" else 0x06))
        i = j + 1 if j < n else j
    return out


# ---------------------------------------------------------------------------
# Layer 3a: Jorge-generation L<n>/R<n> fields (FUN_100285b0 / FUN_10048e30)
#
#   n [ "!"<start> ] SP <dur> SP <val>       (all base-93 numerals)
# ---------------------------------------------------------------------------
def lr_fields(line):
    body = line[1:]                     # drop the 'L'/'R' tag
    if not body:
        return None
    fields = body.split(" ")
    if len(fields) < 2:
        return None
    n = base93(fields[0])
    explicit = None
    idx = 1
    if fields[idx].startswith("!"):
        explicit = base93(fields[idx][1:])
        idx += 1
    if idx + 1 >= len(fields):
        return None
    return {"n": n, "explicit": explicit,
            "dur": base93(fields[idx]), "val": base93(fields[idx + 1]) & 0xFFFF}


# ---------------------------------------------------------------------------
# Layer 3b: legacy D records (FUN_10028700 / FUN_10048f90)
#
#   D=<order>,<S|D>,<start>,<end>,<pitch>     all `_atol` decimal
#   stored: pair(start, (end-start)<<10 | pitch&0xffff)
#   an empty <start> field means "continue from the running accumulator".
# ---------------------------------------------------------------------------
def d_fields(line, acc):
    body = line[2:]                     # drop "D="
    f = body.split(",")
    if len(f) < 5:
        return None
    try:
        order = int(f[0] or "0")
        part = f[1]
        start = int(f[2]) if f[2] != "" else acc
        end = int(f[3])
        val = int(f[4])
    except ValueError:
        return None
    if part not in ("S", "D") or end < start or val < 0:
        return None
    return {"order": order, "part": part, "start": start, "end": end,
            "dur": end - start, "val": val}


# ---------------------------------------------------------------------------
class Unit:
    __slots__ = ("index", "tokens", "flags", "s_flag", "lr", "d")

    def __init__(self, index):
        self.index = index
        self.tokens = []
        self.flags = []
        self.s_flag = None
        self.lr = []      # jorge generation
        self.d = []       # legacy generation


def parse(path):
    text, masked, data = load_text(path)
    lines = text.split("\n")
    hdr = {"lines": len(lines), "first": lines[0] if lines else "", "variant": None}
    units = []
    p_records = []
    cur = None
    acc = 0
    for ln in lines:
        if not ln:
            continue
        t = ln[0]
        if t == "U":
            cur = Unit(len(units))
            for tok, fl in u_tokens(ln[2:]):
                cur.tokens.append(tok)
                cur.flags.append(fl)
            units.append(cur)
        elif t == "L" or t == "R":
            if cur is None:
                continue
            f = lr_fields(ln)
            if f is None:
                continue
            start = f["explicit"] if f["explicit"] is not None else acc
            acc = start + f["dur"]
            r = dict(f)
            r.update(side=t, start=start, end=acc)
            cur.lr.append(r)
        elif t == "D":
            if cur is None:
                continue
            f = d_fields(ln, acc)
            if f is None:
                continue
            acc = f["end"]
            cur.d.append(f)
        elif t == "S":
            if cur is not None and len(ln) > 2:
                cur.s_flag = ln[2]
        elif t == "P":
            p_records.append(ln[2:].split("|"))
        elif t == "N":
            nums = [x for x in ln[2:].split(",")]
            hdr["N"] = [int(x) if x.isdigit() else None for x in nums]
        elif ln.startswith("LTTSComponentVersion="):
            hdr["version"] = ln.split("=", 1)[1]
            hdr["variant"] = "jorge"
        elif ln.startswith("VERSION="):
            hdr["oldversion"] = ln.split("=", 1)[1]
            hdr["variant"] = "legacy"
    hdr["masked"] = masked
    hdr["bytes"] = len(data)
    if hdr["variant"] is None:
        hdr["variant"] = "legacy" if any(u.d for u in units) else (
            "jorge" if any(u.lr for u in units) else "unknown")
    return hdr, units, p_records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--tokens", action="store_true", help="print full U= token distribution")
    args = ap.parse_args()

    hdr, units, p = parse(args.path)
    N = hdr.get("N") or []

    print("== header ==")
    print("  file            :", args.path)
    print("  variant         :", hdr["variant"])
    print("  bytes           :", hdr["bytes"], "(bit-7 masked)" if hdr["masked"] else "(plain)")
    print("  line 0          :", hdr["first"])
    ver = hdr.get("version") or hdr.get("oldversion")
    if ver:
        print("  version marker  :", ("LTTSComponentVersion=" if hdr.get("version")
                                      else "VERSION=") + ver)
    print("  N=              :", N, "(atoms, slots" + (", ?)" if len(N) > 2 else ")"))
    print("  total lines     :", hdr["lines"])

    tok_total = sum(len(u.tokens) for u in units)
    d_total = sum(len(u.d) for u in units)
    lr_total = sum(len(u.lr) for u in units)
    print("== counts ==")
    print("  U= atoms        :", len(units), "  (N[0] =", (N[0] if N else None), ")")
    print("  U= tokens       :", tok_total, "  (N[1] =", (N[1] if len(N) > 1 else None), ")")
    print("  L/R records     :", lr_total)
    print("  D= records      :", d_total, "  (N[2] =", (N[2] if len(N) > 2 else None), ")")
    print("  S= records      :", sum(1 for u in units if u.s_flag))
    print("  P= records      :", len(p))

    print("== first %d atoms ==" % args.limit)
    for u in units[: args.limit]:
        if hdr["variant"] == "jorge":
            print("  U[%d] phonemes=%s ctx=(%s,%s) S=%s slots=%d"
                  % (u.index, " ".join(u.tokens[1:-1]) or "-",
                     u.tokens[0] if u.tokens else "?", u.tokens[-1] if u.tokens else "?",
                     u.s_flag, len(u.tokens)))
        else:
            print("  U[%d] tokens=%s  slots=%d" % (u.index, " ".join(u.tokens), len(u.tokens)))
        for r in u.lr:
            print("      %s%d n=%d start=%d dur=%d end=%d val=%d%s"
                  % (r["side"], r["n"], r["n"], r["start"], r["dur"], r["end"], r["val"],
                     "  (explicit start)" if r["explicit"] is not None else ""))
        for r in u.d:
            print("      D order=%d part=%s start=%d end=%d dur=%d val=%d"
                  % (r["order"], r["part"], r["start"], r["end"], r["dur"], r["val"]))

    dist = collections.Counter()
    for u in units:
        for tok in u.tokens:
            dist[tok] += 1
    print("== U= field (phoneme token) distribution: %d distinct ==" % len(dist))
    for tok, cnt in dist.most_common(None if args.tokens else args.limit):
        print("   %-6s %d" % (tok, cnt))

    if p:
        print("== first P= records ==")
        for r in p[: args.limit]:
            print("   ", "|".join(r))

    ends = [r["end"] for u in units for r in u.lr] + [r["end"] for u in units for r in u.d]
    if ends:
        print("== timeline ==")
        print("  max end position:", max(ends), "(10 us units)")


if __name__ == "__main__":
    main()
