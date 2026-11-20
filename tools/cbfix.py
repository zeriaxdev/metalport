"""Unity's Metal backend uploads a float3 shader constant as 16 bytes, so a scalar that Direct3D packed into the same register's last
lane (e.g. PostProcessing's `_PostExposure` right after `_Lut2D_Params`) is overwritten: image goes dark/wrong.  For Unity 2020.2+
data (separate parameter blobs, same table format as the 2019 blob tail): move such scalars to a free $Globals register in the Metal
copy of the parameter blob and point the translated MSL at it.  The D3D data is not touched.  (Unity 2019 data: see shader2021.repack.)
Used by inject.patch_shader; self-check: python3 cbfix.py"""
import re, struct

CBA = re.compile(rb'(cb(\d+))\.cb\2_data\[([^\]]+)\](?:\.([xyzw]{1,4})(?![A-Za-z0-9_]))?')
TAG = b'\x08\x00\x00\x00$Globals'

def globals_table(pb):
    """$Globals of a parameter blob: (offset of its size field, size, [entry dicts]) or None.  Entry: name, 6 u32 (type, rows, cols, ?, array, offset)."""
    i = pb.find(TAG)
    if i < 0: return None
    p = i + len(TAG); size, count = struct.unpack_from('<II', pb, p); p += 8; ents = []
    for _ in range(count):
        n = struct.unpack_from('<I', pb, p)[0]; q = p + 4 + n + (-n % 4)
        ty, rows, cols, _x, arr, off = struct.unpack_from('<6I', pb, q)
        ents.append(dict(name=pb[p + 4:p + 4 + n], rows=rows, cols=cols, arr=arr, off=off, at=q + 20)); p = q + 24
    return i + len(TAG), size, ents

def regs(e): return {e['off'] // 16 + k for k in range(max(1, e['arr']) * max(1, e['rows']))} | {(e['off'] + 4 * e['cols'] - 1) // 16}

def pass_alloc(blobs):
    """Free-register allocator shared by all programs of one pass (vertex + fragment): Unity's Metal backend fills one $Globals
    buffer per draw from every stage's table, so a moved value must land in a register NO program of the pass uses, and the
    same name must get the same register everywhere (lesson from Outer Wilds: per-program choice gets overwritten)."""
    used, size = set(), 0
    for pb in blobs:
        t = globals_table(pb)
        if t: size = max(size, t[1]); used |= set().union(*(regs(e) for e in t[2])) if t[2] else set()
    pool = [r for r in range(-(-size // 16)) if r not in used]; given = {}
    def alloc(name):
        if name not in given: given[name] = pool.pop(0) if pool else None
        return given[name]
    return alloc

def plan(pb, alloc=None):
    """-> (new parameter blob, {(old slot, lane): new slot}, slot count) or None when nothing is clobbered.  alloc(name) -> register
    (see pass_alloc); without it, registers free in this table only (fine when a pass has a single program)."""
    t = globals_table(pb)
    if not t: return None
    size_at, size, ents = t
    vic = [q for p in ents if p['cols'] == 3 and p['rows'] == 1 and not p['arr']
           for q in ents if q is not p and p['off'] + 12 <= q['off'] < p['off'] + 16 and q['cols'] == 1 and q['rows'] == 1 and not q['arr']]
    if not vic: return None
    used = set().union(*(regs(e) for e in ents)); nslots = -(-size // 16)
    free = [s for s in range(nslots) if s not in used]
    out = bytearray(pb); remap = {}
    for q in vic:
        s = alloc(q['name']) if alloc else (free.pop(0) if free else None)
        if s is None: s = nslots
        nslots = max(nslots, s + 1)
        remap[(q['off'] // 16, (q['off'] % 16) // 4)] = s
        struct.pack_into('<I', out, q['at'], s * 16)
    if nslots * 16 > size: struct.pack_into('<I', out, size_at, nslots * 16)
    return bytes(out), remap, nslots

def patch_msl(msl, remap, nslots):
    """Point reads of moved scalars at their new register (lane x).  Picks the cb whose reads hit the moved lanes.  None = refuse."""
    hits = {}
    for m in CBA.finditer(msl):
        if m.group(3).isdigit():
            for c in (m.group(4) or b'xyzw').decode():
                if (int(m.group(3)), 'xyzw'.index(c)) in remap: hits[int(m.group(2))] = hits.get(int(m.group(2)), 0) + 1
    if len(hits) != 1: return msl if not hits else None              # not read here: fine; read through two buffers: refuse
    b = next(iter(hits))
    if any(int(m.group(2)) == b and not m.group(3).isdigit() for m in CBA.finditer(msl)): return None   # dynamic indexing
    decl = re.search(rb'(\w+)4 cb%d_data\[(\d+)\];' % b, msl)
    if not decl: return None
    ty = decl.group(1).decode()
    def sub(m):
        if int(m.group(2)) != b: return m.group(0)
        slot = int(m.group(3)); sw = (m.group(4) or b'xyzw').decode()
        if not any((slot, 'xyzw'.index(c)) in remap for c in sw): return m.group(0)
        cbn = m.group(1).decode()
        parts = [f'{cbn}.{cbn}_data[{remap[(slot, "xyzw".index(c))]}].x' if (slot, 'xyzw'.index(c)) in remap else f'{cbn}.{cbn}_data[{slot}].{c}' for c in sw]
        return (parts[0] if len(parts) == 1 else f'{ty}{len(parts)}({", ".join(parts)})').encode()
    msl = CBA.sub(sub, msl)
    decl = re.search(rb'(\w+)4 cb%d_data\[(\d+)\];' % b, msl)
    return msl[:decl.start()] + b'%s4 cb%d_data[%d];' % (ty.encode(), b, max(int(decl.group(2)), nslots)) + msl[decl.end():]

if __name__ == '__main__':                                                  # self-check on a synthetic table: float3 at 576, scalar at 588
    def ent(name, cols, off): n = name.encode(); return struct.pack('<I', len(n)) + n + b'\0' * (-len(n) % 4) + struct.pack('<6I', 0, 1, cols, 0, 0, off)
    pb = b'\0' * 24 + TAG + struct.pack('<II', 608, 2) + ent('_Lut2D_Params', 3, 576) + ent('_PostExposure', 1, 588)
    newpb, remap, n = plan(pb)
    assert remap == {(36, 3): 0} and globals_table(newpb)[2][1]['off'] == 0, remap
    msl = b'float4 cb0_data[38];\nx = cb0.cb0_data[36].xyz * cb0.cb0_data[36].w;'
    out = patch_msl(msl, remap, n)
    assert b'cb0.cb0_data[0].x' in out and b'cb0.cb0_data[36].xyz' in out and b'cb0_data[38]' in out, out
    print('cbfix self-check ok')
