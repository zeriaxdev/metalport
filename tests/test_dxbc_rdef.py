"""Original synthetic bytecode; no game files required.

RUN_METAL_TESTS=1 enables HLSLcc + real Metal compiler regression checks.
"""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from dxbc_rdef import add_rdef, chunks
from metal_check import require_valid

ROOT = Path(__file__).resolve().parents[1]


def instruction(opcode, *operands, controls=0):
    return [(1 + len(operands)) << 24 | controls | opcode, *operands]


def program(*instructions):
    words = [word for inst in instructions for word in inst]
    payload = struct.pack('<%dI' % (len(words) + 2), 0x50050, len(words) + 2, *words)
    return (b'DXBC' + bytes(16) + struct.pack('<4I', 1, 44 + len(payload), 1, 36)
            + b'SHEX' + struct.pack('<I', len(payload)) + payload)


def resources(dxbc):
    rdef = next(data for tag, data in chunks(add_rdef(dxbc)) if tag == b'RDEF')
    count, offset = struct.unpack_from('<2I', rdef, 8)
    return [struct.unpack_from('<8I', rdef, offset + i * 32)[1:] for i in range(count)]


class BufferReflection(unittest.TestCase):
    def test_raw_structured_and_typed_resources_keep_binding_and_type(self):
        cases = [
            (instruction(0xa1, 0x00107000, 2), (7, 6, 1, 0, 2, 1, 0)),
            (instruction(0xa2, 0x00107000, 3, 48), (5, 6, 1, 0, 3, 1, 0)),
            (instruction(0x9d, 0x0011e000, 4), (8, 6, 1, 0, 4, 1, 0)),
            (instruction(0x9e, 0x0011e000, 5, 48), (6, 6, 1, 0, 5, 1, 0)),
            (instruction(0x9e, 0x0011e000, 6, 48, controls=0x800000), (11, 6, 1, 0, 6, 1, 0)),
            (instruction(0x9c, 0x0011e000, 7, 0x4444, controls=3 << 11), (4, 4, 4, 0, 7, 1, 0)),
        ]
        for declaration, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(resources(program(declaration, instruction(62))), [expected])

    def test_reconstruction_preserves_program_and_existing_reflection(self):
        original = program(instruction(0xa2, 0x00107000, 0, 48), instruction(62))
        reflected = add_rdef(original)
        self.assertEqual(chunks(reflected)[1:], chunks(original))
        self.assertEqual(add_rdef(reflected), reflected)




@unittest.skipUnless(os.environ.get('RUN_METAL_TESTS') == '1', 'Set RUN_METAL_TESTS=1 for HLSLcc + Metal checks')
class TranslatorRegression(unittest.TestCase):
    def translate(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.dxbc'
            path.write_bytes(add_rdef(source))
            result = subprocess.run([str(ROOT / 'tools/h2m'), str(path), '0x1020081'], capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        require_valid([result.stdout])
        return result.stdout.decode()

    def test_structured_srv_stride_without_constant_buffer_reflection(self):
        msl = self.translate(program(instruction(0xa2, 0x00107000, 0, 48), instruction(155, 1, 1, 1), instruction(62)))
        self.assertIn('uint value[12]', msl)

    def test_structured_uav_atomic_without_original_reflection(self):
        msl = self.translate(program(
            instruction(0x9e, 0x0011e000, 1, 48), instruction(104, 1), instruction(155, 1, 1, 1),
            instruction(54, 0x001000f2, 0, 0x4002, 0, 4, 0, 0),
            instruction(0xad, 0x0011e000, 1, 0x00100046, 0, 0x4001, 1), instruction(62)))
        self.assertIn('uint value[12]', msl)
        self.assertIn('atomic_fetch_add_explicit', msl)




if __name__ == '__main__':
    unittest.main()
