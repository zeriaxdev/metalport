"""Rewrite a Unity 2019.x Shader object (typetree dict, Metal already injected) into the Unity 2021.3 layout, Metal only:
per-subprogram parameters move into m_Parameters, global+local keyword indices become one m_KeywordIndices into the new
shader-wide m_ParsedForm.m_KeywordNames, and each Metal blob entry is re-versioned (one keyword list instead of two).
Everything the 2021 layout adds is filled with defaults from its type tree (merge()).  Used by outer-wilds/convert_all.py."""
import struct, re, copy, lz4.block
from inject import read_subs, pack_chunks
from metalsub import METAL

V2021 = 202012090                       # blob entry version written by 2021.3 players (0x0c0a75ba)
PARAMS = ('m_VectorParams', 'm_MatrixParams', 'm_TextureParams', 'm_BufferParams', 'm_ConstantBuffers', 'm_ConstantBufferBindings', 'm_UAVParams', 'm_Samplers')

def _strings(sp, p):
    n = struct.unpack_from('<I', sp, p)[0]; p += 4; out = []
    for _ in range(n):
        l = struct.unpack_from('<I', sp, p)[0]; out.append(sp[p + 4:p + 4 + l].decode()); p += 4 + l; p += -p % 4
    return out, p

def reentry(sp, prm=None, pnames=None, alloc=lambda n: None):
    """2019 entry (ver, type, 4 ints, global names, local names, code, tail) -> 2021 entry (one names list); returns (entry, names, moves)."""
    g, p = _strings(sp, 24); l, p = _strings(sp, p)
    names = g + l; head = struct.pack('<I', V2021) + sp[4:24] + struct.pack('<I', len(names))
    for s in names:
        b = s.encode(); head += struct.pack('<I', len(b)) + b + b'\0' * (-len(b) % 4)
    rest = bytearray(sp[p:])
    if struct.unpack_from('<I', rest, 4)[0] == 0xf00dcafe:                        # Metal code header: 2021 uses header version 5 and flags without bit 32 (2022: 7, 37/39)
        struct.pack_into('<I', rest, 4 + 8, 5)
        struct.pack_into('<I', rest, 4 + 36, struct.unpack_from('<I', rest, 4 + 36)[0] & ~32)
        if prm is not None: rest, moves = repack(rest, prm, pnames, alloc); return head + bytes(rest), names, moves
    return head + bytes(rest), names, []

CBA = re.compile(rb'(cb(\d+))\.cb\2_data\[([^\]]+)\](?:\.([xyzw]{1,4})(?![A-Za-z0-9_]))?')

