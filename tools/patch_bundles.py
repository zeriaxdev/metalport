"""Add cached Metal shader variants to loose serialized files AND AssetBundles (UnityFS) while preserving every other object's bytes.
Written during the ULTRAKILL port; it reuses inject.patch_shader. Run from the tools/ directory:  python patch_bundles.py <file> [<file> ...]  (files are rewritten in place)."""
from pathlib import Path
import collections
import struct
import sys

import UnityPy
from UnityPy.streams import EndianBinaryReader
from inject import patch_shader
from compute_support import patch_compute, info as compute_info


def patch_serialized(asset, original, stats):
    data = bytearray(original)
    assert asset.header.version >= 21, 'unsupported serialized-file header'
    v22 = asset.header.version >= 22
    data_offset = struct.unpack_from('>q', data, 32)[0] if v22 else struct.unpack_from('>I', data, 12)[0]
    fmt = '<qqI' if v22 else '<qII'
    unchanged = {}
    changed = set()
    for obj in asset.objects.values():
        raw = bytes(obj.get_raw_data())
        if obj.type.name not in ('Shader', 'ComputeShader'):
            unchanged[obj.path_id] = raw
            continue
        tree = obj.read_typetree()
        assert bytes(obj.save_typetree(tree)) == raw, 'shader round-trip changed bytes'
        if not (patch_compute if obj.type.name == 'ComputeShader' else patch_shader)(tree, stats):
            unchanged[obj.path_id] = raw
            continue
        replacement = bytes(obj.save_typetree(tree))
        key = struct.pack(fmt, obj.path_id, obj.byte_start-data_offset, obj.byte_size)
        at = data.find(key, 0, data_offset)
        assert at > 0 and data.find(key, at+1, data_offset) == -1, 'ambiguous object table'
        data.extend(b'\0' * (-(len(data)-data_offset) % 8))
        struct.pack_into(fmt, data, at, obj.path_id, len(data)-data_offset, len(replacement))
        data.extend(replacement)
        changed.add(obj.path_id)
    if not changed:
        return original
    assert v22 or len(data) < 2**32, 'legacy serialized file would exceed 4 GiB'
    struct.pack_into('>q' if v22 else '>I', data, 24 if v22 else 4, len(data))
    result = bytes(data)
    check = UnityPy.load(result)
    found = {obj.path_id: obj for obj in check.objects}
    assert set(found) == set(asset.objects), 'object inventory changed'
    for path_id, raw in unchanged.items():
        assert bytes(found[path_id].get_raw_data()) == raw, f'object changed: {path_id}'
    for path_id in changed:
        obj = found[path_id]
        if obj.type.name == 'ComputeShader':
            assert compute_info(obj.read_typetree())['metal'], 'Metal compute variant missing'
        else:
            assert 14 in obj.read().platforms, 'Metal variant missing'
    return result


def patch_file(path):
    env = UnityPy.load(str(path))
    stats = collections.Counter()
    container = next(iter(env.files.values()))
    if container.__class__.__name__ == 'BundleFile':
        expected = {}
        for name, entry in list(container.files.items()):
            if entry.__class__.__name__ == 'SerializedFile':
                raw = patch_serialized(entry, bytes(entry.reader.bytes), stats)
            else:
                raw = bytes(entry.bytes)
            expected[name] = raw
            reader = EndianBinaryReader(raw)
            reader.flags = entry.flags
            container.files[name] = reader
        output = container.save(packer='lz4')
        loaded = next(iter(UnityPy.load(output).files.values()))
        for name, entry in loaded.files.items():
            raw = entry.reader.bytes if entry.__class__.__name__ == 'SerializedFile' else entry.bytes
            assert bytes(raw) == expected[name], f'bundle entry changed: {name}'
    else:
        output = patch_serialized(container, path.read_bytes(), stats)
    if not (stats['shaders_patched'] or stats['compute_patched']):
        print(path.name, dict(stats), 'unchanged', flush=True)
        return stats
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_bytes(output)
    temporary.replace(path)
    print(path.name, dict(stats), flush=True)
    return stats


if __name__ == '__main__':
    total = collections.Counter()
    for argument in sys.argv[1:]:
        total.update(patch_file(Path(argument)))
    if total['compute_failed'] or total['partial_shaders'] or total['skip_incomplete_shader'] or total['skip_unsupported_stage']:
        sys.exit(2)
