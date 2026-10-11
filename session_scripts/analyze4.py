#!/usr/bin/env python3
import json, sys, numpy as np
sys.path.insert(0, '/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
T = json.load(open('/home/asdf/Downloads/ltts_re/tools/codec210_tables.json'))
cfA = T['band_filters_qmf']['bandA_64tap']['f32']
cfB = T['band_filters_qmf']['bandB_64tap']['f32']
def bf(src, cf, oc, tail=None):
    return np.array(C.band_filter(list(np.asarray(src, float)), cf, oc, 64,
                                  list(tail) if tail is not None else [0.0]*64, [0.0]*(2*oc)), float)
def rms(a): return float(np.sqrt((np.asarray(a, float)**2).mean()))
def corr(a, b):
    a = np.asarray(a, float) - np.mean(a); b = np.asarray(b, float) - np.mean(b)
    return float(a.dot(b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-300))

A3 = json.load(open('/tmp/snaps_apath.json'))   # measure3: L1 snapshot (bfA L1) has valid 8k synth
S2 = json.load(open('/tmp/snaps2.json')); LO = S2['lo']
def arr2(snap, addr, n):
    return np.array(snap[(addr - LO)//4:(addr - LO)//4 + n], float)
def arr3(snap, addr, n):
    i = (addr - snap['lo'])//4
    return np.array(snap['data'][i:i+n], float)

# 8k synth per frame from measure3 L1 snapshot (valid: written before the L1 bf call)
syn8 = {}
for s in A3:
    if s['ev'] == 'bfA' and s.get('lvl') == 'L1' and 36 <= s['frame'] <= 39:
        syn8[s['frame']] = arr3(s['snap'], 0x30012a30, 160)
comb = {(r['frame'], r['lvl']): r for r in S2['comb']}
bfrec = {(r['frame'], r['lvl'], r['filt']): r for r in S2['bf']}

print("### K (combine scale) check: A2src vs 2*(A16-B16), and B2 dst vs bf(synth32,cfB,tail)")
for f in (37, 38, 39):
    s = comb[(f, 'L2')]['snap']
    A2src = arr2(s, 0x30014380, 320)
    A16 = arr2(s, 0x30013430, 320); B16 = arr2(s, 0x30013930, 320)
    A32 = arr2(s, 0x30015780, 640); B32 = arr2(s, 0x30016180, 640)
    print(" f%d corr(A2src, 2*(A16-B16))=%+.8f  rms ratio=%.6f" %
          (f, corr(A2src, 2*(A16-B16)), rms(A2src)/rms(2*(A16-B16))))

print("\n### STAGE rms / corr: real 8k synth -> (port A-path variants) vs real")
hdr = ("f", "rms syn8", "rms A16real", "rms a16port", "corr", "rms A32real", "rms a32 old", "rms a32 patch",
       "rms pcm real", "rms pcm patch", "corr pcm")
print("%-5s"*len(hdr) % hdr)
for f in (37, 38, 39):
    s = comb[(f, 'L2')]['snap']
    x = syn8[f]
    A16r = arr2(s, 0x30013430, 320); B16r = arr2(s, 0x30013930, 320)
    A2src = arr2(s, 0x30014380, 320)
    A32r = arr2(s, 0x30015780, 640); B32r = arr2(s, 0x30016180, 640)
    pcmr = 2.0*(A32r - B32r)
    a16 = bf(x, cfA, 320, bfrec[(f,'L1','A')]['tail_pre'])
    a32_old = bf(a16, cfA, 640)
    out16 = 2.0*a16
    a32_new = bf(out16, cfA, 640)
    pcm_new = 2.0*a32_new
    # reference: patch fed the real out16 (A2src) -> upper bound for A32 exactness
    a32_ref = bf(A2src, cfA, 640, bfrec[(f,'L2','A')]['tail_pre'])
    print("%-5d %9.2f %9.2f %9.2f %+.6f %9.2f %9.2f %9.2f %9.2f %9.2f %+.6f" % (
        f, rms(x), rms(A16r), rms(a16), corr(a16, A16r), rms(A32r), rms(a32_old), rms(a32_new),
        rms(pcmr), rms(pcm_new), corr(pcm_new, pcmr)))
    print("      corr(a32_ref(real A2src),A32real)=%+.8f  rms ratio=%.6f ; corr(a32_new,A32real)=%+.6f" %
          (corr(a32_ref, A32r), rms(a32_ref)/rms(A32r), corr(a32_new, A32r)))
    print("      corr(pcm_new,pcmr)=%+.6f  rms(pcm_new)/rms(pcmr)=%.4f ; corr(2*A32real,pcmr)=%+.6f" %
          (corr(pcm_new, pcmr), rms(pcm_new)/rms(pcmr), corr(2*A32r, pcmr)))
