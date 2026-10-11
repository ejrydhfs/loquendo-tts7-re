#!/usr/bin/env python3
import json, numpy as np
S = json.load(open('/tmp/snaps_apath.json'))
LO = S[0]['snap']['lo']

def arr(snap, addr, n):
    i = (addr - LO)//4
    return np.array(snap['data'][i:i+n], dtype=np.float64)

def corr(a, b):
    a = a - a.mean(); b = b - b.mean()
    return float(a.dot(b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-300))

def rms(a):
    return float(np.sqrt((a*a).mean()))

snaps = {}
for s in S:
    snaps[(s['frame'], s['ev'], s.get('lvl'))] = s

print("=== L1 snapshot @ L1 A-call, buffers 8k-synth / A1src(ring1) / synth16")
for f in (36,37,38,39):
    s = snaps[(f,'bfA','L1')]['snap']
    synth8 = arr(s, 0x30011ea0, 160)
    a1src  = arr(s, 0x30012a30, 160)
    syn16  = arr(s, 0x30012f30, 160)
    print(" f%d rms synth8=%9.2f A1src=%9.2f synth16=%9.2f | corr(A1src,synth8)=%+.6f corr(A1src,syn16)=%+.6f corr(synth8,syn16)=%+.6f"
          % (f, rms(synth8), rms(a1src), rms(syn16), corr(a1src,synth8), corr(a1src,syn16), corr(synth8,syn16)))

print("\n=== L2 snapshot @ L2 A-call: A2src(ring2) vs A1dst / B1dst / out1 (same frame and prev)")
for f in (36,37,38,39):
    s = snaps[(f,'bfA','L2')]['snap']
    a2src = arr(s, 0x30014380, 320)
    syn32 = arr(s, 0x30014d80, 320)
    a1dst = arr(s, 0x30013430, 320)
    b1dst = arr(s, 0x30013930, 320)
    out1  = arr(s, 0x30002220, 320)
    line = " f%d rms A2src=%9.2f syn32=%9.2f A1dst=%9.2f B1dst=%9.2f out1=%9.2f | " % (
        f, rms(a2src), rms(syn32), rms(a1dst), rms(b1dst), rms(out1))
    line += "corr(A2src,A1dst)=%+.6f corr(A2src,out1)=%+.6f corr(A2src,B1dst)=%+.6f" % (
        corr(a2src,a1dst), corr(a2src,out1), corr(a2src,b1dst))
    print(line)

print("\n=== A2src vs out1 of the PREVIOUS frame")
for f in (37,38,39):
    a2src = arr(snaps[(f,'bfA','L2')]['snap'], 0x30014380, 320)
    for g in (f-1, f-2):
        if (g,'bfA','L2') in snaps:
            o = arr(snaps[(g,'bfA','L2')]['snap'], 0x30002220, 320)
            print("  A2src(f%d) vs out1(f%d): corr=%+.6f  ratio_rms=%.4f" % (f, g, corr(a2src,o), rms(a2src)/rms(o)))

print("\n=== L1: is A1dst the band-filter output of A1src? compute with port band_filter")
import sys
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
T = json.load(open('/home/asdf/Downloads/ltts_re/tools/codec210_tables.json'))
cfA = T['band_filters_qmf']['bandA_64tap']['f32']
cfB = T['band_filters_qmf']['bandB_64tap']['f32']
print(" cfA len", len(cfA), "cfB len", len(cfB))

for f in (37,38,39):
    s = snaps[(f,'bfA','L1')]
    snap = s['snap']
    a1src = arr(snap, 0x30012a30, 160)
    syn16 = arr(snap, 0x30012f30, 160)
    tailA = np.array([0.0]*64); tailB = np.array([0.0]*64)
    # use real tails captured before call
    tailA = np.array(s['tailvals'], dtype=np.float64)
    oA = np.array(C.band_filter(list(a1src), cfA, 320, 64, [0.0]*64, [0.0]*1088))
    oB = np.array(C.band_filter(list(syn16), cfB, 320, 64, [0.0]*64, [0.0]*1088))
    realA1 = arr(snap, 0x30013430, 320)
    realB1 = arr(snap, 0x30013930, 320)
    realout1 = arr(snap, 0x30002220, 320)
    print(" f%d L1: corr(portbf(A1src),realA1)=%+.6f  rms port=%.2f real=%.2f" % (f, corr(oA,realA1), rms(oA), rms(realA1)))
    print("       corr(portbf(syn16,cfB),realB1)=%+.6f  rms port=%.2f real=%.2f" % (corr(oB,realB1), rms(oB), rms(realB1)))
    print("       realout1 vs 2*(realA1-realB1): corr=%+.6f" % corr(realout1, 2*(realA1-realB1)))
