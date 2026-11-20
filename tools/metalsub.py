import struct, hashlib, os
S = os.path.dirname(os.path.abspath(__file__))
def prefix(msl):
    flag = 37 | (2 if (b'instance_id' in msl or b'mtl_InstanceID' in msl) else 0)   # observed: instancing variants carry +2
    return struct.pack('<12I', 0xf00dcafe, 48, 7, 60, 0, 0, 0, 0, 0, flag, 0xffffffff, 0)
VS_TYPES = {15, 16}; PS_TYPES = {17, 18}          # DX11 VS/PS SM4/SM5 (UnityPy numbering)
METAL = {'VS': 23, 'PS': 24}

def split(sp):
    """Parse a program sub-blob -> (type, header_bytes_before_size, data, tail_ints)."""
    ver, ty = struct.unpack_from('<II', sp, 0)
    p = 24; nk = struct.unpack_from('<I', sp, p)[0]; p += 4
    for _ in range(nk):
        l = struct.unpack_from('<I', sp, p)[0]; p += 4 + l; p += -p % 4
    if 201806140 <= ver < 202012090:        # Unity 2019.1-2020.1 blobs carry a second, local-keyword list before the code
        nl = struct.unpack_from('<I', sp, p)[0]; p += 4
        for _ in range(nl):
            l = struct.unpack_from('<I', sp, p)[0]; p += 4 + l; p += -p % 4
    dl = struct.unpack_from('<I', sp, p)[0]
    data = sp[p + 4:p + 4 + dl]; e = p + 4 + dl; e += -e % 4
    return ty, sp[24:p], data, struct.unpack_from('<%dI' % ((len(sp) - e) // 4), sp, e), ver

def tail_for_metal(ty, tail):
    if ty in VS_TYPES and len(tail) >= 2:
        mask, n = tail[0], tail[1]
        pairs = [tail[2 + 2 * k] for k in range(n)]
        out = [mask, n]
        for k, ch in enumerate(pairs): out += [ch, 13 + k]
        return tuple(out) + tuple(tail[2 + 2 * n:])
    return tail

def build_metal_sub(sp, msl):
    ty, hdr, data, tail, ver = split(sp)
    mty = METAL['VS'] if ty in VS_TYPES else METAL['PS']
    body = prefix(msl) + b'xlatMtlMain\0' + msl + b'\0'
    out = struct.pack('<II4I', ver, mty, 0, 0, 0, 0) + hdr + struct.pack('<I', len(body)) + body
    out += b'\0' * (-len(out) % 4)
    return out + struct.pack('<%dI' % len(tail_for_metal(ty, tail)), *tail_for_metal(ty, tail))

def dxbc_hash(sp):
    i = sp.find(b'DXBC'); dx = sp[i:i + struct.unpack_from('<I', sp, i + 24)[0]]
    return hashlib.sha1(dx).hexdigest()[:16]
