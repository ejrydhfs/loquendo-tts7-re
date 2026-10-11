import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EBX, UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
NF=38
o = Oracle()
ctx = o.open_decoder(32000, 0x6D)
d=open(BIN,'rb').read()
for i in range(NF):
    o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
regions={
 0x30008060:'ring16', 0x30012a30:'o16+2c', 0x30012f30:'o16+34', 0x30014030:'o16+48',
 0x30002220:'ring32', 0x30014380:'o32+2c', 0x30014d80:'o32+34', 0x30016d80:'o32+48',
 0x30011ea0:'o8+30', 0x30013430:'o16+38', 0x30013930:'o16+3c', 0x30015780:'o32+38', 0x30016180:'o32+3c',
}
sizes={0x30008060:640*4,0x30012a30:160*4,0x30012f30:160*4,0x30014030:160*4,0x30002220:640*4,
 0x30014380:320*4,0x30014d80:320*4,0x30016d80:320*4,0x30011ea0:160*4,
 0x30013430:320*4,0x30013930:320*4,0x30015780:640*4,0x30016180:640*4}
last=[0]; events=[]
def hcode(uc,a,size,u): last[0]=a
def hwrite(uc,access,addr,size,val,u):
    for base,name in regions.items():
        if base<=addr<base+sizes[base]:
            events.append((last[0],name,(addr-base)//4,val))
            break
o.uc.hook_add(UC_HOOK_CODE,hcode,begin=0x10000000,end=0x10040000)
o.uc.hook_add(UC_HOOK_MEM_WRITE,hwrite,begin=0x30000000,end=0x30020000)
# also log selected call sites
sites={0x1000e5e6:'after_read5',0x1000e602:'noise_gain',0x1000e65b:'noise_store',
       0x1000e679:'after_read4',0x1000e6f7:'cb_call',0x1000e70f:'scale16',0x1000e7ca:'?e7ca',
       0x1000e849:'?e849',0x1000e54b:'pref',0x1000e5f7:'prenoise'}
o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
# summarize: for each region, the sequence of distinct pcs in order
print("== write timeline per region ==")
for name in ['ring16','o16+48','o16+34','o16+2c','o16+38','o16+3c','o16+2c','ring32','o32+48','o32+34','o32+2c','o32+38','o32+3c','o8+30','o16+2c']:
    seq=[]
    for pc,n,i,v in events:
        if n==name:
            if not seq or seq[-1][0]!=pc: seq.append((pc,i))
    print("%-8s:"%name, " -> ".join("%08x@%d"%(pc,i) for pc,i in seq[:14]))
print("total events", len(events))
