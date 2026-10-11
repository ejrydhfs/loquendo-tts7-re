import sys
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from codec210_oracle import Oracle
o=Oracle()
for va in (0x1000e68c,0x1000e674,0x1000e691,0x10002ec0):
    b=bytes(o.uc.mem_read(va,6))
    print(hex(va), b.hex(), "call->" if b[0]==0xe8 else "")
    if b[0]==0xe8:
        import struct
        rel=struct.unpack("<i",b[1:5])[0]
        print("   target",hex(va+5+rel))
