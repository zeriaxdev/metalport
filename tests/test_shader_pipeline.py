import collections
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import inject
import metal_check
import shader_coverage
import xlate_all
import port
import lz4.block


def program(ty):
    dxbc = bytearray(32)
    dxbc[:4] = b'DXBC'
    struct.pack_into('<I', dxbc, 24, len(dxbc))
    return struct.pack('<7I', 202012090, ty, 0, 0, 0, 0, 0) + struct.pack('<I', len(dxbc)) + dxbc


def shader(types=(15, 17)):
    subs = [program(ty) for ty in types]
    raw = inject.pack_chunks(subs, False)[0]
    blob = lz4.block.compress(raw, store_size=False)
    return {'platforms': [4], 'offsets': [[0]], 'compressedLengths': [[len(blob)]],
            'decompressedLengths': [[len(raw)]], 'compressedBlob': blob,
            'm_ParsedForm': {'m_Name': 'Example', 'm_SubShaders': []}}


class ShaderChecks(unittest.TestCase):
    def test_missing_variant_does_not_add_partial_metal(self):
        tree = shader()
        before = copy.deepcopy(tree)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'ALLOW_PARTIAL_SHADER':'0'}), patch.object(inject, 'S', directory), patch.object(inject, 'cached_msl', side_effect=[b'valid', None]), patch.object(inject, 'require_valid') as validate:
            stats = collections.Counter()
            self.assertFalse(inject.patch_shader(tree, stats))
            self.assertEqual(tree, before)
            self.assertEqual(stats['skip_incomplete_shader'], 1)
            validate.assert_not_called()

    def test_partial_opt_in_keeps_valid_uber_variants_and_reports_gap(self):
        tree = shader((15,17,17))
        tree['m_ParsedForm']['m_Name']='Hidden/PostProcessing/Uber'
        vertex={'m_SubPrograms':[{'m_BlobIndex':0,'m_GpuProgramType':15}]}
        fragment={'m_SubPrograms':[{'m_BlobIndex':i,'m_GpuProgramType':17} for i in (1,2)]}
        tree['m_ParsedForm']['m_SubShaders']=[{'m_Passes':[{'progVertex':vertex,'progFragment':fragment}]}]
        with patch.dict(os.environ,{'ALLOW_PARTIAL_SHADER':'1','SKIP_SHADER':''}), patch.object(inject,'cached_msl',side_effect=[b'vertex',b'fragment',None]), patch.object(inject,'require_valid') as validate:
            stats=collections.Counter()
            self.assertTrue(inject.patch_shader(tree,stats))
            self.assertEqual(tuple(validate.call_args.args[0]),(b'vertex',b'fragment'))
        self.assertEqual(stats['partial_shaders'],1)
        self.assertEqual(stats['omitted_graphics_variants'],1)
        self.assertEqual([e['m_BlobIndex'] for e in vertex['m_SubPrograms'] if e['m_GpuProgramType']==23],[0])
        self.assertEqual([e['m_BlobIndex'] for e in fragment['m_SubPrograms'] if e['m_GpuProgramType']==24],[1])
        old,_=inject.read_subs(tree,tree['platforms'].index(4),tree['compressedBlob'])
        self.assertEqual(old,[program(t) for t in (15,17,17)])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.assets'; path.write_bytes(b'fixture')
            obj=SimpleNamespace(type=SimpleNamespace(name='Shader'),path_id=1,read_typetree=lambda:tree)
            with patch.object(shader_coverage.UnityPy,'load',return_value=SimpleNamespace(objects=[obj])):
                report,_=shader_coverage.scan(path,audit=True)
            self.assertIn('partial_metal',{i['code'] for i in report['issues']})
            self.assertFalse(shader_coverage.finish(report,Path(directory)/'coverage.json'))

    def test_partial_opt_in_does_not_bypass_metal_compiler_failure(self):
        tree=shader((15,17,17)); before=copy.deepcopy(tree)
        with patch.dict(os.environ,{'ALLOW_PARTIAL_SHADER':'1','SKIP_SHADER':''}), patch.object(inject,'cached_msl',side_effect=[b'valid',b'invalid',None]), patch.object(inject,'require_valid',side_effect=ValueError('Metal rejected it')):
            with self.assertRaisesRegex(ValueError,'Metal rejected'):
                inject.patch_shader(tree,collections.Counter())
        self.assertEqual(tree,before)

    def test_invalid_final_msl_does_not_mutate_shader(self):
        tree = shader((15,))
        before = copy.deepcopy(tree)
        with patch.object(inject, 'cached_msl', return_value=b'invalid MSL'), patch.object(inject, 'require_valid', side_effect=ValueError('Metal rejected it')):
            with self.assertRaisesRegex(ValueError, 'Metal rejected'):
                inject.patch_shader(tree, collections.Counter())
        self.assertEqual(tree, before)

    def test_bundle_only_inventory_reports_compute_and_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / 'StreamingAssets/aa/windows/shaders.bundle'
            bundle.parent.mkdir(parents=True)
            bundle.write_bytes(b'fixture')
            objects = [SimpleNamespace(type=SimpleNamespace(name=kind), path_id=i,
                                       read_typetree=lambda tree=tree: tree)
                       for i, (kind, tree) in enumerate([('Shader', shader((15, 19))), ('ComputeShader', {'m_Name': 'PaletteCompute'})], 1)]
            with patch.object(shader_coverage.UnityPy, 'load', return_value=SimpleNamespace(objects=objects)):
                report, jobs = shader_coverage.scan(directory)
            self.assertEqual(report['counts']['Shader'], 1)
            self.assertEqual(report['counts']['ComputeShader'], 1)
            self.assertEqual(len(jobs), 1)
            self.assertEqual({i['code'] for i in report['issues']}, {'unsupported_stage', 'unsupported_compute'})

    def test_incomplete_cli_fails_and_explicit_override_stays_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'coverage.json'
            report = {'counts': {'ComputeShader': 1}, 'files': [], 'issues': [{'code': 'unsupported_compute', 'detail': 'not supported'}]}
            with patch.object(xlate_all, 'scan', side_effect=lambda *args: (copy.deepcopy(report), {})):
                self.assertEqual(xlate_all.main([directory, '--report', str(output)]), 2)
                self.assertFalse(json.loads(output.read_text())['complete'])
                self.assertEqual(xlate_all.main([directory, '--report', str(output), '--allow-incomplete']), 0)
                self.assertFalse(json.loads(output.read_text())['complete'])

    def test_read_errors_cannot_be_overridden(self):
        with tempfile.TemporaryDirectory() as directory:
            report = {'counts': {}, 'files': [], 'issues': [{'code': 'read_error', 'detail': 'broken asset'}]}
            with patch.object(xlate_all, 'scan', return_value=(report, {})):
                self.assertEqual(xlate_all.main([directory, '--report', str(Path(directory)/'out.json'), '--allow-incomplete']), 2)

    def test_metal_device_unavailable_is_not_a_shader_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'mslcheck'
            result = SimpleNamespace(returncode=3, stdout=b'{"error":"Metal device unavailable"}\n', stderr=b'')
            with patch.object(metal_check, 'checker', return_value=binary), patch.object(metal_check.subprocess, 'run', return_value=result):
                with self.assertRaisesRegex(metal_check.MetalCheckUnavailable, 'device unavailable'):
                    metal_check.validate_sources([b'kernel source'])
            self.assertFalse(list(Path(directory).glob('*.ok')))

    def test_failed_retranslation_cannot_reuse_stale_msl(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(xlate_all, 'S', Path(directory)), patch.object(inject, 'S', directory):
            cache = Path(directory) / 'cache'
            cache.mkdir()
            sub = program(15)
            digest = inject.dxbc_hash(sub)
            (cache / (digest+'.dxbc')).write_bytes(b'DXBC')
            (cache / (digest+'.metal')).write_bytes(b'old valid source')
            result = SimpleNamespace(returncode=1, stdout=b'', stderr=b'failed')
            with patch.object(xlate_all, 'add_rdef', return_value=b'DXBC'), patch.object(xlate_all.subprocess, 'run', return_value=result):
                h, error = xlate_all.work((digest, 'new converter'))
            self.assertEqual(h, digest)
            self.assertTrue(error)
            self.assertIsNone(inject.cached_msl(sub))

    def test_converter_flags_invalidate_identity(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(xlate_all, 'S', Path(directory)):
            for name in ('h2m', 'dxbc_rdef.py', 'xlate_all.py'):
                (Path(directory)/name).write_bytes(b'fixture')
            before = xlate_all.converter_identity()
            with patch.object(xlate_all, 'FLAGS', 'different flags'):
                self.assertNotEqual(before, xlate_all.converter_identity())

    def test_port_stops_before_assembly_when_preflight_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ['--data', directory+'/source', '--unity', directory+'/unity', '--out', directory+'/out', '--name', 'Example']
            with patch.object(port.subprocess, 'run', side_effect=subprocess.CalledProcessError(2, 'preflight')) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    port.main(args)
                self.assertEqual(run.call_count, 1)
            self.assertFalse((Path(directory)/'out/Example.app').exists())

    def test_port_patches_bundles_and_cannot_override_output_read_errors(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'SKIP_SHADER': ''}):
            bundle = Path(directory)/'out/Example.app/Contents/Resources/Data/StreamingAssets/shaders.bundle'
            inventory = {'phase':'source', 'files':[{'path':str(bundle), 'shaders':[{'kind':'Shader'}]}], 'counts':{'Shader':1}, 'issues':[]}
            broken = {'phase':'output', 'files':[], 'counts':{}, 'issues':[{'code':'read_error','detail':'broken output'}]}
            args = ['--data', directory+'/source', '--unity', directory+'/unity', '--out', directory+'/out', '--name', 'Example', '--allow-incomplete']
            with patch.object(port.subprocess, 'run'), patch.object(port, 'scan', side_effect=[(inventory,{}), (broken,{})]), patch.object(port, 'patch_file', side_effect=lambda path: self.assertEqual(os.environ.get('ALLOW_PARTIAL_SHADER'),'1')) as patch_bundle:
                self.assertEqual(port.main(args), 2)
                patch_bundle.assert_called_once_with(bundle)
            self.assertFalse(json.loads((Path(directory)/'out/shader-output-coverage.json').read_text())['complete'])

    @unittest.skipUnless(os.environ.get('RUN_METAL_TESTS') == '1', 'Set RUN_METAL_TESTS=1 on a Mac with Metal device access')
    def test_real_metal_compiler_and_cache_invalidation(self):
        valid = b'#include <metal_stdlib>\nusing namespace metal;\nkernel void computeMain(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i] = i; }'
        invalid = valid + b'\nTHIS_IS_INVALID_METAL;'
        missing_entry = b'#include <metal_stdlib>\nusing namespace metal;\nkernel void wrongName() {}'
        with tempfile.TemporaryDirectory() as directory, patch.object(metal_check, 'CACHE', Path(directory)):
            self.assertEqual(metal_check.validate_sources([valid]), {})
            self.assertEqual(metal_check.validate_sources([valid]), {})
            errors = metal_check.validate_sources([invalid, missing_entry])
            self.assertEqual(set(errors), {hashlib.sha256(s).hexdigest() for s in (invalid, missing_entry)})


if __name__ == '__main__':
    unittest.main()
