"""Like inject.py but never re-serializes a file: patched Shader objects are appended to the end of the
original file and only their object-table entries (24 bytes each) + the header file size are edited."""
import sys, os, struct, collections, UnityPy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject import patch_shader
data_dir = sys.argv[1]; env = UnityPy.load(data_dir); stats = collections.Counter(); per_file = collections.defaultdict(list)
for obj in env.objects:
    if obj.type.name != 'Shader': continue
    try:
        old_size = obj.byte_size; old_start = obj.byte_start
        raw0 = bytes(obj.get_raw_data()); tt = obj.read_typetree()
        if stats['rt'] < 20:                # genuine round-trip check: unmodified typetree must re-serialize to identical bytes
            stats['rt'] += 1; stats['rt_identical'] += bytes(obj.save_typetree(tt)) == raw0
        if patch_shader(tt, stats):
            new_raw = bytes(obj.save_typetree(tt)); path = next(k for k, v in env.files.items() if v is obj.assets_file)
            assert len(new_raw) > old_size, 'serialized shader did not grow'
            per_file[path].append((obj.path_id, old_start, old_size, new_raw))
    except Exception as e:
        stats['errors'] += 1
        if stats['errors'] < 4: print('ERR', obj.path_id, type(e).__name__, e)
print(dict(stats))
for path, items in per_file.items():
    d = bytearray(open(path, 'rb').read()); v22 = struct.unpack('>I', d[8:12])[0] >= 22        # format 22 (Unity 6): 64-bit offsets; 21 (2019-2022): 32-bit
    doff = struct.unpack('>q', d[32:40])[0] if v22 else struct.unpack('>I', d[12:16])[0]; tbl_end = doff
    fmt = '<qqI' if v22 else '<qII'
    for pid, old_start, old_size, new_raw in items:
        old_rel = old_start - doff
        key = struct.pack(fmt, pid, old_rel, old_size); at = d.find(bytes(key), 0, tbl_end)
        assert at > 0, ('table entry not found', pid)
        d += b'\0' * (-(len(d) - doff) % 8); new_rel = len(d) - doff; d += new_raw
        d[at:at + len(key)] = struct.pack(fmt, pid, new_rel, len(new_raw))
    assert v22 or len(d) < 2**32, 'format-21 file would exceed 4 GiB'
    if v22: d[24:32] = struct.pack('>q', len(d))
    else: d[4:8] = struct.pack('>I', len(d))
    open(path, 'wb').write(d); print('patched', os.path.basename(path), len(items), 'shaders; file', len(d) // 1048576, 'MiB')
