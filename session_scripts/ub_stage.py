"""Stage-local validation of the two upper bands against the oracle buffers.

Feeds the oracle's own 8k excitation / tilt / LPC states into the Python
implementation so that only the newly ported stages are under test.
"""
import sys, struct, math, json
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
import codec210 as C
from ub_port import CB16, codebook, tilt_vals, ec0

def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
def rms(v): return (sum(float(x)*x for x in v)/len(v))**0.5

o=Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
par=C.Codec210()
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
def run(fr):
    blk=d[BLOCK_OFFSET+fr*BLOCK_SIZE:BLOCK_OFFSET+(fr+1)*BLOCK_SIZE]
    return blk, par.parse_frame(blk,0x6D), o.decode(ctx, blk)

for N in (37,38,39):
    o2=Oracle(); c2=o2.open_decoder(32000,0x6D)
    for i in range(N): o2.decode(c2, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    o32=o2.r32(c2+0x28); o16=o2.r32(o32+4); o8=o2.r32(o16+4)
    def fl2(a,n): return list(struct.unpack("<%df"%n, bytes(o2.uc.mem_read(a,4*n))))
    prev16=fl2(o2.r32(o16+0x4c),8); prev32=fl2(o2.r32(o32+0x4c),8)
    st16=fl2(o2.r32(o16+0x5c),16); st32=fl2(o2.r32(o32+0x5c),16)
    tA16=fl2(o2.r32(o16+0x40),64); tB16=fl2(o2.r32(o16+0x44),64)
    tA32=fl2(o2.r32(o32+0x40),64); tB32=fl2(o2.r32(o32+0x44),64)
    blk=o2  # rename guard
    blk=d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE]
    f=par.parse_frame(blk,0x6D); pcm=o2.decode(c2, blk)
    exc8=fl2(o2.r32(o8+0x3c),160); tilt8=fl2(0x30012a20,4)
    lsf16=fl2(o2.r32(o16+0x4c),8); lsf32=fl2(o2.r32(o32+0x4c),8)
    sig8=fl2(o2.r32(o8+0x30),160)
    r={}
    r['exc16']=fl2(o2.r32(o16+0x48),160); r['synth16']=fl2(o2.r32(o16+0x34),160)
    r['A16']=fl2(o2.r32(o16+0x38),320); r['B16']=fl2(o2.r32(o16+0x3c),320)
    r['ring32']=fl2(o2.r32(o32+0x28),320)
    r['exc32']=fl2(o2.r32(o32+0x48),320); r['synth32']=fl2(o2.r32(o32+0x34),320)
    r['A32']=fl2(o2.r32(o32+0x38),640); r['B32']=fl2(o2.r32(o32+0x3c),640)
    # ---- Python re-implementation of the two bands (oracle inputs) ----
    ps16=[]
    for sf in range(4):
        lsf_i=C.lsf_stabilise(C.lsf_interp(prev16,lsf16,8,sf,4),0.05)
        a=C.lsf_to_lpc(lsf_i); ps16.append((a,)+tilt_vals(a,8))
    block2=list(exc8)      # the 8k class's cmd-0x65 handler is a PLAIN copy of obj8[+0x3c]
    my_exc=[0.0]*160
    for sf in range(4):
        a,s,d16=ps16[sf]
        norm16=(tilt8[sf]+0.01)/(0.01+d16)
        energy=ec0(block2[40*sf:40*sf+40],40)
        gg=math.exp(f["sub16"][sf][0]*0.27027027027-0.15556)
        gain=(energy+1.0)*(gg/norm16)
        pr=f["sub16"][sf][1]
        v1=codebook(pr[0:5],8,CB16); v2=codebook(pr[5:10],8,CB16)
        my_exc[40*sf:40*sf+40]=[v1[i]*gain+v2[i]*(gain*0.4) for i in range(40)]
    my_synth=list(my_exc); mem=list(st16[:8])
    for sf in range(4):
        y,mem=C.lpc_synth(ps16[sf][0],mem,my_synth[40*sf:40*sf+40])
        my_synth[40*sf:40*sf+40]=y
    a16=C.band_filter(sig8,par.cf_a,320,64,list(tA16),[0.0]*1088)
    b16=C.band_filter(my_synth,par.cf_b,320,64,list(tB16),[0.0]*1088)
    ring=[max(-32768.0,min(32767.0,2.0*(x-y))) for x,y in zip(a16,b16)]
    # 32k
    ps32=[]
    for sf in range(4):
        lsf_i=C.lsf_stabilise(C.lsf_interp(prev32,lsf32,8,sf,4),0.05)
        a=C.lsf_to_lpc(lsf_i); ps32.append((a,)+tilt_vals(a,8))
    src=[0.0]*320
    for k in range(160): src[2*k]=2.0*my_exc[k]
    my32=[0.0]*320
    for sf in range(4):
        a,s,d32=ps32[sf]
        norm32=(ps16[sf][1]+0.01)/(0.01+d32)
        g5=math.exp((f["ref32"][sf]-10)*0.125); amp=g5/norm32; ramp=1.0
        for i in range(80):
            my32[80*sf+i]=((ramp*amp)*0.7)*src[80*sf+i]; ramp*=-1.0
    mem=list(st32[:8])
    for sf in range(4):
        y,mem=C.lpc_synth(ps32[sf][0],mem,my32[80*sf:80*sf+80])
        my32[80*sf:80*sf+80]=y
    a32=C.band_filter(ring,par.cf_a,640,64,list(tA32),[0.0]*2048)
    b32=C.band_filter(my32,par.cf_b,640,64,list(tB32),[0.0]*2048)
    mypcm=[C.clamp_int16(2.0*(x-y)) for x,y in zip(a32,b32)]
    print("=== frame %d"%N)
    print("  energy: mine=%s vs oracle=%s"%(["%.5g"%ec0(block2[40*sf:40*sf+40],40) for sf in range(4)],"True"))
    for k,mine in (('exc16',my_exc),('synth16',my_synth),('A16',a16),('B16',b16),('ring32',ring),
                   ('exc32',my32),('A32',a32),('B32',b32),('pcm',mypcm)):
        ref=r.get(k)
        if ref is None: continue
        print("  %-8s corr=%.6f  rms %.5g / %.5g"%(k,corr(mine,ref),rms(mine),rms(ref)))
