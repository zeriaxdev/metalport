"""Rebuild a minimal RDEF chunk (HLSLcc needs it) for a DXBC whose reflection Unity stripped.
Everything is derived from the dcl_* declarations in SHDR/SHEX."""
import struct

DIM_MAP = {1: 1, 2: 2, 3: 4, 4: 5, 5: 8, 6: 9, 7: 3, 8: 6, 9: 7, 10: 10}   # SHDR resource dim -> RDEF SRV dim

def chunks(dx):
    n = struct.unpack_from('<I', dx, 28)[0]
    offs = struct.unpack_from('<%dI' % n, dx, 32)
    out = []
    for o in offs:
        out.append((dx[o:o+4], dx[o+8:o+8+struct.unpack_from('<I', dx, o+4)[0]]))
    return out

def parse_decls(shdr):
    ver = struct.unpack_from('<I', shdr, 0)[0]
    major = (ver >> 4) & 0xf; minor = ver & 0xf
    words = struct.unpack('<%dI' % (len(shdr)//4), shdr)
    i = 2; cbs = {}; texs = {}; samps = {}; buffers = []
    while i < len(words):
        t = words[i]; op = t & 0x7ff; ln = (t >> 24) & 0x7f
        if op == 0x35: ln = words[i + 1]      # customdata block: length lives in the next dword
        if ln == 0: break
        if op == 0x59:   cbs[words[i+2]] = words[i+3]                       # dcl_constantbuffer cbN[size]
        elif op == 0x58: texs[words[i+2]] = (t >> 11) & 0x1f              # dcl_resource tN, dimension
        elif op == 0x5a: samps[words[i+2]] = (t >> 11) & 0xf              # dcl_sampler sN, mode
        elif op in (0x9c, 0x9d, 0x9e, 0xa1, 0xa2):  # typed/raw/structured UAVs and buffer SRVs
            r = words[i+2]
            ty = {0x9c: 4, 0x9d: 8, 0x9e: 6, 0xa1: 7, 0xa2: 5}[op]
            if op == 0x9e and t & 0x800000: ty = 11  # structured UAV with counter
            ret = words[i+ln-1] & 0xf if op == 0x9c else 6
            dim = DIM_MAP[(t >> 11) & 0x1f] if op == 0x9c else 1
            name = f'uav{r}' if op in (0x9c, 0x9d, 0x9e) else f'buf{r}'
            buffers.append((name, ty, ret, dim, 0, r, 1, 0))
        i += ln
    return major, minor, cbs, texs, samps, buffers

def build_rdef(major, minor, cbs, texs, samps, buffers):
    strs = bytearray(); soff = {}
    def S(s):
        if s not in soff:
            soff[s] = len(strs); strs.extend(s.encode() + b'\0')
        return soff[s]
    sm5 = major >= 5
    ress = []   # (name, type, ret, dim, samples, bind, count, flags)
    for r, n in sorted(cbs.items()):   ress.append((f'cb{r}', 0, 0, 0, 0, r, 1, 0))
    for r, d in sorted(texs.items()):  ress.append((f'tex{r}', 2, 5, DIM_MAP.get(d, 4), 0xffffffff, r, 1, 0x0c))
    for r, m in sorted(samps.items()): ress.append((f'sampler_s{r}', 3, 0, 0, 0, r, 1, 0))
    ress.extend(buffers)
    nvar = 10 if sm5 else 6
    hdr = 28
    res_off = hdr; res_sz = 8 * 4 * len(ress)
    cb_off = res_off + res_sz; cb_sz = 24 * len(cbs)
    var_off = cb_off + cb_sz; var_sz = nvar * 4 * len(cbs)
    typ_off = var_off + var_sz; typ_sz = (4 * 4 if sm5 else 4 * 4) * len(cbs)  # type desc = 4 dwords
    str_off = typ_off + typ_sz
    # strings first (need offsets) -> build with placeholder base then shift
    body = bytearray(); base = str_off
    creator = S('rdef')
    res_b = bytearray(); cb_b = bytearray(); var_b = bytearray(); typ_b = bytearray()
    for (n, t, rt, dm, ns, bp, bc, fl) in ress:
        res_b += struct.pack('<8I', base + S(n), t, rt, dm, ns, bp, bc, fl)
    for k, (r, n) in enumerate(sorted(cbs.items())):
        vo = var_off + k * nvar * 4; to = typ_off + k * 16
        cb_b += struct.pack('<6I', base + S(f'cb{r}'), 1, vo, n * 16, 0, 0)
        v = [base + S(f'cb{r}_data'), 0, n * 16, 2, to, 0]
        if sm5: v += [0xffffffff, 0, 0xffffffff, 0]
        var_b += struct.pack('<%dI' % nvar, *v)
        typ_b += struct.pack('<HHHHHH', 1, 3, 1, 4, n, 0) + struct.pack('<I', 0) + struct.pack('<I', 0)
        # (class vector, type float, 1 row, 4 cols, n elements, 0 members) + memberOffset + pad
    # fix: type desc is class/type, rows/cols, elements/members, memberOffset => 4 dwords
    typ_b = bytearray()
    for k, (r, n) in enumerate(sorted(cbs.items())):
        typ_b += struct.pack('<6HI', 1, 3, 1, 4, n, 0, 0)
    head = struct.pack('<7I', len(cbs), cb_off, len(ress), res_off, (major << 8) | minor, 0, base + creator)
    data = head + bytes(res_b) + bytes(cb_b) + bytes(var_b) + bytes(typ_b)
    assert len(data) == str_off, (len(data), str_off)
    data += bytes(strs); data += b'\0' * (-len(data) % 4)
    return data

def add_rdef(dx):
    ch = chunks(dx)
    if any(f == b'RDEF' for f, _ in ch): return dx
    shdr = next(d for f, d in ch if f in (b'SHDR', b'SHEX'))
    rdef = (b'RDEF', build_rdef(*parse_decls(shdr)))
    new = [rdef] + [(f, d) for f, d in ch]
    n = len(new); off = 32 + 4 * n; body = b''; offs = []
    for f, d in new:
        offs.append(off + len(body)); pad = b'\0' * (-len(d) % 4)
        body += f + struct.pack('<I', len(d) + len(pad)) + d + pad
    total = off + len(body)
    return b'DXBC' + dx[4:20] + struct.pack('<III', 1, total, n) + struct.pack('<%dI' % n, *offs) + body

if __name__ == '__main__':
    import sys
    dx = open(sys.argv[1], 'rb').read()
    open(sys.argv[2], 'wb').write(add_rdef(dx))
    print(parse_decls(next(d for f, d in chunks(dx) if f in (b'SHDR', b'SHEX'))))
