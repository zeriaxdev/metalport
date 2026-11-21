"""Opt-in integration checks; no game assets are stored in this repository.
RUN_METAL_TESTS=1 UNITY_COMPUTE_TEST_BUNDLE=/path/to/ULTRAKILL/shaders.bundle python -m unittest discover -s tests -v
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import UnityPy
import compute_support as C
import inject
from patch_bundles import patch_file
from shader_coverage import scan
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('RUN_METAL_TESTS')=='1' and os.environ.get('UNITY_COMPUTE_TEST_BUNDLE'), 'Set RUN_METAL_TESTS=1 and UNITY_COMPUTE_TEST_BUNDLE for real-asset GPU checks')
class ComputeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path(os.environ['UNITY_COMPUTE_TEST_BUNDLE'])
        cls.original_hash=hashlib.sha256(cls.source.read_bytes()).hexdigest()
        cls.temporary=tempfile.TemporaryDirectory()
        cls.work=Path(cls.temporary.name)
        cls.runner=cls.work/'compute_dispatch'
        subprocess.run(['clang','-fobjc-arc','-O2',str(Path(__file__).with_name('compute_dispatch.m')),'-framework','Foundation','-framework','Metal','-o',str(cls.runner)],check=True)

    @classmethod
    def tearDownClass(cls):
        assert hashlib.sha256(cls.source.read_bytes()).hexdigest()==cls.original_hash
        cls.temporary.cleanup()

    def objects(self):
        return [o for o in UnityPy.load(str(self.source)).objects if o.type.name=='ComputeShader']

    def test_real_kernels_gpu_readback_and_keyword_preservation(self):
        results=[]
        for obj in self.objects():
            original=obj.read_typetree(); before=copy.deepcopy(original)
            if original['m_Name'] not in ('PaletteCompute','OutlineCompute'):continue
            converted=C.convert(original)
            self.assertEqual(original,before)
            self.assertEqual(converted['variants'][:len(original['variants'])],original['variants'])
            for vi,ki,layout,index,kv in C.descriptors(converted,16):
                name=converted['variants'][vi]['kernels'][ki]['name']
                mode={'ComputeLUT':'palette','CreateMask':'mask','Composite':'composite'}.get(name)
                if not mode:continue
                prefix=self.work/(str(obj.path_id)+'-'+str(ki)+'-'+str(index))
                msl=prefix.with_suffix('.metal'); msl.write_bytes(kv['code'][20:])
                bindings=prefix.with_suffix('.json')
                bindings.write_text(json.dumps({'kernel':{k:v for k,v in kv.items() if k!='code'},'constantBuffers':converted['variants'][vi]['constantBuffers']}))
                run=subprocess.run([str(self.runner),mode,str(msl),str(bindings)],capture_output=True,text=True)
                self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                result=json.loads(run.stdout); self.assertEqual(result['matched'],result['texels'])
                results.append(result)
        self.assertEqual({r['mode'] for r in results},{'palette','mask','composite'})
        print('GPU readback:',json.dumps(results),flush=True)

    def test_bundle_preservation_and_idempotence(self):
        target=self.work/'compute.bundle'; shutil.copy2(self.source,target)
        # Graphics conversion is deliberately excluded from this compute-only check.
        with patch.object(inject,'cached_msl',return_value=None):
            stats=patch_file(target)
            self.assertEqual(stats['compute_patched'],2)
            self.assertEqual(stats['shaders_patched'],0)
            digest=hashlib.sha256(target.read_bytes()).hexdigest()
            again=patch_file(target)
            self.assertEqual(again['compute_patched'],0)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),digest)
        report,_=scan(target,audit=True)
        self.assertEqual(report['counts']['ComputeWithMetal'],2)
        self.assertFalse(any(i['code'] in ('unsupported_compute','missing_metal_compute','read_error') for i in report['issues']))

    def test_compute_only_preflight_and_loose_formats(self):
        env=UnityPy.load(str(self.source))
        objects=[o for o in env.objects if o.type.name=='ComputeShader']
        self.assertEqual(len(objects),2)
        asset=objects[0].assets_file
        self.assertTrue(all(o.assets_file is asset for o in objects))
        asset.objects={o.path_id:o for o in objects}
        raw=asset.save()
        tools=Path(__file__).resolve().parents[1]/'tools'
        for version in (22,21):
            with self.subTest(format=version):
                loaded=UnityPy.load(raw).file
                loaded.header.version=version
                target=self.work/f'compute-v{version}.assets'
                target.write_bytes(loaded.save())
                report=self.work/f'source-{version}.json'
                subprocess.run([sys.executable,str(tools/'xlate_all.py'),str(target),'--report',str(report)],check=True)
                data=json.loads(report.read_text())
                self.assertTrue(data['complete'])
                self.assertEqual(data['compute_translation']['kernel_variants'],5)
                stats=patch_file(target)
                self.assertEqual(stats['compute_patched'],2)
                subprocess.run([sys.executable,str(tools/'xlate_all.py'),str(target),'--audit-only','--report',str(report)],check=True)
                self.assertTrue(json.loads(report.read_text())['complete'])
                self.assertEqual(json.loads(report.read_text())['counts']['ComputeWithMetal'],2)


if __name__=='__main__':unittest.main()
