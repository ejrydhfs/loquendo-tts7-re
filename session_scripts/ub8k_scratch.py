"""Read the DLL's LTP tap scratch (arg10 of FUN_10006bb0) at a drift sub-frame."""
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
o=Oracle(); ctx=o.open_decoder(32000,0x6D)
for i in range(N):
    o.decode(ctx, d[150+i*110:150+(i+1)*110])
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
calls=[]
def h(uc,a,s,u):
    esp=uc.reg_read(UC_X86_REG_ESP)
    if a==0x10009c0d:
        args=[o.r32(esp+4*k) for k in range(14)]
        calls.append(('call',args))
    if a==0x10009c12 and calls and calls[-1][0]=='call':
        # read the scratch (arg10) and the output base (arg1) 40 samples
        args=calls[-1][1]
        scratch, outbase = args[9], args[0]
        calls.append(('after',scratch,outbase,
                      ["%.6g"%x for x in fl(scratch,120)],
                      ["%.6g"%x for x in fl(outbase,40)]))
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
pcm=o.decode(ctx, blk)
for c in calls[:6]:
    if c[0]=='call':
        print("LTP call args:",[hex(x) for x in c[1]])
    else:
        print(" scratch@%08x out@%08x"%(c[1],c[2]))
        print("   scratch[:12]=",c[3][:12])
        print("   scratch[36:52]=",c[3][36:52])
        print("   scratch[72:96]=",c[3][72:96])
        print("   out(first 8)=",c[4][:8])
# port's own view for the first sub-frame
buf=list(dec.buf); buf[0:P.HIST]=buf[160:160+P.HIST]
lag_d,idx,b3,cbi=f["sub8"][0]; p=P.HIST; lag=lag_d+17
tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
print("frame %d sf0: lag=%d idx=%d g=%s w0=%d (p=%d)"%(N,lag,idx,["%.5f"%x for x in g],p-(lag+1),p))
