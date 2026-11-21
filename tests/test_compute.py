import copy
import struct
import os
import collections
import tempfile
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import compute_support as C


def descriptor(cb=False):
    code=bytearray(32); code[:4]=b'DXBC'; struct.pack_into('<I',code,24,32)
    return {'cbVariantIndices':[0] if cb else [],
            'cbs':[{'name':'$Globals','bindPoint':0}] if cb else [],
            'textures':[], 'inBuffers':[], 'outBuffers':[], 'builtinSamplers':[],
            'threadGroupSize':[8,8,1], 'code':list(code), 'requirements':16385}


def tree(layout='uniqueVariants', cb=False):
    kv=descriptor(cb)
    kernel={'name':'Example','globalKeywords':['FEATURE'],'localKeywords':['LOCAL'],'dynamicKeywords':[]}
    if layout=='uniqueVariants':
        kernel.update(uniqueVariants=[kv],variantIndices=[['',0],['FEATURE',0]])
    else: kernel.update(variantMap=[['FEATURE',kv]])
    constant={'name':'$Globals','byteSize':16,'params':[]}
    return {'m_Name':'Fixture','variants':[{'targetRenderer':2,'kernels':[kernel],'constantBuffers':[constant] if cb else [],'resourcesResolved':True}]}


class ComputeChecks(unittest.TestCase):
    def converted(self, original, translations=None):
        translations=translations or [('kernel void computeMain() {}',[])]
        with patch.object(C.C,'fixed_dxbc',return_value=b'fixture'), patch.object(C,'translate',side_effect=translations), patch.object(C,'require_valid'):
            return C.convert(original)

    def test_2022_keywords_indices_and_original_platforms_are_preserved(self):
        original=tree(); before=copy.deepcopy(original)
        output=self.converted(original)
        self.assertEqual(original,before)
        self.assertEqual(output['variants'][0],original['variants'][0])
        kernel=output['variants'][1]['kernels'][0]
        self.assertEqual(kernel['variantIndices'],[['',0],['FEATURE',0]])
        self.assertEqual(kernel['globalKeywords'],['FEATURE'])
        self.assertEqual(kernel['localKeywords'],['LOCAL'])
        kv=kernel['uniqueVariants'][0]
        self.assertEqual(struct.unpack_from('<3I4H',kv['code']),(0xDEADCAFE,1,20,8,8,1,1))
        self.assertTrue(C.info(output)['metal'])

    def test_2021_variant_map_supported_including_tuple_pairs(self):
        original=tree('variantMap')
        kernel=original['variants'][0]['kernels'][0]
        kernel['variantMap']=[tuple(kernel['variantMap'][0])]
        output=self.converted(original)
        self.assertEqual(output['variants'][1]['kernels'][0]['variantMap'][0][0],'FEATURE')
        self.assertTrue(C.info(output)['metal'])

    def test_inventory_includes_extensionless_default_resources(self):
        from shader_coverage import asset_files
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'Resources/unity default resources'
            path.parent.mkdir(); path.write_bytes(b'fixture')
            self.assertIn(path.resolve(),list(asset_files(directory)))

    def test_explicit_compute_exclusion_preserves_source(self):
        original=tree(); before=copy.deepcopy(original)
        with patch.dict(os.environ,{'SKIP_SHADER':'Fixture'}), patch.object(C,'convert') as convert:
            stats=collections.Counter()
            self.assertFalse(C.patch_compute(original,stats))
            convert.assert_not_called()
            self.assertEqual(stats['compute_excluded'],1)
        self.assertEqual(original,before)

    def test_bad_keyword_index_is_rejected(self):
        original=tree(); original['variants'][0]['kernels'][0]['variantIndices'][0][1]=4
        with self.assertRaisesRegex(ValueError,'variantIndices'): C.info(original)

    def test_bad_cbuffer_index_is_rejected(self):
        original=tree(cb=True); original['variants'][0]['kernels'][0]['uniqueVariants'][0]['cbVariantIndices']=[3]
        with self.assertRaisesRegex(ValueError,'constant-buffer indices'): C.info(original)

    def test_unknown_layout_is_rejected(self):
        original=tree(); del original['variants'][0]['kernels'][0]['variantIndices']
        with self.assertRaisesRegex(ValueError,'serialization'): C.info(original)

    def test_same_name_different_layouts_use_distinct_cbuffer_entries(self):
        original=tree(cb=True)
        variant=original['variants'][0]
        variant['kernels'].append(copy.deepcopy(variant['kernels'][0])); variant['kernels'][1]['name']='Other'
        # Same D3D CB index, different emitted layouts: each Metal kernel needs its own table entry.
        translations=[('struct Globals_Type\n{\nfloat A;\n};\nkernel void computeMain() {}',[{'kind':'cbuffer','name':'Globals','index':3}]),
                      ('struct Globals_Type\n{\nfloat2 B;\n};\nkernel void computeMain() {}',[{'kind':'cbuffer','name':'Globals','index':3}])]
        output=self.converted(original,translations)
        metal=output['variants'][1]
        self.assertEqual(len(metal['constantBuffers']),2)
        for i,name in enumerate(('A','B')):
            kv=metal['kernels'][i]['uniqueVariants'][0]
            self.assertEqual(kv['cbs'][0]['bindPoint'],3)
            index=kv['cbVariantIndices'][0]
            self.assertEqual(metal['constantBuffers'][index]['params'][0]['name'],name)

    def test_failure_in_later_kernel_leaves_whole_compute_unchanged(self):
        original=tree(); original['variants'][0]['kernels'].append(copy.deepcopy(original['variants'][0]['kernels'][0]))
        before=copy.deepcopy(original)
        with patch.object(C.C,'fixed_dxbc',return_value=b'fixture'), patch.object(C,'translate',side_effect=[('kernel void computeMain() {}',[]), ValueError('unsupported instruction')]), patch.object(C,'require_valid'):
            with self.assertRaisesRegex(ValueError,'unsupported instruction'): C.convert(original)
        self.assertEqual(original,before)
        self.assertEqual(len(original['variants']),1)

    def test_rejected_msl_does_not_add_metal_renderer(self):
        original=tree(); before=copy.deepcopy(original)
        with patch.object(C.C,'fixed_dxbc',return_value=b'fixture'), patch.object(C,'translate',return_value=('invalid',[])), patch.object(C,'require_valid',side_effect=ValueError('compiler error')):
            with self.assertRaisesRegex(ValueError,'compiler error'): C.convert(original)
        self.assertEqual(original,before)

    def test_mislabeled_native_metal_payload_is_not_accepted(self):
        original=tree(); original['variants'][0]['targetRenderer']=16
        with self.assertRaisesRegex(ValueError,'Metal compute payload'): C.info(original)

    def test_native_metal_cannot_omit_required_kernel(self):
        original=tree(); output=self.converted(original)
        extra=copy.deepcopy(original['variants'][0]['kernels'][0]); extra['name']='Missing'
        output['variants'][0]['kernels'].append(extra)
        with self.assertRaisesRegex(ValueError,'missing required kernels'): C.info(output)

    def test_native_metal_cannot_omit_required_keyword_variant(self):
        output=self.converted(tree())
        output['variants'][1]['kernels'][0]['variantIndices']=[['',0]]
        with self.assertRaisesRegex(ValueError,'missing required keyword variants'): C.info(output)

    def test_preflight_handles_repeated_path_ids_in_bundle_children(self):
        first,second=tree(),tree()
        first['m_Name']='First'; second['m_Name']='Second'
        outputs={t['m_Name']:self.converted(t) for t in (first,second)}
        objects=[SimpleNamespace(type=SimpleNamespace(name='ComputeShader'),path_id=1,read_typetree=lambda t=t:t) for t in (first,second)]
        rows=[{'kind':'ComputeShader','path_id':1,'name':t['m_Name'],'issues':[],'compute':{'metal':False}} for t in (first,second)]
        report={'files':[{'path':'fixture.bundle','shaders':rows}],'issues':[]}
        import UnityPy
        with patch.object(UnityPy,'load',return_value=SimpleNamespace(objects=objects)), patch.object(C,'convert',side_effect=lambda t:outputs[t['m_Name']]):
            C.preflight(report)
        self.assertEqual(report['compute_translation']['objects'],2)
        self.assertTrue(all(r['compute']['validated_kernel_variants']==1 for r in rows))

    def test_thread_group_payload_and_metadata_must_agree(self):
        output=self.converted(tree())
        output['variants'][1]['kernels'][0]['uniqueVariants'][0]['threadGroupSize']=[1,1,1]
        with self.assertRaisesRegex(ValueError,'metadata mismatch'): C.info(output)


if __name__=='__main__': unittest.main()