def free_slots(ps):
    """Registers of $Globals that no program of this pass uses: moved values go there (Unity uploads only m_Size bytes, so growing the buffer reads garbage)."""
    names = {v: k for k, v in ps['m_NameIndices']}; used = set(); size = 0
    for st in ('progVertex', 'progFragment', 'progGeometry', 'progHull', 'progDomain'):
        for e in ps.get(st, {}).get('m_SubPrograms', []):
            for c in e.get('m_ConstantBuffers', []):
                if names.get(c['m_NameIndex']) != '$Globals': continue
                size = max(size, c['m_Size'])
                for v in c['m_VectorParams']: used |= {(v['m_Index'] + 4 * k) // 16 for k in range(v['m_Dim'] * max(1, v['m_ArraySize']))}
                for m in c['m_MatrixParams']: used |= {m['m_Index'] // 16 + k for k in range(4 * max(1, m['m_ArraySize']))}
    pool = [s for s in range(size // 16) if s not in used]; given = {}
    def alloc(name_index):                       # same parameter -> same register across the pass's programs
        if name_index not in given: given[name_index] = pool.pop(0) if pool else None
        return given[name_index]
    return alloc

def repack(rest, prm, names, alloc=lambda n: None):
    """Unity's Metal backend uploads a float3 parameter as 16 bytes, overwriting anything Direct3D packed into the last lane of
    that register (e.g. _ExposureEV right after _LogLut_Params: post-processing went black).  Move such values to fresh registers
    at the end of $Globals and point the MSL reads there.  rest: entry bytes from the code length on.
    Returns (rest, moves) with moves = [(cb name index, old offset, new offset, new cb size)]."""
    L = struct.unpack_from('<I', rest, 0)[0]; code = bytes(rest[4:4 + L])
    head, msl = code[:48 + 12], code[48 + 12:]                                  # 48-byte Metal header + b'xlatMtlMain\0'
    end = msl.find(b'\0'); msl, trail = (msl[:end], msl[end:]) if end >= 0 else (msl, b'')
    moves = []
    for cb in prm.get('m_ConstantBuffers', []):
        if names.get(cb['m_NameIndex']) != '$Globals': continue
        b = next((x['m_Index'] for x in prm['m_ConstantBufferBindings'] if x['m_NameIndex'] == cb['m_NameIndex']), None)
        vec = cb['m_VectorParams']
        vic = [q for p in vec if p['m_Dim'] == 3 and not p['m_ArraySize'] for q in vec if q is not p and p['m_Index'] + 12 <= q['m_Index'] < p['m_Index'] + 16]
        if b is None or not vic: continue
        acc = [m for m in CBA.finditer(msl) if int(m.group(2)) == b]
        decl = re.search(rb'(\w+)4 cb%d_data\[(\d+)\];' % b, msl)
        if not decl or any(not m.group(3).isdigit() for m in acc): continue     # dynamic indexing: leave alone
        base = max(-(-cb['m_Size'] // 16), int(decl.group(2))); remap = {}; grow = 0
        for q in vic:
            s = alloc(q['m_NameIndex'])
            if s is None: s = base + grow; grow += 1                              # no free register: grow (last resort)
            remap[(q['m_Index'] // 16, (q['m_Index'] % 16) // 4)] = s
            moves.append((cb['m_NameIndex'], q['m_Index'], s * 16, (base + grow) * 16, q['m_NameIndex']))
        base += grow
        ty = decl.group(1)
        def sub(m):
            if int(m.group(2)) != b: return m.group(0)
            slot = int(m.group(3)); sw = (m.group(4) or b'xyzw').decode()
            if not any((slot, 'xyzw'.index(c)) in remap for c in sw): return m.group(0)
            cbn = m.group(1).decode()
            parts = [f'{cbn}.{cbn}_data[{remap[(slot, "xyzw".index(c))]}].x' if (slot, 'xyzw'.index(c)) in remap else f'{cbn}.{cbn}_data[{slot}].{c}' for c in sw]
            return (parts[0] if len(parts) == 1 else f'{ty.decode()}{len(parts)}({", ".join(parts)})').encode()
        msl = CBA.sub(sub, msl)
        decl = re.search(rb'(\w+)4 cb%d_data\[(\d+)\];' % b, msl)
        msl = msl[:decl.start()] + b'%s4 cb%d_data[%d];' % (ty, b, max(base, max(remap.values()) + 1)) + msl[decl.end():]
    if not moves: return rest, moves
    code = head + msl + trail; tail = bytearray(rest[4 + L + (-(4 + L) % 4):])
    for _, old, new, size, pni in moves:      # the player binds from this trailing table, not from m_Parameters: entry = name, type, rows, cols, matrix, array, offset
        nm = names[pni].encode(); pat = struct.pack('<I', len(nm)) + nm + b'\0' * (-len(nm) % 4); at = tail.find(pat)
        assert at >= 0 and struct.unpack_from('<I', tail, at + len(pat) + 20)[0] == old, ('binding table mismatch', names[pni])
        struct.pack_into('<I', tail, at + len(pat) + 20, new)
        g = b'\x08\x00\x00\x00$Globals'; gi = tail.find(g)                          # $Globals size follows its name
        if gi >= 0 and struct.unpack_from('<I', tail, gi + 12)[0] < size: struct.pack_into('<I', tail, gi + 12, size)
    out = struct.pack('<I', len(code)) + code; out += b'\0' * (-len(out) % 4)
    return bytearray(out + tail), moves

def default(node):
    if node.m_Type == 'string': return ''                    # before the Array test: a string node has an Array child too
    if node.m_Type in ('vector', 'map', 'set', 'staticvector') or (node.m_Children and node.m_Children[0].m_Type == 'Array'): return []
    if node.m_Type == 'TypelessData': return b''
    if not node.m_Children: return 0.0 if node.m_Type in ('float', 'double') else (False if node.m_Type == 'bool' else 0)
    return {c.m_Name: default(c) for c in node.m_Children}

def merge(node, v):
    """Shape value v (2019 data) to node (2021 layout): keep matching fields, default the missing ones, drop the rest."""
    if v is None: return default(node)
    if node.m_Type == 'string' or not node.m_Children: return v
    arr = node.m_Children[0] if node.m_Children[0].m_Type == 'Array' else None
    if arr is not None:
        item = arr.m_Children[1]
        if not item.m_Children or item.m_Type == 'string': return v
        if item.m_Type == 'pair': return [(merge(item.m_Children[0], a), merge(item.m_Children[1], b)) for a, b in v]
        return [merge(item, x) for x in v]
    if not isinstance(v, dict): return default(node)
    return {c.m_Name: merge(c, v.get(c.m_Name)) for c in node.m_Children}

def convert(tt, node2021):
    """tt: 2019 Shader dict with platform 14 present.  Returns the 2021 dict (Metal only)."""
    subs, multi = read_subs(tt, tt['platforms'].index(14), bytes(tt['compressedBlob'])) if 14 in tt['platforms'] else ([], False)
    P = tt['m_ParsedForm']; kw = []; kwi = {}; done = {}
    for ss in P['m_SubShaders']:
        for ps in ss['m_Passes']:
            used = set(); pnames = {v: k for k, v in ps['m_NameIndices']}; alloc = free_slots(ps)
            for st in ('progVertex', 'progFragment', 'progGeometry', 'progHull', 'progDomain', 'progRayTracing'):
                if st not in ps: continue
                keep = []
                for e in ps[st]['m_SubPrograms']:
                    if e['m_GpuProgramType'] not in METAL.values(): continue      # D3D entries: no blob on this platform list
                    bi = e['m_BlobIndex']
                    e = copy.deepcopy(e); e['m_Parameters'] = {k: e.pop(k, []) for k in PARAMS}
                    if bi not in done: done[bi] = reentry(subs[bi], e['m_Parameters'], pnames, alloc)
                    for ni, old, new, size, _ in done[bi][2]:                        # registers moved by repack(): same for every user of this blob
                        for cb in e['m_Parameters']['m_ConstantBuffers']:
                            if cb['m_NameIndex'] != ni: continue
                            cb['m_Size'] = max(cb['m_Size'], size)
                            for v in cb['m_VectorParams']:
                                if v['m_Index'] == old: v['m_Index'] = new
                    idx = []
                    for n in done[bi][1]:
                        if n not in kwi: kwi[n] = len(kw); kw.append(n)
                        idx.append(kwi[n])
                    e['m_KeywordIndices'] = sorted(idx); used |= set(idx)
                    keep.append(e)
                ps[st]['m_SubPrograms'] = keep
            ps['m_Platforms'] = [14]; ps['m_SerializedKeywordStateMask'] = sorted(used)
    P['m_KeywordNames'] = kw; P['m_KeywordFlags'] = [0] * len(kw)
    if not subs:                                                                    # no Metal: keep the object loadable, with nothing to run
        tt.update(platforms=[], offsets=[], compressedLengths=[], decompressedLengths=[], compressedBlob=b'', stageCounts=[])
        return merge(node2021, tt)
    new = [done[i][0] if i in done else b'' for i in range(len(subs))]
    raws = pack_chunks(new, multi); comps = [lz4.block.compress(r, store_size=False, mode='high_compression', compression=9) for r in raws]
    offs, pos = [], 0
    for c in comps: offs.append(pos); pos += len(c)
    tt.update(platforms=[14], offsets=[offs], compressedLengths=[[len(c) for c in comps]], decompressedLengths=[[len(r) for r in raws]],
              compressedBlob=b''.join(comps), stageCounts=[2])
    return merge(node2021, tt)
