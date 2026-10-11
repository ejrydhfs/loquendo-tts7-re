#!/usr/bin/env python3
"""Run the port (original and patched) for frames 0..39, dumping sig8/a16/a32 per frame."""
import importlib.util, sys, json, numpy as np

BIN = ("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
       "Jorge.32000.LTTS7Codec210.44000.10.bin")

def run(path):
    spec = importlib.util.spec_from_file_location('c210x', path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    d, info = mod.read_container(BIN)
    caps = {'sig8': [], 'bf': []}
    obf = mod.band_filter
    def bfcap(src, cf, oc, ntaps, tail, work):
        out = obf(src, cf, oc, ntaps, tail, work)
        caps['bf'].append(np.array(out, float)); return out
    mod.band_filter = bfcap
    dec = mod.Codec210()
    osyn = dec.synth8
    def syn(*a, **k):
        r = osyn(*a, **k); caps['sig8'].append(np.array(r, float)); return r
    dec.synth8 = syn
    per = []
    for i, blk in mod.iter_blocks(d, info):
        if i >= 40: break
        caps['bf'] = []; caps['sig8'] = []
        pcm = dec.decode_frame(blk, key=info['key'])
        per.append(dict(f=i, pcm=np.array(pcm, float), sig8=caps['sig8'][0],
                        a16=caps['bf'][0], a32=caps['bf'][1]))
    return per

def rms(a): return float(np.sqrt((np.asarray(a, float)**2).mean()))
def corr(a, b):
    a = np.asarray(a, float)-np.mean(a); b = np.asarray(b, float)-np.mean(b)
    return float(a.dot(b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-300))

S2 = json.load(open('/tmp/snaps2.json')); LO = S2['lo']
comb = {(r['frame'], r['lvl']): r for r in S2['comb']}
def arr(snap, addr, n):
    return np.array(snap[(addr-LO)//4:(addr-LO)//4+n], float)
real = {}
for f in (36, 37, 38, 39):
    s = comb[(f, 'L2')]['snap']
    A16 = arr(s, 0x30013430, 320); B16 = arr(s, 0x30013930, 320)
    A32 = arr(s, 0x30015780, 640); B32 = arr(s, 0x30016180, 640)
    real[f] = dict(A16=A16, B16=B16, A32=A32, B32=B32, out16=2*(A16-B16),
                   pcm=2*(A32-B32))

for tag, path in (('OLD', '/home/asdf/Downloads/ltts_re/tools/codec210.py'),
                  ('PATCHED', '/tmp/codec210_patched.py')):
    per = run(path)
    print("\n=== %s ===" % tag)
    print("%4s %10s %10s %10s %10s %10s" % ("f", "rms pcm", "rms real", "rms sig8", "rms a16", "rms a32"))
    for r in per:
        if r['f'] in (37, 38, 39):
            print("%4d %10.2f %10.2f %10.2f %10.2f %10.2f" % (
                r['f'], rms(r['pcm']), rms(real[r['f']]['pcm']), rms(r['sig8']),
                rms(r['a16']), rms(r['a32'])))
    # shape comparisons
    print("  frame 37/38/39: corr(pcm_port, pcm_real), corr(a32_port, A32_real), corr(a16_port, A16_real), rms ratio pcm")
    for r in per:
        if r['f'] in (37, 38, 39):
            R = real[r['f']]
            print("   f%d corr_pcm=%+.6f corr_a32=%+.6f corr_a16=%+.6f ratio=%.4f" % (
                r['f'], corr(r['pcm'], R['pcm']), corr(r['a32'], R['A32']),
                corr(r['a16'], R['A16']), rms(r['pcm'])/rms(R['pcm'])))
    # overall correlation frames 0..39
    allp = np.concatenate([r['pcm'] for r in per])
    print("  (no overall real reference stored here)")
