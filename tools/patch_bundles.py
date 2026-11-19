"""Add cached Metal shader variants to loose serialized files AND AssetBundles (UnityFS) while preserving every other object's bytes.
Contributed by the Codex session that ported ULTRAKILL; it reuses inject.patch_shader. Run from the tools/ directory:  python patch_bundles.py <file> [<file> ...]  (files are rewritten in place)."""
from pathlib import Path
import collections
import struct
import sys

import UnityPy
from UnityPy.streams import EndianBinaryReader
from inject import patch_shader


def patch_serialized(asset, original, stats):
    data = bytearray(original)
    assert asset.header.version >= 22, 'unsupported serialized-file header'
    data_offset = struct.unpack_from('>q', data, 32)[0]
    unchanged = {}
    changed = set()
    for obj in asset.objects.values():
        raw = bytes(obj.get_raw_data())
        if obj.type.name != 'Shader':
            unchanged[obj.path_id] = raw
            continue
        tree = obj.read_typetree()
        assert bytes(obj.save_typetree(tree)) == raw, 'shader round-trip changed bytes'
        if not patch_shader(tree, stats):
            unchanged[obj.path_id] = raw
            continue
        replacement = bytes(obj.save_typetree(tree))
        key = struct.pack('<qqI', obj.path_id, obj.byte_start-data_offset, obj.byte_size)
        at = data.find(key, 0, data_offset)
        assert at > 0 and data.find(key, at+1, data_offset) == -1, 'ambiguous object table'
        data.extend(b'\0' * (-(len(data)-data_offset) % 8))
        struct.pack_into('<qqI', data, at, obj.path_id, len(data)-data_offset, len(replacement))
        data.extend(replacement)
        changed.add(obj.path_id)
    if not changed:
        return original
    struct.pack_into('>q', data, 24, len(data))
    result = bytes(data)
    check = UnityPy.load(result)
    found = {obj.path_id: obj for obj in check.objects}
    assert set(found) == set(asset.objects), 'object inventory changed'
    for path_id, raw in unchanged.items():
        assert bytes(found[path_id].get_raw_data()) == raw, f'object changed: {path_id}'
    for path_id in changed:
        assert 14 in found[path_id].read().platforms, 'Metal variant missing'
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
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_bytes(output)
    temporary.replace(path)
    print(path.name, dict(stats), flush=True)


if __name__ == '__main__':
    for argument in sys.argv[1:]:
        patch_file(Path(argument))
