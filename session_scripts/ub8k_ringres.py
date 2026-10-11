"""Per-sample residual of the ring rule for frame 118 sf1 (lag=20)."""
import sys, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import UC_X86_REG_ESP
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
EXC=0x30012364
PCS={0x10009b6f:'clear',0x10009c0d:'ltp',0x10009f3e:'cb1',0x10009ff1:'cb2'}
N,SF=118,1
dec=P.Codec210(); snap=[]
for i in range(N+1):
    dec.decode_frame(d[150+i*110:150+(i+1)*110],key=0x6D); snap.append(list(dec.buf))
pre=snap[N-1]
f=dec.parse_frame(d[150+N*110:150+(N+1)*110],0x6D)
o=Oracle(); ctx=o.open_decoder(32000,0x6D); snap2=[]
for i in range(N): o.decode(ctx, d[150+i*110:150+(i+1)*110])
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
snaps=[]; pend=None
def h(uc,a,s,u):
    global pend
    esp=uc.reg_read(UC_X86_REG_ESP)
    if a==0x10009c0d: pend=[o.r32(esp+4*k) for k in range(14)]
    elif a==0x10009c12 and pend: snaps.append(fl(pend[9],120)); pend=None
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
o.decode(ctx, d[150+N*110:150+(N+1)*110])
ev=[]; last=[0]
def hc(uc,a,s,u): last[0]=a
def hw(uc,acc,addr,size,val,u):
    if EXC<=addr<EXC+640:
        ev.append((PCS.get(last[0],hex(last[0])),(addr-EXC)//4,struct.unpack("<f",struct.pack("<I",val))[0]))
b=list(pre); b[0:P.HIST]=b[160:160+P.HIST]
for sf in range(SF):
    lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
    tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
    for k in range(40): b[p+k]=0.0
    w0=p-(lag+1)
    o_=[P._f32(g[2]*b[w0+i]+g[1]*b[w0+i+1]+g[0]*b[w0+i+2]) for i in range(40)]
    gg=dec.exc_gain(f["energy8"],b3); g2v=P._f32(gg*P.CB2_RATIO)
    cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
    for i in range(40):
        v=P._f32(o_[i]+P._f32(gg*cb1[i])); b[p+i]=P._f32(v+P._f32(g2v*cb2[i]))
sf=SF; lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
w0=p-(lag+1)
S=snaps[sf]
def R(b,w0,lag,k):
    return b[w0+k] if k<=lag else b[w0+1+((k-1)%lag)]
mine=[P._f32(g[2]*R(b,w0,lag,i)+g[1]*R(b,w0,lag,i+1)+g[0]*R(b,w0,lag,i+2)) for i in range(40)]
# DLL from the scratch slices (verified mapping): W0=S[0:40], W1=S[40:80], W2=S[80:120]
dll=[P._f32(g[2]*S[i]+g[1]*S[40+i]+g[0]*S[80+i]) for i in range(40)]
# DLL from the writes (the actual output)
L=[None]*40
for pc,pos,val in ev:
    if pc=='ltp' and 40*sf<=pos<40*sf+40: L[pos-40*sf]=val
print("lag=%d idx=%d g=%s w0=%d"%(lag,idx,["%.5f"%x for x in g],w0))
print(" i :   mine      dll_scratch   dll_writes   mine-dll")
for i in range(40):
    print(" %2d: %10.5f %12.5f %12s %10.4f"%(i,mine[i],dll[i],
          ("%.5f"%L[i]) if L[i] is not None else "-", mine[i]-(L[i] if L[i] is not None else dll[i])))
