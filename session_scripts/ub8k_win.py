"""Decisive test: compare the DLL's three LTP tap windows (scratch at 0x3000e0a4) with
the port's buffer content (a) after the clear and (b) before the clear (stale/previous)."""
import sys, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
N=int(sys.argv[1]) if len(sys.argv)>1 else 118
dec=P.Codec210()
for i in range(N):
    dec.decode_frame(d[150+i*110:150+(i+1)*110],key=0x6D)
blk=d[150+N*110:150+(N+1)*110]
f=dec.parse_frame(blk,0x6D)
pre=list(dec.buf)                     # the port's state before frame N
o=Oracle(); ctx=o.open_decoder(32000,0x6D)
for i in range(N):
    o.decode(ctx, d[150+i*110:150+(i+1)*110])
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
calls=[]; pend=None
def h(uc,a,s,u):
    global pend
    esp=uc.reg_read(UC_X86_REG_ESP)
    if a==0x10009c0d:
        pend=[o.r32(esp+4*k) for k in range(14)]
    elif a==0x10009c12 and pend:
        calls.append(list(pend)); pend=None
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
o.decode(ctx, blk)
print("frame %d: %d LTP calls"%(N,len(calls)))
buf=list(pre); buf[0:P.HIST]=buf[160:160+P.HIST]
for sf,args in enumerate(calls[:4]):
    base, lag_d, _, _, _, blen = args[0], args[1], args[2], args[3], args[4], args[5]
    scr=args[9]; off=args[11]
    lag=f["sub8"][sf][0]+17; p=base-P.HIST if base>=P.HIST else None
    W=fl(scr,120)
    print(" sf%d base=%08x lag(claim)=%d+17=%d blen=%d scratch=%08x"%(sf,base,lag_d,lag,blen,scr))
    # the port's w0 for the same sub-frame (the port's buffer indexing)
    psf=P.HIST+40*sf
    w0=psf-(lag+1)
    stale=[pre[psf+k] for k in range(40)]
    for wi in range(3):
        dw=W[40*wi:40*wi+40]
        # port: pre-clear window and post-clear window
        prew=[buf[pref] if 0<=pref<len(buf) else 0.0 for pref in (w0+wi+k for k in range(40))]
        postw=[0.0 if (w0+wi+k)>=psf else prew[k] for k in range(40)]
        md_pre=max(abs(a-b) for a,b in zip(dw,prew))
        md_post=max(abs(a-b) for a,b in zip(dw,postw))
        print("    W%d: max|dll-port_preclear|=%.4g  max|dll-port_postclear|=%.4g"%(wi,md_pre,md_post))
        if wi==2:
            print("       dll W2[16:26]=%s"%["%.5g"%x for x in dw[16:26]])
            print("       my  W2[16:26]=%s"%["%.5g"%x for x in prew[16:26]])
            print("       stl W2[16:26]=%s"%["%.5g"%x for x in stale[16:26]])
