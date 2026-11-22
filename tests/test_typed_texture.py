import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compute_shader.compute import fixed_dxbc
from compute_shader.rdef import dxbc_info
from dxbc_rdef import add_rdef


def texture_return_types(dxbc):
    rdef = dxbc_info(dxbc)[3][b"RDEF"]
    count, offset = struct.unpack_from("<2I", rdef, 8)
    return {
        (kind, index): return_type
        for _, kind, return_type, _, _, index, _, _ in
        (struct.unpack_from("<8I", rdef, offset + 32 * item) for item in range(count))
    }


class TypedTextureTests(unittest.TestCase):
    def test_signed_sampled_and_unsigned_storage_texture_keep_their_types(self):
        def declaration(opcode, slot, return_type):
            return (opcode | (3 << 11) | (4 << 24), 0, slot, return_type * 0x1111)

        bytecode = struct.pack(
            "<10I", 0x50050, 10,
            *declaration(0x58, 6, 3),
            *declaration(0x9C, 2, 4),
        )
        dxbc = b"DXBC" + bytes(16) + struct.pack("<4I", 1, 44 + len(bytecode), 1, 36)
        dxbc += b"SHEX" + struct.pack("<I", len(bytecode)) + bytecode
        descriptor = {
            "code": dxbc, "cbVariantIndices": [], "cbs": [],
            "textures": [{"name": "Source", "bindPoint": 6, "samplerBindPoint": -1, "texDimension": 2}],
            "inBuffers": [], "builtinSamplers": [],
            "outBuffers": [{"name": "Target", "bindPoint": 2, "texDimension": 2}],
        }
        expected = {(2, 6): 3, (4, 2): 4}
        self.assertEqual(texture_return_types(add_rdef(dxbc)), expected)
        self.assertEqual(texture_return_types(fixed_dxbc({"constantBuffers": []}, descriptor)), expected)
