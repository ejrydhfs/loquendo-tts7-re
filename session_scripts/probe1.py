#!/usr/bin/env python3
import sys, struct, json
sys.path.insert(0, '/home/asdf/Downloads/ltts_re/tools')
import codec210_oracle as O
import numpy as np
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESI, UC_X86_REG_ESP, UC_X86_REG_EDX

o = O.Oracle(); r32 = o.r32; mem = o.uc.mem_read
frame_no = [0]; out = []

# constants
for va in (0x100240a8, 0x100241a8, 0x10022e58, 0x10022e50, 0x10021260, 0x10023e88):
    v = struct.unpack("<f", bytes(mem(va, 4)))[0]
    print("DAT %08x = %.9g" % (va, v))
coefA = struct.unpack("<64f", bytes(mem(0x100240a8, 256)))
coefB = struct.unpack("<64f", bytes(mem(0x100241a8, 256)))
print("sum coefA = %.6f  sum coefB=%.6f" % (sum(coefA), sum(coefB)))
print("sum|coefA| = %.6f  A[0..3]=%s" % (sum(abs(c) for c in coefA), coefA[:4]))
print("sum|coefB| = %.6f  B[0..3]=%s" % (sum(abs(c) for c in coefB), coefB[:4]))

def hook(uc, addr, size, user):
    sp = uc.reg_read(UC_X86_REG_ESP); esi = uc.reg_read(UC_X86_REG_ESI); f = frame_no[0]
    if addr == 0x1000e87b and esi == 0x300021a0 and f == 38:
        r2 = np.frombuffer(bytes(mem(0x30002220, 4*1280)), dtype='<f4').astype(float)
        a2 = np.frombuffer(bytes(mem(0x30014380, 4*320)), dtype='<f4').astype(float)
        a1 = np.frombuffer(bytes(mem(0x30013430, 4*320)), dtype='<f4').astype(float)
        b1 = np.frombuffer(bytes(mem(0x30013930, 4*320)), dtype='<f4').astype(float)
        out.append((r2, a2, a1, b1, uc.reg_read(UC_X86_REG_EDX)))
o.uc.hook_add(UC_HOOK_CODE, hook, begin=0x1000e87b, end=0x1000e87c)
d = open(O.BIN, "rb").read(); ctx = o.open_decoder(32000, 0x6D)
for i in range(39):
    frame_no[0] = i
    o.decode(ctx, d[O.BLOCK_OFFSET+i*O.BLOCK_SIZE: O.BLOCK_OFFSET+(i+1)*O.BLOCK_SIZE])
r2, a2, a1, b1, edx = out[0]
def corr(a,b):
    a=a-a.mean(); b=b-b.mean(); return float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)+1e-300))
print("\nring2 quarters rms:", ["%.1f" % (np.sqrt((r2[i*320:(i+1)*320]**2).mean())) for i in range(4)])
print("corr(A2src, ring2[0:320])=%+.6f" % corr(a2, r2[0:320]))
print("corr(A2src, ring2[320:640])=%+.6f" % corr(a2, r2[320:640]))
print("corr(A2src, ring2[640:960])=%+.6f" % corr(a2, r2[640:960]))
print("A2src[:6]  =", ["%.2f"%v for v in a2[:6]])
print("ring2[0:6] =", ["%.2f"%v for v in r2[:6]])
print("2*A1[:6]   =", ["%.2f"%v for v in (2*a1)[:6]])
print("A1[:6]     =", ["%.2f"%v for v in a1[:6]])
print("B1[:6]     =", ["%.2f"%v for v in b1[:6]])
print("2*(A1-B1)[:6]=", ["%.2f"%v for v in (2*(a1-b1))[:6]])
print("edx at L2 bfA =", hex(edx))
