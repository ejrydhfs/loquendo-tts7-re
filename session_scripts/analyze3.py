#!/usr/bin/env python3
import json, sys, numpy as np
sys.path.insert(0, '/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
T = json.load(open('/home/asdf/Downloads/ltts_re/tools/codec210_tables.json'))
cfA = T['band_filters_qmf']['bandA_64tap']['f32']
cfB = T['band_filters_qmf']['bandB_64tap']['f32']
def bf(src, cf, oc):
    return np.array(C.band_filter(list(np.asarray(src, float)), cf, oc, 64, [0.0]*64, [0.0]*(2*oc)), float)
def rms(a): return float(np.sqrt((np.asarray(a, float)**2).mean()))
def corr(a, b):
    a = np.asarray(a, float) - np.mean(a); b = np.asarray(b, float) - np.mean(b)
    return float(a.dot(b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-300))

print("### A. Intrinsic amplitude response of one FUN_10003960 call (64-tap, zero tail)")
for name, x in (("DC=1.0", np.ones(160)), ("ramp", np.arange(160.0)),
                ("sine fs/16", np.sin(2*np.pi*np.arange(160)/16)),
                ("sine fs/4", np.sin(2*np.pi*np.arange(160)/4)),
                ("white", np.random.RandomState(0).randn(160))):
    for tag, cf in (("A", cfA), ("B", cfB)):
        y = bf(x, cf, 320)
        print("  %-10s %s: rms(in)=%9.4f rms(out)=%9.4f ratio=%.6f" % (name, tag, rms(x), rms(y), rms(y)/rms(x)))
imp = np.zeros(160); imp[0] = 1.0
print("  impulse step response (DC gain sum of IR):  A=%.6f  B=%.6f" % (bf(imp, cfA, 320).sum(), bf(imp, cfB, 320).sum()))

S = json.load(open('/tmp/snaps2.json')); LO = S['lo']
def arr(snap, addr, n):
    i = (addr - LO)//4
    return np.array(snap[i:i+n], float)
comb = {(r['frame'], r['lvl']): r for r in S['comb']}
bfrec = {(r['frame'], r['lvl'], r['filt']): r for r in S['bf']}
K = 2.0
print("\n### B. Per-frame stage rms table (real) frames 37..39")
print("%5s %10s %10s %10s %10s %10s %10s %10s" % ("f", "sig8", "A16", "B16", "out16", "A32", "B32", "pcm"))
for f in (37, 38, 39):
    s = comb[(f, 'L2')]['snap']
    sig8 = arr(s, 0x30012a30, 160)          # ring1 head == 8k synthesis
    A16 = arr(s, 0x30013430, 320); B16 = arr(s, 0x30013930, 320)
    out16 = K*(A16 - B16)
    A32 = arr(s, 0x30015780, 640); B32 = arr(s, 0x30016180, 640)
    pcm = K*(A32 - B32)
    print("%5d %10.2f %10.2f %10.2f %10.2f %10.2f %10.2f %10.2f" % (
        f, rms(sig8), rms(A16), rms(B16), rms(out16), rms(A32), rms(B32), rms(pcm)))
    # per-call gains
    print("      call gains rms(dst)/rms(src): A16=%.4f B16=%.4f A32=%.4f B32=%.4f" % (
        rms(A16)/rms(sig8), rms(B16)/rms(arr(s,0x30014d80,320)), rms(A32)/rms(out16),
        rms(B32)/rms(arr(s,0x30014d80,320)) if False else rms(B32)/rms(arr(s,0x30014d80,320))))

print("\n### C. Patched chain vs the REAL chain (feed the real 8k synth), B16=B32=0")
print("%5s %10s %10s %10s %10s %10s %10s" % ("f", "rms(port_old)", "rms(port_patch)", "rms(real_pcm)", "corr_patch", "corr_old", "corr_A32"))
notes = {}
for f in (37, 38, 39):
    s = comb[(f, 'L2')]['snap']
    sig8 = arr(s, 0x30012a30, 160)
    A16r = arr(s, 0x30013430, 320); B16r = arr(s, 0x30013930, 320)
    A32r = arr(s, 0x30015780, 640); B32r = arr(s, 0x30016180, 640)
    pcmr = K*(A32r - B32r)
    # old port A-path: a16=bf(sig8); a32=bf(a16); out=2*a32
    a16 = bf(sig8, cfA, 320); a32_old = bf(a16, cfA, 640); out_old = 2*a32_old
    # patched: out16=2*(a16-0); a32=bf(out16); out=2*a32
    out16 = K*a16; a32_new = bf(out16, cfA, 640); out_new = K*a32_new
    # patched with real out16 (i.e. with B16 known) - upper bound
    out16r = K*(A16r - B16r); a32_r = bf(out16r, cfA, 640); out_r = K*a32_r
    print("%5d %10.2f %10.2f %10.2f %10.6f %10.6f %10.6f" % (
        f, rms(out_old), rms(out_new), rms(pcmr), corr(out_new, pcmr), corr(out_old, pcmr), corr(a32_r, A32r)))
    notes[f] = dict(rms_old=rms(out_old), rms_new=rms(out_new), rms_real=rms(pcmr),
                    corr_new=corr(out_new, pcmr), corr_old=corr(out_old, pcmr),
                    corr_A32_realin=corr(a32_r, A32r), rms_a32_new=rms(a32_new), rms_a32_real=rms(A32r),
                    ratio=rms(pcmr)/rms(out_new))
print()
for f, v in notes.items():
    print("f%d: patch/real rms ratio = %.4f   rms(A32_patch_with_realB16)=%.1f vs real=%.1f (%.2f%%)"
          % (f, v['ratio'], v['rms_a32_new'], v['rms_a32_real'], 100*(v['rms_a32_new']/v['rms_a32_real']-1)))
