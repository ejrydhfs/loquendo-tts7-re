import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import pefile
from codec210_oracle import Oracle
DLL="/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/bin/LTTS7Codec210.dll"
pe=pefile.PE(DLL); data=open(DLL,'rb').read()
def filebytes(va,n):
    rva=va-0x10000000
    for s in pe.sections:
        if s.VirtualAddress<=rva<s.VirtualAddress+max(s.SizeOfRawData,s.Misc_VirtualSize):
            off=s.PointerToRawData+(rva-s.VirtualAddress); return data[off:off+n], s.Name, s.VirtualAddress, s.PointerToRawData
    return None,None,None,None
o=Oracle()
for va in (0x1000e68c,0x1000e691,0x1000e5e6,0x1000e602,0x100105c0):
    fb,sec,sva,sp=filebytes(va,16)
    mb=bytes(o.uc.mem_read(va,16))
    print(hex(va), "file:",fb.hex(), " mem:",mb.hex(), " same:", fb==mb, sec, hex(sva), hex(sp))
