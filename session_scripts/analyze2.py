#!/usr/bin/env python3
import json, sys, numpy as np
sys.path.insert(0, '/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
T = json.load(open('/home/asdf/Downloads/ltts_re/tools/codec210_tables.json'))
cfA = T['band_filters_qmf']['bandA_64tap']['f32']
cfB = T['band_filters_qmf']['bandB_64tap']['f32']
S = json.load(open('/tmp/snaps2.json'))
LO = S['lo']
def arr(snap, addr, n):
    i = (addr - LO)//4
    return np.array(snap[i:i+n], dtype=np.float64)
def corr(a, b):
    a = np.asarray(a, float) - np.mean(a); b = np.asarray(b, float) - np.mean(b)
    return float(a.dot(b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-300))
def rms(a): return float(np.sqrt((np.asarray(a, float)**2).mean()))

bf = {(r['frame'], r['lvl'], r['filt']): r for r in S['bf']}
comb = {(r['frame'], r['lvl']): r for r in S['comb']}

print("### 1. Reproduce each real band-filter call from its own src + real tail")

# src values: we did not store src buffers in snaps2 (only tail_pre). Use comb snapshots to read buffers.
for f in (37, 38, 39):
    sc1 = comb[(f, 'L1')]['snap']; sc2 = comb[(f, 'L2')]['snap']
    A1src = arr(sc2, 0x30012a30, 160)   # ring1 head (fresh enough)
    syn16 = arr(sc2, 0x30012f30, 160)
    A2src = arr(sc2, 0x30014380, 320)
    syn32 = arr(sc2, 0x30014d80, 320)
    rA1 = bf[(f,'L1','A')]; rB1 = bf[(f,'L1','B')]
    rA2 = bf[(f,'L2','A')]; rB2 = bf[(f,'L2','B')]
    for tag, src, rec, cf, outn in (('L1A', A1src, rA1, cfA, 320), ('L1B', syn16, rB1, cfB, 320),
                                    ('L2A', A2src, rA2, cfA, 640), ('L2B', syn32, rB2, cfB, 640)):
        dst = arr(sc2, rec['dst'], outn)
        oA = np.array(C.band_filter(list(src), cf, outn, 64, list(rec['tail_pre']), [0.0]*(2*outn)), dtype=float)
        print("f%d %s: rms(src)=%9.2f rms(dst)=%9.2f ratio=%.6f  corr(portbf,real)=%+.6f  maxdiff=%.4g"
              % (f, tag, rms(src), rms(dst), rms(dst)/rms(src), corr(oA, dst), np.max(np.abs(oA-dst))))
    print()

print("### 2. Combine check: out1 == 2*(A1-B1)?  out2 == 2*(A2-B2)?")
pcm = S['pcm_rms']
for f in (37, 38, 39):
    sc1 = comb[(f,'L1')]['snap']; sc2 = comb[(f,'L2')]['snap']
    A1 = arr(sc2, 0x30013430, 320); B1 = arr(sc2, 0x30013930, 320)
    A2 = arr(sc2, 0x30015780, 640); B2 = arr(sc2, 0x30016180, 640)
    out1 = arr(sc2, 0x30002220, 320)
    print(" f%d L1: corr(out1_, 2*(A1-B1))=%+.6f  corr(out1_,2*A1)=%+.6f  rms out1_=%9.2f 2*(A1-B1)=%9.2f"
          % (f, corr(out1, 2*(A1-B1)), corr(out1, 2*A1), rms(out1), rms(2*(A1-B1))))
    print(" f%d L2: rms(2*(A2-B2))=%9.2f rms(2*A2)=%9.2f  pcm_rms=%9.2f  A2rms=%9.2f B2rms=%9.2f"
          % (f, rms(2*(A2-B2)), rms(2*A2), pcm[f], rms(A2), rms(B2)))

print("\n### 3. A2src(ring2) vs 2*A1dst / 2*(A1-B1) / out1 same+prev frame")
for f in (37, 38, 39):
    sc2 = comb[(f,'L2')]['snap']
    A2src = arr(sc2, 0x30014380, 320)
    A1 = arr(sc2, 0x30013430, 320); B1 = arr(sc2, 0x30013930, 320)
    print(" f%d: corr(A2src,2*A1)=%+.6f ratio=%.4f | corr(A2src,2*(A1-B1))=%+.6f ratio=%.4f"
          % (f, corr(A2src, 2*A1), rms(A2src)/rms(2*A1), corr(A2src, 2*(A1-B1)), rms(A2src)/rms(2*(A1-B1))))
    for g in (f-1,):
        if (g,'L2') in comb:
            A1p = arr(comb[(g,'L2')]['snap'], 0x30013430, 320)
            print("      vs prev-frame A1: corr=%+.6f ratio=%.4f" % (corr(A2src, A1p), rms(A2src)/rms(A1p)))
