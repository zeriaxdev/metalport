#!/usr/bin/env python3
"""Make the player believe the build contains Metal: BuildSettings.m_GraphicsAPIs (e.g. [D3D11, D3D12]) -> first entry becomes Metal (16).
In-place byte patch of `globalgamemanagers` (same size; re-serializing the file is NOT safe).  usage: patch_buildsettings.py <Data>/globalgamemanagers"""
import sys, struct, UnityPy
path = sys.argv[1]; env = UnityPy.load(path); METAL = 16
obj = next(o for o in env.objects if o.type.name == 'BuildSettings')
apis = obj.read_typetree()['m_GraphicsAPIs']; print('before:', apis)
if METAL in apis: print('already has Metal'); sys.exit(0)
raw = bytes(obj.get_raw_data()); n = len(apis); tail = struct.unpack(f'<{n + 1}I', raw[-4 * (n + 1):])
assert tail == (n, *apis), 'm_GraphicsAPIs is not the last field here; adapt this script'
d = bytearray(open(path, 'rb').read()); at = obj.byte_start + len(raw) - 4 * n
assert bytes(d[obj.byte_start:obj.byte_start + len(raw)]) == raw
struct.pack_into('<I', d, at, METAL); open(path, 'wb').write(d); print('after :', [METAL] + apis[1:])
